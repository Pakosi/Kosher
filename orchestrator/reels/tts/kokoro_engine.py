"""Kokoro-82M via the `kokoro` package (torch; CPU or Apple MPS). Voice ids like
am_michael, af_heart, bm_george, bf_emma (first letter = language: a=US, b=UK)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

_pipes: dict[str, object] = {}


def synth(name, text, voice, speed, out: Path, cfg) -> None:
    from kokoro import KPipeline  # heavy import, lazy

    lang = voice.voice[0] if voice.voice[:1] in "abefhijpz" else "a"
    if lang not in _pipes:
        _pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    chunks = [audio for _, _, audio in _pipes[lang](text, voice=voice.voice, speed=speed)]
    if not chunks:
        raise RuntimeError("kokoro produced no audio")
    audio = np.concatenate([np.asarray(c, dtype=np.float32) for c in chunks])
    sf.write(str(out), audio, 24000)
