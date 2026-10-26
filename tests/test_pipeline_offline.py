"""End-to-end through the timeline step with the offline test profile (no render)."""

import shutil

import pytest

from reels.spec import Alignment, AudioManifest, Timeline


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_episode_to_timeline(cfg, series):
    from reels.pipeline import new_episode, run_episode
    ep = new_episode(series, cfg)
    status = run_episode(ep, cfg, stop="timeline")
    assert status == "timeline"
    audio = ep.read("audio", AudioManifest)
    al = ep.read("align", Alignment)
    assert audio.duration > 10 and al.words and al.visemes
    tl = ep.read("timeline", Timeline)
    assert tl.durationInFrames == pytest.approx(audio.duration * 30, abs=1)
    assert tl.scenes[0].start == 0 and tl.scenes[-1].end == pytest.approx(audio.duration)
    assert all(a.end >= a.start for a in tl.scenes)
    assert (ep.path("public") / tl.narration).exists()
    assert tl.music and (ep.path("public") / tl.music.src).exists()
    for s in tl.sfx:
        assert (ep.path("public") / s.src).exists()
    # rerun is fully cached
    from reels.cache import StepCache
    before = StepCache(ep.dir).data["tts"]["at"]
    run_episode(ep, cfg, stop="timeline")
    assert StepCache(ep.dir).data["tts"]["at"] == before
