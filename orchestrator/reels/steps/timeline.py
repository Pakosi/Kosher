"""Timeline: resolve storyboard + audio + assets into the exact Remotion props
(seconds-based), and assemble the render bundle (public dir) for this episode."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from ..cache import hash_file
from ..config import ROOT
from ..episode import Episode
from ..spec import (AssetManifest, AudioManifest, Rig, Storyboard, Timeline, TLBackground, TLCaption,
                    TLCharacter, TLMusic, TLPalette, TLProcedural, TLProp, TLScene, TLSfx, TLSpan, TLText,
                    TLViseme, TLWord, Script, Alignment)
from ..synth import music_bed, write_sfx
from .base import Ctx, Step, console, register

AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".aac", ".flac")


def _music_source(ep: Episode, ctx: Ctx) -> Path | None:
    folder = ctx.series.music_folder
    cands: list[Path] = []
    for d in filter(None, [Path(folder).expanduser() if folder else None,
                           ctx.cfg.paths.p("library") / "music" / ctx.series.id,
                           ctx.cfg.paths.p("library") / "music"]):
        d = d if d.is_absolute() else ROOT / d
        if d.is_dir():
            cands = sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT)
            if cands:
                break
    if not cands:
        return None
    idx = int(hashlib.sha256(ep.id.encode()).hexdigest(), 16) % len(cands)
    return cands[idx]


def _sfx_source(name: str, ctx: Ctx) -> Path | None:
    d = ctx.cfg.paths.p("library") / "sfx"
    for ext in AUDIO_EXT:
        p = d / f"{name}{ext}"
        if p.exists():
            return p
    return None


def _load_rig(path: str | None, char_id: str) -> Rig | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text())
    for name, pose in data["poses"].items():
        pose["src"] = f"characters/{char_id}/{Path(pose['src']).name}"
    return Rig.model_validate(data)


def _run(ep: Episode, ctx: Ctx) -> None:
    cfg, series = ctx.cfg, ctx.series
    sb = ep.read("storyboard", Storyboard)
    audio = ep.read("audio", AudioManifest)
    assets = ep.read("assets", AssetManifest)
    script = ep.read("script", Script)
    al = ep.read("align", Alignment)
    pub = ep.path("public")
    (pub / "audio").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ep.path("audio/narration.wav"), pub / "audio" / "narration.wav")

    line_start = {l.line_id: l.start for l in audio.lines}
    line_end = {l.line_id: l.start + l.duration for l in audio.lines}
    total = audio.duration
    fps = cfg.render.fps

    # scene windows: start at first line, end at next scene start
    starts = [max(0.0, line_start[s.line_ids[0]] - (0.0 if i == 0 else 0.12)) for i, s in enumerate(sb.scenes)]
    starts[0] = 0.0
    ends = starts[1:] + [total]

    rigs = {cid: _load_rig(p, cid) for cid, p in assets.rigs.items()}
    looks = {c.id: c.procedural for c in series.all_characters()}

    scenes: list[TLScene] = []
    sfx_events: list[TLSfx] = []
    sfx_files: dict[str, str] = {}

    def sfx_src(name: str) -> str:
        if name not in sfx_files:
            src = _sfx_source(name, ctx)
            dest = pub / "sfx" / (f"{name}{src.suffix}" if src else f"{name}.wav")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src:
                shutil.copy2(src, dest)
            else:
                write_sfx(name, dest)
            sfx_files[name] = f"sfx/{dest.name}"
        return sfx_files[name]

    for sc, st, en in zip(sb.scenes, starts, ends):
        sw = [w for w in al.words if w.line_id in sc.line_ids]

        def word_time(idx: int | None) -> float:
            if idx is None or not sw:
                return st
            return sw[max(0, min(idx, len(sw) - 1))].start

        bg_ref = assets.backgrounds.get(sc.id)
        if bg_ref and bg_ref.kind == "image" and bg_ref.src:
            bg = TLBackground(kind="image", src=bg_ref.src)
        else:
            bg = TLBackground(kind="builtin", name=sc.background if not sc.background.startswith("prompt:") else "plain")

        chars = []
        for c in sc.characters:
            look = looks.get(c.id) or series.character.procedural
            chars.append(TLCharacter(id=c.id, pose=c.pose, expression=c.expression, x=c.x, y=c.y, scale=c.scale,
                                     flip=c.flip, enter=c.enter, rig=rigs.get(c.id),
                                     procedural=TLProcedural(**look.model_dump())))
        props = []
        for p in sc.props:
            ref = assets.props.get(f"{sc.id}/{p.id}")
            if ref is None or ref.kind == "icon":
                props.append(TLProp(id=p.id, kind="icon", icon=(ref.src if ref else p.icon) or "question",
                                    label=p.label, x=p.x, y=p.y, scale=p.scale, rotation=p.rotation,
                                    at=word_time(p.appear_word), animation=p.animation))
            else:
                props.append(TLProp(id=p.id, kind=ref.kind if ref.kind in ("svg", "image") else "image",
                                    src=ref.src, label=p.label, x=p.x, y=p.y, scale=p.scale,
                                    rotation=p.rotation, at=word_time(p.appear_word), animation=p.animation))
        text = None
        if sc.on_screen_text:
            text = TLText(text=sc.on_screen_text.text, style=sc.on_screen_text.style,
                          at=word_time(sc.on_screen_text.appear_word), color=sc.on_screen_text.color)
        for cue in sc.sfx:
            sfx_events.append(TLSfx(src=sfx_src(cue.name), at=round(max(0.0, word_time(cue.at_word) + cue.offset), 3),
                                    volume=cue.volume))
        if sc.transition_in in ("whip", "zoom") and scenes:
            sfx_events.append(TLSfx(src=sfx_src("whoosh"), at=max(0.0, st - 0.05), volume=0.5))
        scenes.append(TLScene(id=sc.id, start=round(st, 3), end=round(en, 3), background=bg, characters=chars,
                              props=props, camera=sc.camera, cameraIntensity=sc.camera_intensity, text=text,
                              transition=sc.transition_in))

    music = None
    msrc = _music_source(ep, ctx)
    (pub / "music").mkdir(exist_ok=True)
    if msrc:
        dest = pub / "music" / f"bed{msrc.suffix}"
        shutil.copy2(msrc, dest)
    else:
        console.print("    [yellow]no music in library -> procedural bed (add tracks to library/music/<series>/)[/yellow]")
        dest = music_bed(pub / "music" / "bed.wav", total, seed=int(hashlib.sha256(ep.id.encode()).hexdigest()[:6], 16))
    music = TLMusic(src=f"music/{dest.name}", volume=cfg.audio.music_volume, duckVolume=cfg.audio.duck_volume)

    pal = series.palette
    tl = Timeline(
        episodeId=ep.id, title=script.title, fps=fps, width=cfg.render.width, height=cfg.render.height,
        durationInFrames=int(math.ceil(total * fps)),
        palette=TLPalette(**pal.model_dump()),
        caption=TLCaption(font=series.caption.font, size=series.caption.size, highlight=series.caption.highlight,
                          position=series.caption.position, wordsPerChunk=series.caption.words_per_chunk),
        narration="audio/narration.wav", music=music,
        speech=[TLSpan(start=l.start, end=round(l.start + l.duration, 3)) for l in audio.lines],
        sfx=sorted(sfx_events, key=lambda s: s.at),
        words=[TLWord(text=w.text, start=w.start, end=w.end, emphasis=w.emphasis) for w in al.words],
        visemes=[TLViseme(**v.model_dump()) for v in al.visemes],
        scenes=scenes, sfxVolume=cfg.audio.sfx_volume,
    )
    ep.write("timeline", tl)


register(Step(
    name="timeline", version="3", status_after="timeline", description="compose Remotion props + bundle",
    outputs=lambda ep: [ep.path("timeline")],
    inputs=lambda ep, ctx: {"sb": hash_file(ep.path("storyboard")), "audio": hash_file(ep.path("audio")),
                            "align": hash_file(ep.path("align")),
                            "assets": hash_file(ep.path("assets")),
                            "series": ctx.series.model_dump(include={"palette", "caption", "music_folder", "character", "cast"}),
                            "cfg": ctx.cfg.model_dump(include={"render", "audio"})},
    run=_run,
))
