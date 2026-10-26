"""Script: local draft (hook -> setup -> escalation -> twist -> payoff -> loop),
automatic length/structure repair, then one polish call to Claude (falls back to
a local self-critique pass when Claude isn't configured)."""

from __future__ import annotations


from ..cache import hash_file
from ..episode import Episode
from ..llm import LLMError, get_llm
from ..spec import BEATS, Idea, Script
from ..text import find_banned
from .base import Ctx, Step, StepError, console, register

WPS = 2.7   # spoken words per second at speed 1.0 for punchy narration

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "speaker": {"type": "string"}, "text": {"type": "string"},
            "beat": {"type": "string", "enum": list(BEATS)}, "emotion": {"type": "string"},
            "emphasis": {"type": "array", "items": {"type": "string"}}},
            "required": ["id", "speaker", "text", "beat", "emotion", "emphasis"]}},
        "loop_note": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "lines", "loop_note", "caption", "hashtags"],
}

CRAFT = """STRUCTURE (strict order):
1. hook (1 line, <=14 words, 0-3s): the idea's hook, verbatim or sharper. No greeting.
2. setup (1-2 lines): the obvious/naive answer, usually from the main character.
3. escalation (2-4 lines): each attempt raises stakes; the narrator knocks each one down
   with a concrete fact, number or consequence. Rapid back-and-forth.
4. twist (1 line): the reveal the viewer didn't see coming.
5. payoff (1-2 lines): the satisfying lesson/answer, quotable, share-worthy.
6. loop (1 line): a final line that flows straight back into the hook so the reel loops
   seamlessly (often the hook question re-asked by the character, or an unfinished sentence
   the hook completes).
CRAFT RULES:
- Short spoken sentences. Contractions. Every line earns its place. Zero filler.
- Specific numbers and real mechanisms beat vague claims. No made-up statistics.
- The main character is funny, flawed, confident; the narrator is dry and smart.
- Mark 1-3 emphasis words per line (exact words from the line) for kinetic captions.
- emotion is one of: neutral, excited, smug, shocked, whisper, serious, sad, angry.
- Write numbers as digits or $ amounts; they're converted for TTS automatically."""


def _speakers(ctx: Ctx) -> str:
    out = []
    for key, v in ctx.series.voices.items():
        who = next((c for c in ctx.series.all_characters() if c.speaker == key or c.id == key), None)
        out.append(f"- {key}: " + (f"{who.name} (on-screen character, {who.personality})" if who else "off-screen narrator"))
    return "\n".join(out)


def target_words(ctx: Ctx) -> tuple[int, int]:
    lo, hi = ctx.series.target_seconds
    return int(lo * WPS), int(hi * WPS)


def validate(script: Script, ctx: Ctx) -> list[str]:
    problems = []
    beats = [l.beat for l in script.lines]
    for b in BEATS:
        if b not in beats:
            problems.append(f"missing beat '{b}'")
    if beats and beats[0] != "hook":
        problems.append("first line must be the hook")
    if beats and beats[-1] != "loop":
        problems.append("last line must be the loop")
    order = [BEATS.index(b) for b in beats]
    if order != sorted(order):
        problems.append("beats out of order")
    bad = {l.speaker for l in script.lines} - set(ctx.series.voices)
    if bad:
        problems.append(f"unknown speakers {sorted(bad)}; use only {sorted(ctx.series.voices)}")
    lo, hi = target_words(ctx)
    n = script.word_count()
    if n < lo:
        problems.append(f"too short: {n} words, need {lo}-{hi}; add about {(lo + hi) // 2 - n} words, e.g. one more "
                        "escalation exchange with a concrete fact or consequence")
    if n > hi:
        problems.append(f"too long: {n} words, need {lo}-{hi}")
    if hit := find_banned(script.text(), ctx.series.banned_words):
        problems.append(f"banned words: {hit}")
    if script.lines and len(script.lines[0].text.split()) > 16:
        problems.append("hook longer than 16 words")
    return problems


def _normalise(data: dict, ctx: Ctx) -> Script:
    s = Script.model_validate(data)
    for i, l in enumerate(s.lines):
        l.id = f"l{i + 1}"
        if l.speaker not in ctx.series.voices:
            # map character names/ids to their voice key
            for c in ctx.series.all_characters():
                if l.speaker.lower() in (c.id.lower(), c.name.lower()):
                    l.speaker = c.speaker or c.id
        if l.speaker not in ctx.series.voices:
            l.speaker = "narrator" if "narrator" in ctx.series.voices else next(iter(ctx.series.voices))
        l.emphasis = [w for w in l.emphasis if w.lower() in l.text.lower()][:3]
    return s


def draft(idea: Idea, ctx: Ctx) -> Script:
    lo, hi = target_words(ctx)
    llm = get_llm("draft", ctx.cfg)
    rules = "\n".join(f"- {r}" for r in ctx.series.content_rules)
    prompt = f"""Write the script for a {ctx.series.target_seconds[0]}-{ctx.series.target_seconds[1]} second Instagram Reel
({lo}-{hi} spoken words total, aim for about {(lo + hi) // 2}) for the series "{ctx.series.name}".
Tone: {ctx.series.tone}
CHARACTER_ID: {ctx.series.character.id}

IDEA
title: {idea.title}
hook: {idea.hook}
premise: {idea.premise}
payoff: {idea.payoff}

SPEAKERS (use these exact keys in "speaker"):
{_speakers(ctx)}

{CRAFT}
Series content rules:
{rules or '- factual, entertaining'}

Also write an IG caption (1-2 punchy sentences + a question to drive comments) and 3-6 hashtags without #.
Return JSON {{title, lines:[{{id, speaker, text, beat, emotion, emphasis}}], loop_note, caption, hashtags}}."""
    script = _normalise(llm.complete_json("script", "You write viral short-form scripts. Output JSON only.",
                                          prompt, SCRIPT_SCHEMA), ctx)
    for _ in range(2):
        problems = validate(script, ctx)
        if not problems:
            break
        console.print(f"    [yellow]repairing draft: {problems}[/yellow]")
        fix = f"""{prompt}

Your previous draft had problems: {problems}
Previous draft: {script.model_dump_json()}
Fix every problem while keeping what works."""
        script = _normalise(llm.complete_json("script", "You write viral short-form scripts. Output JSON only.",
                                              fix, SCRIPT_SCHEMA), ctx)
    llm.unload()
    return script


def polish(script: Script, idea: Idea, ctx: Ctx) -> Script:
    lo, hi = target_words(ctx)
    pc = ctx.cfg.llm.polish
    system = ("You are a top short-form script doctor (think MrBeast retention editing meets Kurzgesagt clarity). "
              "You punch up scripts without changing facts you can't verify.")
    prompt = f"""Polish this Reel script for maximum retention. Keep the JSON shape, line ids may change.
Series: {ctx.series.name} — {ctx.series.tone}
CHARACTER_ID: {ctx.series.character.id}
Speakers allowed: {sorted(ctx.series.voices)}
Length: {lo}-{hi} words total.

{CRAFT}

Checklist: hook stops the scroll in under 2s; every line creates or pays off tension; jokes land on the
last word; numbers are accurate or removed; the loop line flows seamlessly into the hook; caption ends in a question.
Remove anything that reads as step-by-step instructions for wrongdoing; explain mechanisms and consequences instead.

IDEA: {idea.model_dump_json()}
SCRIPT: {script.model_dump_json()}"""
    llm = get_llm("polish", ctx.cfg)
    use_claude = pc.enabled and pc.backend == "claude" and getattr(llm, "available", lambda: True)()
    if not use_claude:
        if pc.backend == "claude":
            console.print("    [yellow]Claude polish unavailable (no SDK/key) -> local self-critique pass[/yellow]")
            llm = get_llm("draft", ctx.cfg)
    try:
        out = _normalise(llm.complete_json("polish", system, prompt, SCRIPT_SCHEMA), ctx)
    except LLMError as e:
        console.print(f"    [yellow]polish failed ({e}); keeping draft[/yellow]")
        return script
    finally:
        llm.unload()
    if (bad := validate(out, ctx)) and not validate(script, ctx):
        console.print(f"    [yellow]polished script failed validation ({bad}); keeping draft[/yellow]")
        return script
    out.polished = True
    return out


def _run(ep: Episode, ctx: Ctx) -> None:
    idea = ep.read("idea", Idea)
    d = draft(idea, ctx)
    ep.write("script_draft", d)
    final = polish(d, idea, ctx)
    problems = validate(final, ctx)
    if any(p.startswith(("missing", "unknown", "banned")) for p in problems):
        raise StepError(f"script invalid: {problems}")
    ep.write("script", final)
    ep.update_meta(title=final.title)


register(Step(
    name="script", version="4", status_after="scripted", description="draft + polish script",
    outputs=lambda ep: [ep.path("script")],
    inputs=lambda ep, ctx: {"idea": hash_file(ep.path("idea")),
                            "series": ctx.series.model_dump(include={"tone", "voices", "content_rules",
                                                                     "banned_words", "target_seconds"}),
                            "llm": ctx.cfg.llm.model_dump(include={"draft", "polish"})},
    run=_run,
))


def manual_script(ep: Episode, data: dict, ctx: Ctx) -> Script:
    """Use a hand-written script (JSON) instead of generating one."""
    s = _normalise(data, ctx)
    ep.write("script_draft", s)
    ep.write("script", s)
    return s


__all__ = ["draft", "polish", "validate", "manual_script"]
