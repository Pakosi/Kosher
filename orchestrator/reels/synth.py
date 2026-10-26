"""Procedural audio so a fresh install (or CI) never renders silence: simple
cartoon SFX and a soft music bed. Drop real files into library/sfx and
library/music/<series>/ to override."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100


def _t(d: float) -> np.ndarray:
    return np.arange(int(SR * d)) / SR


def _env(n: int, attack: float = 0.005, decay: float = 4.0) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-decay * t)


def _noise(d: float, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(int(SR * d))


def _lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def sfx(name: str) -> np.ndarray:
    if name in ("whoosh", "swoosh_up"):
        d = 0.45
        t = _t(d)
        n = _noise(d, 1)
        shape = np.sin(np.pi * t / d) ** 2
        cutoff = np.linspace(0.02, 0.25, len(t)) if name == "swoosh_up" else 0.06 + 0.2 * np.sin(np.pi * t / d)
        y = np.empty_like(n)
        acc = 0.0
        for i in range(len(n)):
            a = cutoff[i] if isinstance(cutoff, np.ndarray) else cutoff
            acc += a * (n[i] - acc)
            y[i] = acc
        return 2.2 * y * shape
    if name == "pop":
        t = _t(0.12)
        f = 900 * np.exp(-30 * t) + 300
        return 0.8 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 35)
    if name in ("ding", "sparkle"):
        t = _t(0.9)
        base = 1318 if name == "ding" else 2093
        y = sum(np.sin(2 * np.pi * base * k * t) / k ** 1.5 for k in (1, 2.01, 3.03))
        return 0.5 * y * _env(len(t), 0.002, 5)
    if name in ("boom", "thud"):
        d = 0.9 if name == "boom" else 0.3
        t = _t(d)
        f = 120 * np.exp(-6 * t) + 38
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 4 if name == "boom" else 14)
        return 0.95 * (body + 0.25 * _lowpass(_noise(d, 3), 0.05) * _env(len(t), 0.001, 8))
    if name == "record_scratch":
        t = _t(0.5)
        f = 400 + 900 * np.sin(2 * np.pi * 3 * t) ** 2
        return 0.4 * np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * _env(len(t), 0.002, 5) * 0.6
    if name in ("alarm", "buzzer"):
        t = _t(0.8)
        f = np.where((t * 6) % 1 < 0.5, 880, 660) if name == "alarm" else 140
        return 0.3 * np.sign(np.sin(2 * np.pi * f * t)) * np.minimum(1, (0.8 - t) * 10)
    if name == "cash":
        a = sfx("ding")[: int(SR * 0.5)]
        c = 0.4 * _lowpass(_noise(0.2, 9), 0.4) * _env(int(SR * 0.2), 0.001, 25)
        out = np.zeros(int(SR * 0.6))
        out[: len(c)] += c
        out[int(SR * 0.1): int(SR * 0.1) + len(a)] += a
        return out
    if name in ("click", "tick", "camera_shutter"):
        t = _t(0.05)
        return 0.7 * _noise(0.05, 5) * _env(len(t), 0.0005, 120)
    if name == "riser":
        t = _t(1.2)
        f = 200 * 2 ** (3 * t / 1.2)
        return 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / 1.2) ** 2
    if name == "scribble":
        d = 0.6
        n = _lowpass(_noise(d, 7), 0.3)
        mod = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 9 * _t(d)))
        return 0.5 * n * mod
    return sfx("pop")


def write_sfx(name: str, dest: Path) -> Path:
    y = sfx(name)
    y = y / max(np.max(np.abs(y)), 1e-6) * 0.8
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), y.astype(np.float32), SR)
    return dest


def music_bed(dest: Path, seconds: float, seed: int = 0, bpm: int = 96) -> Path:
    """Playful minor-key pluck + soft kick bed."""
    rng = np.random.default_rng(seed)
    n = int(SR * (seconds + 1))
    out = np.zeros(n)
    beat = 60 / bpm
    roots = [57, 53, 48, 55]                 # Am F C G
    rng.shuffle(roots)
    scale = [0, 3, 5, 7, 10, 12]
    t_beat = 0.0
    i = 0
    while t_beat < seconds:
        start = int(t_beat * SR)
        # kick on 1 and 3
        if i % 2 == 0:
            k = sfx("thud")[: int(SR * 0.25)] * 0.35
            out[start:start + len(k)] += k[: max(0, min(len(k), n - start))]
        # pluck on eighths
        for half in (0, 1):
            s = start + int(half * beat / 2 * SR)
            root = roots[(i // 4) % 4]
            note = root + 12 + scale[rng.integers(0, len(scale))]
            f = 440 * 2 ** ((note - 69) / 12)
            tt = _t(beat * 0.9)
            pl = 0.12 * (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt)) * _env(len(tt), 0.002, 7)
            e = min(len(pl), n - s)
            if e > 0:
                out[s:s + e] += pl[:e]
        # pad
        if i % 4 == 0:
            root = roots[(i // 4) % 4]
            tt = _t(beat * 4)
            pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((root + iv - 69) / 12) * tt) for iv in (0, 3, 7)) * 0.04
            pad *= np.minimum(1, tt / 0.3) * np.minimum(1, (beat * 4 - tt) / 0.3)
            e = min(len(pad), n - start)
            out[start:start + e] += pad[:e]
        t_beat += beat
        i += 1
    out = out / max(np.max(np.abs(out)), 1e-6) * 0.7
    fade = int(SR * 1.0)
    out[-fade:] *= np.linspace(1, 0, fade)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest), out.astype(np.float32), SR)
    return dest
