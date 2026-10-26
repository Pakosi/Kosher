from types import SimpleNamespace as NS

from reels.steps.qa import settled_time


def _tl():
    scene = NS(start=15.67, end=18.35, props=[NS(at=15.79), NS(at=16.79)], text=NS(at=16.79))
    return NS(scenes=[NS(start=0.0, end=15.67, props=[], text=None), scene])


def test_settled_time_skips_entrance_animations():
    tl = _tl()
    assert settled_time(17.1, tl) == 16.79 + 0.8      # mid slide-in / text reveal -> after it lands
    assert settled_time(10.0, tl) == 10.0             # nothing animating -> unchanged


def test_settled_time_keeps_time_when_scene_too_short():
    tl = NS(scenes=[NS(start=0.0, end=0.5, props=[], text=None)])
    assert settled_time(0.25, tl) == 0.25
