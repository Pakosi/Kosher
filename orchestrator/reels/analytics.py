"""Analytics feedback loop: pull Reel insights, compute an engagement score, and
once a reel has matured (48h) feed it into per-formula stats that bias future
hook generation and idea ranking."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

from . import db
from .config import PipelineConfig, load_pipeline, load_series
from .episode import Episode
from .publish import Graph, PublishError, credentials
from .spec import AudioManifest

MATURE_AFTER = timedelta(hours=48)


def engagement_score(m: dict[str, float], duration: float) -> float:
    """Retention-weighted score, roughly 0..3. Watch-time share dominates because
    it drives distribution; shares and saves signal value; raw reach is log-damped."""
    views = m.get("views") or m.get("plays") or 0.0
    reach = max(m.get("reach", views), 1.0)
    awt = (m.get("ig_reels_avg_watch_time", 0.0) or 0.0) / 1000.0     # API returns ms
    retention = min(awt / max(duration, 1.0), 1.5)
    share_rate = m.get("shares", 0.0) / reach
    save_rate = m.get("saved", 0.0) / reach
    comment_rate = m.get("comments", 0.0) / reach
    return round(1.2 * retention + 0.25 * math.log1p(1000 * share_rate) + 0.15 * math.log1p(1000 * save_rate)
                 + 0.1 * math.log1p(1000 * comment_rate) + 0.08 * math.log10(max(views, 1.0)), 4)


def pull(cfg: PipelineConfig | None = None) -> list[str]:
    cfg = cfg or load_pipeline()
    lines = []
    for row in db.episodes_by_status(["published"], cfg):
        ep = Episode(row["series"], row["id"], cfg)
        meta = ep.meta
        if not meta.media_id:
            continue
        series = load_series(ep.series, cfg)
        try:
            _, tok = credentials(series)
            metrics = Graph(cfg, tok).insights(meta.media_id, cfg.publish.insights_metrics)
        except PublishError as e:
            lines.append(f"{ep.ref}: {e}")
            continue
        dur = ep.read("audio", AudioManifest).duration if ep.has("audio") else 45.0
        score = engagement_score(metrics, dur)
        db.save_metrics(ep.ref, meta.media_id, metrics, score, cfg)
        state_f = ep.path("analytics.json")
        state = json.loads(state_f.read_text()) if state_f.exists() else {}
        published = datetime.fromisoformat(state.get("published_at") or meta.updated_at)
        if not state.get("recorded") and datetime.now(timezone.utc) - published >= MATURE_AFTER and meta.formula_id:
            db.record_formula_score(ep.series, meta.formula_id, score, cfg)
            state["recorded"] = True
        state.update({"last": metrics, "score": score, "at": datetime.now(timezone.utc).isoformat()})
        state_f.write_text(json.dumps(state, indent=2))
        lines.append(f"{ep.ref}: score {score:.3f} {metrics}")
    return lines
