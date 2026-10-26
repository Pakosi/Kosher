"""Small text utilities shared by ideas, QA and alignment."""

from __future__ import annotations

import re

_NUM_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
    19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
    70: "seventy", 80: "eighty", 90: "ninety",
}


def number_to_words(n: int) -> str:
    if n < 0:
        return "minus " + number_to_words(-n)
    if n in _NUM_WORDS:
        return _NUM_WORDS[n]
    if n < 100:
        return f"{_NUM_WORDS[n // 10 * 10]} {_NUM_WORDS[n % 10]}"
    for unit, word in ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand"), (100, "hundred")):
        if n >= unit:
            head, rest = divmod(n, unit)
            return f"{number_to_words(head)} {word}" + (f" {number_to_words(rest)}" if rest else "")
    return str(n)


def speakable(text: str) -> str:
    """Normalise text for TTS: $20M -> twenty million dollars, 9,000 -> nine thousand, % -> percent."""
    def money(m: re.Match) -> str:
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "thousand": 1e3, "million": 1e6,
                "billion": 1e9, "trillion": 1e12}.get(unit, 1)
        return f"{number_to_words(int(round(num * mult)))} dollars"
    text = re.sub(r"\$([\d,]+(?:\.\d+)?)(?:\s?(k|m|b|t|thousand|million|billion|trillion)\b)?", money, text,
                  flags=re.I)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: f"{m.group(1)} percent", text)
    text = re.sub(r"\b(\d+)\.(\d+)\b", lambda m: f"{number_to_words(int(m.group(1)))} point "
                  + " ".join(number_to_words(int(d)) for d in m.group(2)), text)
    text = re.sub(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b",
                  lambda m: number_to_words(int(m.group(0).replace(",", ""))), text)
    return text.replace("&", " and ")


def shorten(text: str, limit: int) -> str:
    """Trim to at most `limit` chars on a word boundary (never leaves half a word on screen)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    out = ""
    for w in text.split(" "):
        if len(out) + len(w) + (1 if out else 0) > limit:
            break
        out = f"{out} {w}" if out else w
    return out.rstrip(",;:-–—") or text[:limit]


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def trigrams(text: str) -> set[str]:
    t = " ".join(words(text))
    return {t[i:i + 3] for i in range(max(len(t) - 2, 0))}


def similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    if not r:
        return 0.0 if not h else 1.0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / len(r)


def find_banned(text: str, banned: list[str]) -> list[str]:
    low = " " + " ".join(words(text)) + " "
    return [b for b in banned if f" {' '.join(words(b))} " in low]


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee")):
        n -= 1
    return max(n, 1)
