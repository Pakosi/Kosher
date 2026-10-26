"""Word-level timestamps. Engines: mlx-whisper (Apple Silicon), faster-whisper,
whisper.cpp CLI, or `estimate` (syllable-weighted, energy-gated; no model)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from ..audio_utils import load_mono, speech_segments
from ..config import AlignConfig
from ..text import syllables, words


def transcribe_words(path: Path, cfg: AlignConfig, prompt: str = "") -> list[dict]:
    """Returns [{word, start, end}] in seconds relative to the clip."""
    if cfg.engine == "mlx-whisper":
        import mlx_whisper
        res = mlx_whisper.transcribe(str(path), path_or_hf_repo=cfg.model, word_timestamps=True,
                                     initial_prompt=prompt or None, language="en")
        return [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]}
                for s in res.get("segments", []) for w in s.get("words", [])]
    if cfg.engine == "faster-whisper":
        from faster_whisper import WhisperModel
        model = _fw_model(cfg.model)
        segs, _ = model.transcribe(str(path), word_timestamps=True, initial_prompt=prompt or None, language="en")
        return [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segs for w in (s.words or [])]
    if cfg.engine == "whisper-cpp":
        exe = shutil.which(cfg.whisper_cpp_bin)
        if not exe:
            raise RuntimeError(f"{cfg.whisper_cpp_bin} not found")
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "out"
            subprocess.run([exe, "-m", str(Path(cfg.whisper_cpp_model).expanduser()), "-f", str(path),
                            "-ml", "1", "-sow", "-oj", "-of", str(base), "-l", "en",
                            *(["--prompt", prompt] if prompt else [])],
                           check=True, capture_output=True)
            data = json.loads(base.with_suffix(".json").read_text())
        out = []
        for seg in data.get("transcription", []):
            txt = seg["text"].strip()
            if txt:
                out.append({"word": txt, "start": seg["offsets"]["from"] / 1000, "end": seg["offsets"]["to"] / 1000})
        return out
    raise ValueError(f"engine {cfg.engine} has no transcriber")


_FW: dict[str, object] = {}


def _fw_model(name: str):
    from faster_whisper import WhisperModel
    if name not in _FW:
        size = name.split("/")[-1].replace("whisper-", "") if "/" in name else name
        _FW[name] = WhisperModel(size, compute_type="int8")
    return _FW[name]


def estimate_words(path: Path, text: str, sr: int = 24000) -> list[dict]:
    """Model-free alignment: spread script words over detected speech regions,
    weighted by syllable count. Good enough for captions; used offline / in CI."""
    x = load_mono(path, sr)
    segs = speech_segments(x, sr) or [(0.0, len(x) / sr)]
    toks = text.split()
    if not toks:
        return []
    weights = np.array([syllables(t) + (0.6 if t.endswith((",", ".", "?", "!")) else 0) for t in toks], float)
    total_speech = sum(b - a for a, b in segs)
    # map cumulative syllable fraction onto cumulative speech time
    cum = np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * total_speech

    def speech_to_clock(s: float) -> float:
        acc = 0.0
        for a, b in segs:
            if s <= acc + (b - a):
                return a + (s - acc)
            acc += b - a
        return segs[-1][1]

    out = []
    for i, t in enumerate(toks):
        st, en = speech_to_clock(cum[i]), speech_to_clock(cum[i + 1])
        out.append({"word": t, "start": round(st, 3), "end": round(max(en, st + 0.05), 3)})
    return out


def match_script(script_tokens: list[str], heard: list[dict], clip_dur: float) -> list[tuple[str, float, float]]:
    """Align recognised words to script tokens (keeps the script's spelling and
    punctuation, takes whisper's timing). Unmatched tokens are interpolated."""
    norm = lambda s: "".join(words(s))  # noqa: E731
    sn = [norm(t) for t in script_tokens]
    hn = [norm(h["word"]) for h in heard]
    n, m = len(sn), len(hn)
    # LCS-style DP on normalised tokens (fuzzy: prefix match counts)
    dp = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            same = sn[i] and hn[j] and (sn[i] == hn[j] or sn[i].startswith(hn[j]) or hn[j].startswith(sn[i]))
            dp[i, j] = dp[i + 1, j + 1] + 1 if same else max(dp[i + 1, j], dp[i, j + 1])
    times: list[tuple[float, float] | None] = [None] * n
    i = j = 0
    while i < n and j < m:
        same = sn[i] and hn[j] and (sn[i] == hn[j] or sn[i].startswith(hn[j]) or hn[j].startswith(sn[i]))
        if same:
            times[i] = (heard[j]["start"], heard[j]["end"])
            i += 1
            j += 1
        elif dp[i + 1, j] >= dp[i, j + 1]:
            i += 1
        else:
            j += 1
    # interpolate gaps
    k = 0
    while k < n:
        if times[k] is not None:
            k += 1
            continue
        a = k
        while k < n and times[k] is None:
            k += 1
        left = times[a - 1][1] if a > 0 else 0.0
        right = times[k][0] if k < n else clip_dur
        span = max(right - left, 0.06 * (k - a))
        step = span / (k - a)
        for q in range(a, k):
            times[q] = (left + (q - a) * step, left + (q - a + 1) * step)
    return [(script_tokens[q], round(times[q][0], 3), round(times[q][1], 3)) for q in range(n)]  # type: ignore[index]
