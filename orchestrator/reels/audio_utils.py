"""Audio helpers built on numpy/soundfile + ffmpeg."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          check=True, capture_output=True, text=True)


def to_wav(src: Path, dest: Path, sr: int) -> Path:
    ffmpeg("-i", str(src), "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(dest))
    return dest


def load_mono(path: Path, sr: int) -> np.ndarray:
    data, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    data = data.mean(axis=1)
    if file_sr != sr:
        tmp = path.with_suffix(".rs.wav")
        to_wav(path, tmp, sr)
        data, _ = sf.read(str(tmp), dtype="float32")
        tmp.unlink(missing_ok=True)
    return data


def trim_silence(x: np.ndarray, sr: int, thresh_db: float = -42.0, pad: float = 0.04) -> np.ndarray:
    if len(x) == 0:
        return x
    win = max(int(sr * 0.01), 1)
    n = len(x) // win
    if n == 0:
        return x
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    loud = np.where(db > thresh_db)[0]
    if len(loud) == 0:
        return x
    p = int(pad * sr)
    return x[max(loud[0] * win - p, 0):min((loud[-1] + 1) * win + p, len(x))]


def speech_segments(x: np.ndarray, sr: int, thresh_db: float = -38.0, min_gap: float = 0.12) -> list[tuple[float, float]]:
    """Energy-based voiced regions (seconds)."""
    win = max(int(sr * 0.01), 1)
    n = len(x) // win
    if n == 0:
        return []
    rms = np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    voiced = 20 * np.log10(rms + 1e-12) > thresh_db
    segs: list[list[float]] = []
    for i, v in enumerate(voiced):
        t = i * win / sr
        if v:
            if segs and t - segs[-1][1] <= min_gap:
                segs[-1][1] = t + win / sr
            else:
                segs.append([t, t + win / sr])
    return [(a, b) for a, b in segs]


def loudness(path: Path) -> dict[str, float]:
    """Integrated LUFS / true peak / LRA via ffmpeg loudnorm analysis."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af",
                        "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, flags=re.S)
    if not m:
        raise RuntimeError(f"loudnorm analysis failed: {p.stderr[-400:]}")
    d = json.loads(m.group(0))
    return {"lufs": float(d["input_i"]), "true_peak": float(d["input_tp"]), "lra": float(d["input_lra"]),
            "thresh": float(d["input_thresh"]), "offset": float(d["target_offset"])}


def loudnorm_video(src: Path, dest: Path, lufs: float, tp: float) -> dict[str, float]:
    """Two-pass loudness normalisation of the video's audio track (video copied)."""
    m = loudness(src)
    flt = (f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={m['lufs']}:measured_TP={m['true_peak']}:"
           f"measured_LRA={m['lra']}:measured_thresh={m['thresh']}:offset={m['offset']}:linear=true,"
           # brickwall a bit under the target so AAC encoding overs stay below the true-peak ceiling;
           # 4x oversampled so the limiter catches inter-sample (true) peaks, not just sample peaks
           f"aresample=192000,alimiter=limit={10 ** ((tp - 1.5) / 20):.4f}:level=false:attack=1:release=50,"
           "aresample=48000")
    # ffmpeg's native AAC at 192k overshot the limiter by ~2 dB true peak; 320k stays within ~0.3 dB
    ffmpeg("-i", str(src), "-c:v", "copy", "-af", flt, "-ar", "48000", "-c:a", "aac", "-b:a", "320k",
           "-movflags", "+faststart", str(dest))
    return m


def probe_duration(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(p.stdout.strip())
