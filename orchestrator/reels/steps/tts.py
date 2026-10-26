"""TTS: one clip per script line (per-line cache, so editing one line only
re-voices that line), silence-trimmed and assembled into the narration track
with beat-aware pauses."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from ..audio_utils import load_mono, trim_silence
from ..cache import hash_file, hash_obj
from ..episode import Episode
from ..spec import AudioManifest, LineAudio, Script
from ..text import speakable
from ..tts import synthesize
from .base import Ctx, Step, console, register


def _run(ep: Episode, ctx: Ctx) -> None:
    script = ep.read("script", Script)
    sr = ctx.cfg.tts.sample_rate
    lines_dir = ep.path("audio/lines")
    lines_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[np.ndarray] = []
    out_lines: list[LineAudio] = []
    t = 0.0
    prev_beat = None
    for line in script.lines:
        voice = ctx.series.voices[line.speaker]
        text = speakable(line.text)
        key = hash_obj({"t": text, "v": voice.model_dump(), "e": line.emotion, "sr": sr})[:16]
        clip = lines_dir / f"{line.id}-{key}.wav"
        engine = "cache"
        if not clip.exists():
            raw = lines_dir / f"{line.id}-{key}.raw.wav"
            engine = synthesize(text, voice, raw, ctx.cfg, line.emotion)
            audio = trim_silence(load_mono(raw, sr), sr)
            sf.write(str(clip), audio, sr)
            raw.unlink(missing_ok=True)
            console.print(f"    [dim]{line.id} {line.speaker} via {engine}[/dim]")
        audio = load_mono(clip, sr)
        if prev_beat is not None:
            gap = ctx.cfg.tts.line_gap + (ctx.cfg.tts.beat_gap if line.beat != prev_beat else 0.0)
            pieces.append(np.zeros(int(gap * sr), dtype=np.float32))
            t += gap
        out_lines.append(LineAudio(line_id=line.id, speaker=line.speaker, path=str(clip.relative_to(ep.dir)),
                                   start=round(t, 3), duration=round(len(audio) / sr, 3), engine=engine))
        pieces.append(audio)
        t += len(audio) / sr
        prev_beat = line.beat
    pieces.append(np.zeros(int(0.25 * sr), dtype=np.float32))   # tail so the last word isn't clipped
    narration = np.concatenate(pieces)
    peak = float(np.max(np.abs(narration))) or 1.0
    narration = narration * min(1.0, 0.89 / peak)
    sf.write(str(ep.path("audio/narration.wav")), narration, sr)
    # drop stale clips from earlier versions of lines
    keep = {l.path.split("/")[-1] for l in out_lines}
    for f in lines_dir.glob("*.wav"):
        if f.name not in keep:
            f.unlink()
    ep.write("audio", AudioManifest(duration=round(len(narration) / sr, 3), sample_rate=sr, lines=out_lines))


register(Step(
    name="tts", version="2", status_after="voiced", description="voice every line", isolate=True,
    outputs=lambda ep: [ep.path("audio"), ep.path("audio/narration.wav")],
    inputs=lambda ep, ctx: {"script": hash_file(ep.path("script")),
                            "voices": {k: v.model_dump() for k, v in ctx.series.voices.items()},
                            "tts": ctx.cfg.tts.model_dump()},
    run=_run,
))
