from reels.text import find_banned, number_to_words, similarity, speakable, syllables, wer


def test_numbers_and_money():
    assert number_to_words(20_000_000) == "twenty million"
    assert number_to_words(9000) == "nine thousand"
    assert number_to_words(1234) == "one thousand two hundred thirty four"
    assert speakable("$20M in cash") == "twenty million dollars in cash"
    assert speakable("Deposit $9,000 now") == "Deposit nine thousand dollars now"
    assert "percent" in speakable("40% of it")
    assert speakable("$5 million") == "five million dollars"
    assert speakable("2.5 times") == "two point five times"


def test_wer_and_similarity():
    assert wer("the cat sat", "the cat sat") == 0
    assert abs(wer("the cat sat", "the dog sat") - 1 / 3) < 1e-9
    assert similarity("If you had 20 million", "if you had 20 million!") > 0.9
    assert similarity("banks report deposits", "pizza recipes are fun") < 0.2


def test_banned_and_syllables():
    assert find_banned("This is a foolproof plan", ["foolproof", "untraceable"]) == ["foolproof"]
    assert find_banned("totally fine", ["foolproof"]) == []
    assert syllables("laundromat") == 3
    assert syllables("cash") == 1
