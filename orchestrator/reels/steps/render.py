"""Render: Remotion CLI -> raw.mp4, then two-pass loudness normalisation to the
IG target (-14 LUFS, -1 dBTP) -> final.mp4, plus a cover still."""

from __future__ import annotations

import shutil
import subprocess

from ..audio_utils import loudnorm_video
from ..cache import hash_file, hash_tree
from ..episode import Episode
from ..spec import Timeline
from .base import Ctx, Step, StepError, console, register


def _remotion_cmd(ctx: Ctx) -> list[str]:
    rdir = ctx.cfg.paths.p("remotion")
    local = rdir / "node_modules" / ".bin" / "remotion"
    if local.exists():
        return [str(local)]
    if shutil.which("npx"):
        return ["npx", "--no-install", "remotion"]
    raise StepError("Remotion not installed: run `npm install` in remotion/")


def _browser_flags(ctx: Ctx) -> list[str]:
    rc = ctx.cfg.render
    out = []
    if rc.gl:
        out.append(f"--gl={rc.gl}")
    if rc.browser_executable:
        out.append(f"--browser-executable={rc.browser_executable}")
    return out


def render_video(ep: Episode, ctx: Ctx, out_name: str = "raw.mp4", extra: list[str] | None = None) -> None:
    rc = ctx.cfg.render
    rdir = ctx.cfg.paths.p("remotion")
    out = ep.path(f"render/{out_name}")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [*_remotion_cmd(ctx), "render", "src/index.ts", "Reel", str(out),
           f"--props={ep.path('timeline')}", f"--public-dir={ep.path('public')}",
           f"--concurrency={rc.concurrency}", f"--crf={rc.crf}", f"--codec={rc.codec}",
           "--audio-codec=aac", "--log=warn", *(extra or [])]
    cmd += _browser_flags(ctx)
    p = subprocess.run(cmd, cwd=rdir, capture_output=True, text=True)
    if p.returncode != 0:
        raise StepError(f"remotion render failed:\n{p.stdout[-2000:]}\n{p.stderr[-3000:]}")


def render_still(ep: Episode, ctx: Ctx, frame: int) -> None:
    rdir = ctx.cfg.paths.p("remotion")
    cmd = [*_remotion_cmd(ctx), "still", "src/index.ts", "Reel", str(ep.path("render/cover.png")),
           f"--props={ep.path('timeline')}", f"--public-dir={ep.path('public')}", f"--frame={frame}", "--log=warn", *_browser_flags(ctx)]
    p = subprocess.run(cmd, cwd=rdir, capture_output=True, text=True)
    if p.returncode != 0:
        console.print(f"    [yellow]cover still failed: {p.stderr[-500:]}[/yellow]")


def _run(ep: Episode, ctx: Ctx) -> None:
    tl = ep.read("timeline", Timeline)
    render_video(ep, ctx)
    loudnorm_video(ep.path("video_raw"), ep.path("video"), ctx.cfg.audio.target_lufs, ctx.cfg.audio.true_peak)
    # cover: the frame where the hook's on-screen text is fully in
    first = tl.scenes[0]
    t = (first.text.at + 0.8) if first.text else min(1.5, tl.durationInFrames / tl.fps / 2)
    render_still(ep, ctx, min(int(t * tl.fps), tl.durationInFrames - 1))


register(Step(
    name="render", version="3", status_after="rendered", description="Remotion render + loudnorm",
    outputs=lambda ep: [ep.path("video")],
    inputs=lambda ep, ctx: {"tl": hash_file(ep.path("timeline")),
                            "pub": sorted(str(p.relative_to(ep.path("public"))) + ":" + str(p.stat().st_size)
                                          for p in ep.path("public").rglob("*") if p.is_file()),
                            "render": ctx.cfg.render.model_dump(), "audio": ctx.cfg.audio.model_dump(),
                            "code": hash_tree(ctx.cfg.paths.p("remotion") / "src")},
    run=_run,
))
