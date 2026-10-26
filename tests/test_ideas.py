import random

from reels.steps.ideas import generate_pool, hook_lint, load_formulas, pick_formulas, take_best_idea


def test_hook_lint_prefers_punchy_hooks():
    good = hook_lint("If you had $20 million in dirty cash, how would you clean it?")
    bad = hook_lint("So today in this video we are going to talk about some interesting facts about banking systems and more")
    assert good > bad


def test_formula_sampling_respects_priors():
    fs = load_formulas()
    rng = random.Random(1)
    picks = pick_formulas(fs, {fs[0]["id"]: 3.0}, 400, rng)
    share = sum(p["id"] == fs[0]["id"] for p in picks) / 400
    assert share > 0.5


def test_pool_keeps_top_20_percent(cfg, series):
    pool = generate_pool(series, cfg, n=10, seed=3)
    assert len(pool.candidates) == 10
    assert len(pool.kept) == 2
    alive = [c for c in pool.candidates if not c.killed_reason]
    assert all(k.total >= max(c.total for c in pool.candidates if c.killed_reason == "bottom_80") for k in pool.kept) or not alive
    first = take_best_idea(series.id, cfg)
    second = take_best_idea(series.id, cfg)
    assert first and second and first.id != second.id
    assert take_best_idea(series.id, cfg) is None
