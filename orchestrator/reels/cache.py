"""Content-addressed step cache. A step's key is a hash of everything that can
change its output (its own version, relevant config, and the bytes of upstream
files). Upstream edits therefore invalidate exactly the downstream steps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .spec import now_iso


def hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hash_obj(obj: Any) -> str:
    return hash_bytes(json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode())


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")) if root.exists() else []:
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(hash_file(p).encode())
    return h.hexdigest()


def fingerprint(paths: list[Path]) -> dict[str, str]:
    return {p.name: (hash_file(p) if p.exists() else "missing") for p in paths}


class StepCache:
    def __init__(self, episode_dir: Path):
        self.file = episode_dir / ".cache.json"
        self.data: dict[str, dict] = json.loads(self.file.read_text()) if self.file.exists() else {}

    def key(self, step: str, version: str, inputs: Any) -> str:
        return hash_obj({"step": step, "v": version, "in": inputs})[:24]

    def fresh(self, step: str, key: str, outputs: list[Path]) -> bool:
        rec = self.data.get(step)
        return bool(rec and rec.get("key") == key and all(p.exists() for p in outputs))

    def store(self, step: str, key: str, outputs: list[Path], seconds: float) -> None:
        self.data[step] = {"key": key, "at": now_iso(), "seconds": round(seconds, 2),
                           "outputs": [p.name for p in outputs]}
        self.file.write_text(json.dumps(self.data, indent=2))

    def invalidate(self, step: str) -> None:
        if self.data.pop(step, None) is not None:
            self.file.write_text(json.dumps(self.data, indent=2))


class AssetCache:
    """Global, cross-episode cache for generated props/backgrounds keyed by prompt."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.index_file = root / "index.json"
        self.index: dict[str, dict] = json.loads(self.index_file.read_text()) if self.index_file.exists() else {}

    def key(self, kind: str, prompt: str, params: dict) -> str:
        return hash_obj({"k": kind, "p": prompt.strip().lower(), "x": params})[:20]

    def get(self, key: str) -> Path | None:
        rec = self.index.get(key)
        if rec:
            p = self.root / rec["file"]
            if p.exists():
                return p
        return None

    def put(self, key: str, src: Path, kind: str, prompt: str) -> Path:
        dest = self.root / kind / f"{key}{src.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        self.index[key] = {"file": str(dest.relative_to(self.root)), "kind": kind,
                           "prompt": prompt, "at": now_iso()}
        self.index_file.write_text(json.dumps(self.index, indent=2))
        return dest
