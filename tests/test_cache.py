from pathlib import Path

from reels.cache import AssetCache, StepCache


def test_step_cache(tmp_path: Path):
    c = StepCache(tmp_path)
    out = tmp_path / "x.json"
    k1 = c.key("script", "1", {"a": 1})
    assert k1 == c.key("script", "1", {"a": 1})
    assert k1 != c.key("script", "2", {"a": 1})
    assert not c.fresh("script", k1, [out])
    out.write_text("{}")
    c.store("script", k1, [out], 0.1)
    assert StepCache(tmp_path).fresh("script", k1, [out])
    c.invalidate("script")
    assert not StepCache(tmp_path).fresh("script", k1, [out])


def test_asset_cache(tmp_path: Path):
    ac = AssetCache(tmp_path / "ac")
    src = tmp_path / "a.png"
    src.write_bytes(b"png")
    k = ac.key("prop", "Gold Bars ", {"s": 1})
    assert k == ac.key("prop", "gold bars", {"s": 1})
    assert ac.get(k) is None
    ac.put(k, src, "prop", "gold bars")
    assert AssetCache(tmp_path / "ac").get(k).read_bytes() == b"png"
