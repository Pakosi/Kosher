"""ComfyUI API-format workflow builders (core nodes only, plus optional
IPAdapter-plus nodes for reference-image consistency)."""

from __future__ import annotations

from ..config import ComfyConfig

DOODLE_STYLE = ("flat 2D doodle cartoon, thick clean black marker outlines, hand-drawn, simple shapes, "
                "limited flat colors, sticker style, white background, centered, no shadow")
NEGATIVE = ("photo, realistic, 3d render, gradient, shading, blurry, noisy, text, watermark, signature, "
            "logo, frame, border, multiple views, cropped, extra limbs, deformed hands, busy background")


def txt2img(cc: ComfyConfig, positive: str, negative: str = NEGATIVE, *, width: int | None = None,
            height: int | None = None, seed: int = 0, batch: int = 1,
            loras: list[tuple[str, float]] | None = None,
            ipadapter_image: str | None = None, ipadapter_weight: float = 0.7) -> dict:
    wf: dict[str, dict] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": cc.checkpoint}},
    }
    model, clip = ["1", 0], ["1", 1]
    chain = list(loras or [])
    if cc.style_lora:
        chain.append((cc.style_lora, cc.style_lora_strength))
    nid = 10
    for name, strength in chain:
        wf[str(nid)] = {"class_type": "LoraLoader", "inputs": {
            "model": model, "clip": clip, "lora_name": name,
            "strength_model": strength, "strength_clip": strength}}
        model, clip = [str(nid), 0], [str(nid), 1]
        nid += 1
    if ipadapter_image:
        wf["30"] = {"class_type": "LoadImage", "inputs": {"image": ipadapter_image}}
        wf["31"] = {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": model, "preset": "PLUS (high strength)"}}
        wf["32"] = {"class_type": "IPAdapterAdvanced", "inputs": {
            "model": ["31", 0], "ipadapter": ["31", 1], "image": ["30", 0], "weight": ipadapter_weight,
            "weight_type": "style and composition", "combine_embeds": "concat",
            "start_at": 0.0, "end_at": 0.85, "embeds_scaling": "V only"}}
        model = ["32", 0]
    wf.update({
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": positive}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": clip, "text": negative}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width or cc.width, "height": height or cc.height, "batch_size": batch}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": model, "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": seed, "steps": cc.steps, "cfg": cc.cfg, "sampler_name": cc.sampler,
            "scheduler": cc.scheduler, "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "reels"}},
    })
    return wf


def prop_prompt(subject: str) -> str:
    return f"{subject}, single object, {DOODLE_STYLE}"


def background_prompt(subject: str) -> str:
    return (f"{subject}, wide empty scene background for a cartoon, flat 2D doodle illustration, "
            "black marker outlines, pastel flat colors, lots of empty space in the middle, no characters, no text")


POSE_TEXT = {
    "neutral": "standing relaxed, arms at sides, facing viewer",
    "point": "pointing to the side with one arm extended, confident",
    "shock": "jumping back in shock, hands up, eyes wide",
    "think": "hand on chin, thinking, looking up",
    "smug": "arms crossed, smug confident lean",
    "shrug": "shrugging with both palms up",
    "run": "running fast, side view, motion pose",
    "sneak": "tiptoeing sneakily, hunched",
    "celebrate": "both arms raised celebrating",
    "facepalm": "facepalm, hand over face",
}


def character_prompt(trigger: str | None, description: str, pose: str) -> str:
    head = f"{trigger}, " if trigger else ""
    return (f"{head}{description}, full body, {POSE_TEXT.get(pose, pose)}, mouth closed, "
            f"character design, {DOODLE_STYLE}")
