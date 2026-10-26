from reels.align.visemes import rules_visemes, word_shapes
from reels.align.whisper import match_script


def test_word_shapes():
    assert word_shapes("map")[0] == "A"          # closed lips first
    assert "G" in word_shapes("five")
    assert word_shapes("") == ["B"]


def test_visemes_are_ordered_and_cover_words():
    words = [("Hello", 0.0, 0.4), ("there", 0.45, 0.8), ("money", 1.5, 2.0)]
    cues = rules_visemes(words, "vinnie")
    starts = [c["start"] for c in cues]
    assert starts == sorted(starts)
    assert any(c["shape"] == "X" and c["start"] >= 0.8 for c in cues)    # rest during the gap
    assert cues[-1]["shape"] == "X"
    assert all(c["speaker"] == "vinnie" for c in cues)


def test_match_script_keeps_script_text_and_interpolates():
    script = ["If", "you", "had", "$20M,", "what?"]
    heard = [{"word": "If", "start": 0.0, "end": 0.1}, {"word": "you", "start": 0.12, "end": 0.2},
             {"word": "had", "start": 0.22, "end": 0.35},
             {"word": "what", "start": 1.2, "end": 1.5}]
    out = match_script(script, heard, 1.6)
    assert [o[0] for o in out] == script
    assert out[3][1] >= 0.35 and out[3][2] <= 1.2        # interpolated between neighbours
    assert out[4][1] == 1.2
