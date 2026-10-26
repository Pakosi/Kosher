"""F5-TTS voice cloning on MLX (`pip install f5-tts-mlx`). Needs a 5-10s clean
reference clip + its transcript in the voice config. [Mac-only]"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from ..audio_utils import to_wav
from ..config import ROOT


def synth(name, text, voice, speed, out: Path, cfg) -> None:
    if not voice.ref_audio or not voice.ref_text:
        raise RuntimeError("f5 needs ref_audio and ref_text in the voice config")
    ref = Path(voice.ref_audio).expanduser()
    ref = ref if ref.is_absolute() else ROOT / ref
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "f5.wav"
        subprocess.run([sys.executable, "-m", "f5_tts_mlx.generate", "--text", text,
                        "--ref-audio", str(ref), "--ref-text", voice.ref_text,
                        "--speed", f"{speed:.3f}", "--output", str(raw)],
                       check=True, capture_output=True, text=True)
        to_wav(raw, out, cfg.tts.sample_rate)
