"""Storyboard: turn the script into scenes (background, character pose/expression,
props, camera, on-screen text, SFX). Output is sanitised against the shared
visual vocabulary so the renderer never meets an unknown name."""

from __future__ import annotations

import re

from ..cache import hash_file
from ..episode import Episode
from ..llm import get_llm
from ..spec import Script, Storyboard
from ..text import shorten
from ..vocab import (BACKGROUNDS, CAMERAS, EXPRESSIONS, ICONS, POSES, PROP_ANIMS, SFX,
                     TEXT_STYLES, TRANSITIONS)
from .base import Ctx, Step, register

SB_SCHEMA = {
    "type": "object",
    "properties": {"scenes": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"},
        "line_ids": {"type": "array", "items": {"type": "string"}},
        "background": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "pose": {"type": "string"}, "expression": {"type": "string"},
            "x": {"type": "number"}, "y": {"type": "number"}, "scale": {"type": "number"},
            "flip": {"type": "boolean"}, "enter": {"type": "string"}},
            "required": ["id", "pose", "expression", "x", "y", "scale", "flip", "enter"]}},
        "props": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "icon": {"type": ["string", "null"]}, "prompt": {"type": ["string", "null"]},
            "label": {"type": ["string", "null"]}, "x": {"type": "number"}, "y": {"type": "number"},
            "scale": {"type": "number"}, "rotation": {"type": "number"},
            "appear_word": {"type": ["integer", "null"]}, "animation": {"type": "string"}},
            "required": ["id", "icon", "prompt", "label", "x", "y", "scale", "rotation", "appear_word", "animation"]}},
        "camera": {"type": "string"}, "camera_intensity": {"type": "number"},
        "on_screen_text": {"type": ["object", "null"], "properties": {
            "text": {"type": "string"}, "style": {"type": "string"},
            "appear_word": {"type": ["integer", "null"]}, "color": {"type": ["string", "null"]}},
            "required": ["text", "style", "appear_word", "color"]},
        "sfx": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "at_word": {"type": ["integer", "null"]},
            "offset": {"type": "number"}, "volume": {"type": "number"}},
            "required": ["name", "at_word", "offset", "volume"]}},
        "transition_in": {"type": "string"}},
        "required": ["id", "line_ids", "background", "characters", "props", "camera", "camera_intensity",
                     "on_screen_text", "sfx", "transition_in"]}}},
    "required": ["scenes"],
}


RELATIVE_BG = re.compile(r"\b(same|as before|previous|again|earlier|beginning)\b", re.I)
MAX_GENERATED_BG = 3   # generated backgrounds are meant to be rare; each costs ~35 s of SDXL


def _spread(props: list, min_dx: float = 0.24) -> None:
    """Props on the same row closer than min_dx overlap (icons and labels): space them evenly."""
    if len(props) < 2:
        return
    xs = sorted(p.x for p in props)
    if all(b - a >= min_dx for a, b in zip(xs, xs[1:])):
        return
    n = len(props)
    lo, hi = (0.5 - min_dx * (n - 1) / 2, 0.5 + min_dx * (n - 1) / 2) if min_dx * (n - 1) <= 0.68 else (0.16, 0.84)
    for i, p in enumerate(sorted(props, key=lambda p: p.x)):
        p.x = round(lo + (hi - lo) * i / (n - 1), 3)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def coerce(raw: dict) -> dict:
    """Make raw model output schema-valid before pydantic sees it (unknown enum
    values -> defaults; missing ids/fields filled)."""
    def pick(v, allowed, default):
        return v if v in allowed else default

    scenes = []
    for i, sc in enumerate(raw.get("scenes") or []):
        if not isinstance(sc, dict):
            continue
        sc = dict(sc)
        sc["id"] = str(sc.get("id") or f"s{i + 1}")
        sc["line_ids"] = [str(x) for x in sc.get("line_ids") or []]
        sc["background"] = str(sc.get("background") or "plain")
        sc["camera"] = pick(sc.get("camera"), CAMERAS, "static")
        sc["transition_in"] = pick(sc.get("transition_in"), TRANSITIONS, "cut")
        sc["camera_intensity"] = float(sc.get("camera_intensity") or 0.5)
        chars = []
        for c in sc.get("characters") or []:
            if isinstance(c, dict):
                c = dict(c)
                c["enter"] = pick(c.get("enter"), ["none", "pop", "slide_left", "slide_right", "drop"], "none")
                c["id"] = str(c.get("id") or "")
                chars.append({k: v for k, v in c.items() if v is not None})
        sc["characters"] = chars
        props = []
        for j, p in enumerate(sc.get("props") or []):
            if isinstance(p, dict):
                p = dict(p)
                p["id"] = str(p.get("id") or f"p{j + 1}")
                p["animation"] = pick(p.get("animation"), PROP_ANIMS, "draw")
                props.append({k: v for k, v in p.items() if v is not None or k in ("icon", "prompt", "label", "appear_word")})
        sc["props"] = props
        t = sc.get("on_screen_text")
        if isinstance(t, dict) and t.get("text"):
            t = dict(t)
            t["style"] = pick(t.get("style"), TEXT_STYLES, "marker")
            sc["on_screen_text"] = t
        else:
            sc["on_screen_text"] = None
        sc["sfx"] = [dict(x, name=str(x.get("name"))) for x in sc.get("sfx") or [] if isinstance(x, dict) and x.get("name")]
        for x in sc["sfx"]:
            x["offset"] = float(x.get("offset") or 0.0)
            x["volume"] = float(x.get("volume") or 1.0)
        scenes.append(sc)
    return {"scenes": scenes}


def sanitise(sb: Storyboard, script: Script, ctx: Ctx) -> Storyboard:
    line_ids = [l.id for l in script.lines]
    char_ids = {c.id for c in ctx.series.all_characters()}
    main = ctx.series.character.id
    covered: list[str] = []
    scenes = []
    for sc in sb.scenes:
        sc.line_ids = [l for l in sc.line_ids if l in line_ids and l not in covered]
        if not sc.line_ids:
            continue
        covered += sc.line_ids
        scenes.append(sc)
    # any lines the model skipped get appended to the nearest previous scene
    for lid in line_ids:
        if lid not in covered:
            idx = line_ids.index(lid)
            target = next((s for s in reversed(scenes) if any(line_ids.index(x) < idx for x in s.line_ids)), None)
            (target or scenes[0]).line_ids.append(lid)
    for s in scenes:
        s.line_ids.sort(key=line_ids.index)
    scenes.sort(key=lambda s: line_ids.index(s.line_ids[0]))

    generated: list[str] = []
    for i, sc in enumerate(scenes):
        sc.id = f"s{i + 1}"
        if not (sc.background in BACKGROUNDS or sc.background.startswith("prompt:")):
            sc.background = "plain"
        if sc.background.startswith("prompt:") and i:
            # "same room as before" would be generated as a brand-new random scene: reuse instead
            if RELATIVE_BG.search(sc.background):
                sc.background = scenes[0 if "beginning" in sc.background.lower() else i - 1].background
            elif sc.background not in generated and len(generated) >= MAX_GENERATED_BG:
                sc.background = scenes[i - 1].background
        if sc.background.startswith("prompt:") and sc.background not in generated:
            generated.append(sc.background)
        sc.camera = sc.camera if sc.camera in CAMERAS else "static"
        sc.camera_intensity = _clamp(sc.camera_intensity, 0, 1)
        sc.transition_in = "cut" if i == 0 else (sc.transition_in if sc.transition_in in TRANSITIONS else "cut")
        chars = []
        for c in sc.characters[:2]:
            if c.id not in char_ids:
                c.id = main
            c.pose = c.pose if c.pose in POSES else "neutral"
            c.expression = c.expression if c.expression in EXPRESSIONS else "neutral"
            c.x, c.y = _clamp(c.x, 0.2, 0.8), _clamp(c.y, 0.84, 0.95)
            c.scale = _clamp(c.scale, 0.6, 1.4)
            chars.append(c)
        sc.characters = chars
        props = []
        for j, p in enumerate(sc.props[:4]):
            p.id = f"p{j + 1}"
            if p.icon and p.icon not in ICONS:
                p.prompt, p.icon = p.prompt or p.icon.replace("_", " "), None
            if not p.icon and not p.prompt:
                p.icon = "question"
            p.x, p.y = _clamp(p.x, 0.14, 0.86), _clamp(p.y, 0.24, 0.42)   # keep clear of captions + IG UI
            p.scale = _clamp(p.scale, 0.5, 1.8)
            p.rotation = _clamp(p.rotation, -25, 25)
            p.animation = p.animation if p.animation in PROP_ANIMS else "draw"
            if p.label:
                p.label = p.label.rstrip("0123456789_ ") or None
            props.append(p)
        _spread(props)
        sc.props = props
        if sc.on_screen_text:
            full = " ".join(sc.on_screen_text.text.split())
            short = shorten(full, 28)
            # a banner showing half a sentence reads as a bug; captions already carry the full line
            sc.on_screen_text.text = short
            if len(short) < 0.75 * len(full):
                sc.on_screen_text = None
            elif sc.on_screen_text.style not in TEXT_STYLES:
                sc.on_screen_text.style = "marker"
        sc.sfx = [x for x in sc.sfx if x.name in SFX][:3]
    return Storyboard(scenes=scenes)


def _run(ep: Episode, ctx: Ctx) -> None:
    script = ep.read("script", Script)
    lines = "\n".join(f"{l.id} [{l.beat}] {l.speaker} ({l.emotion}): {l.text}" for l in script.lines)
    chars = "\n".join(f"- {c.id}: {c.name}, {c.description}" for c in ctx.series.all_characters())
    prompt = f"""Storyboard this Reel as a 2D doodle animation, 1080x1920 vertical.
CHARACTER_ID: {ctx.series.character.id}
Characters (use these ids):
{chars}

SCRIPT (one scene per line usually; merge two very short consecutive lines when it helps pacing):
{lines}

VOCABULARY (use ONLY these names):
backgrounds: {BACKGROUNDS} or "prompt:<short description>" for a special generated background (rare)
poses: {POSES}
expressions: {EXPRESSIONS}
icons (props): {ICONS}
  -> if no icon fits, set icon null and give a short "prompt" (e.g. "a stack of gold bars") to generate one
prop animations: {PROP_ANIMS}
cameras: {CAMERAS}
transitions: {TRANSITIONS}
on-screen text styles: {TEXT_STYLES}
sfx: {SFX}

LAYOUT: x,y are 0..1 of the frame. Vertical zones: on-screen text 0.10-0.20, props 0.24-0.42 (y = prop centre),
captions ~0.50 (keep clear), character feet at y ~0.9 (character occupies 0.55-0.9). x 0.2-0.8 for characters. 1-3 props per scene, each appearing on the word that
mentions it (appear_word = 0-based index into that scene's words). Big numbers and key terms go in
on_screen_text (max ~24 chars). The character reacts physically to every line (pose + expression match the
emotion). Vary camera moves; use shake/whip_zoom for twists, push_in for reveals. 1-2 sfx per scene max.
Return JSON {{"scenes": [...]}}."""
    llm = get_llm("draft", ctx.cfg)
    raw = llm.complete_json("storyboard", "You are a storyboard artist for doodle explainer reels. Output JSON only.",
                            prompt, SB_SCHEMA)
    llm.unload()
    ep.write("storyboard", sanitise(Storyboard.model_validate(coerce(raw)), script, ctx))


register(Step(
    name="storyboard", version="5", status_after="boarded", description="scenes, props, camera, sfx",
    outputs=lambda ep: [ep.path("storyboard")],
    inputs=lambda ep, ctx: {"script": hash_file(ep.path("script")),
                            "chars": [c.model_dump() for c in ctx.series.all_characters()],
                            "llm": ctx.cfg.llm.draft.model_dump()},
    run=_run,
))
