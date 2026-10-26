from reels.spec import Idea, Line, Script, Storyboard
from reels.steps.base import Ctx
from reels.steps.script import draft, validate
from reels.steps.storyboard import coerce, sanitise


def test_validate_flags_structure(cfg, series):
    ctx = Ctx(cfg, series)
    s = Script(title="x", lines=[Line(id="l1", speaker="narrator", text="short", beat="setup")])
    problems = validate(s, ctx)
    assert any("missing beat 'hook'" in p for p in problems)
    assert any("too short" in p for p in problems)


def test_mock_draft_is_valid(cfg, series):
    ctx = Ctx(cfg, series)
    s = draft(Idea(title="t", hook="h", premise="p", formula_id="hypothetical_windfall"), ctx)
    assert validate(s, ctx) == []
    assert s.lines[0].beat == "hook" and s.lines[-1].beat == "loop"


def test_storyboard_sanitise_covers_every_line_and_clamps(cfg, series):
    ctx = Ctx(cfg, series)
    script = Script(title="t", lines=[Line(id=f"l{i}", speaker="narrator", text="word " * 5, beat=b)
                                      for i, b in enumerate(["hook", "setup", "twist", "payoff", "loop"], 1)])
    raw = Storyboard.model_validate(coerce({"scenes": [
        {"id": "a", "line_ids": ["l1", "l2"], "background": "spaceship", "camera": "dolly",
         "characters": [{"id": "nobody", "pose": "dab", "expression": "meh", "x": 2, "y": -1}],
         "props": [{"id": "x", "icon": "flux_capacitor", "y": 0.95}, {"id": "y"}]},
        {"id": "b", "line_ids": ["l4", "l99"]},
    ]}))
    sb = sanitise(raw, script, ctx)
    covered = [l for s in sb.scenes for l in s.line_ids]
    assert covered == ["l1", "l2", "l3", "l4", "l5"]
    s0 = sb.scenes[0]
    assert s0.background == "plain" and s0.camera == "static"
    assert s0.characters[0].id == series.character.id and s0.characters[0].pose == "neutral"
    assert 0.2 <= s0.characters[0].x <= 0.8
    assert s0.props[0].icon is None and s0.props[0].prompt == "flux capacitor"
    assert s0.props[0].y <= 0.42
    assert s0.props[1].icon == "question"


def test_storyboard_reuses_relative_and_excess_generated_backgrounds(cfg, series):
    ctx = Ctx(cfg, series)
    bgs = ["prompt:a white bathroom", "prompt:same room as before", "prompt:a lab", "prompt:a chart",
           "prompt:a beach", "prompt:same room as beginning"]
    script = Script(title="t", lines=[Line(id=f"l{i}", speaker="narrator", text="w", beat="setup")
                                      for i in range(1, len(bgs) + 1)])
    raw = Storyboard.model_validate(coerce({"scenes": [
        {"id": str(i), "line_ids": [f"l{i}"], "background": b} for i, b in enumerate(bgs, 1)]}))
    got = [s.background for s in sanitise(raw, script, ctx).scenes]
    assert got == ["prompt:a white bathroom", "prompt:a white bathroom", "prompt:a lab", "prompt:a chart",
                   "prompt:a chart", "prompt:a white bathroom"]


def test_storyboard_spreads_close_props_and_drops_fragment_text(cfg, series):
    ctx = Ctx(cfg, series)
    script = Script(title="t", lines=[Line(id="l1", speaker="narrator", text="w", beat="hook"),
                                      Line(id="l2", speaker="narrator", text="w", beat="setup")])
    raw = Storyboard.model_validate(coerce({"scenes": [
        {"id": "a", "line_ids": ["l1"], "on_screen_text": {"text": "A study shows people take an average of 6 seconds",
                                                           "style": "marker", "appear_word": 0, "color": "red"},
         "props": [{"id": "x", "icon": "document", "label": "study", "x": 0.5},
                   {"id": "y", "icon": "clock", "label": "clock3", "x": 0.6}]},
        {"id": "b", "line_ids": ["l2"], "on_screen_text": {"text": "20 seconds, not 4", "style": "marker",
                                                           "appear_word": 0, "color": "red"}},
    ]}))
    a, b = sanitise(raw, script, ctx).scenes
    xs = sorted(p.x for p in a.props)
    assert xs[1] - xs[0] >= 0.24 - 1e-9
    assert [p.label for p in a.props] == ["study", "clock"]
    assert a.on_screen_text is None
    assert b.on_screen_text.text == "20 seconds, not 4"
