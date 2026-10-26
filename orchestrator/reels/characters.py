"""Recurring-character tooling (ComfyUI, run once per character):

  design    -> N design candidates from the text description (pick one as reference.png)
  dataset   -> ~30 consistent variations from the reference (IPAdapter) + captions, for LoRA training
  train     -> writes a kohya sd-scripts LoRA config + command (runs on the Mac, MPS)
  sheet     -> pose/expression sheet candidates using the LoRA (or IPAdapter reference)
  pick      -> choose a candidate per pose: background removed -> poses/<pose>.png
  autorig   -> vision model locates mouth + eyes per pose -> rig.json (fine-tune in the dashboard)

Layout: characters/<id>/{reference.png, design/, dataset/, lora/, candidates/<pose>/, poses/, rig.json}
Until a rig exists, the renderer uses the built-in procedural SVG character."""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image

from .comfy.client import ComfyClient
from .comfy.workflows import DOODLE_STYLE, character_prompt, txt2img
from .config import CharacterConfig, PipelineConfig, SeriesConfig
from .imaging import remove_white_background, sample_color
from .llm import get_llm
from .steps.base import console
from .vocab import POSES

EXPRESSION_POSE = {"neutral": "neutral", "happy": "celebrate", "smug": "smug", "worried": "think",
                   "shocked": "shock", "angry": "point", "sad": "facepalm", "excited": "celebrate",
                   "suspicious": "sneak"}


def char_dir(cfg: PipelineConfig, ch: CharacterConfig) -> Path:
    d = cfg.paths.p("characters") / ch.id
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_character(series: SeriesConfig, char_id: str | None) -> CharacterConfig:
    if not char_id:
        return series.character
    for c in series.all_characters():
        if c.id == char_id:
            return c
    raise KeyError(f"character {char_id} not in series {series.id}")


def _client(cfg: PipelineConfig) -> ComfyClient:
    c = ComfyClient(cfg.comfy.host, cfg.comfy.timeout)
    if not c.alive():
        raise RuntimeError(f"ComfyUI not reachable at {cfg.comfy.host} (start it: see README)")
    return c


def design(cfg: PipelineConfig, ch: CharacterConfig, n: int = 8) -> list[Path]:
    client = _client(cfg)
    out = char_dir(cfg, ch) / "design"
    paths = []
    try:
        for i in range(n):
            wf = txt2img(cfg.comfy, f"{ch.description}, full body, standing, facing viewer, character design, {DOODLE_STYLE}",
                         seed=random.randint(0, 2**31))
            paths += client.run(wf, out, f"design{i:02d}")
    finally:
        client.free()
    console.print(f"pick one and copy it to {char_dir(cfg, ch) / 'reference.png'}")
    return paths


DATASET_PROMPTS = [
    "standing, front view", "standing, three-quarter view", "side view", "back view", "walking",
    "running", "sitting", "jumping", "waving", "pointing", "arms crossed", "thinking", "laughing",
    "shocked", "angry", "sad", "sneaking", "holding a coin", "close-up portrait", "head shot smiling",
]


def dataset(cfg: PipelineConfig, ch: CharacterConfig, count: int = 30) -> Path:
    ref = char_dir(cfg, ch) / "reference.png"
    if not ref.exists():
        raise FileNotFoundError(f"{ref} missing: run `reels character design` and pick a reference")
    client = _client(cfg)
    if not client.has_node("IPAdapterAdvanced"):
        raise RuntimeError("ComfyUI_IPAdapter_plus custom node not installed (setup/macos.sh installs it)")
    up = client.upload_image(ref)
    out = char_dir(cfg, ch) / "dataset"
    out.mkdir(exist_ok=True)
    trigger = ch.lora_trigger or ch.id
    try:
        for i in range(count):
            desc = DATASET_PROMPTS[i % len(DATASET_PROMPTS)]
            wf = txt2img(cfg.comfy, f"{ch.description}, {desc}, {DOODLE_STYLE}", seed=random.randint(0, 2**31),
                         ipadapter_image=up, ipadapter_weight=0.8)
            img = client.run(wf, out, f"{i:03d}")[0]
            img.with_suffix(".txt").write_text(f"{trigger}, {desc}, flat 2D doodle cartoon, white background")
    finally:
        client.free()
    console.print(f"dataset in {out}: delete off-model images, then `reels character train`")
    return out


def train_config(cfg: PipelineConfig, ch: CharacterConfig, sd_scripts: str = "~/sd-scripts") -> Path:
    d = char_dir(cfg, ch) / "lora"
    d.mkdir(exist_ok=True)
    data = char_dir(cfg, ch) / "dataset"
    toml = d / "dataset.toml"
    toml.write_text(f"""[general]
enable_bucket = true
caption_extension = ".txt"

[[datasets]]
resolution = 1024
batch_size = 1

  [[datasets.subsets]]
  image_dir = "{data}"
  num_repeats = 10
""")
    ckpt = "~/ComfyUI/models/checkpoints/" + cfg.comfy.checkpoint
    script = d / "train.sh"
    script.write_text(f"""#!/usr/bin/env bash
# SDXL character LoRA on Apple Silicon (MPS). ~1-2h on an M5 Pro for 1500 steps. [Mac-only]
set -euo pipefail
cd {sd_scripts}
source venv/bin/activate
PYTORCH_ENABLE_MPS_FALLBACK=1 accelerate launch --num_cpu_threads_per_process 8 sdxl_train_network.py \\
  --pretrained_model_name_or_path {ckpt} \\
  --dataset_config {toml} \\
  --output_dir {d} --output_name {ch.id}_v1 --save_model_as safetensors \\
  --network_module networks.lora --network_dim 32 --network_alpha 16 \\
  --learning_rate 1e-4 --unet_lr 1e-4 --text_encoder_lr 5e-5 \\
  --max_train_steps 1500 --save_every_n_steps 500 \\
  --optimizer_type AdamW --lr_scheduler cosine --mixed_precision no \\
  --gradient_checkpointing --cache_latents --sdpa --seed 42
cp {d}/{ch.id}_v1.safetensors ~/ComfyUI/models/loras/
echo "Set lora: {ch.id}_v1.safetensors in the series yaml, then run: reels character sheet"
""")
    script.chmod(0o755)
    return script


def sheet(cfg: PipelineConfig, ch: CharacterConfig, candidates: int = 4, poses: list[str] | None = None) -> Path:
    client = _client(cfg)
    ref = char_dir(cfg, ch) / "reference.png"
    loras = [(ch.lora, ch.lora_strength)] if ch.lora else []
    ip = client.upload_image(ref) if (not loras and ref.exists() and client.has_node("IPAdapterAdvanced")) else None
    if not loras and not ip:
        console.print("[yellow]no LoRA and no reference/IPAdapter: poses may drift off-model[/yellow]")
    out = char_dir(cfg, ch) / "candidates"
    try:
        for pose in poses or POSES:
            prompt = character_prompt(ch.lora_trigger if ch.lora else None, ch.description, pose)
            for k in range(candidates):
                wf = txt2img(cfg.comfy, prompt, width=832, height=1216, seed=random.randint(0, 2**31),
                             loras=loras, ipadapter_image=ip)
                client.run(wf, out / pose, f"{k}")
    finally:
        client.free()
    console.print(f"candidates in {out}: pick per pose with `reels character pick` or in the dashboard")
    return out


def pick(cfg: PipelineConfig, ch: CharacterConfig, pose: str, candidate: Path) -> Path:
    d = char_dir(cfg, ch) / "poses"
    dest = remove_white_background(candidate, d / f"{pose}.png")
    rig_f = char_dir(cfg, ch) / "rig.json"
    rig = json.loads(rig_f.read_text()) if rig_f.exists() else {"poses": {}, "expressions": {}, "mouthColor": "#1B1B1B", "skinColor": "#FFFFFF"}
    w, h = Image.open(dest).size
    prev = rig["poses"].get(pose, {})
    rig["poses"][pose] = {"src": f"poses/{pose}.png", "width": w, "height": h,
                          "mouth": prev.get("mouth", {"x": w * 0.5, "y": h * 0.3, "w": w * 0.12, "rotation": 0}),
                          "eyes": prev.get("eyes", [])}
    rig["expressions"] = {e: p for e, p in EXPRESSION_POSE.items() if p in rig["poses"]}
    rig_f.write_text(json.dumps(rig, indent=2))
    return dest


RIG_SCHEMA = {"type": "object", "properties": {
    "mouth": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}},
              "required": ["x", "y", "w"]},
    "eyes": {"type": "array", "items": {"type": "object", "properties": {
        "x": {"type": "number"}, "y": {"type": "number"}, "r": {"type": "number"}}, "required": ["x", "y", "r"]}}},
    "required": ["mouth", "eyes"]}


def autorig(cfg: PipelineConfig, ch: CharacterConfig) -> Path:
    rig_f = char_dir(cfg, ch) / "rig.json"
    rig = json.loads(rig_f.read_text())
    llm = get_llm("vision", cfg)
    for name, pose in rig["poses"].items():
        img = char_dir(cfg, ch) / pose["src"]
        r = llm.complete_json("rig", "You locate facial features in cartoon images. Output JSON only.",
                              "Locate this cartoon character's mouth and eyes. Give coordinates as fractions "
                              "0..1 of image width (x) and height (y). mouth: centre x,y and width w (fraction "
                              "of image width). eyes: list of {x, y, r} with r = eye radius as a fraction of width.",
                              RIG_SCHEMA, images=[str(img)])
        w, h = pose["width"], pose["height"]
        m = r["mouth"]
        pose["mouth"] = {"x": m["x"] * w, "y": m["y"] * h, "w": max(m["w"] * w, 20), "rotation": 0}
        pose["eyes"] = [{"x": e["x"] * w, "y": e["y"] * h, "r": max(e["r"] * w, 6)} for e in r.get("eyes", [])[:2]]
        if name == "neutral":
            rig["skinColor"] = sample_color(img, int(pose["mouth"]["x"]), int(pose["mouth"]["y"] - pose["mouth"]["w"] * 0.6))
    llm.unload()
    rig_f.write_text(json.dumps(rig, indent=2))
    return rig_f


__all__ = ["design", "dataset", "train_config", "sheet", "pick", "autorig"]
