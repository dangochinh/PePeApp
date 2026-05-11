"""
Video Engine — Two-stage image-to-video pipeline:
  Stage 1: Draw Things API  → PNG still image
  Stage 2: ComfyUI AnimateDiff → MP4 video clip (optional, only when ComfyUI online)
"""
import asyncio
import base64
import time
import uuid
import httpx
from pathlib import Path
from urllib import parse
from config import settings
from worker.service_control import start_draw_things, stop_draw_things

# ── Style Presets ─────────────────────────────────────────────────────────────

STYLE_PRESETS: dict[str, dict] = {
    "cinematic": {
        "prefix": "cinematic photograph, film grain, anamorphic lens, dramatic lighting, 35mm RAW",
        "negative": "cartoon, anime, illustration, flat colors",
    },
    "anime": {
        "prefix": "anime style, cel shading, vibrant colors, 2D illustration, high quality anime art",
        "negative": "photorealistic, photograph, 3D render, blurry",
    },
    "watercolor": {
        "prefix": "watercolor painting, soft wet brushstrokes, pastel colors, artistic illustration, flowing ink",
        "negative": "photorealistic, sharp edges, photograph, digital art",
    },
    "oil_painting": {
        "prefix": "oil painting on canvas, thick impasto brushstrokes, classical art, renaissance lighting",
        "negative": "photograph, digital flat art, anime, cartoon",
    },
    "neon": {
        "prefix": "neon lights, cyberpunk aesthetic, dark background, glowing neon colors, synthwave mood",
        "negative": "daytime, natural lighting, muted colors, watercolor",
    },
    "photorealistic": {
        "prefix": "ultra photorealistic, DSLR photo, 8K detail, sharp focus, professional photography",
        "negative": "illustration, painting, anime, cartoon, CGI",
    },
}

_BASE_NEGATIVE = "(people, person, human, man, woman, girl, boy, face, hands, crowd, figure, body, portrait, skin:1.5), (worst quality, low quality, normal quality:1.4), blur:1.5, watermark, text, nsfw, deformed, bad anatomy"


# ── Draw Things ────────────────────────────────────────────────────────────────

async def _check_draw_things() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.draw_things_base_url}/")
            return r.status_code == 200
    except Exception:
        return False


def _make_placeholder(prompt: str, output_path: Path, scene_number: int):
    """Pillow placeholder for when Draw Things is offline."""
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    colors = [(15, 15, 35), (30, 10, 60), (10, 30, 50)]
    color = colors[scene_number % len(colors)]
    for y in range(H):
        r = int(color[0] + (color[0] * 0.5) * y / H)
        g = int(color[1] + (color[1] * 0.5) * y / H)
        b = int(color[2] + (color[2] * 1.5) * y / H)
        draw.line([(0, y), (W, y)], fill=(min(r, 255), min(g, 255), min(b, 255)))

    draw.ellipse([W//2-60, H//2-220, W//2+60, H//2-100], fill=(80, 40, 120))
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
        font_med = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        font_sm  = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font_big = font_med = font_sm = ImageFont.load_default()

    draw.text((W//2, H//2-160), str(scene_number), font=font_big, fill="white", anchor="mm")
    draw.text((W//2, H//2-60), "SCENE PLACEHOLDER", font=font_sm, fill=(150, 150, 200), anchor="mm")
    lines = textwrap.wrap(prompt[:200], width=32)[:6]
    y_text = H//2 + 20
    for line in lines:
        draw.text((W//2, y_text), line, font=font_med, fill=(200, 200, 220), anchor="mm")
        y_text += 50
    draw.text((W//2, H - 80), "Draw Things API offline", font=font_sm, fill=(80, 80, 100), anchor="mm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))


def _sanitize_visual_prompt(prompt: str) -> str:
    """Replace Vietnamese/non-ASCII prompts with English category fallback."""
    non_ascii = sum(1 for c in prompt if ord(c) > 127)
    if non_ascii < 5:
        return prompt  # Already English
    from worker.script_engine import _detect_category, _CATEGORY_VISUALS
    category = _detect_category(prompt)
    return _CATEGORY_VISUALS[category]


async def _upscale_png(png_path: Path) -> Path:
    """Upscale PNG via Real-ESRGAN binary if available, else PIL Lanczos to 1080x1920."""
    import shutil as _shutil
    binary = _shutil.which("realesrgan-ncnn-vulkan") or _shutil.which("realesrgan")
    if binary:
        out_path = png_path.with_stem(png_path.stem + "_up")
        try:
            proc = await asyncio.create_subprocess_exec(
                binary, "-i", str(png_path), "-o", str(out_path), "-n", "realesrgan-x4plus",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0 and out_path.exists():
                png_path.unlink(missing_ok=True)
                out_path.rename(png_path)
                return png_path
        except Exception as e:
            print(f"[upscale] Real-ESRGAN failed: {e} — falling back to PIL Lanczos")

    # PIL Lanczos fallback — upscale to video output resolution
    try:
        from PIL import Image as _PILImg
        with _PILImg.open(png_path) as img:
            W, H = img.size
            if W < 1080 or H < 1920:
                up = img.resize((1080, 1920), _PILImg.LANCZOS)
                up.save(str(png_path), "PNG")
    except Exception as e:
        print(f"[upscale] PIL fallback failed: {e}")
    return png_path


async def generate_clip(
    visual_prompt: str,
    output_path: Path,
    scene_number: int = 1,
    mode: str = "image",
    on_progress=None,
    seed: int = -1,
    image_style: str = "",
    ref_image_path: Path | None = None,
) -> str:
    """
    Stage 1: Generate a still image via Draw Things.
    Falls back to Pillow placeholder when offline.
    Always returns the actual path created (extension may change to .png).
    When ref_image_path is set and settings.use_img2img_ref is True, uses img2img
    for visual consistency across scenes.
    """
    if on_progress:
        await on_progress(f"Rendering scene {scene_number}...", 10)

    if not await _check_draw_things():
        if on_progress:
            await on_progress(f"Draw Things offline — starting up...", 15)

        async def _dt_status(msg: str):
            if on_progress:
                await on_progress(f"🖼️ {msg}", 20)

        ready = await start_draw_things(on_status=_dt_status)

        if not ready:
            if on_progress:
                await on_progress(f"Draw Things did not start — using placeholder for scene {scene_number}", 50)
            png_path = output_path.with_suffix(".png")
            await asyncio.get_event_loop().run_in_executor(
                None, _make_placeholder, visual_prompt, png_path, scene_number
            )
            if on_progress:
                await on_progress(f"Scene {scene_number} placeholder ready", 100)
            return str(png_path)

    visual_prompt = _sanitize_visual_prompt(visual_prompt)

    style_key = (image_style or settings.image_style).lower().replace(" ", "_")
    preset = STYLE_PRESETS.get(style_key, STYLE_PRESETS["cinematic"])
    styled_prompt = f"{preset['prefix']}, {visual_prompt}"
    negative = f"{preset['negative']}, {_BASE_NEGATIVE}"

    use_ref = (
        ref_image_path is not None
        and ref_image_path.exists()
        and settings.use_img2img_ref
    )

    if use_ref:
        if on_progress:
            await on_progress(f"Sending scene {scene_number} to Draw Things (img2img)...", 20)
        ref_b64 = base64.b64encode(ref_image_path.read_bytes()).decode()
        payload = {
            "init_images": [ref_b64],
            "prompt": styled_prompt,
            "negative_prompt": negative,
            "seed": seed if seed != -1 else -1,
            "width": 768,
            "height": 1344,
            "steps": settings.draw_things_steps,
            "cfg_scale": settings.draw_things_cfg,
            "denoising_strength": settings.img2img_denoising,
            "sampler_name": "Euler a",
            "batch_size": 1,
        }
        endpoint = f"{settings.draw_things_base_url}/sdapi/v1/img2img"
    else:
        if on_progress:
            await on_progress(f"Sending scene {scene_number} to Draw Things...", 20)
        payload = {
            "prompt": styled_prompt,
            "negative_prompt": negative,
            "seed": seed if seed != -1 else -1,
            "width": 768,
            "height": 1344,
            "steps": settings.draw_things_steps,
            "cfg_scale": settings.draw_things_cfg,
            "sampler_name": "Euler a",
            "batch_size": 1,
        }
        endpoint = f"{settings.draw_things_base_url}/sdapi/v1/txt2img"

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(endpoint, json=payload)
        resp.raise_for_status()

    resp_data = resp.json()
    images = resp_data.get("images", [])
    if not images:
        raise RuntimeError("Draw Things returned no images")

    png_path = output_path.with_suffix(".png")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(base64.b64decode(images[0]))

    # Save used seed alongside image so re-renders can reproduce it
    used_seed = resp_data.get("info", {}).get("seed", seed) if isinstance(resp_data.get("info"), dict) else seed
    seed_file = png_path.with_suffix(".seed")
    seed_file.write_text(str(used_seed))

    # Upscale PNG if enabled
    if settings.enable_upscale:
        png_path = await _upscale_png(png_path)

    if on_progress:
        await on_progress(f"Scene {scene_number} image ready", 100)
    return str(png_path)


# ── Phase 6: Text-to-Video engines ────────────────────────────────────────────

async def generate_t2v(
    image_path: Path,
    visual_prompt: str,
    output_path: Path,
    scene_number: int = 1,
    on_progress=None,
) -> str | None:
    """
    Stage 2 (Phase 6): Animate a Draw Things PNG into MP4 via the configured T2V engine.
    Returns MP4 path on success, None to fall back to the PNG / AnimateDiff path.
    Engine is selected by settings.t2v_engine:
      "none"         → skip (return None)
      "comfyui_wan"  → ComfyUI Wan2.1 (requires WanVideoWrapper custom nodes)
      "replicate"    → Replicate cloud API (wan-ai/wan2.1-i2v-480p by default)
    """
    engine = settings.t2v_engine
    if engine == "none":
        return None
    if engine == "comfyui_wan":
        return await _t2v_comfyui_wan(image_path, visual_prompt, output_path, scene_number, on_progress)
    if engine == "replicate":
        return await _t2v_replicate(image_path, visual_prompt, output_path, scene_number, on_progress)
    return None


async def _t2v_comfyui_wan(
    image_path: Path,
    visual_prompt: str,
    output_path: Path,
    scene_number: int,
    on_progress,
) -> str | None:
    """ComfyUI Wan2.1 I2V via WanVideoWrapper custom nodes."""
    if not await _check_comfyui():
        return None

    try:
        uploaded_name = await _upload_image_to_comfyui(image_path)
    except Exception as e:
        print(f"[t2v/wan] ComfyUI upload failed scene {scene_number}: {e}")
        return None

    seed = int(time.time())
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
        "2": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "model": settings.wan_model_name,
                "image": ["1", 0],
                "positive": f"cinematic video, smooth motion, {visual_prompt}, no humans, no people",
                "negative": "people, person, human, face, hands, static, frozen, blurry, low quality, watermark",
                "num_frames": settings.t2v_num_frames,
                "fps": settings.t2v_fps,
                "guidance_scale": 7.5,
                "seed": seed,
                "steps": 30,
            },
        },
        "3": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["2", 0],
                "frame_rate": settings.t2v_fps,
                "loop_count": 0,
                "filename_prefix": "PePeWan",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }

    client_id = str(uuid.uuid4())
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.comfyui_base_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            resp.raise_for_status()
            prompt_id = resp.json()["prompt_id"]
    except Exception as e:
        print(f"[t2v/wan] ComfyUI submit failed: {e}")
        return None

    if on_progress:
        await on_progress(f"Scene {scene_number} queued in ComfyUI Wan2.1...", 20)

    mp4_path = output_path.with_suffix(".mp4")
    try:
        return await _poll_comfyui_and_download(prompt_id, mp4_path, scene_number, on_progress)
    except Exception as e:
        print(f"[t2v/wan] ComfyUI poll failed scene {scene_number}: {e}")
        return None


async def _t2v_replicate(
    image_path: Path,
    visual_prompt: str,
    output_path: Path,
    scene_number: int,
    on_progress,
) -> str | None:
    """Replicate cloud T2V API (Wan2.1 I2V by default)."""
    if not settings.replicate_api_key:
        print("[t2v/replicate] No Replicate API key configured")
        return None

    if on_progress:
        await on_progress(f"Scene {scene_number} — submitting to Replicate T2V...", 15)

    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    img_data_uri = f"data:image/png;base64,{img_b64}"

    model_slug = settings.replicate_t2v_model or "wan-ai/wan2.1-i2v-480p"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Token {settings.replicate_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_slug,
                    "input": {
                        "image": img_data_uri,
                        "prompt": f"cinematic smooth video, {visual_prompt}, no humans, no people",
                        "negative_prompt": "people, person, human, face, hands, static, frozen, blurry, watermark",
                        "num_frames": settings.t2v_num_frames,
                        "guidance_scale": 7.5,
                    },
                },
            )
            resp.raise_for_status()
            prediction = resp.json()
    except Exception as e:
        print(f"[t2v/replicate] Submit failed: {e}")
        return None

    pred_id = prediction.get("id")
    if not pred_id:
        print(f"[t2v/replicate] No prediction ID in response: {prediction}")
        return None

    if on_progress:
        await on_progress(f"Scene {scene_number} Replicate prediction {pred_id} queued...", 25)

    max_wait = 600
    waited = 0
    while waited < max_wait:
        await asyncio.sleep(5)
        waited += 5
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                result = (
                    await client.get(
                        f"https://api.replicate.com/v1/predictions/{pred_id}",
                        headers={"Authorization": f"Token {settings.replicate_api_key}"},
                    )
                ).json()
        except Exception:
            continue

        status = result.get("status")
        if status == "succeeded":
            output = result.get("output")
            video_url = output[0] if isinstance(output, list) else output
            if not video_url:
                return None
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    dl = await client.get(video_url)
                mp4_path = output_path.with_suffix(".mp4")
                mp4_path.parent.mkdir(parents=True, exist_ok=True)
                mp4_path.write_bytes(dl.content)
                if on_progress:
                    await on_progress(f"Scene {scene_number} T2V ready!", 100)
                return str(mp4_path)
            except Exception as e:
                print(f"[t2v/replicate] Download failed: {e}")
                return None
        elif status in ("failed", "canceled"):
            print(f"[t2v/replicate] Prediction {status}: {result.get('error')}")
            return None
        elif on_progress and waited % 30 == 0:
            pct = min(30 + int(waited / max_wait * 60), 90)
            await on_progress(f"Scene {scene_number} T2V generating... ({waited}s)", pct)

    print(f"[t2v/replicate] Timed out after {max_wait}s")
    return None


# ── ComfyUI I2V (AnimateDiff, legacy) ─────────────────────────────────────────

async def _check_comfyui() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.comfyui_base_url}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def _upload_image_to_comfyui(image_path: Path) -> str:
    """Upload a local image to ComfyUI and return the server-side filename."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {"image": (image_path.name, image_path.read_bytes(), "image/png")}
        resp = await client.post(f"{settings.comfyui_base_url}/upload/image", files=files)
        resp.raise_for_status()
        return resp.json()["name"]


def _build_i2v_workflow(uploaded_filename: str, prompt: str) -> dict:
    """
    AnimateDiff I2V workflow:
      LoadImage → VAEEncode → RepeatLatentBatch
      CheckpointLoader → ADE_AnimateDiffLoader → KSampler → VAEDecode → VHS_VideoCombine
    """
    seed = int(time.time())
    frames = settings.comfyui_i2v_frames
    fps = settings.comfyui_i2v_fps
    denoise = settings.comfyui_i2v_denoise

    return {
        # Load the Draw Things image
        "1": {"class_type": "LoadImage", "inputs": {
            "image": uploaded_filename,
        }},
        # Load SDXL checkpoint
        "2": {"class_type": "CheckpointLoaderSimple", "inputs": {
            "ckpt_name": settings.comfyui_checkpoint,
        }},
        # Positive prompt
        "3": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 1],
            "text": f"score_9, score_8_up, masterpiece, best quality, no humans, no people, {prompt}",
        }},
        # Negative prompt
        "4": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 1],
            "text": "people, person, human, man, woman, girl, boy, face, hands, crowd, figure, body, portrait, skin, worst quality, bad hands, extra fingers, blurry, low quality, static, frozen",
        }},
        # Encode image to latent
        "5": {"class_type": "VAEEncode", "inputs": {
            "pixels": ["1", 0],
            "vae": ["2", 2],
        }},
        # Repeat latent for animation frames
        "6": {"class_type": "RepeatLatentBatch", "inputs": {
            "samples": ["5", 0],
            "amount": frames,
        }},
        # Load AnimateDiff motion module
        "7": {"class_type": "ADE_AnimateDiffLoaderWithContext", "inputs": {
            "model": ["2", 0],
            "model_name": settings.comfyui_motion_module,
            "beta_schedule": "sqrt_linear (AnimateDiff)",
            "motion_scale": 1.0,
            "apply_v2_models_properly": False,
        }},
        # Sample
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["7", 0],
            "positive": ["3", 0],
            "negative": ["4", 0],
            "latent_image": ["6", 0],
            "seed": seed,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "karras",
            "denoise": denoise,
        }},
        # Decode
        "9": {"class_type": "VAEDecode", "inputs": {
            "samples": ["8", 0],
            "vae": ["2", 2],
        }},
        # Combine frames → MP4
        "10": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0],
            "frame_rate": fps,
            "loop_count": 0,
            "filename_prefix": "PePeVideo",
            "format": "video/h264-mp4",
            "pingpong": False,
            "save_output": True,
        }},
    }


async def _poll_comfyui_and_download(prompt_id: str, output_path: Path, scene_number: int, on_progress) -> str:
    """Poll ComfyUI until the job completes, then download the result."""
    max_wait = 600
    waited = 0
    while waited < max_wait:
        async with httpx.AsyncClient(timeout=10.0) as client:
            history = (await client.get(f"{settings.comfyui_base_url}/history/{prompt_id}")).json()

        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            for node_output in outputs.values():
                # VHS_VideoCombine returns "videos", SaveImage returns "images"
                files = node_output.get("videos") or node_output.get("images") or []
                if files:
                    f = files[0]
                    params = parse.urlencode({
                        "filename": f["filename"],
                        "subfolder": f.get("subfolder", ""),
                        "type": f.get("type", "output"),
                    })
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        dl = await client.get(f"{settings.comfyui_base_url}/view?{params}")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(dl.content)
                    if on_progress:
                        await on_progress(f"Scene {scene_number} video ready!", 100)
                    return str(output_path)

        await asyncio.sleep(3)
        waited += 3
        if on_progress and waited % 30 == 0:
            pct = min(30 + int(waited / max_wait * 60), 90)
            await on_progress(f"Scene {scene_number} animating... ({waited}s)", pct)

    raise TimeoutError(f"ComfyUI I2V timed out for scene {scene_number} after {max_wait}s")


async def generate_video_from_image(
    image_path: Path,
    visual_prompt: str,
    output_path: Path,
    scene_number: int = 1,
    on_progress=None,
) -> str | None:
    """
    Stage 2: Animate a Draw Things PNG into an MP4 via ComfyUI AnimateDiff.
    Returns the MP4 path, or None if ComfyUI is offline (caller keeps the PNG).
    """
    if not await _check_comfyui():
        return None

    if on_progress:
        await on_progress(f"Uploading scene {scene_number} image to ComfyUI...", 10)

    try:
        uploaded_name = await _upload_image_to_comfyui(image_path)
    except Exception as e:
        print(f"ComfyUI upload failed scene {scene_number}: {e}")
        return None

    workflow = _build_i2v_workflow(uploaded_name, visual_prompt)
    client_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.comfyui_base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

    if on_progress:
        await on_progress(f"Scene {scene_number} queued in ComfyUI AnimateDiff...", 20)

    mp4_path = output_path.with_suffix(".mp4")
    return await _poll_comfyui_and_download(prompt_id, mp4_path, scene_number, on_progress)
