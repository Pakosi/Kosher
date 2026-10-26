"""`reels` command line."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from . import db
from .config import ROOT, list_series, load_pipeline, load_series
from .episode import Episode
from .steps.base import ORDER, Ctx, console

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Automated doodle Reels pipeline.")
char_app = typer.Typer(no_args_is_help=True, help="Recurring character design, LoRA and rig tools.")
app.add_typer(char_app, name="character")


def _cfg():
    return load_pipeline()


# ------------------------------------------------------------------ ideas / episodes

@app.command()
def series():
    """List configured series."""
    cfg = _cfg()
    t = Table("id", "name", "character", "voices")
    for sid in list_series(cfg):
        s = load_series(sid, cfg)
        t.add_row(s.id, s.name, f"{s.character.name} ({s.character.procedural.species})", ", ".join(s.voices))
    console.print(t)


@app.command()
def ideas(series_id: str, n: int = typer.Option(0, help="candidates (default from config)"),
          seed: Optional[int] = None):
    """Generate + score an idea pool; keeps the top 20%."""
    from .steps.ideas import generate_pool
    cfg = _cfg()
    pool = generate_pool(load_series(series_id, cfg), cfg, n or None, seed)
    t = Table("score", "formula", "hook", title=f"kept {len(pool.kept)}/{len(pool.candidates)}")
    for i in pool.kept:
        t.add_row(f"{i.total:.2f}", i.formula_id, i.hook)
    console.print(t)
    killed = {}
    for c in pool.candidates:
        if c.killed_reason:
            killed[c.killed_reason.split(":")[0]] = killed.get(c.killed_reason.split(":")[0], 0) + 1
    console.print(f"killed: {killed}")


@app.command()
def new(series_id: str, hook: Optional[str] = typer.Option(None, help="use this hook instead of the idea pool"),
        premise: str = typer.Option("", help="with --hook: what the episode delivers"),
        script: Optional[Path] = typer.Option(None, help="hand-written script JSON (skips script generation)")):
    """Create an episode (best unused idea, or your own hook/script)."""
    from .pipeline import new_episode
    from .spec import Idea
    cfg = _cfg()
    s = load_series(series_id, cfg)
    idea = Idea(title=hook[:60], hook=hook, premise=premise or hook, formula_id="manual") if hook else None
    ep = new_episode(s, cfg, idea)
    if script:
        from .steps.script import manual_script
        manual_script(ep, json.loads(script.read_text()), Ctx(cfg, s))
        ep.update_meta(status="scripted")
    console.print(ep.ref)


@app.command()
def run(episode: str, start: Optional[str] = typer.Option(None, "--from", help=f"one of {ORDER}"),
        stop: Optional[str] = typer.Option(None, "--to"),
        force: str = typer.Option("", help="comma list of steps to force, or 'all'")):
    """Run (or resume) an episode. Cached steps are skipped automatically."""
    from .pipeline import run_episode
    ep = Episode.find(episode, _cfg())
    run_episode(ep, start=start, stop=stop, force=set(filter(None, force.split(","))))


@app.command()
def make(series_id: str, count: int = 1, stop: Optional[str] = typer.Option(None, "--to")):
    """New episode(s) end to end: idea -> ... -> QA -> review queue."""
    from .pipeline import new_episode, run_episode
    cfg = _cfg()
    s = load_series(series_id, cfg)
    for _ in range(count):
        ep = new_episode(s, cfg)
        try:
            run_episode(ep, cfg, stop=stop)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]{ep.ref} failed: {e}[/red]")


@app.command()
def batch(series_ids: str = typer.Option("all", "--series", help="comma list or 'all'"),
          count: int = typer.Option(2, help="episodes per series"),
          stop: Optional[str] = typer.Option(None, "--to")):
    """Overnight batch, stage by stage (one model type in memory at a time)."""
    from .pipeline import batch as run_batch
    cfg = _cfg()
    ids = list_series(cfg) if series_ids == "all" else series_ids.split(",")
    eps = run_batch(ids, count, cfg, stop)
    t = Table("episode", "status", "title")
    for ep in eps:
        m = ep.meta
        t.add_row(ep.ref, m.status, m.title)
    console.print(t)


@app.command()
def status(series_id: Optional[str] = typer.Argument(None), limit: int = 30):
    """Episode list with status."""
    cfg = _cfg()
    t = Table("episode", "status", "title", "scheduled", "error")
    for ep in Episode.all(series_id, cfg)[-limit:]:
        m = ep.meta
        t.add_row(ep.ref, m.status, m.title[:40], m.scheduled_at or "", (m.error or "")[:50])
    console.print(t)


@app.command()
def show(episode: str):
    """Print an episode's script and QA report."""
    from .spec import QAReport, Script
    ep = Episode.find(episode, _cfg())
    if ep.has("script"):
        for l in ep.read("script", Script).lines:
            console.print(f"[dim]{l.id} {l.beat:<10}[/dim] [bold]{l.speaker}[/bold]: {l.text}")
    if ep.has("qa"):
        for c in ep.read("qa", QAReport).checks:
            colour = {"pass": "green", "warn": "yellow", "fail": "red", "skip": "dim"}[c.status]
            console.print(f"  [{colour}]{c.status:<4}[/{colour}] {c.name:<14} {c.detail}")


# ------------------------------------------------------------------ review / publish

@app.command()
def approve(episode: str, at: Optional[str] = typer.Option(None, help="ISO time; default next free slot"),
            now: bool = typer.Option(False, help="publish immediately")):
    """Approve an episode: schedule it (or publish now)."""
    from .publish import publish_episode, schedule
    ep = Episode.find(episode, _cfg())
    if now:
        console.print(publish_episode(ep))
        return
    slot = schedule(ep, datetime.fromisoformat(at) if at else None)
    console.print(f"{ep.ref} scheduled for {slot.isoformat()}")


@app.command()
def reject(episode: str, note: str = typer.Option("", help="why"),
           rerun: Optional[str] = typer.Option(None, help="re-run from this step after rejecting")):
    """Reject an episode (optionally regenerate from a step)."""
    from .cache import StepCache
    from .pipeline import run_episode
    ep = Episode.find(episode, _cfg())
    ep.update_meta(status="rejected", review_note=note)
    if rerun:
        StepCache(ep.dir).invalidate(rerun)
        run_episode(ep, start=rerun, force={rerun})


@app.command()
def publish(what: str = typer.Argument("due", help="'due' or an episode ref"),
            dry_run: bool = typer.Option(False)):
    """Publish due scheduled episodes (cron/launchd) or one episode now."""
    from .publish import publish_due, publish_episode
    if what == "due":
        for line in publish_due(_cfg(), dry_run):
            console.print(line)
    else:
        console.print(publish_episode(Episode.find(what, _cfg()), dry_run))


@app.command()
def analytics():
    """Pull insights for published reels and update formula stats."""
    from .analytics import pull
    for line in pull(_cfg()):
        console.print(line)
    cfg = _cfg()
    for sid in list_series(cfg):
        pri = db.formula_priors(sid, cfg)
        if pri:
            console.print(f"[bold]{sid}[/bold] formula priors: " +
                          ", ".join(f"{k}={v:+.2f}" for k, v in sorted(pri.items(), key=lambda x: -x[1])))


@app.command()
def dashboard(host: str = "127.0.0.1", port: int = 8765):
    """Local approve/reject dashboard."""
    import uvicorn
    console.print(f"dashboard: http://{host}:{port}")
    uvicorn.run("reels.dashboard.app:app", host=host, port=port, log_level="warning")


@app.command("install-scheduler")
def install_scheduler(interval_min: int = 15):
    """macOS: launchd job that runs `reels publish due` + `reels analytics` every N minutes."""
    exe = shutil.which("reels") or "reels"
    label = "com.doodlereels.publisher"
    plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
    log = ROOT / "state" / "scheduler.log"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>cd {ROOT} &amp;&amp; set -a &amp;&amp; [ -f .env ] &amp;&amp; source .env; set +a; {exe} publish due &amp;&amp; {exe} analytics</string>
  </array>
  <key>StartInterval</key><integer>{interval_min * 60}</integer>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
""")
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=False)
    console.print(f"installed {plist}")


# ------------------------------------------------------------------ utilities

@app.command()
def free():
    """Unload every model (Ollama + ComfyUI) from memory."""
    from .comfy.client import ComfyClient
    from .llm.ollama import unload_all
    cfg = _cfg()
    console.print(f"ollama unloaded: {unload_all(cfg.llm.draft.host)}")
    ComfyClient(cfg.comfy.host).free()


@app.command()
def doctor():
    """Check every dependency and model the current profile needs."""
    import httpx
    cfg = _cfg()
    rows: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = ""):
        rows.append((name, ok, detail))

    for tool in ("ffmpeg", "ffprobe", "node", "potrace"):
        check(tool, bool(shutil.which(tool)), shutil.which(tool) or "missing")
    check("remotion", (cfg.paths.p("remotion") / "node_modules/.bin/remotion").exists(), "npm install in remotion/")
    check("rhubarb (optional)", bool(shutil.which("rhubarb")), "brew install rhubarb-lip-sync")
    roles = {r: getattr(cfg.llm, r) for r in ("draft", "judge", "polish", "vision")}
    if any(lc.backend == "ollama" for lc in roles.values()):
        try:
            tags = {m["name"] for m in httpx.get(f"{cfg.llm.draft.host}/api/tags", timeout=3).json()["models"]}
            check("ollama", True, cfg.llm.draft.host)
            for r, lc in roles.items():
                if lc.backend == "ollama":
                    have = lc.model in tags or f"{lc.model}:latest" in tags
                    check(f"  model {lc.model} ({r})", have, "ok" if have else f"ollama pull {lc.model}")
        except Exception as e:  # noqa: BLE001
            check("ollama", False, str(e))
    if cfg.llm.polish.backend == "claude":
        from .llm.claude import ClaudeLLM
        check("claude polish", ClaudeLLM(cfg.llm.polish).available(), "pip install anthropic + ANTHROPIC_API_KEY")
    if cfg.comfy.enabled:
        from .comfy.client import ComfyClient
        check("comfyui", ComfyClient(cfg.comfy.host).alive(), cfg.comfy.host)
    import importlib.util
    eng = cfg.tts.default_engine
    mod = {"kokoro": "kokoro", "mlx-kokoro": "mlx_audio", "f5": "f5_tts_mlx"}.get(eng)
    if mod:
        check(f"tts {eng}", importlib.util.find_spec(mod) is not None, f"pip install {mod}")
    amod = {"mlx-whisper": "mlx_whisper", "faster-whisper": "faster_whisper"}.get(cfg.align.engine)
    if amod:
        check(f"align {cfg.align.engine}", importlib.util.find_spec(amod) is not None, f"pip install {amod}")
    for sid in list_series(cfg):
        s = load_series(sid, cfg)
        music = cfg.paths.p("library") / "music" / sid
        n = len(list(music.glob("*"))) if music.exists() else 0
        check(f"series {sid} music", n > 0, f"{n} tracks in {music}" if n else f"add tracks to {music} (procedural bed used)")
        rig = s.character.rig_path(cfg)
        check(f"series {sid} rig", rig.exists(), str(rig) if rig.exists() else "procedural character in use")
    t = Table("check", "ok", "detail", title=f"profile: {cfg.profile}")
    for n, ok, d in rows:
        t.add_row(n, "[green]✓[/green]" if ok else "[red]✗[/red]", d)
    console.print(t)


@app.command("studio-sample")
def studio_sample(episode: str):
    """Use an episode as the Remotion Studio default props (npm run studio)."""
    cfg = _cfg()
    ep = Episode.find(episode, cfg)
    rdir = cfg.paths.p("remotion")
    pub = rdir / "public"
    if pub.exists():
        shutil.rmtree(pub)
    shutil.copytree(ep.path("public"), pub)
    shutil.copy2(ep.path("timeline"), rdir / "src" / "sample.json")
    console.print("updated remotion/src/sample.json + remotion/public/")


# ------------------------------------------------------------------ characters

def _char(series_id: str, char: Optional[str]):
    from .characters import find_character
    cfg = _cfg()
    return cfg, find_character(load_series(series_id, cfg), char)


@char_app.command("design")
def c_design(series_id: str, char: Optional[str] = None, n: int = 8):
    """Generate design candidates from the description."""
    from .characters import design
    cfg, ch = _char(series_id, char)
    design(cfg, ch, n)


@char_app.command("dataset")
def c_dataset(series_id: str, char: Optional[str] = None, count: int = 30):
    """IPAdapter variations of reference.png + captions for LoRA training."""
    from .characters import dataset
    cfg, ch = _char(series_id, char)
    dataset(cfg, ch, count)


@char_app.command("train")
def c_train(series_id: str, char: Optional[str] = None, sd_scripts: str = "~/sd-scripts"):
    """Write the kohya LoRA training config + script."""
    from .characters import train_config
    cfg, ch = _char(series_id, char)
    console.print(f"run: {train_config(cfg, ch, sd_scripts)}")


@char_app.command("sheet")
def c_sheet(series_id: str, char: Optional[str] = None, candidates: int = 4, poses: str = ""):
    """Generate pose sheet candidates (uses the LoRA or reference)."""
    from .characters import sheet
    cfg, ch = _char(series_id, char)
    sheet(cfg, ch, candidates, poses.split(",") if poses else None)


@char_app.command("pick")
def c_pick(series_id: str, pose: str, candidate: Path, char: Optional[str] = None):
    """Use a candidate image for a pose (bg removed, added to rig.json)."""
    from .characters import pick
    cfg, ch = _char(series_id, char)
    console.print(pick(cfg, ch, pose, candidate))


@char_app.command("autorig")
def c_autorig(series_id: str, char: Optional[str] = None):
    """Locate mouth/eyes in each pose with the vision model."""
    from .characters import autorig
    cfg, ch = _char(series_id, char)
    console.print(autorig(cfg, ch))


if __name__ == "__main__":
    app()
