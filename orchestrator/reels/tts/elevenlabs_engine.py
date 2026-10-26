"""ElevenLabs fallback (cloud, paid). Set ELEVENLABS_API_KEY and voice.elevenlabs_voice_id."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf


def synth(name, text, voice, speed, out: Path, cfg) -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or not voice.elevenlabs_voice_id:
        raise RuntimeError("ELEVENLABS_API_KEY / elevenlabs_voice_id not set")
    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice.elevenlabs_voice_id}",
        params={"output_format": "pcm_24000"},
        headers={"xi-api-key": key},
        json={"text": text, "model_id": cfg.tts.elevenlabs_model,
              "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35,
                                 "speed": max(0.7, min(1.2, speed))}},
        timeout=120)
    r.raise_for_status()
    pcm = np.frombuffer(r.content, dtype=np.int16).astype(np.float32) / 32768.0
    sf.write(str(out), pcm, 24000)
