"""Zero-download engines: macOS `say`, `espeak-ng`, and `sine` (test tone shaped
like syllables, used by CI so timing/lip-sync logic still gets exercised)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from ..audio_utils import to_wav
from ..text import syllables


def synth(name, text, voice, speed, out: Path, cfg) -> None:
    sr = cfg.tts.sample_rate
    if name == "say":
        if not shutil.which("say"):
            raise RuntimeError("`say` only exists on macOS")
        with tempfile.TemporaryDirectory() as td:
            aiff = Path(td) / "s.aiff"
            v = voice.voice if not voice.voice[:3] in ("am_", "af_", "bm_", "bf_") else "Samantha"
            subprocess.run(["say", "-v", v, "-r", str(int(185 * speed)), "-o", str(aiff), text], check=True)
            to_wav(aiff, out, sr)
        return
    if name == "espeak":
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            raise RuntimeError("espeak-ng not installed")
        variant = {"am_": "en-us+m3", "af_": "en-us+f3", "bm_": "en-gb+m3", "bf_": "en-gb+f2"}.get(voice.voice[:3], "en-us")
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "e.wav"
            subprocess.run([exe, "-v", variant, "-s", str(int(170 * speed)), "-w", str(raw), text], check=True)
            to_wav(raw, out, sr)
        return
    # sine: one tone burst per syllable, short gaps between words
    rng = np.random.default_rng(abs(hash(voice.voice)) % 2**32)
    base = 110 + rng.integers(0, 120)
    parts = []
    for w in text.split():
        for _ in range(syllables(w)):
            n = int(sr * 0.16 / speed)
            t = np.arange(n) / sr
            env = np.sin(np.pi * t / t[-1]) ** 0.6
            f = base * (1 + 0.1 * rng.standard_normal())
            parts.append(0.25 * env * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)))
        parts.append(np.zeros(int(sr * 0.06 / speed)))
        if w.endswith((".", "?", "!", ",")):
            parts.append(np.zeros(int(sr * 0.18 / speed)))
    sf.write(str(out), np.concatenate(parts).astype(np.float32), sr)
