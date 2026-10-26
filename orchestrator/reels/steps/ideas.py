"""Idea + hook generation. Generates many candidates against the hook-formula
library, de-duplicates against series history, scores them with a judge model
plus deterministic hook heuristics and analytics priors, and keeps the top 20%."""

from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime
from pathlib import Path

import yaml

from .. import db
from ..config import PipelineConfig, SeriesConfig
from ..llm import get_llm
from ..spec import Idea, IdeaPool
from ..text import find_banned, similarity, words

DATA = Path(__file__).resolve().parents[1] / "data"

RUBRIC = {   # weights sum to 1.0
    "hook_strength": 0.28, "curiosity_gap": 0.20, "payoff_potential": 0.16,
    "specificity": 0.12, "series_fit": 0.12, "visual_potential": 0.12,
}

IDEAS_SCHEMA = {
    "type": "object",
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object",
        "properties": {k: {"type": "string"} for k in ("title", "hook", "premise", "formula_id", "topic", "payoff")},
        "required": ["title", "hook", "premise", "formula_id", "topic", "payoff"]}}},
    "required": ["ideas"],
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"scores": {"type": "array", "items": {
        "type": "object",
        "properties": {"index": {"type": "integer"}, **{k: {"type": "number"} for k in RUBRIC},
                       "risk": {"type": "number"}, "reason": {"type": "string"}},
        "required": ["index", *RUBRIC, "risk", "reason"]}}},
    "required": ["scores"],
}


def load_formulas(series: SeriesConfig | None = None) -> list[dict]:
    allf = yaml.safe_load((DATA / "hook_formulas.yaml").read_text())
    if series and series.hook_formulas:
        allf = [f for f in allf if f["id"] in series.hook_formulas] or allf
    return allf


def pick_formulas(formulas: list[dict], priors: dict[str, float], n: int, rng: random.Random) -> list[dict]:
    """Softmax-weighted sampling: proven formulas show up more, but every formula
    keeps some exploration probability."""
    temp = 0.5
    weights = [math.exp(priors.get(f["id"], 0.0) / temp) for f in formulas]
    return rng.choices(formulas, weights=weights, k=n)


def hook_lint(hook: str) -> float:
    """Deterministic 0..10 hook heuristics for the first ~2 seconds."""
    w = words(hook)
    s = 6.0
    if len(w) > 18:
        s -= 2.5
    elif len(w) <= 13:
        s += 1.0
    if re.search(r"\d|million|billion|thousand|hundred", hook.lower()):
        s += 1.0                                   # concrete numbers
    if re.search(r"\byou(r)?\b", hook.lower()):
        s += 1.0                                   # direct address
    if hook.strip().endswith("?"):
        s += 0.5
    if re.match(r"^(so|well|hey|today|in this video)\b", hook.lower()):
        s -= 3.0                                   # slow openers
    return max(0.0, min(10.0, s))


def _gen_prompt(series: SeriesConfig, batch: list[dict], past: list[str], top: list[tuple[str, float]]) -> str:
    fl = "\n".join(f"FORMULA: {f['id']} — {f['name']}: \"{f['template']}\" e.g. {f['examples'][0]}" for f in batch)
    proven = "\n".join(f"- {h} (score {s:.2f})" for h, s in top) or "- (no analytics yet)"
    avoid = "\n".join(f"- {p}" for p in past[:60]) or "- (none yet)"
    topics = ", ".join(series.topics) or "anything that fits the series"
    rules = "\n".join(f"- {r}" for r in series.content_rules)
    return f"""Series: {series.name}
Tone: {series.tone}
Audience: {series.audience}
Topic pool: {topics}
Main character: {series.character.name} — {series.character.personality}
CHARACTER_ID: {series.character.id}

Generate {len(batch)} Instagram Reel ideas, one per formula below, in order. Use each formula's
structure but make the hook feel natural and specific, never a fill-in-the-blank.

{fl}

Hook rules: under 14 words, spoken in the first 2 seconds, concrete numbers or stakes,
creates a question the viewer NEEDS answered, no "today we", no "did you know".
Premise: the actual story beats, with a twist and a satisfying payoff (one sentence each).
Content rules:
{rules or '- keep it factual and entertaining'}

Hooks that performed best on this account (imitate the energy, not the words):
{proven}

Already used — do NOT repeat these angles:
{avoid}

Return JSON {{"ideas": [{{title, hook, premise, formula_id, topic, payoff}}]}}."""


def _judge_prompt(series: SeriesConfig, ideas: list[Idea]) -> str:
    listing = "\n".join(f"[{i}] HOOK: {x.hook}\n    PREMISE: {x.premise}\n    PAYOFF: {x.payoff}" for i, x in enumerate(ideas))
    return f"""You are a ruthless short-form video editor for "{series.name}" ({series.tone}).
Score each idea 0-10 on: hook_strength (would a scrolling viewer stop in 1.5s?),
curiosity_gap (must they watch to the end?), payoff_potential (is the ending satisfying /
share-worthy?), specificity (concrete numbers, names, stakes), series_fit, visual_potential
(easy to show with doodles, a character and props). Also risk 0-10 (misinformation,
harmful how-to, defamation, platform-policy issues). Be harsh: most ideas are a 5.

{listing}

Return JSON {{"scores": [{{index, hook_strength, curiosity_gap, payoff_potential, specificity,
series_fit, visual_potential, risk, reason}}]}} for every index."""


def score_ideas(series: SeriesConfig, ideas: list[Idea], cfg: PipelineConfig, priors: dict[str, float]) -> None:
    judge = get_llm("judge", cfg)
    bs = cfg.ideas.batch_size
    for off in range(0, len(ideas), bs):
        chunk = ideas[off:off + bs]
        res = judge.complete_json("judge", "You score video ideas. Output JSON only.",
                                  _judge_prompt(series, chunk), JUDGE_SCHEMA)
        for s in res.get("scores", []):
            i = int(s.get("index", -1))
            if 0 <= i < len(chunk):
                chunk[i].scores = {k: float(s.get(k, 0)) for k in (*RUBRIC, "risk")}
    judge.unload()
    for idea in ideas:
        if idea.killed_reason:
            continue
        sc = idea.scores
        if not sc:
            idea.killed_reason = "unscored"
            continue
        base = sum(sc.get(k, 0) * w for k, w in RUBRIC.items())
        sc["hook_lint"] = hook_lint(idea.hook)
        prior = priors.get(idea.formula_id, 0.0)
        idea.total = round(0.8 * base + 0.2 * sc["hook_lint"] + 2.0 * prior - 0.4 * max(sc.get("risk", 0) - 3, 0), 3)
        if sc.get("risk", 0) >= 7:
            idea.killed_reason = "risk"


def generate_pool(series: SeriesConfig, cfg: PipelineConfig, n: int | None = None, seed: int | None = None) -> IdeaPool:
    n = n or cfg.ideas.candidates
    rng = random.Random(seed)
    priors = db.formula_priors(series.id, cfg)
    formulas = load_formulas(series)
    past = db.past_hooks(series.id, cfg=cfg)
    top = db.top_hooks(series.id, cfg=cfg)
    draft = get_llm("draft", cfg)
    known = {f["id"] for f in formulas}

    ideas: list[Idea] = []
    bs = cfg.ideas.batch_size
    while len(ideas) < n:
        batch = pick_formulas(formulas, priors, min(bs, n - len(ideas)), rng)
        res = draft.complete_json("ideas", "You are a viral short-form story writer. Output JSON only.",
                                  _gen_prompt(series, batch, past, top), IDEAS_SCHEMA)
        got = res.get("ideas", [])
        if not got:
            break
        for j, raw in enumerate(got[:len(batch)]):
            raw["formula_id"] = raw.get("formula_id") if raw.get("formula_id") in known else batch[j]["id"]
            ideas.append(Idea(**{k: raw.get(k, "") for k in ("title", "hook", "premise", "formula_id", "topic", "payoff")}))
    draft.unload()

    # dedupe vs history + within pool, banned words
    seen: list[str] = list(past)
    for i, idea in enumerate(ideas):
        idea.id = f"i{i + 1:03d}"
        if bad := find_banned(f"{idea.hook} {idea.premise}", series.banned_words):
            idea.killed_reason = f"banned:{','.join(bad)}"
            continue
        if any(similarity(idea.hook, s) > cfg.ideas.novelty_threshold for s in seen):
            idea.killed_reason = "duplicate"
            continue
        seen.append(idea.hook)

    score_ideas(series, ideas, cfg, priors)
    alive = sorted([x for x in ideas if not x.killed_reason], key=lambda x: x.total, reverse=True)
    keep_n = max(1, round(len(ideas) * cfg.ideas.keep_ratio))
    kept, cut = alive[:keep_n], alive[keep_n:]
    for x in cut:
        x.killed_reason = "bottom_80"
    pool = IdeaPool(series=series.id, candidates=ideas, kept=kept)
    save_pool(pool, cfg)
    return pool


def pool_dir(series_id: str, cfg: PipelineConfig) -> Path:
    d = cfg.paths.p("state") / "ideas" / series_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_pool(pool: IdeaPool, cfg: PipelineConfig) -> Path:
    p = pool_dir(pool.series, cfg) / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(pool.model_dump_json(indent=2))
    return p


def take_best_idea(series_id: str, cfg: PipelineConfig) -> Idea | None:
    """Pop the highest-scoring unused kept idea across all saved pools."""
    used_file = pool_dir(series_id, cfg) / "used.json"
    used = set(json.loads(used_file.read_text())) if used_file.exists() else set()
    best: tuple[float, str, Idea] | None = None
    for f in sorted(pool_dir(series_id, cfg).glob("2*.json")):
        pool = IdeaPool.model_validate_json(f.read_text())
        for idea in pool.kept:
            uid = f"{f.stem}:{idea.id}"
            if uid not in used and (best is None or idea.total > best[0]):
                best = (idea.total, uid, idea)
    if not best:
        return None
    used.add(best[1])
    used_file.write_text(json.dumps(sorted(used)))
    return best[2]
