"""SQLite state: episode index, publish queue, hook history and analytics-driven
formula stats. The episode folders stay the source of truth for content."""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import PipelineConfig, load_pipeline
from .spec import EpisodeMeta, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
  ref TEXT PRIMARY KEY, id TEXT, series TEXT, status TEXT, title TEXT, formula_id TEXT,
  created_at TEXT, updated_at TEXT, scheduled_at TEXT, media_id TEXT, permalink TEXT
);
CREATE TABLE IF NOT EXISTS hooks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, series TEXT, hook TEXT, title TEXT,
  formula_id TEXT, episode_ref TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, episode_ref TEXT, media_id TEXT,
  fetched_at TEXT, data TEXT, score REAL
);
CREATE TABLE IF NOT EXISTS formula_stats (
  series TEXT, formula_id TEXT, n INTEGER, mean REAL, m2 REAL, updated_at TEXT,
  PRIMARY KEY (series, formula_id)
);
"""


def db_path(cfg: PipelineConfig) -> Path:
    p = cfg.paths.p("state")
    p.mkdir(parents=True, exist_ok=True)
    return p / "reels.db"


@contextmanager
def connect(cfg: PipelineConfig | None = None) -> Iterator[sqlite3.Connection]:
    cfg = cfg or load_pipeline()
    con = sqlite3.connect(db_path(cfg))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert_episode(m: EpisodeMeta, cfg: PipelineConfig | None = None) -> None:
    with connect(cfg) as con:
        con.execute(
            """INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(ref) DO UPDATE SET status=excluded.status, title=excluded.title,
               formula_id=excluded.formula_id, updated_at=excluded.updated_at,
               scheduled_at=excluded.scheduled_at, media_id=excluded.media_id,
               permalink=excluded.permalink""",
            (f"{m.series}/{m.id}", m.id, m.series, m.status, m.title, m.formula_id,
             m.created_at, m.updated_at, m.scheduled_at, m.media_id, m.permalink))


def episodes_by_status(statuses: list[str], cfg: PipelineConfig | None = None) -> list[sqlite3.Row]:
    q = ",".join("?" * len(statuses))
    with connect(cfg) as con:
        return con.execute(f"SELECT * FROM episodes WHERE status IN ({q}) ORDER BY created_at",
                           statuses).fetchall()


def add_hook(series: str, hook: str, title: str, formula_id: str, ref: str,
             cfg: PipelineConfig | None = None) -> None:
    with connect(cfg) as con:
        con.execute("INSERT INTO hooks (series,hook,title,formula_id,episode_ref,created_at) VALUES (?,?,?,?,?,?)",
                    (series, hook, title, formula_id, ref, now_iso()))


def past_hooks(series: str, limit: int = 300, cfg: PipelineConfig | None = None) -> list[str]:
    with connect(cfg) as con:
        rows = con.execute("SELECT hook, title FROM hooks WHERE series=? ORDER BY id DESC LIMIT ?",
                           (series, limit)).fetchall()
    return [f"{r['title']} | {r['hook']}" for r in rows]


# ----------------------------------------------------------- formula stats (Welford)

def record_formula_score(series: str, formula_id: str, score: float,
                         cfg: PipelineConfig | None = None) -> None:
    with connect(cfg) as con:
        row = con.execute("SELECT n, mean, m2 FROM formula_stats WHERE series=? AND formula_id=?",
                          (series, formula_id)).fetchone()
        n, mean, m2 = (row["n"], row["mean"], row["m2"]) if row else (0, 0.0, 0.0)
        n += 1
        d = score - mean
        mean += d / n
        m2 += d * (score - mean)
        con.execute("""INSERT INTO formula_stats VALUES (?,?,?,?,?,?)
                       ON CONFLICT(series, formula_id) DO UPDATE SET n=excluded.n, mean=excluded.mean,
                       m2=excluded.m2, updated_at=excluded.updated_at""",
                    (series, formula_id, n, mean, m2, now_iso()))


def formula_priors(series: str, cfg: PipelineConfig | None = None) -> dict[str, float]:
    """Shrunk mean performance per formula, centred on 0. Positive = beats the
    series average. Shrinkage k=3 keeps one lucky reel from dominating."""
    with connect(cfg) as con:
        rows = con.execute("SELECT formula_id, n, mean FROM formula_stats WHERE series=?", (series,)).fetchall()
    if not rows:
        return {}
    total_n = sum(r["n"] for r in rows)
    grand = sum(r["mean"] * r["n"] for r in rows) / max(total_n, 1)
    k = 3.0
    return {r["formula_id"]: (r["n"] / (r["n"] + k)) * (r["mean"] - grand) for r in rows}


def top_hooks(series: str, limit: int = 5, cfg: PipelineConfig | None = None) -> list[tuple[str, float]]:
    with connect(cfg) as con:
        rows = con.execute(
            """SELECT h.hook, MAX(m.score) AS s FROM metrics m JOIN hooks h ON h.episode_ref = m.episode_ref
               WHERE h.series=? GROUP BY h.hook ORDER BY s DESC LIMIT ?""", (series, limit)).fetchall()
    return [(r["hook"], r["s"]) for r in rows if r["s"] is not None and not math.isnan(r["s"])]


def save_metrics(ref: str, media_id: str, data: dict, score: float,
                 cfg: PipelineConfig | None = None) -> None:
    with connect(cfg) as con:
        con.execute("INSERT INTO metrics (episode_ref, media_id, fetched_at, data, score) VALUES (?,?,?,?,?)",
                    (ref, media_id, now_iso(), json.dumps(data), score))
