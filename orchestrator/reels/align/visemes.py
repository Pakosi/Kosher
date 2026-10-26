"""Mouth shapes (Rhubarb/Preston Blair set A-H + X rest) from word timings.
`rules` is a fast letter-cluster heuristic; `rhubarb` shells out to Rhubarb
Lip Sync for phoneme-accurate cues when installed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

DIGRAPHS = [("th", "B"), ("sh", "B"), ("ch", "B"), ("ph", "G"), ("oo", "F"), ("ou", "F"), ("ow", "F"),
            ("ee", "B"), ("ea", "C"), ("ai", "C"), ("ay", "C"), ("oa", "E"), ("qu", "F"), ("wh", "F")]
SINGLE = {"m": "A", "b": "A", "p": "A", "f": "G", "v": "G", "l": "H", "w": "F", "q": "F", "o": "E",
          "u": "F", "a": "D", "e": "C", "i": "C", "y": "B", "r": "E"}
MIN_SHAPE = 0.06


def word_shapes(word: str) -> list[str]:
    w = re.sub(r"[^a-z]", "", word.lower())
    shapes: list[str] = []
    i = 0
    while i < len(w):
        pair = w[i:i + 2]
        hit = next((s for d, s in DIGRAPHS if d == pair), None)
        if hit:
            shapes.append(hit)
            i += 2
            continue
        shapes.append(SINGLE.get(w[i], "B"))
        i += 1
    if w.endswith("e") and len(shapes) > 1 and len(w) > 3:
        shapes.pop()                     # silent trailing e
    out: list[str] = []
    for s in shapes:
        if not out or out[-1] != s:
            out.append(s)
    return out or ["B"]


def rules_visemes(words: list[tuple[str, float, float]], speaker: str) -> list[dict]:
    cues: list[dict] = []
    for text, st, en in words:
        shapes = word_shapes(text)
        dur = max(en - st, MIN_SHAPE)
        max_n = max(1, int(dur / MIN_SHAPE))
        if len(shapes) > max_n:          # keep the most visible shapes (vowels/closures)
            pri = {"D": 0, "E": 1, "F": 1, "A": 2, "C": 2, "G": 3, "H": 4, "B": 5}
            keep = sorted(range(len(shapes)), key=lambda i: pri.get(shapes[i], 9))[:max_n]
            shapes = [shapes[i] for i in sorted(keep)]
        step = dur / len(shapes)
        if cues and st - cues[-1]["end"] > 0.12:
            cues.append({"speaker": speaker, "shape": "X", "start": cues[-1]["end"], "end": st})
        for k, s in enumerate(shapes):
            cues.append({"speaker": speaker, "shape": s, "start": round(st + k * step, 3),
                         "end": round(st + (k + 1) * step, 3)})
    if cues:
        cues.append({"speaker": speaker, "shape": "X", "start": cues[-1]["end"], "end": cues[-1]["end"] + 0.2})
    return cues


def rhubarb_visemes(wav: Path, text: str, speaker: str, exe: str = "rhubarb") -> list[dict]:
    path = shutil.which(exe)
    if not path:
        raise RuntimeError("rhubarb not installed")
    dialog = wav.with_suffix(".txt")
    dialog.write_text(text)
    p = subprocess.run([path, "-f", "json", "-d", str(dialog), "--extendedShapes", "GHX", str(wav)],
                       check=True, capture_output=True, text=True)
    dialog.unlink(missing_ok=True)
    data = json.loads(p.stdout)
    return [{"speaker": speaker, "shape": c["value"], "start": c["start"], "end": c["end"]}
            for c in data.get("mouthCues", [])]
