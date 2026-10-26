"""Minimal ComfyUI HTTP client (queue prompt -> poll history -> download images)."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, host: str = "http://127.0.0.1:8188", timeout: float = 900.0):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex
        self.http = httpx.Client(timeout=60)

    def alive(self) -> bool:
        try:
            return self.http.get(f"{self.host}/system_stats", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    def object_info(self, node: str) -> dict:
        r = self.http.get(f"{self.host}/object_info/{node}")
        r.raise_for_status()
        return r.json()

    def has_node(self, node: str) -> bool:
        try:
            return node in self.object_info(node)
        except httpx.HTTPError:
            return False

    def upload_image(self, path: Path) -> str:
        with path.open("rb") as f:
            r = self.http.post(f"{self.host}/upload/image",
                               files={"image": (path.name, f, "image/png")}, data={"overwrite": "true"})
        r.raise_for_status()
        d = r.json()
        return f"{d['subfolder']}/{d['name']}" if d.get("subfolder") else d["name"]

    def queue(self, workflow: dict) -> str:
        r = self.http.post(f"{self.host}/prompt", json={"prompt": workflow, "client_id": self.client_id})
        if r.status_code != 200:
            raise ComfyError(f"queue failed {r.status_code}: {r.text[:500]}")
        return r.json()["prompt_id"]

    def wait(self, prompt_id: str, poll: float = 1.0) -> dict:
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            r = self.http.get(f"{self.host}/history/{prompt_id}")
            if r.status_code == 200 and prompt_id in (h := r.json()):
                entry = h[prompt_id]
                st = entry.get("status", {})
                if st.get("status_str") == "error":
                    raise ComfyError(f"workflow error: {st.get('messages')}")
                if st.get("completed", True) and entry.get("outputs"):
                    return entry["outputs"]
            time.sleep(poll)
        raise ComfyError(f"timeout waiting for {prompt_id}")

    def download(self, image: dict, dest: Path) -> Path:
        r = self.http.get(f"{self.host}/view", params={
            "filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output")})
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest

    def run(self, workflow: dict, out_dir: Path, prefix: str) -> list[Path]:
        outputs = self.wait(self.queue(workflow))
        paths = []
        for node_out in outputs.values():
            for i, img in enumerate(node_out.get("images", [])):
                paths.append(self.download(img, out_dir / f"{prefix}_{len(paths) + i}.png"))
        if not paths:
            raise ComfyError("workflow produced no images")
        return paths

    def free(self) -> None:
        """Unload checkpoints/LoRAs from (unified) memory before the next stage."""
        try:
            self.http.post(f"{self.host}/free", json={"unload_models": True, "free_memory": True}, timeout=30)
        except httpx.HTTPError:
            pass
