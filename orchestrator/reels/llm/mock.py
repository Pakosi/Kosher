"""Deterministic offline LLM used by the `test` profile and unit tests. It returns
schema-valid, plausible content so every downstream step (TTS, render, QA) can
run without any model installed."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..config import LLMConfig

_SCRIPT = [
    ("hook", "narrator", "If you had twenty million dollars in dirty cash, how would you clean it?", "serious", ["twenty", "million", "dirty"]),
    ("setup", "{char}", "Easy. I just walk into a bank and deposit it.", "smug", ["bank"]),
    ("setup", "narrator", "Any cash deposit over ten thousand dollars gets reported to the government. Automatically.", "neutral", ["reported"]),
    ("escalation", "{char}", "Fine. I split it into tiny deposits. Nine thousand at a time.", "excited", ["tiny"]),
    ("escalation", "narrator", "That's called structuring. Banks have software that flags that exact pattern. And it's a crime on its own.", "serious", ["structuring", "crime"]),
    ("escalation", "{char}", "Okay, okay. I buy a laundromat and say customers paid in cash.", "smug", ["laundromat"]),
    ("twist", "narrator", "Here's the problem. A laundromat with four machines can't make twenty million dollars. Investigators just count the quarters.", "excited", ["count", "quarters"]),
    ("payoff", "narrator", "Almost every big case falls apart the same way. The money is bigger than the story that explains it.", "serious", ["bigger", "story"]),
    ("loop", "{char}", "So what do I do with twenty million dollars in dirty cash?", "shocked", ["twenty", "million"]),
]


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


class MockLLM:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def unload(self) -> None:
        pass

    def complete_json(self, task: str, system: str, prompt: str, schema: dict,
                      images: list[str] | None = None) -> Any:
        char = (re.search(r"CHARACTER_ID:\s*([\w-]+)", prompt) or [None, "hero"])[1]
        formulas = re.findall(r"FORMULA:\s*([\w-]+)", prompt) or ["hypothetical_windfall"]
        if task == "ideas":
            n = int((re.search(r"Generate (\d+)", prompt) or [None, 10])[1])
            return {"ideas": [{
                "title": f"Dirty money myth #{i + 1}",
                "hook": ["If you had twenty million dollars in dirty cash, how would you clean it?",
                         "He laundered millions perfectly. Then he bought a yacht.",
                         "Nobody asks where seized cash actually goes.",
                         "Banks have a secret alarm for cash deposits."][i % 4],
                "premise": "Walk through the naive plan, show why each step gets caught, end on the real lesson.",
                "formula_id": formulas[i % len(formulas)],
                "topic": "money laundering myths",
                "payoff": "The money is always bigger than the story that explains it.",
            } for i in range(n)]}
        if task == "judge":
            ids = re.findall(r"\[(\d+)\]", prompt)
            return {"scores": [{
                "index": int(i),
                "hook_strength": 5 + _seed(i + "h") % 5, "curiosity_gap": 5 + _seed(i + "c") % 5,
                "specificity": 4 + _seed(i + "s") % 6, "payoff_potential": 5 + _seed(i + "p") % 5,
                "series_fit": 6 + _seed(i + "f") % 4, "visual_potential": 5 + _seed(i + "v") % 5,
                "risk": _seed(i + "r") % 3, "reason": "mock score",
            } for i in ids]}
        if task in ("script", "polish"):
            return {
                "title": "How would you clean $20M?",
                "lines": [{"id": f"l{i + 1}", "speaker": sp.replace("{char}", char), "text": tx,
                           "beat": beat, "emotion": emo, "emphasis": em}
                          for i, (beat, sp, tx, emo, em) in enumerate(_SCRIPT)],
                "loop_note": "Final question is the hook again.",
                "caption": "Every laundering plan dies the same way. Would yours?",
                "hashtags": ["moneyfacts", "truecrime", "doodle"],
            }
        if task == "storyboard":
            lines = re.findall(r"^(l\d+)\s*\[", prompt, flags=re.M) or [f"l{i + 1}" for i in range(len(_SCRIPT))]
            plan = [
                ("plain", ["icon:money_stack"], "push_in", "$20,000,000", "stamp", ["whoosh"]),
                ("bank", ["icon:bank"], "pan_right", None, None, ["pop"]),
                ("bank", ["icon:document", "icon:alarm"], "static", "> $10,000 = REPORTED", "banner", ["alarm"]),
                ("grid", ["icon:coin", "icon:coin", "icon:coin"], "pull_out", "$9,000 x 2,222", "marker", ["pop"]),
                ("grid", ["icon:laptop", "icon:police"], "shake", "STRUCTURING", "stamp", ["record_scratch"]),
                ("city", ["icon:washing_machine"], "push_in", None, None, ["ding"]),
                ("plain", ["icon:magnifier", "icon:coin"], "whip_zoom", "4 MACHINES ≠ $20M", "marker", ["boom"]),
                ("dots", ["icon:scale"], "static", None, None, ["whoosh"]),
                ("plain", ["icon:money_stack", "icon:question"], "push_in", "?", "stamp", ["pop"]),
            ]
            scenes = []
            for i, lid in enumerate(lines):
                bg, props, cam, txt, style, sfx = plan[i % len(plan)]
                scenes.append({
                    "id": f"s{i + 1}", "line_ids": [lid], "background": bg,
                    "characters": [{"id": char, "pose": ["neutral", "smug", "think", "point", "shock"][i % 5],
                                    "expression": ["neutral", "smug", "worried", "excited", "shocked"][i % 5],
                                    "x": 0.3 if i % 2 else 0.7, "y": 0.9, "scale": 1.0, "flip": bool(i % 2),
                                    "enter": "pop" if i == 0 else "none"}],
                    "props": [{"id": f"p{j + 1}", "icon": p.split(":", 1)[1], "prompt": None,
                               "label": None, "x": 0.25 + 0.25 * j, "y": 0.35, "scale": 1.0,
                               "rotation": (-6 + 6 * j), "appear_word": j * 2, "animation": "draw"}
                              for j, p in enumerate(props)],
                    "camera": cam, "camera_intensity": 0.5,
                    "on_screen_text": {"text": txt, "style": style, "appear_word": 1, "color": None} if txt else None,
                    "sfx": [{"name": s, "at_word": None, "offset": 0.0, "volume": 1.0} for s in sfx],
                    "transition_in": "cut" if i == 0 else ["whip", "paper", "zoom", "ink_wipe"][i % 4],
                })
            return {"scenes": scenes}
        if task == "vision":
            return {"ok": True, "issues": [], "score": 8}
        return {}
