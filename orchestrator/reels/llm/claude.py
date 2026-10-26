from __future__ import annotations

import json
import os
from typing import Any

from ..config import LLMConfig
from . import LLMError, extract_json


class ClaudeLLM:
    """Single polish call per episode. Uses structured outputs so the reply is
    schema-valid JSON. Needs `pip install anthropic` and an API key / `ant auth login`."""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                    or os.path.isdir(os.path.expanduser("~/.config/anthropic")))

    def complete_json(self, task: str, system: str, prompt: str, schema: dict,
                      images: list[str] | None = None) -> Any:
        try:
            import anthropic
        except ImportError as e:
            raise LLMError("anthropic SDK not installed (pip install 'reels[claude]')") from e
        client = anthropic.Anthropic(timeout=self.cfg.timeout)
        try:
            resp = client.messages.create(
                model=self.cfg.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.cfg.effort,
                               "format": {"type": "json_schema", "schema": _strict(schema)}},
            )
        except anthropic.APIError as e:
            raise LLMError(f"claude {task}: {e}") from e
        if resp.stop_reason == "refusal":
            raise LLMError(f"claude refused {task}")
        text = "".join(b.text for b in resp.content if b.type == "text")
        return extract_json(text)

    def unload(self) -> None:
        pass


def _strict(schema: dict) -> dict:
    """Structured outputs require additionalProperties: false on every object."""
    s = json.loads(json.dumps(schema))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(s)
    return s
