"""Assets: resolve every background, prop and character rig the storyboard needs.
Built-in doodle icons/backgrounds are free; anything else is generated once via
ComfyUI (SDXL + LoRA), background-removed, vectorised and stored in the global
asset cache so future episodes reuse it."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..cache import AssetCache, hash_file
from ..comfy.client import ComfyClient, ComfyError
from ..comfy.workflows import background_prompt, prop_prompt, txt2img
from ..episode import Episode
from ..imaging import remove_white_background, vectorize
from ..spec import AssetManifest, AssetRef, Storyboard
from .base import Ctx, Step, console, register


def _generate(client: ComfyClient | None, ctx: Ctx, cache: AssetCache, kind: str, subject: str,
              tmp: Path) -> Path | None:
    cc = ctx.cfg.comfy
    params = {"ckpt": cc.checkpoint, "lora": cc.style_lora, "steps": cc.steps, "v": 2}
    key = cache.key(kind, subject, params)
    if hit := cache.get(key):
        return hit
    if client is None:
        return None
    if kind == "prop":
        wf = txt2img(cc, prop_prompt(subject), seed=int(key[:8], 16))
    else:
        w, h = cc.background_size
        wf = txt2img(cc, background_prompt(subject), width=w, height=h, seed=int(key[:8], 16))
    raw = client.run(wf, tmp, key)[0]
    if kind == "prop":
        cut = remove_white_background(raw, tmp / f"{key}_cut.png")
        stored = cache.put(key, cut, kind, subject)
        if svg := vectorize(cut, tmp / f"{key}.svg"):
            cache.put(key + "v", svg, kind, subject)
        return stored
    return cache.put(key, raw, kind, subject)


def _run(ep: Episode, ctx: Ctx) -> None:
    sb = ep.read("storyboard", Storyboard)
    cache = AssetCache(ctx.cfg.paths.p("assets_cache"))
    pub = ep.path("public")
    (pub / "assets").mkdir(parents=True, exist_ok=True)
    tmp = ep.path("tmp_assets")
    tmp.mkdir(exist_ok=True)

    needs_gen = any(p.prompt and not p.icon for s in sb.scenes for p in s.props) or \
        any(s.background.startswith("prompt:") for s in sb.scenes)
    client = None
    if needs_gen and ctx.cfg.comfy.enabled:
        c = ComfyClient(ctx.cfg.comfy.host, ctx.cfg.comfy.timeout)
        if c.alive():
            client = c
        else:
            console.print("    [yellow]ComfyUI not reachable: generated props fall back to built-in icons[/yellow]")

    man = AssetManifest()

    def publish(src: Path) -> str:
        dest = pub / "assets" / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
        return f"assets/{src.name}"

    try:
        for sc in sb.scenes:
            if sc.background.startswith("prompt:"):
                subj = sc.background.split(":", 1)[1].strip()
                try:
                    got = _generate(client, ctx, cache, "background", subj, tmp)
                except ComfyError as e:
                    console.print(f"    [yellow]background gen failed: {e}[/yellow]")
                    got = None
                man.backgrounds[sc.id] = (AssetRef(kind="image", src=publish(got), source="comfy", key=got.stem)
                                          if got else AssetRef(kind="procedural", src=None, source="fallback"))
            for p in sc.props:
                k = f"{sc.id}/{p.id}"
                if p.icon:
                    man.props[k] = AssetRef(kind="icon", src=p.icon, source="builtin")
                    continue
                try:
                    got = _generate(client, ctx, cache, "prop", p.prompt or "", tmp)
                except ComfyError as e:
                    console.print(f"    [yellow]prop gen failed ({p.prompt}): {e}[/yellow]")
                    got = None
                if not got:
                    man.props[k] = AssetRef(kind="icon", src="question", source="fallback")
                    continue
                svg = cache.get(got.stem + "v")
                man.props[k] = (AssetRef(kind="svg", src=publish(svg), source="comfy", key=got.stem) if svg
                                else AssetRef(kind="image", src=publish(got), source="comfy", key=got.stem))
    finally:
        if client:
            client.free()
        shutil.rmtree(tmp, ignore_errors=True)

    for ch in ctx.series.all_characters():
        rig = ch.rig_path(ctx.cfg)
        if rig.exists():
            # copy pose images into the render bundle
            dest = pub / "characters" / ch.id
            dest.mkdir(parents=True, exist_ok=True)
            for f in rig.parent.glob("poses/*.png"):
                shutil.copy2(f, dest / f.name)
            man.rigs[ch.id] = str(rig)
        else:
            man.rigs[ch.id] = None
    ep.write("assets", man)


def _inputs(ep: Episode, ctx: Ctx) -> dict:
    rigs = {}
    for ch in ctx.series.all_characters():
        r = ch.rig_path(ctx.cfg)
        rigs[ch.id] = hash_file(r) if r.exists() else None
    return {"sb": hash_file(ep.path("storyboard")), "rigs": rigs,
            "comfy": ctx.cfg.comfy.model_dump(include={"checkpoint", "style_lora", "steps", "enabled"})}


register(Step(
    name="assets", version="2", status_after="assets", description="icons, ComfyUI props/backgrounds, rigs",
    outputs=lambda ep: [ep.path("assets")], inputs=_inputs, run=_run,
))
