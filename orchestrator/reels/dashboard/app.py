"""Local review dashboard: watch renders, read QA, approve (schedule) or reject
(optionally regenerate from a step), and position mouth/eyes on character rigs."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .. import db
from ..cache import StepCache
from ..config import list_series, load_pipeline, load_series
from ..episode import Episode
from ..spec import EpisodeMeta, Idea, QAReport, Script

app = FastAPI(title="Doodle Reels")
STATIC = Path(__file__).parent / "static"
_jobs: dict[str, str] = {}


def _ep(series: str, eid: str) -> Episode:
    ep = Episode(series, eid, load_pipeline())
    if not ep.has("meta"):
        raise HTTPException(404, "episode not found")
    return ep


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text()


@app.get("/api/episodes")
def episodes(status: str = "") -> list[dict]:
    cfg = load_pipeline()
    wanted = set(filter(None, status.split(",")))
    out = []
    for ep in reversed(Episode.all(None, cfg)):
        m = ep.meta
        if wanted and m.status not in wanted:
            continue
        qa = ep.maybe("qa", QAReport)
        out.append({**m.model_dump(), "ref": ep.ref, "qa": qa.status if qa else None,
                    "has_video": ep.has("video"), "job": _jobs.get(ep.ref)})
    return out


@app.get("/api/episodes/{series}/{eid}")
def episode(series: str, eid: str) -> dict:
    ep = _ep(series, eid)
    return {"meta": ep.meta.model_dump(), "idea": ep.maybe("idea", Idea), "script": ep.maybe("script", Script),
            "qa": ep.maybe("qa", QAReport), "job": _jobs.get(ep.ref),
            "cache": json.loads((ep.dir / ".cache.json").read_text()) if (ep.dir / ".cache.json").exists() else {}}


@app.get("/media/{series}/{eid}/{kind}")
def media(series: str, eid: str, kind: str):
    ep = _ep(series, eid)
    path = {"video": ep.path("video"), "cover": ep.path("render/cover.png")}.get(kind)
    if not path or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


class Approve(BaseModel):
    at: str | None = None
    now: bool = False


@app.post("/api/episodes/{series}/{eid}/approve")
def approve(series: str, eid: str, body: Approve) -> EpisodeMeta:
    from ..publish import publish_episode, schedule
    ep = _ep(series, eid)
    if body.now:
        publish_episode(ep)
    else:
        schedule(ep, datetime.fromisoformat(body.at) if body.at else None)
    return ep.meta


class Reject(BaseModel):
    note: str = ""
    rerun: str | None = None


def _rerun(ep: Episode, start: str) -> None:
    from ..pipeline import run_episode
    _jobs[ep.ref] = f"running from {start}"
    try:
        run_episode(ep, start=start, force={start})
        _jobs[ep.ref] = "done"
    except Exception as e:  # noqa: BLE001
        _jobs[ep.ref] = f"failed: {e}"


@app.post("/api/episodes/{series}/{eid}/reject")
def reject(series: str, eid: str, body: Reject) -> EpisodeMeta:
    ep = _ep(series, eid)
    ep.update_meta(status="rejected", review_note=body.note)
    if body.rerun:
        StepCache(ep.dir).invalidate(body.rerun)
        threading.Thread(target=_rerun, args=(ep, body.rerun), daemon=True).start()
    return ep.meta


@app.post("/api/episodes/{series}/{eid}/unschedule")
def unschedule(series: str, eid: str) -> EpisodeMeta:
    ep = _ep(series, eid)
    ep.update_meta(status="review", scheduled_at=None)
    return ep.meta


@app.get("/api/stats")
def stats() -> dict:
    cfg = load_pipeline()
    return {sid: {"priors": db.formula_priors(sid, cfg), "top_hooks": db.top_hooks(sid, 10, cfg)}
            for sid in list_series(cfg)}


# ---------------------------------------------------------------- rig editor

@app.get("/api/characters")
def characters() -> list[dict]:
    cfg = load_pipeline()
    out = []
    for sid in list_series(cfg):
        for ch in load_series(sid, cfg).all_characters():
            rig = ch.rig_path(cfg)
            out.append({"series": sid, "id": ch.id, "name": ch.name,
                        "rig": json.loads(rig.read_text()) if rig.exists() else None})
    return out


@app.get("/characters/{cid}/{path:path}")
def char_file(cid: str, path: str):
    cfg = load_pipeline()
    root = (cfg.paths.p("characters") / cid).resolve()
    f = (root / path).resolve()
    if not str(f).startswith(str(root)) or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


@app.post("/api/characters/{cid}/rig")
def save_rig(cid: str, rig: dict) -> dict:
    cfg = load_pipeline()
    f = cfg.paths.p("characters") / cid / "rig.json"
    if not f.exists():
        raise HTTPException(404, "no rig yet: pick poses first")
    f.write_text(json.dumps(rig, indent=2))
    return {"ok": True}
