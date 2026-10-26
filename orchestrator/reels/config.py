"""Pipeline + per-series configuration (YAML -> pydantic)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("REELS_ROOT", Path(__file__).resolve().parents[2]))


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------- pipeline

class LLMConfig(BaseModel):
    backend: Literal["ollama", "openai", "claude", "mock"] = "ollama"
    model: str = "qwen3:14b"
    host: str = "http://127.0.0.1:11434"
    temperature: float = 0.8
    num_ctx: int = 8192
    effort: str = "medium"          # claude only
    enabled: bool = True
    timeout: float = 600.0
    keep_alive: str = "0"           # ollama: unload right after each call by default


class LLMSet(BaseModel):
    draft: LLMConfig = LLMConfig()
    judge: LLMConfig = LLMConfig(model="gemma3:12b", temperature=0.2)
    polish: LLMConfig = LLMConfig(backend="claude", model="claude-opus-5-5")
    vision: LLMConfig = LLMConfig(model="qwen2.5vl:7b", temperature=0.0)


class ComfyConfig(BaseModel):
    enabled: bool = True
    host: str = "http://127.0.0.1:8188"
    checkpoint: str = "sd_xl_base_1.0.safetensors"
    style_lora: str | None = None          # optional global doodle-style LoRA
    style_lora_strength: float = 0.8
    steps: int = 28
    cfg: float = 6.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    width: int = 1024
    height: int = 1024
    background_size: tuple[int, int] = (832, 1216)
    remove_background: bool = True
    timeout: float = 900.0


class TTSConfig(BaseModel):
    default_engine: str = "kokoro"
    force_engine: str | None = None        # override every voice's engine (test profile / quick drafts)
    sample_rate: int = 24000
    line_gap: float = 0.18                 # seconds of silence between lines
    beat_gap: float = 0.35                 # extra pause on beat change (hook->setup etc)
    elevenlabs_model: str = "eleven_multilingual_v2"


class AlignConfig(BaseModel):
    engine: Literal["mlx-whisper", "faster-whisper", "whisper-cpp", "estimate"] = "mlx-whisper"
    model: str = "mlx-community/whisper-large-v3-turbo"
    whisper_cpp_bin: str = "whisper-cli"
    whisper_cpp_model: str = "~/models/ggml-large-v3-turbo.bin"
    lipsync: Literal["rhubarb", "rules"] = "rules"
    rhubarb_bin: str = "rhubarb"


class RenderConfig(BaseModel):
    fps: int = 30
    width: int = 1080
    height: int = 1920
    concurrency: int = 4
    crf: int = 18
    codec: str = "h264"
    gl: str | None = None                   # e.g. "angle" on mac if needed
    browser_executable: str | None = None   # use an existing Chrome/Chromium instead of Remotion's download


class AudioConfig(BaseModel):
    target_lufs: float = -14.0
    true_peak: float = -1.0
    music_volume: float = 0.32
    duck_volume: float = 0.07
    sfx_volume: float = 0.7


class QAConfig(BaseModel):
    min_seconds: float = 28.0
    max_seconds: float = 62.0
    lufs_tolerance: float = 1.5
    max_wer: float = 0.18
    max_sync_drift: float = 0.25
    vision_check: bool = True
    vision_frames: int = 6


class IdeasConfig(BaseModel):
    candidates: int = 40
    keep_ratio: float = 0.2
    batch_size: int = 10
    novelty_threshold: float = 0.55        # trigram similarity above this vs history = duplicate


class PublishConfig(BaseModel):
    graph_version: str = "v23.0"
    graph_host: str = "https://graph.facebook.com"
    upload_host: str = "https://rupload.facebook.com"
    poll_seconds: float = 10.0
    poll_timeout: float = 900.0
    insights_metrics: list[str] = Field(default_factory=lambda: [
        "views", "reach", "likes", "comments", "shares", "saved",
        "total_interactions", "ig_reels_avg_watch_time",
    ])


class Paths(BaseModel):
    episodes: str = "episodes"
    state: str = "state"
    library: str = "library"
    assets_cache: str = "assets_cache"
    characters: str = "characters"
    remotion: str = "remotion"
    series: str = "config/series"

    def p(self, name: str) -> Path:
        v = Path(getattr(self, name)).expanduser()
        return v if v.is_absolute() else ROOT / v


class PipelineConfig(BaseModel):
    profile: str = "default"
    paths: Paths = Paths()
    llm: LLMSet = LLMSet()
    comfy: ComfyConfig = ComfyConfig()
    tts: TTSConfig = TTSConfig()
    align: AlignConfig = AlignConfig()
    render: RenderConfig = RenderConfig()
    audio: AudioConfig = AudioConfig()
    qa: QAConfig = QAConfig()
    ideas: IdeasConfig = IdeasConfig()
    publish: PublishConfig = PublishConfig()


# ---------------------------------------------------------------- series

class VoiceConfig(BaseModel):
    engine: str | None = None              # kokoro | mlx-kokoro | f5 | elevenlabs | say | espeak | sine
    voice: str = "am_michael"
    speed: float = 1.0
    ref_audio: str | None = None           # f5: reference clip for cloning
    ref_text: str | None = None
    elevenlabs_voice_id: str | None = None
    fallback: list[str] = Field(default_factory=list)  # engines to try if primary fails


class ProceduralLook(BaseModel):
    """Used by the built-in SVG character when no generated rig exists."""
    species: Literal["raccoon", "blob", "cat", "human"] = "blob"
    body: str = "#FFFFFF"
    accent: str = "#E63946"
    accessory: Literal["none", "fedora", "glasses", "beanie", "crown", "headphones"] = "none"


class CharacterConfig(BaseModel):
    id: str
    name: str
    description: str                        # visual prompt
    personality: str = ""
    speaker: str = ""                       # which voice key this character speaks with
    lora: str | None = None
    lora_trigger: str | None = None
    lora_strength: float = 0.9
    procedural: ProceduralLook = ProceduralLook()

    def rig_path(self, cfg: PipelineConfig) -> Path:
        return cfg.paths.p("characters") / self.id / "rig.json"


class Palette(BaseModel):
    paper: str = "#F7F3E8"
    ink: str = "#1B1B1B"
    accent: str = "#E63946"
    accent2: str = "#2A9D8F"
    highlight: str = "#FFD166"


class CaptionStyle(BaseModel):
    font: str = "Gochi Hand"               # any @remotion/google-fonts family in remotion/src/lib/fonts.ts
    size: int = 92
    highlight: str = "#FFD166"
    words_per_chunk: int = 3
    position: float = 0.5                   # 0..1 of height (centre of caption block)


class SeriesPublish(BaseModel):
    ig_user_id_env: str = ""
    token_env: str = ""
    hashtags: list[str] = Field(default_factory=list)
    post_times: list[str] = Field(default_factory=lambda: ["18:00"])
    timezone: str = "America/New_York"
    caption_template: str = "{title}\n\n{cta}\n\n{hashtags}"
    cta: str = "Follow for part 2."


class SeriesConfig(BaseModel):
    id: str
    name: str
    tone: str
    audience: str = ""
    topics: list[str] = Field(default_factory=list)
    hook_formulas: list[str] = Field(default_factory=list)   # empty = all
    banned_words: list[str] = Field(default_factory=list)
    content_rules: list[str] = Field(default_factory=list)
    character: CharacterConfig
    cast: list[CharacterConfig] = Field(default_factory=list)  # optional extra recurring characters
    palette: Palette = Palette()
    voices: dict[str, VoiceConfig]
    music_folder: str | None = None
    caption: CaptionStyle = CaptionStyle()
    target_seconds: tuple[int, int] = (35, 55)
    publish: SeriesPublish = SeriesPublish()

    def all_characters(self) -> list[CharacterConfig]:
        return [self.character, *self.cast]


# ---------------------------------------------------------------- loaders

@lru_cache(maxsize=1)
def load_pipeline(profile: str | None = None) -> PipelineConfig:
    profile = profile or os.environ.get("REELS_PROFILE", "default")
    data: dict[str, Any] = {}
    base = ROOT / "config" / "pipeline.yaml"
    if base.exists():
        data = yaml.safe_load(base.read_text()) or {}
    if profile != "default":
        over = ROOT / "config" / f"pipeline.{profile}.yaml"
        if over.exists():
            data = _deep_merge(data, yaml.safe_load(over.read_text()) or {})
    local = ROOT / "config" / "pipeline.local.yaml"     # untracked personal overrides
    if local.exists():
        data = _deep_merge(data, yaml.safe_load(local.read_text()) or {})
    data["profile"] = profile
    return PipelineConfig.model_validate(data)


def series_dir(cfg: PipelineConfig) -> Path:
    return cfg.paths.p("series")


def list_series(cfg: PipelineConfig) -> list[str]:
    return sorted(p.stem for p in series_dir(cfg).glob("*.yaml"))


def load_series(series_id: str, cfg: PipelineConfig | None = None) -> SeriesConfig:
    cfg = cfg or load_pipeline()
    path = series_dir(cfg) / f"{series_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"series config not found: {path}")
    return SeriesConfig.model_validate(yaml.safe_load(path.read_text()))
