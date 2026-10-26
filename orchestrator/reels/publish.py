"""Instagram publishing via the Meta Graph API (Instagram API with Facebook/
Instagram Login, content publishing). Reels are uploaded with the resumable
upload flow so no public video URL is needed.

Per series: env vars named in series.publish.ig_user_id_env / token_env hold the
IG professional account id and a long-lived access token with
instagram_content_publish (+ instagram_manage_insights for analytics)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from . import db
from .config import PipelineConfig, SeriesConfig, load_pipeline, load_series
from .episode import Episode
from .spec import Script, Timeline


class PublishError(RuntimeError):
    pass


class Graph:
    def __init__(self, cfg: PipelineConfig, token: str):
        self.pc = cfg.publish
        self.token = token
        self.base = f"{self.pc.graph_host}/{self.pc.graph_version}"
        self.http = httpx.Client(timeout=120)

    def _check(self, r: httpx.Response) -> dict:
        try:
            data = r.json()
        except ValueError:
            raise PublishError(f"HTTP {r.status_code}: {r.text[:300]}")
        if r.status_code >= 400 or "error" in data:
            raise PublishError(f"Graph error {r.status_code}: {data.get('error', data)}")
        return data

    def create_reel_container(self, ig_user: str, caption: str, thumb_offset_ms: int = 0) -> str:
        r = self.http.post(f"{self.base}/{ig_user}/media", data={
            "media_type": "REELS", "upload_type": "resumable", "caption": caption,
            "share_to_feed": "true", "thumb_offset": str(thumb_offset_ms), "access_token": self.token})
        return self._check(r)["id"]

    def upload(self, container_id: str, video: Path) -> None:
        size = video.stat().st_size
        r = self.http.post(f"{self.pc.upload_host}/ig-api-upload/{self.pc.graph_version}/{container_id}",
                           headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)},
                           content=video.read_bytes(), timeout=600)
        data = self._check(r)
        if not data.get("success", True):
            raise PublishError(f"upload failed: {data}")

    def wait_ready(self, container_id: str) -> None:
        t0 = time.time()
        while time.time() - t0 < self.pc.poll_timeout:
            d = self._check(self.http.get(f"{self.base}/{container_id}",
                                          params={"fields": "status_code,status", "access_token": self.token}))
            code = d.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise PublishError(f"container {code}: {d.get('status')}")
            time.sleep(self.pc.poll_seconds)
        raise PublishError("timed out waiting for media processing")

    def publish(self, ig_user: str, container_id: str) -> str:
        r = self.http.post(f"{self.base}/{ig_user}/media_publish",
                           data={"creation_id": container_id, "access_token": self.token})
        return self._check(r)["id"]

    def permalink(self, media_id: str) -> str | None:
        d = self._check(self.http.get(f"{self.base}/{media_id}", params={"fields": "permalink", "access_token": self.token}))
        return d.get("permalink")

    def insights(self, media_id: str, metrics: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        # request metrics one by one-ish: unsupported metric names fail the whole call
        r = self.http.get(f"{self.base}/{media_id}/insights",
                          params={"metric": ",".join(metrics), "access_token": self.token})
        if r.status_code >= 400:
            for m in metrics:
                rr = self.http.get(f"{self.base}/{media_id}/insights", params={"metric": m, "access_token": self.token})
                if rr.status_code < 400:
                    out.update(_parse_insights(rr.json()))
            return out
        return _parse_insights(r.json())


def _parse_insights(data: dict) -> dict[str, float]:
    out = {}
    for item in data.get("data", []):
        vals = item.get("values") or [{}]
        v = vals[0].get("value", item.get("total_value", {}).get("value"))
        if isinstance(v, (int, float)):
            out[item["name"]] = float(v)
    return out


def credentials(series: SeriesConfig) -> tuple[str, str]:
    ig = os.environ.get(series.publish.ig_user_id_env or "", "")
    tok = os.environ.get(series.publish.token_env or "", "")
    if not ig or not tok:
        raise PublishError(f"set {series.publish.ig_user_id_env} and {series.publish.token_env} (see README: publishing)")
    return ig, tok


def build_caption(ep: Episode, series: SeriesConfig) -> str:
    script = ep.read("script", Script)
    tags = list(dict.fromkeys([*script.hashtags, *series.publish.hashtags]))[:12]
    return series.publish.caption_template.format(
        title=script.caption or script.title, cta=series.publish.cta,
        hashtags=" ".join(f"#{t.lstrip('#')}" for t in tags)).strip()


def next_slot(series: SeriesConfig, cfg: PipelineConfig, after: datetime | None = None) -> datetime:
    tz = ZoneInfo(series.publish.timezone)
    now = (after or datetime.now(tz)).astimezone(tz)
    taken = {r["scheduled_at"] for r in db.episodes_by_status(["scheduled", "published"], cfg)
             if r["series"] == series.id and r["scheduled_at"]}
    for day in range(0, 60):
        d = (now + timedelta(days=day)).date()
        for hhmm in sorted(series.publish.post_times):
            h, m = map(int, hhmm.split(":"))
            slot = datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
            if slot > now + timedelta(minutes=10) and slot.isoformat() not in taken:
                return slot
    raise PublishError("no free slot in the next 60 days")


def schedule(ep: Episode, when: datetime | None = None) -> datetime:
    series = load_series(ep.series, ep.cfg)
    slot = when or next_slot(series, ep.cfg)
    ep.update_meta(status="scheduled", scheduled_at=slot.isoformat())
    return slot


def publish_episode(ep: Episode, dry_run: bool = False) -> str:
    series = load_series(ep.series, ep.cfg)
    video = ep.path("video")
    if not video.exists():
        raise PublishError("no rendered video")
    caption = build_caption(ep, series)
    tl = ep.read("timeline", Timeline)
    first = tl.scenes[0]
    thumb_ms = int(((first.text.at + 0.8) if first.text else 1.5) * 1000)
    if dry_run:
        return f"[dry-run] would publish {video} with caption:\n{caption}"
    ig, tok = credentials(series)
    g = Graph(ep.cfg, tok)
    cid = g.create_reel_container(ig, caption, thumb_ms)
    g.upload(cid, video)
    g.wait_ready(cid)
    media_id = g.publish(ig, cid)
    link = None
    try:
        link = g.permalink(media_id)
    except PublishError:
        pass
    ep.update_meta(status="published", media_id=media_id, permalink=link)
    ep.path("analytics.json").write_text(json.dumps({"published_at": datetime.now(timezone.utc).isoformat()}))
    ep.log(f"published media {media_id} {link}")
    return media_id


def publish_due(cfg: PipelineConfig | None = None, dry_run: bool = False) -> list[str]:
    cfg = cfg or load_pipeline()
    done = []
    now = datetime.now().astimezone()
    for row in db.episodes_by_status(["scheduled"], cfg):
        if row["scheduled_at"] and datetime.fromisoformat(row["scheduled_at"]) <= now:
            ep = Episode(row["series"], row["id"], cfg)
            try:
                done.append(f"{ep.ref}: {publish_episode(ep, dry_run)}")
            except PublishError as e:
                ep.update_meta(error=f"publish: {e}")
                done.append(f"{ep.ref}: FAILED {e}")
    return done
