"""TTS engines behind one call. Each engine writes a mono WAV at the pipeline
sample rate. Engines are tried in order: voice.engine, voice.fallback..., so a
series can say e.g. "f5 clone, else kokoro, else elevenlabs"."""

from __future__ import annotations

import importlib
from pathlib import Path

from ..config import PipelineConfig, VoiceConfig

ENGINES = {
    "kokoro": "reels.tts.kokoro_engine",
    "mlx-kokoro": "reels.tts.mlx_engine",
    "f5": "reels.tts.f5_engine",
    "elevenlabs": "reels.tts.elevenlabs_engine",
    "say": "reels.tts.system_engine",
    "espeak": "reels.tts.system_engine",
    "sine": "reels.tts.system_engine",
}

EMOTION_SPEED = {"excited": 1.07, "angry": 1.05, "shocked": 1.04, "smug": 0.98, "serious": 0.97,
                 "whisper": 0.94, "sad": 0.92}


class TTSError(RuntimeError):
    pass


_loaded: dict[str, object] = {}


def engine(name: str):
    if name not in ENGINES:
        raise TTSError(f"unknown TTS engine '{name}'")
    if name not in _loaded:
        _loaded[name] = importlib.import_module(ENGINES[name])
    return _loaded[name]


def synthesize(text: str, voice: VoiceConfig, out: Path, cfg: PipelineConfig, emotion: str = "neutral") -> str:
    """Returns the engine name that succeeded."""
    if cfg.tts.force_engine:
        chain = [cfg.tts.force_engine, "sine"]
    else:
        chain = [voice.engine or cfg.tts.default_engine, *voice.fallback]
    speed = voice.speed * EMOTION_SPEED.get(emotion, 1.0)
    errors = []
    for name in dict.fromkeys(chain):
        try:
            engine(name).synth(name, text, voice, speed, out, cfg)
            if out.exists() and out.stat().st_size > 1000:
                return name
            errors.append(f"{name}: empty output")
        except Exception as e:  # noqa: BLE001 - try next engine
            errors.append(f"{name}: {e}")
    raise TTSError("all TTS engines failed: " + " | ".join(errors))
