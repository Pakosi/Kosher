from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from ..config import LLMConfig
from . import LLMError, extract_json


class OpenAICompatLLM:
    """Any OpenAI-compatible local server: `mlx_lm.server`, LM Studio, llama.cpp server."""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def complete_json(self, task: str, system: str, prompt: str, schema: dict,
                      images: list[str] | None = None, retries: int = 2) -> Any:
        content: Any = prompt
        if images:
            content = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()}}
                for p in images]
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "system", "content": system + "\nReply with JSON only."},
                         {"role": "user", "content": content}],
            "temperature": self.cfg.temperature,
            "response_format": {"type": "json_schema", "json_schema": {"name": task, "schema": schema}},
        }
        last: Exception | None = None
        for _ in range(retries + 1):
            try:
                r = httpx.post(f"{self.cfg.host.rstrip('/')}/v1/chat/completions", json=body,
                               timeout=self.cfg.timeout)
                if r.status_code == 400:      # server without json_schema support
                    body.pop("response_format", None)
                    r = httpx.post(f"{self.cfg.host.rstrip('/')}/v1/chat/completions", json=body,
                                   timeout=self.cfg.timeout)
                r.raise_for_status()
                return extract_json(r.json()["choices"][0]["message"]["content"])
            except (httpx.HTTPError, ValueError, LLMError) as e:
                last = e
        raise LLMError(f"openai-compat {self.cfg.model} failed for {task}: {last}")

    def unload(self) -> None:
        pass
