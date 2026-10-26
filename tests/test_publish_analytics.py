from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from reels import db
from reels.analytics import engagement_score
from reels.publish import Graph, next_slot


def test_graph_resumable_flow(cfg, tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 2048)
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.host, req.url.path))
        if req.url.path.endswith("/media") and req.method == "POST":
            body = req.content.decode()
            assert "media_type=REELS" in body and "upload_type=resumable" in body
            return httpx.Response(200, json={"id": "C1"})
        if req.url.host == "rupload.facebook.com":
            assert req.headers["file_size"] == "2048" and req.headers["Authorization"].startswith("OAuth ")
            return httpx.Response(200, json={"success": True})
        if req.url.path.endswith("/C1"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if req.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "M1"})
        return httpx.Response(404, json={"error": "nope"})

    g = Graph(cfg, "tok")
    g.http = httpx.Client(transport=httpx.MockTransport(handler))
    cid = g.create_reel_container("IG1", "caption", 1500)
    g.upload(cid, video)
    g.wait_ready(cid)
    assert g.publish("IG1", cid) == "M1"
    assert [s[2].split("/")[-1] for s in seen] == ["media", "C1", "C1", "media_publish"]


def test_next_slot_skips_taken(cfg, series):
    tz = ZoneInfo(series.publish.timezone)
    after = datetime(2026, 1, 5, 9, 0, tzinfo=tz)
    s1 = next_slot(series, cfg, after)
    assert s1.hour == 12 and s1.minute == 30
    from reels.spec import EpisodeMeta
    db.upsert_episode(EpisodeMeta(id="e1", series=series.id, status="scheduled", scheduled_at=s1.isoformat()), cfg)
    s2 = next_slot(series, cfg, after)
    assert s2.hour == 19


def test_engagement_and_priors(cfg):
    weak = engagement_score({"views": 1000, "reach": 900, "ig_reels_avg_watch_time": 8000, "shares": 2}, 45)
    strong = engagement_score({"views": 1000, "reach": 900, "ig_reels_avg_watch_time": 30000, "shares": 40, "saved": 30}, 45)
    assert strong > weak
    for s in (2.0, 2.2, 1.9):
        db.record_formula_score("dirty-money", "villain_pov", s, cfg)
    db.record_formula_score("dirty-money", "rank_it", 0.5, cfg)
    pri = db.formula_priors("dirty-money", cfg)
    assert pri["villain_pov"] > 0 > pri["rank_it"]
