"""Align: word timestamps per line (whisper, biased with the line text) mapped
onto the script's own tokens, plus mouth-shape cues for the speaking character."""

from __future__ import annotations

from pathlib import Path

from ..align.visemes import rhubarb_visemes, rules_visemes
from ..align.whisper import estimate_words, match_script, transcribe_words
from ..cache import hash_file
from ..episode import Episode
from ..spec import Alignment, AudioManifest, Script, Viseme, Word
from .base import Ctx, Step, console, register


def speaker_character(ctx: Ctx, speaker: str) -> str:
    for c in ctx.series.all_characters():
        if c.speaker == speaker or c.id == speaker:
            return c.id
    return speaker


def _run(ep: Episode, ctx: Ctx) -> None:
    script = ep.read("script", Script)
    audio = ep.read("audio", AudioManifest)
    by_id = {l.id: l for l in script.lines}
    acfg = ctx.cfg.align
    engine = acfg.engine
    all_words: list[Word] = []
    visemes: list[Viseme] = []
    for la in audio.lines:
        line = by_id[la.line_id]
        clip = ep.dir / la.path
        tokens = line.text.split()
        heard: list[dict] | None = None
        if engine != "estimate":
            try:
                heard = transcribe_words(clip, acfg, prompt=line.text)
            except Exception as e:  # noqa: BLE001
                console.print(f"    [yellow]{engine} failed on {la.line_id} ({e}); using estimate[/yellow]")
                engine = "estimate"
        if heard:
            timed = match_script(tokens, heard, la.duration)
        else:
            est = estimate_words(Path(clip), line.text, audio.sample_rate)
            timed = [(w["word"], w["start"], w["end"]) for w in est]
        emph = {e.lower() for e in line.emphasis}
        for tok, st, en in timed:
            clean = tok.strip(".,!?;:\"'()").lower()
            all_words.append(Word(text=tok, start=round(la.start + st, 3), end=round(la.start + en, 3),
                                  line_id=line.id, emphasis=clean in emph))
        who = speaker_character(ctx, line.speaker)
        cues = None
        if acfg.lipsync == "rhubarb":
            try:
                cues = rhubarb_visemes(clip, line.text, who, acfg.rhubarb_bin)
            except Exception as e:  # noqa: BLE001
                console.print(f"    [yellow]rhubarb failed ({e}); rules lipsync[/yellow]")
        if cues is None:
            cues = rules_visemes(timed, who)
        visemes += [Viseme(speaker=c["speaker"], shape=c["shape"], start=round(la.start + c["start"], 3),
                           end=round(la.start + c["end"], 3)) for c in cues]
    ep.write("align", Alignment(words=all_words, visemes=visemes, engine=engine))


register(Step(
    name="align", version="2", status_after="aligned", description="word timestamps + visemes", isolate=True,
    outputs=lambda ep: [ep.path("align")],
    inputs=lambda ep, ctx: {"narr": hash_file(ep.path("audio/narration.wav")),
                            "script": hash_file(ep.path("script")), "audio": hash_file(ep.path("audio")),
                            "align": ctx.cfg.align.model_dump()},
    run=_run,
))
