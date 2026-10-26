from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from ..config import LLMConfig
from . import LLMError, extract_json


class OllamaLLM:
    """Ollama /api/chat with JSON-schema constrained output. keep_alive=0 by
    default so the model leaves unified memory as soon as the call returns."""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def complete_json(self, task: str, system: str, prompt: str, schema: dict,
                      images: list[str] | None = None, retries: int = 2) -> Any:
        msg: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            msg["images"] = [base64.b64encode(Path(p).read_bytes()).decode() for p in images]
        body = {
            "model": self.cfg.model,
            "messages": [{"role": "system", "content": system}, msg],
            "format": schema,
            "stream": False,
            "think": False,
            "keep_alive": self.cfg.keep_alive,
            "options": {"temperature": self.cfg.temperature, "num_ctx": self.cfg.num_ctx},
        }
        last: Exception | None = None
        for _ in range(retries + 1):
            try:
                r = httpx.post(f"{self.cfg.host}/api/chat", json=body, timeout=self.cfg.timeout)
                if r.status_code == 400 and "think" in r.text:   # model without thinking support
                    body.pop("think", None)
                    r = httpx.post(f"{self.cfg.host}/api/chat", json=body, timeout=self.cfg.timeout)
                r.raise_for_status()
                return extract_json(r.json()["message"]["content"])
            except (httpx.HTTPError, ValueError, LLMError) as e:
                last = e
        raise LLMError(f"ollama {self.cfg.model} failed for {task}: {last}")

    def unload(self) -> None:
        try:
            httpx.post(f"{self.cfg.host}/api/generate",
                       json={"model": self.cfg.model, "keep_alive": 0}, timeout=30)
        except httpx.HTTPError:
            pass


def unload_all(host: str = "http://127.0.0.1:11434") -> list[str]:
    """Evict every loaded Ollama model (used between pipeline stages)."""
    try:
        ps = httpx.get(f"{host}/api/ps", timeout=5).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return []
    names = [m["name"] for m in ps]
    for n in names:
        try:
            httpx.post(f"{host}/api/generate", json={"model": n, "keep_alive": 0}, timeout=30)
        except httpx.HTTPError:
            pass
    return names
