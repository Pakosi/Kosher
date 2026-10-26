"""Orchestration: create episodes, run steps (with caching), and batch-produce
many episodes stage by stage so only one kind of model is in memory at a time."""

from __future__ import annotations

import traceback

from . import db
from .config import PipelineConfig, SeriesConfig, load_pipeline, load_series
from .episode import Episode
from .llm.ollama import unload_all
from .spec import Idea, QAReport
from .steps import load_all
from .steps.base import ORDER, REGISTRY, Ctx, console, execute
from .steps.ideas import generate_pool, take_best_idea

load_all()

LLM_STAGES = {"script", "storyboard"}


def new_episode(series: SeriesConfig, cfg: PipelineConfig, idea: Idea | None = None) -> Episode:
    if idea is None:
        idea = take_best_idea(series.id, cfg)
        if idea is None:
            console.print(f"[cyan]no unused ideas for {series.id}: generating a pool[/cyan]")
            generate_pool(series, cfg)
            idea = take_best_idea(series.id, cfg)
        if idea is None:
            raise RuntimeError("idea generation produced nothing usable")
    ep = Episode.create(series.id, idea.title, cfg)
    ep.write("idea", idea)
    ep.update_meta(title=idea.title, formula_id=idea.formula_id)
    db.add_hook(series.id, idea.hook, idea.title, idea.formula_id, ep.ref, cfg)
    console.print(f"[bold]new episode[/bold] {ep.ref}\n  hook: {idea.hook}")
    return ep


def steps_between(start: str | None, stop: str | None) -> list[str]:
    i = ORDER.index(start) if start else 0
    j = ORDER.index(stop) + 1 if stop else len(ORDER)
    return ORDER[i:j]


def run_episode(ep: Episode, cfg: PipelineConfig | None = None, start: str | None = None,
                stop: str | None = None, force: set[str] | None = None) -> str:
    cfg = cfg or ep.cfg
    series = load_series(ep.series, cfg)
    force = force or set()
    console.print(f"[bold]{ep.ref}[/bold]")
    for name in steps_between(start, stop):
        ctx = Ctx(cfg, series, force=name in force or "all" in force)
        try:
            ran = execute(ep, REGISTRY[name], ctx)
        except Exception as e:
            ep.update_meta(status="failed", error=f"{name}: {e}")
            ep.log(traceback.format_exc())
            console.print(f"  [red]✗ {name}: {e}[/red]")
            raise
        if ran and name in LLM_STAGES:
            unload_all(cfg.llm.draft.host)
        if name == "qa":
            rep = ep.read("qa", QAReport)
            ep.update_meta(status="qa_failed" if rep.status == "fail" else "review")
            colour = {"pass": "green", "warn": "yellow", "fail": "red"}[rep.status]
            console.print(f"  QA: [{colour}]{rep.status}[/{colour}]")
    return ep.meta.status


def batch(series_ids: list[str], count: int, cfg: PipelineConfig | None = None,
          stop: str | None = None) -> list[Episode]:
    """Stage-major batch: all LLM work first (one model resident), then ComfyUI,
    then TTS, then Whisper, then renders. Failures don't stop other episodes."""
    cfg = cfg or load_pipeline()
    eps: list[Episode] = []
    for sid in series_ids:
        series = load_series(sid, cfg)
        for _ in range(count):
            try:
                eps.append(new_episode(series, cfg))
            except Exception as e:  # noqa: BLE001
                console.print(f"[red]{sid}: could not create episode: {e}[/red]")
    alive = list(eps)
    for name in steps_between(None, stop):
        console.rule(f"stage: {name}")
        for ep in list(alive):
            try:
                ctx = Ctx(cfg, load_series(ep.series, cfg))
                execute(ep, REGISTRY[name], ctx)
                if name == "qa":
                    rep = ep.read("qa", QAReport)
                    ep.update_meta(status="qa_failed" if rep.status == "fail" else "review")
            except Exception as e:  # noqa: BLE001
                ep.update_meta(status="failed", error=f"{name}: {e}")
                ep.log(traceback.format_exc())
                console.print(f"  [red]✗ {ep.ref} {name}: {e}[/red]")
                alive.remove(ep)
        if name in LLM_STAGES or name == "storyboard":
            unload_all(cfg.llm.draft.host)
    return eps
