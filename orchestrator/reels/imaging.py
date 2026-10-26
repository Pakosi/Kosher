"""Image post-processing for doodle assets: white-background removal by border
flood fill (keeps interior whites), autocrop, and potrace vectorisation so props
can be drawn on stroke by stroke in Remotion."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def remove_white_background(src: Path, dest: Path, tol: int = 28) -> Path:
    img = Image.open(src).convert("RGBA")
    a = np.array(img)
    h, w = a.shape[:2]
    rgb = a[..., :3].astype(np.int16)
    near_white = (255 - rgb).max(axis=2) <= tol
    mask = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if near_white[y, x] and not mask[y, x]:
                mask[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near_white[y, x] and not mask[y, x]:
                mask[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and near_white[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                q.append((ny, nx))
    a[..., 3] = np.where(mask, 0, 255).astype(np.uint8)
    out = Image.fromarray(a)
    bbox = out.getbbox()
    if bbox:
        pad = 12
        out = out.crop((max(bbox[0] - pad, 0), max(bbox[1] - pad, 0),
                        min(bbox[2] + pad, w), min(bbox[3] + pad, h)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)
    return dest


def has_potrace() -> bool:
    return shutil.which("potrace") is not None


def vectorize(src: Path, dest: Path, threshold: int = 110, turdsize: int = 12) -> Path | None:
    """Trace the dark ink lines into an SVG. Returns None if potrace is missing."""
    if not has_potrace():
        return None
    img = Image.open(src).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    gray = Image.alpha_composite(bg, img).convert("L")
    bw = gray.point(lambda p: 0 if p < threshold else 255, mode="1")
    with tempfile.TemporaryDirectory() as td:
        pbm = Path(td) / "in.pbm"
        bw.save(pbm)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["potrace", str(pbm), "-s", "-o", str(dest), "-t", str(turdsize),
                        "--flat", "-O", "0.4"], check=True, capture_output=True)
    return dest


def sample_color(src: Path, x: int, y: int, radius: int = 6) -> str:
    img = Image.open(src).convert("RGB")
    a = np.array(img)
    h, w = a.shape[:2]
    patch = a[max(y - radius, 0):min(y + radius, h), max(x - radius, 0):min(x + radius, w)].reshape(-1, 3)
    r, g, b = np.median(patch, axis=0).astype(int) if len(patch) else (255, 255, 255)
    return f"#{r:02x}{g:02x}{b:02x}"
