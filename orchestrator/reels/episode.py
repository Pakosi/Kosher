"""Episode folder access. One folder per episode holds every step's output, so any
step can be inspected, edited by hand, and re-run on its own."""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .config import PipelineConfig, load_pipeline
from .spec import EpisodeMeta, now_iso

T = TypeVar("T", bound=BaseModel)

FILES = {
    "meta": "meta.json",
    "idea": "idea.json",
    "script_draft": "script.draft.json",
    "script": "script.json",
    "storyboard": "storyboard.json",
    "assets": "assets.json",
    "audio": "audio.json",
    "align": "align.json",
    "timeline": "timeline.json",
    "qa": "qa.json",
    "video": "render/final.mp4",
    "video_raw": "render/raw.mp4",
}


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].strip("-") or "episode"


class Episode:
    def __init__(self, series: str, episode_id: str, cfg: PipelineConfig | None = None):
        self.cfg = cfg or load_pipeline()
        self.series = series
        self.id = episode_id
        self.dir = self.cfg.paths.p("episodes") / series / episode_id

    # ---------------------------------------------------------- creation / lookup
    @classmethod
    def create(cls, series: str, title: str = "", cfg: PipelineConfig | None = None) -> "Episode":
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        eid = f"{stamp}-{slugify(title, 28) if title else secrets.token_hex(3)}"
        ep = cls(series, eid, cfg)
        ep.dir.mkdir(parents=True, exist_ok=True)
        ep.save_meta(EpisodeMeta(id=eid, series=series, title=title))
        return ep

    @classmethod
    def find(cls, ref: str, cfg: PipelineConfig | None = None) -> "Episode":
        """Accepts 'series/id', a path, or a bare id (searched across series)."""
        cfg = cfg or load_pipeline()
        root = cfg.paths.p("episodes")
        p = Path(ref)
        if p.is_dir() and (p / FILES["meta"]).exists():
            return cls(p.parent.name, p.name, cfg)
        if "/" in ref:
            s, e = ref.split("/", 1)
            return cls(s, e, cfg)
        hits = [d for d in root.glob(f"*/*{ref}*") if (d / FILES["meta"]).exists()]
        if len(hits) != 1:
            raise FileNotFoundError(f"episode '{ref}': {len(hits)} matches")
        return cls(hits[0].parent.name, hits[0].name, cfg)

    @classmethod
    def all(cls, series: str | None = None, cfg: PipelineConfig | None = None) -> list["Episode"]:
        cfg = cfg or load_pipeline()
        root = cfg.paths.p("episodes")
        pattern = f"{series}/*" if series else "*/*"
        return [cls(d.parent.name, d.name, cfg)
                for d in sorted(root.glob(pattern)) if (d / FILES["meta"]).exists()]

    # ---------------------------------------------------------- io
    def path(self, key_or_rel: str) -> Path:
        return self.dir / FILES.get(key_or_rel, key_or_rel)

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def read(self, key: str, model: type[T]) -> T:
        return model.model_validate_json(self.path(key).read_text())

    def maybe(self, key: str, model: type[T]) -> T | None:
        return self.read(key, model) if self.has(key) else None

    def write(self, key: str, obj: BaseModel | dict) -> Path:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = obj.model_dump(mode="json") if isinstance(obj, BaseModel) else obj
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.replace(p)
        return p

    @property
    def meta(self) -> EpisodeMeta:
        return self.read("meta", EpisodeMeta)

    def save_meta(self, meta: EpisodeMeta) -> None:
        meta.updated_at = now_iso()
        self.write("meta", meta)
        from . import db  # local import: db imports episode-free modules only
        db.upsert_episode(meta, self.cfg)

    def update_meta(self, **fields) -> EpisodeMeta:
        m = self.meta
        for k, v in fields.items():
            setattr(m, k, v)
        self.save_meta(m)
        return m

    def log(self, msg: str) -> None:
        with (self.dir / "log.txt").open("a") as f:
            f.write(f"[{now_iso()}] {msg}\n")

    @property
    def ref(self) -> str:
        return f"{self.series}/{self.id}"

    def __repr__(self) -> str:
        return f"Episode({self.ref})"
