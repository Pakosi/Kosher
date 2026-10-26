"""LLM backends with one interface: complete_json(task, system, prompt, schema)."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from ..config import LLMConfig, PipelineConfig, load_pipeline


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    cfg: LLMConfig

    def complete_json(self, task: str, system: str, prompt: str, schema: dict,
                      images: list[str] | None = None) -> Any: ...

    def unload(self) -> None: ...


def extract_json(text: str) -> Any:
    """Parse JSON from model text, tolerating <think> blocks and code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
        if start < 0:
            raise LLMError(f"no JSON in model output: {text[:200]!r}")
        end = max(text.rfind("}"), text.rfind("]"))
        return json.loads(text[start:end + 1])


def get_llm(role: str, cfg: PipelineConfig | None = None) -> LLM:
    cfg = cfg or load_pipeline()
    lc: LLMConfig = getattr(cfg.llm, role)
    if lc.backend == "ollama":
        from .ollama import OllamaLLM
        return OllamaLLM(lc)
    if lc.backend == "openai":
        from .openai_compat import OpenAICompatLLM
        return OpenAICompatLLM(lc)
    if lc.backend == "claude":
        from .claude import ClaudeLLM
        return ClaudeLLM(lc)
    from .mock import MockLLM
    return MockLLM(lc)
