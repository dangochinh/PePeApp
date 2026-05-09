"""
Video Engine — Sends visual prompts to ComfyUI and downloads the generated clips.
Supports: SVD XT, CogVideoX, AnimateDiff
"""
import json
import time
import uuid
import httpx
from pathlib import Path
from urllib import request as urllib_request, parse
from config import settings


# ComfyUI workflow templates per model
def get_image_workflow(prompt: str, seed: int = None) -> dict:
    """Fast SDXL/Flux workflow for still frames"""
    if seed is None:
        seed = int(time.time())
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "cfg": 7, "denoise": 1, "latent_image": ["5", 0],
            "model": ["4", 0], "negative": ["7", 0], "positive": ["6", 0],
            "sampler_name": "euler", "scheduler": "karras", "seed": seed, "steps": 25
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 720, "width": 1280}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "blurry, bad anatomy, low quality"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "PePeScene", "images": ["8", 0]}}
    }

def get_svd_workflow(prompt: str, seed: int = None) -> dict:
    """Stable Video Diffusion XT workflow - image2video or text2video"""
    if seed is None:
        seed = int(time.time())
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "cfg": 7, "denoise": 1, "latent_image": ["5", 0],
            "model": ["4", 0], "negative": ["7", 0], "positive": ["6", 0],
            "sampler_name": "euler", "scheduler": "karras", "seed": seed, "steps": 20
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "svd_xt.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": 576, "width": 1024}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": "blurry, low quality, watermark, text, nsfw"}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "PePeVideo", "images": ["8", 0]}}
    }


async def generate_clip(
    visual_prompt: str,
    output_path: Path,
    scene_number: int = 1,
    mode: str = "video",
    on_progress=None,
) -> str:
    """
    Generate a video clip or still image from a visual prompt.
    """
    client_id = str(uuid.uuid4())
    server = settings.comfyui_base_url.replace("http://", "").replace("https://", "")

    if on_progress:
        await on_progress(f"Rendering {'scene' if mode == 'image' else 'video'} {scene_number}...", 10)

    if mode == "image":
        workflow = get_image_workflow(visual_prompt)
    else:
        workflow = get_svd_workflow(visual_prompt)

    # Queue prompt
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.comfyui_base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id}
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

    if on_progress:
        await on_progress(f"Scene {scene_number} queued, waiting for ComfyUI...", 30)

    # Poll for completion
    max_wait = 600  # 10 minutes
    waited = 0
    while waited < max_wait:
        async with httpx.AsyncClient(timeout=10.0) as client:
            history_resp = await client.get(f"{settings.comfyui_base_url}/history/{prompt_id}")
            history = history_resp.json()

        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            for node_id, node_output in outputs.items():
                images = node_output.get("images") or node_output.get("videos") or []
                if images:
                    file_info = images[0]
                    filename = file_info["filename"]
                    subfolder = file_info.get("subfolder", "")
                    file_type = file_info.get("type", "output")

                    params = parse.urlencode({"filename": filename, "subfolder": subfolder, "type": file_type})
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        dl_resp = await client.get(f"{settings.comfyui_base_url}/view?{params}")
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(dl_resp.content)

                    if on_progress:
                        await on_progress(f"Scene {scene_number} rendered!", 100)

                    return str(output_path)

        await asyncio.sleep(3)
        waited += 3

        if on_progress and waited % 30 == 0:
            pct = min(30 + int((waited / max_wait) * 60), 90)
            await on_progress(f"Scene {scene_number} still rendering... ({waited}s)", pct)

    raise TimeoutError(f"ComfyUI timed out for scene {scene_number} after {max_wait}s")


import asyncio
