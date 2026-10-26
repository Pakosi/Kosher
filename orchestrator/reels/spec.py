"""Episode JSON spec. Each pipeline step writes one of these documents into the
episode folder; `Timeline` is exactly the input-props contract of the Remotion
`Reel` composition (mirrored by remotion/src/schema.ts)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Beat = Literal["hook", "setup", "escalation", "twist", "payoff", "loop"]
BEATS: tuple[str, ...] = ("hook", "setup", "escalation", "twist", "payoff", "loop")
Status = Literal["new", "scripted", "boarded", "assets", "voiced", "aligned",
                 "timeline", "rendered", "qa_failed", "review", "approved",
                 "rejected", "scheduled", "published", "failed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ ideas

class Idea(BaseModel):
    id: str = ""
    title: str
    hook: str                     # the literal first spoken line (<= ~14 words)
    premise: str                  # what the episode actually delivers
    formula_id: str
    topic: str = ""
    payoff: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    total: float = 0.0
    killed_reason: str | None = None


class IdeaPool(BaseModel):
    series: str
    created_at: str = Field(default_factory=now_iso)
    candidates: list[Idea]
    kept: list[Idea]


# ------------------------------------------------------------------ script

class Line(BaseModel):
    id: str
    speaker: str                  # key into series.voices
    text: str
    beat: Beat
    emotion: str = "neutral"      # neutral|excited|smug|shocked|whisper|serious|sad|angry
    emphasis: list[str] = Field(default_factory=list)  # words to pop in captions


class Script(BaseModel):
    title: str
    lines: list[Line]
    loop_note: str = ""           # how the last line flows back into the hook
    caption: str = ""             # IG caption body
    hashtags: list[str] = Field(default_factory=list)
    polished: bool = False

    def text(self) -> str:
        return " ".join(l.text for l in self.lines)

    def word_count(self) -> int:
        return len(self.text().split())


# ------------------------------------------------------------------ storyboard

Camera = Literal["static", "push_in", "pull_out", "pan_left", "pan_right", "shake", "whip_zoom", "tilt_up"]
PropAnim = Literal["draw", "pop", "slide_left", "slide_right", "drop", "stamp"]
Transition = Literal["cut", "whip", "paper", "zoom", "ink_wipe"]


class PropSpec(BaseModel):
    id: str
    icon: str | None = None       # built-in doodle icon name (see remotion/src/icons)
    prompt: str | None = None     # otherwise generated via ComfyUI
    label: str | None = None      # handwritten label under the prop
    x: float = 0.5                # 0..1 of frame width (centre)
    y: float = 0.32
    scale: float = 1.0
    rotation: float = 0.0
    appear_word: int | None = None  # index into the scene's word list; None = scene start
    animation: PropAnim = "draw"


class CharacterShot(BaseModel):
    id: str                        # character id
    pose: str = "neutral"          # neutral|point|shock|think|smug|shrug|run|sneak|celebrate|facepalm
    expression: str = "neutral"
    x: float = 0.5
    y: float = 0.9                 # feet position (0..1 of height)
    scale: float = 1.0
    flip: bool = False
    enter: Literal["none", "pop", "slide_left", "slide_right", "drop"] = "none"


class OnScreenText(BaseModel):
    text: str
    style: Literal["stamp", "marker", "counter", "banner"] = "marker"
    appear_word: int | None = None
    color: str | None = None


class SfxCue(BaseModel):
    name: str                      # library/sfx/<name>.(wav|mp3) or synthesized fallback
    at_word: int | None = None     # None = scene start
    offset: float = 0.0
    volume: float = 1.0


class Scene(BaseModel):
    id: str
    line_ids: list[str]
    background: str = "plain"      # built-in: plain|grid|dots|desk|city|bank|alley|lab|map; or "prompt:<text>"
    characters: list[CharacterShot] = Field(default_factory=list)
    props: list[PropSpec] = Field(default_factory=list)
    camera: Camera = "static"
    camera_intensity: float = 0.5
    on_screen_text: OnScreenText | None = None
    sfx: list[SfxCue] = Field(default_factory=list)
    transition_in: Transition = "cut"


class Storyboard(BaseModel):
    scenes: list[Scene]


# ------------------------------------------------------------------ assets

class AssetRef(BaseModel):
    kind: Literal["svg", "image", "icon", "procedural"]
    src: str | None = None         # path relative to the render public dir
    source: str = ""               # comfy|cache|builtin|fallback
    key: str = ""                  # cache key


class AssetManifest(BaseModel):
    backgrounds: dict[str, AssetRef] = Field(default_factory=dict)   # scene id -> ref
    props: dict[str, AssetRef] = Field(default_factory=dict)         # "<scene>/<prop>" -> ref
    rigs: dict[str, str | None] = Field(default_factory=dict)        # character id -> rig.json path or None


# ------------------------------------------------------------------ audio

class Word(BaseModel):
    text: str
    start: float
    end: float
    line_id: str = ""
    emphasis: bool = False


class Viseme(BaseModel):
    speaker: str                   # character id (or voice key if no character)
    shape: Literal["A", "B", "C", "D", "E", "F", "G", "H", "X"]
    start: float
    end: float


class LineAudio(BaseModel):
    line_id: str
    speaker: str
    path: str                      # relative to episode dir
    start: float                   # position in narration track (s)
    duration: float
    engine: str = ""


class AudioManifest(BaseModel):
    narration: str = "audio/narration.wav"
    duration: float
    sample_rate: int
    lines: list[LineAudio]


class Alignment(BaseModel):
    words: list[Word]
    visemes: list[Viseme]
    engine: str


# ------------------------------------------------------------------ timeline (Remotion props)

class TLPalette(BaseModel):
    paper: str
    ink: str
    accent: str
    accent2: str
    highlight: str


class TLCaption(BaseModel):
    font: str
    size: int
    highlight: str
    position: float
    wordsPerChunk: int


class TLWord(BaseModel):
    text: str
    start: float
    end: float
    emphasis: bool = False


class TLViseme(BaseModel):
    speaker: str
    shape: str
    start: float
    end: float


class TLSfx(BaseModel):
    src: str
    at: float
    volume: float = 1.0


class TLSpan(BaseModel):
    start: float
    end: float


class RigPose(BaseModel):
    src: str
    width: int
    height: int
    mouth: dict[str, float]        # {x, y, w, rotation} in pose-image pixels
    eyes: list[dict[str, float]] = Field(default_factory=list)   # [{x,y,r}] for blink lids


class Rig(BaseModel):
    poses: dict[str, RigPose]
    expressions: dict[str, str] = Field(default_factory=dict)    # expression -> pose name
    mouthColor: str = "#1B1B1B"
    skinColor: str = "#FFFFFF"     # colour used for blink lids


class TLProcedural(BaseModel):
    species: str
    body: str
    accent: str
    accessory: str


class TLCharacter(BaseModel):
    id: str
    pose: str
    expression: str
    x: float
    y: float
    scale: float
    flip: bool
    enter: str
    rig: Rig | None = None
    procedural: TLProcedural


class TLProp(BaseModel):
    id: str
    kind: Literal["icon", "svg", "image"]
    icon: str | None = None
    src: str | None = None
    label: str | None = None
    x: float
    y: float
    scale: float
    rotation: float
    at: float
    animation: str


class TLText(BaseModel):
    text: str
    style: str
    at: float
    color: str | None = None


class TLBackground(BaseModel):
    kind: Literal["builtin", "image", "svg"]
    name: str = "plain"
    src: str | None = None


class TLScene(BaseModel):
    id: str
    start: float
    end: float
    background: TLBackground
    characters: list[TLCharacter]
    props: list[TLProp]
    camera: str
    cameraIntensity: float
    text: TLText | None = None
    transition: str


class TLMusic(BaseModel):
    src: str
    volume: float
    duckVolume: float
    startFrom: float = 0.0


class Timeline(BaseModel):
    episodeId: str
    title: str
    fps: int
    width: int
    height: int
    durationInFrames: int
    palette: TLPalette
    caption: TLCaption
    narration: str
    music: TLMusic | None = None
    speech: list[TLSpan]
    sfx: list[TLSfx]
    words: list[TLWord]
    visemes: list[TLViseme]
    scenes: list[TLScene]
    lineBoil: bool = True
    showSafeZones: bool = False
    sfxVolume: float = 0.7


# ------------------------------------------------------------------ qa / meta

class QACheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail", "skip"]
    detail: str = ""
    value: float | str | None = None


class QAReport(BaseModel):
    status: Literal["pass", "warn", "fail"]
    checks: list[QACheck]
    created_at: str = Field(default_factory=now_iso)


class EpisodeMeta(BaseModel):
    id: str
    series: str
    status: Status = "new"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    title: str = ""
    formula_id: str = ""
    error: str | None = None
    review_note: str | None = None
    scheduled_at: str | None = None
    media_id: str | None = None
    permalink: str | None = None
