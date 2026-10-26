"""QA gate: format, length, loudness, dead air, black frames, banned words, hook
timing, safe zones, caption/audio sync (re-transcribes the final render) and a
local vision-model frame check. Pass/warn -> review queue, fail -> qa_failed."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from ..align.whisper import match_script, transcribe_words
from ..audio_utils import loudness, probe_duration
from ..cache import hash_file
from ..episode import Episode
from ..llm import get_llm
from ..spec import Alignment, AudioManifest, QACheck, QAReport, Script, Timeline
from ..text import find_banned, wer
from .base import Ctx, Step, register

VISION_SCHEMA = {"type": "object", "properties": {
    "ok": {"type": "boolean"}, "score": {"type": "number"},
    "issues": {"type": "array", "items": {"type": "string"}}}, "required": ["ok", "score", "issues"]}


def _probe(video: Path) -> dict:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)],
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def _detect(video: Path, flt: str, key: str) -> list[float]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), *flt.split(" "), "-f", "null", "-"],
                       capture_output=True, text=True)
    return [float(x) for x in re.findall(rf"{key}:\s*([\d.]+)", p.stderr)]


def _frames(video: Path, times: list[float], out: Path) -> list[Path]:
    paths = []
    for i, t in enumerate(times):
        dest = out / f"f{i}.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=540:-1", str(dest)], check=True)
        paths.append(dest)
    return paths


def settled_time(t: float, tl: Timeline, settle: float = 0.8) -> float:
    """Move a sample time off entrance animations (scene cut, prop pop/slide, text reveal) so the
    vision check judges the settled layout, not a half-drawn banner or a prop mid-slide."""
    for sc in tl.scenes:
        if sc.start <= t < sc.end:
            events = [sc.start] + [p.at for p in sc.props] + ([sc.text.at] if sc.text else [])
            ok = lambda x: all(not (e <= x < e + settle) for e in events)  # noqa: E731
            if ok(t):
                return t
            good = [e + settle for e in events if e + settle < sc.end - 0.05 and ok(e + settle)]
            later = [c for c in good if c >= t]
            return min(later) if later else max(good, default=t)
    return t


def run_checks(ep: Episode, ctx: Ctx) -> QAReport:
    q = ctx.cfg.qa
    video = ep.path("video")
    tl = ep.read("timeline", Timeline)
    script = ep.read("script", Script)
    audio = ep.read("audio", AudioManifest)
    al = ep.read("align", Alignment)
    checks: list[QACheck] = []
    add = lambda name, status, detail="", value=None: checks.append(  # noqa: E731
        QACheck(name=name, status=status, detail=detail, value=value))

    # format
    info = _probe(video)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v or not a:
        add("format", "fail", "missing video or audio stream")
    else:
        fr = v.get("r_frame_rate", "0/1").split("/")
        fps = float(fr[0]) / max(float(fr[1]), 1)
        ok = v["width"] == ctx.cfg.render.width and v["height"] == ctx.cfg.render.height and abs(fps - ctx.cfg.render.fps) < 0.5
        add("format", "pass" if ok else "fail", f"{v['width']}x{v['height']} @ {fps:.2f}fps, {v['codec_name']}/{a['codec_name']}")

    # length
    dur = probe_duration(video)
    status = "pass" if q.min_seconds <= dur <= q.max_seconds else ("warn" if 20 <= dur <= 90 else "fail")
    add("length", status, f"{dur:.1f}s (target {q.min_seconds:.0f}-{q.max_seconds:.0f}s)", round(dur, 2))

    # loudness
    ld = loudness(video)
    dl = abs(ld["lufs"] - ctx.cfg.audio.target_lufs)
    add("loudness", "pass" if dl <= q.lufs_tolerance else ("warn" if dl <= 2 * q.lufs_tolerance else "fail"),
        f"{ld['lufs']:.1f} LUFS (target {ctx.cfg.audio.target_lufs})", ld["lufs"])
    add("true_peak", "pass" if ld["true_peak"] <= ctx.cfg.audio.true_peak + 0.5 else "warn",
        f"{ld['true_peak']:.1f} dBTP", ld["true_peak"])

    # dead air (inside narration) and black frames
    sil = _detect(video, "-af silencedetect=noise=-45dB:d=1.2", "silence_duration")
    add("dead_air", "pass" if not sil else "warn", f"{len(sil)} silences >1.2s" if sil else "none")
    black = _detect(video, "-vf blackdetect=d=0.3:pix_th=0.1", "black_duration")
    add("black_frames", "pass" if not black else "fail", f"{sum(black):.1f}s black" if black else "none")

    # language
    bad = find_banned(f"{script.text()} {script.caption}", ctx.series.banned_words)
    add("banned_words", "fail" if bad else "pass", ", ".join(bad) if bad else "none")

    # hook timing
    hook_line = next((l for l in audio.lines if l.line_id == script.lines[0].id), None)
    if hook_line:
        hook_end = hook_line.start + hook_line.duration
        add("hook_timing", "pass" if hook_end <= 4.0 else ("warn" if hook_end <= 5.5 else "fail"),
            f"hook ends at {hook_end:.1f}s", round(hook_end, 2))
    first_word = al.words[0].start if al.words else 0
    add("cold_open", "pass" if first_word <= 0.4 else "warn", f"first word at {first_word:.2f}s")

    # safe zones (IG UI covers ~top 14% and bottom 20%, right rail ~12%)
    issues = []
    if not 0.3 <= tl.caption.position <= 0.7:
        issues.append(f"caption at y={tl.caption.position}")
    for sc in tl.scenes:
        for p in sc.props:
            if p.y > 0.5 or p.y < 0.15 or p.x > 0.9 or p.x < 0.1:
                issues.append(f"{sc.id}/{p.id} at ({p.x:.2f},{p.y:.2f})")
    add("safe_zones", "pass" if not issues else "warn", "; ".join(issues) or "all elements inside safe area")

    # sync: re-transcribe the final mix and compare to caption timings
    if ctx.cfg.align.engine == "estimate" or al.engine == "estimate":
        add("sync", "skip", "no ASR configured (estimate aligner)")
    else:
        try:
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "final.wav"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-ac", "1", "-ar", "16000",
                                str(wav)], check=True)
                heard = transcribe_words(wav, ctx.cfg.align, prompt=script.text())
            hyp = " ".join(h["word"] for h in heard)
            w = wer(script.text(), hyp)
            matched = match_script([x.text for x in al.words], heard, dur)
            drift = float(np.median([abs(m[1] - x.start) for m, x in zip(matched, al.words)])) if matched else 0
            st = "pass" if w <= q.max_wer and drift <= q.max_sync_drift else ("warn" if w <= 2 * q.max_wer else "fail")
            add("sync", st, f"WER {w:.2f}, median caption drift {drift * 1000:.0f}ms", round(w, 3))
        except Exception as e:  # noqa: BLE001
            add("sync", "warn", f"ASR check failed: {e}")

    # frames: deterministic + vision model
    with tempfile.TemporaryDirectory() as td:
        n = q.vision_frames
        times = [settled_time(min(dur - 0.1, (i + 0.5) * dur / n), tl) for i in range(n)]
        frames = _frames(video, times, Path(td))
        flat = []
        for f in frames:
            arr = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
            if arr.std() < 6:
                flat.append(f.name)
        add("frame_content", "pass" if not flat else "fail", f"flat frames: {flat}" if flat else f"{n} frames have content")
        if q.vision_check:
            try:
                llm = get_llm("vision", ctx.cfg)
                verdicts = []
                for f, t in zip(frames, times):
                    r = llm.complete_json("vision", "You are a strict video QA reviewer. Output JSON only.",
                                          "This is a frame from a vertical 2D doodle-animation Instagram Reel. "
                                          "Check: is any text cut off or overlapping? Is the main character fully "
                                          "visible (not cropped awkwardly)? Any visual glitch, broken image, or "
                                          "unreadable caption? Score 0-10 overall quality. "
                                          "Return {ok, score, issues}.", VISION_SCHEMA, images=[str(f)])
                    verdicts.append((t, r))
                llm.unload()
                bad_frames = [f"{t:.1f}s: {', '.join(r.get('issues', []))}" for t, r in verdicts
                              if not r.get("ok", True) or r.get("score", 10) < 5]
                avg = sum(r.get("score", 0) for _, r in verdicts) / max(len(verdicts), 1)
                add("vision", "pass" if not bad_frames else "warn",
                    "; ".join(bad_frames) or f"avg score {avg:.1f}/10", round(avg, 2))
            except Exception as e:  # noqa: BLE001
                add("vision", "skip", f"vision model unavailable: {e}")
        else:
            add("vision", "skip", "disabled")

    overall = "fail" if any(c.status == "fail" for c in checks) else (
        "warn" if any(c.status == "warn" for c in checks) else "pass")
    return QAReport(status=overall, checks=checks)


def _run(ep: Episode, ctx: Ctx) -> None:
    rep = run_checks(ep, ctx)
    ep.write("qa", rep)




register(Step(
    name="qa", version="3", status_after="review", description="quality gate",
    outputs=lambda ep: [ep.path("qa")],
    inputs=lambda ep, ctx: {"video": hash_file(ep.path("video")), "qa": ctx.cfg.qa.model_dump(),
                            "banned": ctx.series.banned_words},
    run=_run,
))
