"""Kokoro on MLX via mlx-audio (Apple Silicon, fastest). Runs the CLI in a
subprocess so weights are released immediately. [Mac-only]"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from ..audio_utils import to_wav


def synth(name, text, voice, speed, out: Path, cfg) -> None:
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "line"
        subprocess.run([sys.executable, "-m", "mlx_audio.tts.generate",
                        "--model", "mlx-community/Kokoro-82M-bf16", "--text", text,
                        "--voice", voice.voice, "--speed", f"{speed:.3f}", "--lang_code", voice.voice[0],
                        "--file_prefix", str(prefix), "--audio_format", "wav", "--join_audio"],
                       check=True, capture_output=True, text=True)
        produced = sorted(Path(td).glob("*.wav"))
        if not produced:
            raise RuntimeError("mlx-audio produced no wav")
        to_wav(produced[-1], out, cfg.tts.sample_rate)
