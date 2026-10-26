import json

import httpx

from reels.comfy.client import ComfyClient
from reels.comfy.workflows import txt2img
from reels.config import ComfyConfig


def test_workflow_chains_loras_and_ipadapter():
    wf = txt2img(ComfyConfig(style_lora="doodle.safetensors"), "a coin", loras=[("vinnie.safetensors", 0.9)],
                 ipadapter_image="ref.png")
    classes = [n["class_type"] for n in wf.values()]
    assert classes.count("LoraLoader") == 2
    assert "IPAdapterAdvanced" in classes
    ks = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert ks["inputs"]["model"] == ["32", 0]           # sampler uses the IPAdapter-patched model


def test_client_roundtrip(tmp_path):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path == "/prompt":
            assert "prompt" in json.loads(req.content)
            return httpx.Response(200, json={"prompt_id": "p1"})
        if req.url.path == "/history/p1":
            return httpx.Response(200, json={"p1": {"status": {"completed": True, "status_str": "success"},
                                                    "outputs": {"7": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}}})
        if req.url.path == "/view":
            return httpx.Response(200, content=b"\x89PNG")
        return httpx.Response(404)

    c = ComfyClient("http://comfy")
    c.http = httpx.Client(transport=httpx.MockTransport(handler))
    paths = c.run({"1": {}}, tmp_path, "x")
    assert paths[0].read_bytes() == b"\x89PNG"
    assert calls == ["/prompt", "/history/p1", "/view"]
