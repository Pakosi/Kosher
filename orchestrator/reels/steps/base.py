"""Step framework: every step is cached, individually re-runnable, and can run
in a child process so its model weights are released when it exits."""

from __future__ import annotations

import multiprocessing as mp
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from rich.console import Console

from ..cache import StepCache
from ..config import PipelineConfig, SeriesConfig, load_pipeline, load_series
from ..episode import Episode

console = Console()


@dataclass
class Ctx:
    cfg: PipelineConfig
    series: SeriesConfig
    force: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class StepError(RuntimeError):
    pass


@dataclass
class Step:
    name: str
    version: str
    status_after: str
    outputs: Callable[[Episode], list[Path]]
    inputs: Callable[[Episode, Ctx], Any]
    run: Callable[[Episode, Ctx], None]
    isolate: bool = False            # run in a spawned process (frees MLX/torch memory)
    description: str = ""


REGISTRY: dict[str, Step] = {}
ORDER = ["script", "storyboard", "assets", "tts", "align", "timeline", "render", "qa"]


def register(step: Step) -> Step:
    REGISTRY[step.name] = step
    return step


def _child(series: str, ep_id: str, step_name: str, profile: str, q: "mp.Queue") -> None:
    try:
        from . import load_all
        load_all()
        cfg = load_pipeline(profile)
        ep = Episode(series, ep_id, cfg)
        REGISTRY[step_name].run(ep, Ctx(cfg, load_series(series, cfg)))
        q.put(None)
    except BaseException:  # noqa: BLE001 - forwarded to parent
        q.put(traceback.format_exc())


def execute(ep: Episode, step: Step, ctx: Ctx) -> bool:
    """Run one step if its cache key changed. Returns True if it ran."""
    cache = StepCache(ep.dir)
    key = cache.key(step.name, step.version, step.inputs(ep, ctx))
    outs = step.outputs(ep)
    if not ctx.force and cache.fresh(step.name, key, outs):
        console.print(f"  [dim]· {step.name:<10} cached[/dim]")
        return False
    console.print(f"  [cyan]▸ {step.name:<10}[/cyan] {step.description}")
    t0 = time.time()
    ep.log(f"step {step.name} start")
    if step.isolate:
        mpctx = mp.get_context("spawn")
        q = mpctx.Queue()
        p = mpctx.Process(target=_child, args=(ep.series, ep.id, step.name, ctx.cfg.profile, q))
        p.start()
        p.join()
        err = q.get() if not q.empty() else (None if p.exitcode == 0 else f"exit code {p.exitcode}")
        if err:
            raise StepError(f"{step.name} failed:\n{err}")
    else:
        step.run(ep, ctx)
    missing = [str(o) for o in outs if not o.exists()]
    if missing:
        raise StepError(f"{step.name} did not produce {missing}")
    dt = time.time() - t0
    cache = StepCache(ep.dir)          # reload: child process may not share state
    cache.store(step.name, key, outs, dt)
    ep.update_meta(status=step.status_after, error=None)
    ep.log(f"step {step.name} done in {dt:.1f}s")
    console.print(f"  [green]✓ {step.name:<10}[/green] {dt:.1f}s")
    return True
