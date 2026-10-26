import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))
os.environ.setdefault("REELS_PROFILE", "test")


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Test-profile config with all mutable state redirected into tmp_path."""
    from reels import config as config_mod
    from reels.steps import base, load_all

    load_all()

    config_mod.load_pipeline.cache_clear()
    c = config_mod.load_pipeline("test")
    c.paths.episodes = str(tmp_path / "episodes")
    c.paths.state = str(tmp_path / "state")
    c.paths.assets_cache = str(tmp_path / "assets_cache")
    c.paths.characters = str(tmp_path / "characters")
    c.paths.library = str(tmp_path / "library")
    c.paths.series = str(REPO / "config" / "series")
    c.paths.remotion = str(REPO / "remotion")
    # child processes would reload config from disk; run in-process for tests
    for step in base.REGISTRY.values():
        monkeypatch.setattr(step, "isolate", False)
    monkeypatch.setattr(config_mod, "load_pipeline", lambda profile=None: c)
    return c


@pytest.fixture
def series(cfg):
    from reels.config import load_series
    return load_series("dirty-money", cfg)
