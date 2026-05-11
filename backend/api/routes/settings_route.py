"""
Settings API — Toggle TTS engine, video model, and other config.
"""
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from config import settings, BASE_DIR

router = APIRouter()

_ENV_PATH = BASE_DIR / "backend" / ".env"


def _persist_env(key: str, value: str) -> None:
    """Write or update a PEPE_KEY=value line in backend/.env."""
    env_key = f"PEPE_{key.upper()}"
    try:
        if _ENV_PATH.exists():
            lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}=") or line.startswith(f"{env_key} ="):
                lines[i] = f'{env_key}="{value}"'
                updated = True
                break
        if not updated:
            lines.append(f'{env_key}="{value}"')
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"[settings] could not write .env: {e}")


class SettingsUpdate(BaseModel):
    tts_engine: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    use_cloud_ai: Optional[bool] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    claude_model: Optional[str] = None
    comfyui_base_url: Optional[str] = None
    tts_voice: Optional[str] = None
    scenes_per_video: Optional[int] = None
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None
    youtube_refresh_token: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    tiktok_session_id: Optional[str] = None
    facebook_access_token: Optional[str] = None
    facebook_page_id: Optional[str] = None
    # Phase 1 — image quality & style
    draw_things_steps: Optional[int] = None
    draw_things_cfg: Optional[float] = None
    image_style: Optional[str] = None
    transition_style: Optional[str] = None
    ken_burns: Optional[bool] = None
    color_grade: Optional[str] = None
    bg_music_path: Optional[str] = None
    bg_music_volume: Optional[float] = None
    # Phase 5 — visual consistency
    enable_upscale: Optional[bool] = None
    use_img2img_ref: Optional[bool] = None
    img2img_denoising: Optional[float] = None
    # Phase 6 — text-to-video
    t2v_engine: Optional[str] = None
    replicate_api_key: Optional[str] = None
    replicate_t2v_model: Optional[str] = None
    wan_model_name: Optional[str] = None
    t2v_num_frames: Optional[int] = None
    t2v_fps: Optional[int] = None
    # Phase 4 — branding
    watermark_path: Optional[str] = None
    watermark_position: Optional[str] = None
    watermark_opacity: Optional[float] = None
    enable_intro_card: Optional[bool] = None
    enable_outro_card: Optional[bool] = None
    outro_card_text: Optional[str] = None
    # 2.0 — HTML scene engine
    scene_engine: Optional[str] = None
    html_template: Optional[str] = None

@router.get("/")
async def get_settings():
    """Get current settings."""
    return {
        "tts_engine": settings.tts_engine,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "use_cloud_ai": settings.use_cloud_ai,
        "openai_api_key": settings.openai_api_key,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "anthropic_api_key": settings.anthropic_api_key,
        "claude_model": settings.claude_model,
        "comfyui_base_url": settings.comfyui_base_url,
        "tts_voice": settings.tts_voice,
        "scenes_per_video": settings.scenes_per_video,
        "available_tts_engines": ["vieneu", "edge-tts", "piper", "faster-qwen3-tts"],
        "draw_things_steps": settings.draw_things_steps,
        "draw_things_cfg": settings.draw_things_cfg,
        "image_style": settings.image_style,
        "transition_style": settings.transition_style,
        "available_image_styles": ["cinematic", "anime", "watercolor", "oil_painting", "neon", "photorealistic"],
        "available_transitions": ["auto", "fade", "slideleft", "slideright", "slideup", "wipeleft", "wiperight", "dissolve", "pixelize", "radial"],
        "ken_burns": settings.ken_burns,
        "color_grade": settings.color_grade,
        "available_color_grades": ["none", "warm", "cool", "noir", "vibrant", "muted", "golden"],
        "bg_music_path": settings.bg_music_path,
        "bg_music_volume": settings.bg_music_volume,
        "enable_upscale": settings.enable_upscale,
        "use_img2img_ref": settings.use_img2img_ref,
        "img2img_denoising": settings.img2img_denoising,
        "t2v_engine": settings.t2v_engine,
        "available_t2v_engines": ["none", "comfyui_wan", "replicate"],
        "replicate_api_key": settings.replicate_api_key,
        "replicate_t2v_model": settings.replicate_t2v_model,
        "wan_model_name": settings.wan_model_name,
        "t2v_num_frames": settings.t2v_num_frames,
        "t2v_fps": settings.t2v_fps,
        "watermark_path": settings.watermark_path,
        "watermark_position": settings.watermark_position,
        "watermark_opacity": settings.watermark_opacity,
        "available_watermark_positions": ["topleft", "topright", "bottomleft", "bottomright"],
        "enable_intro_card": settings.enable_intro_card,
        "enable_outro_card": settings.enable_outro_card,
        "outro_card_text": settings.outro_card_text,
        "scene_engine": settings.scene_engine,
        "available_scene_engines": ["drawthings", "html"],
        "html_template": settings.html_template,
        "available_html_templates": ["dark", "gradient", "minimal", "bold", "news", "cinematic"],
        "social": {
            "youtube": {
                "client_id": settings.youtube_client_id,
                "client_secret": settings.youtube_client_secret,
                "refresh_token": settings.youtube_refresh_token,
            },
            "tiktok": {
                "access_token": settings.tiktok_access_token,
                "session_id": settings.tiktok_session_id,
            },
            "facebook": {
                "access_token": settings.facebook_access_token,
                "page_id": settings.facebook_page_id,
            }
        }
    }


@router.put("/")
async def update_settings(update: SettingsUpdate):
    """Update settings (runtime only, not persisted to .env yet)."""
    changed = {}
    if update.youtube_client_id is not None:
        settings.youtube_client_id = update.youtube_client_id
        changed["youtube_client_id"] = update.youtube_client_id
    if update.youtube_client_secret is not None:
        settings.youtube_client_secret = update.youtube_client_secret
        changed["youtube_client_secret"] = update.youtube_client_secret
    if update.youtube_refresh_token is not None:
        settings.youtube_refresh_token = update.youtube_refresh_token
        changed["youtube_refresh_token"] = update.youtube_refresh_token
    if update.tiktok_access_token is not None:
        settings.tiktok_access_token = update.tiktok_access_token
        changed["tiktok_access_token"] = update.tiktok_access_token
    if update.tiktok_session_id is not None:
        settings.tiktok_session_id = update.tiktok_session_id
        changed["tiktok_session_id"] = update.tiktok_session_id
    if update.facebook_access_token is not None:
        settings.facebook_access_token = update.facebook_access_token
        changed["facebook_access_token"] = update.facebook_access_token
    if update.facebook_page_id is not None:
        settings.facebook_page_id = update.facebook_page_id
        changed["facebook_page_id"] = update.facebook_page_id

    if update.anthropic_api_key is not None:
        settings.anthropic_api_key = update.anthropic_api_key
        changed["anthropic_api_key"] = update.anthropic_api_key
        _persist_env("anthropic_api_key", update.anthropic_api_key)
    if update.claude_model is not None:
        settings.claude_model = update.claude_model
        changed["claude_model"] = update.claude_model
        _persist_env("claude_model", update.claude_model)
    if update.use_cloud_ai is not None:
        settings.use_cloud_ai = update.use_cloud_ai
        changed["use_cloud_ai"] = update.use_cloud_ai
        _persist_env("use_cloud_ai", str(update.use_cloud_ai).lower())
    if update.openai_api_key is not None:
        settings.openai_api_key = update.openai_api_key
        changed["openai_api_key"] = update.openai_api_key
        _persist_env("openai_api_key", update.openai_api_key)
    if update.openai_base_url is not None:
        settings.openai_base_url = update.openai_base_url
        changed["openai_base_url"] = update.openai_base_url
        _persist_env("openai_base_url", update.openai_base_url)
    if update.openai_model is not None:
        settings.openai_model = update.openai_model
        changed["openai_model"] = update.openai_model
        _persist_env("openai_model", update.openai_model)
    if update.ollama_base_url is not None:
        settings.ollama_base_url = update.ollama_base_url
        changed["ollama_base_url"] = update.ollama_base_url
        _persist_env("ollama_base_url", update.ollama_base_url)
    if update.comfyui_base_url is not None:
        settings.comfyui_base_url = update.comfyui_base_url
        changed["comfyui_base_url"] = update.comfyui_base_url
        _persist_env("comfyui_base_url", update.comfyui_base_url)
    if update.tts_engine is not None:
        settings.tts_engine = update.tts_engine
        changed["tts_engine"] = update.tts_engine
        _persist_env("tts_engine", update.tts_engine)
    if update.tts_voice is not None:
        settings.tts_voice = update.tts_voice
        changed["tts_voice"] = update.tts_voice
        _persist_env("tts_voice", update.tts_voice)
    if update.ollama_model is not None:
        settings.ollama_model = update.ollama_model
        changed["ollama_model"] = update.ollama_model
        _persist_env("ollama_model", update.ollama_model)
    if update.scenes_per_video is not None:
        settings.scenes_per_video = update.scenes_per_video
        changed["scenes_per_video"] = update.scenes_per_video
        _persist_env("scenes_per_video", str(update.scenes_per_video))
    if update.draw_things_steps is not None:
        settings.draw_things_steps = update.draw_things_steps
        changed["draw_things_steps"] = update.draw_things_steps
        _persist_env("draw_things_steps", str(update.draw_things_steps))
    if update.draw_things_cfg is not None:
        settings.draw_things_cfg = update.draw_things_cfg
        changed["draw_things_cfg"] = update.draw_things_cfg
        _persist_env("draw_things_cfg", str(update.draw_things_cfg))
    if update.image_style is not None:
        settings.image_style = update.image_style
        changed["image_style"] = update.image_style
        _persist_env("image_style", update.image_style)
    if update.transition_style is not None:
        settings.transition_style = update.transition_style
        changed["transition_style"] = update.transition_style
        _persist_env("transition_style", update.transition_style)
    if update.ken_burns is not None:
        settings.ken_burns = update.ken_burns
        changed["ken_burns"] = update.ken_burns
        _persist_env("ken_burns", str(update.ken_burns).lower())
    if update.color_grade is not None:
        settings.color_grade = update.color_grade
        changed["color_grade"] = update.color_grade
        _persist_env("color_grade", update.color_grade)
    if update.bg_music_path is not None:
        settings.bg_music_path = update.bg_music_path
        changed["bg_music_path"] = update.bg_music_path
        _persist_env("bg_music_path", update.bg_music_path)
    if update.t2v_engine is not None:
        settings.t2v_engine = update.t2v_engine
        changed["t2v_engine"] = update.t2v_engine
        _persist_env("t2v_engine", update.t2v_engine)
    if update.replicate_api_key is not None:
        settings.replicate_api_key = update.replicate_api_key
        changed["replicate_api_key"] = update.replicate_api_key
        _persist_env("replicate_api_key", update.replicate_api_key)
    if update.replicate_t2v_model is not None:
        settings.replicate_t2v_model = update.replicate_t2v_model
        changed["replicate_t2v_model"] = update.replicate_t2v_model
        _persist_env("replicate_t2v_model", update.replicate_t2v_model)
    if update.wan_model_name is not None:
        settings.wan_model_name = update.wan_model_name
        changed["wan_model_name"] = update.wan_model_name
        _persist_env("wan_model_name", update.wan_model_name)
    if update.t2v_num_frames is not None:
        settings.t2v_num_frames = update.t2v_num_frames
        changed["t2v_num_frames"] = update.t2v_num_frames
        _persist_env("t2v_num_frames", str(update.t2v_num_frames))
    if update.t2v_fps is not None:
        settings.t2v_fps = update.t2v_fps
        changed["t2v_fps"] = update.t2v_fps
        _persist_env("t2v_fps", str(update.t2v_fps))
    if update.enable_upscale is not None:
        settings.enable_upscale = update.enable_upscale
        changed["enable_upscale"] = update.enable_upscale
        _persist_env("enable_upscale", str(update.enable_upscale).lower())
    if update.use_img2img_ref is not None:
        settings.use_img2img_ref = update.use_img2img_ref
        changed["use_img2img_ref"] = update.use_img2img_ref
        _persist_env("use_img2img_ref", str(update.use_img2img_ref).lower())
    if update.img2img_denoising is not None:
        settings.img2img_denoising = update.img2img_denoising
        changed["img2img_denoising"] = update.img2img_denoising
        _persist_env("img2img_denoising", str(update.img2img_denoising))
    if update.bg_music_volume is not None:
        settings.bg_music_volume = update.bg_music_volume
        changed["bg_music_volume"] = update.bg_music_volume
        _persist_env("bg_music_volume", str(update.bg_music_volume))
    if update.watermark_path is not None:
        settings.watermark_path = update.watermark_path
        changed["watermark_path"] = update.watermark_path
        _persist_env("watermark_path", update.watermark_path)
    if update.watermark_position is not None:
        settings.watermark_position = update.watermark_position
        changed["watermark_position"] = update.watermark_position
        _persist_env("watermark_position", update.watermark_position)
    if update.watermark_opacity is not None:
        settings.watermark_opacity = update.watermark_opacity
        changed["watermark_opacity"] = update.watermark_opacity
        _persist_env("watermark_opacity", str(update.watermark_opacity))
    if update.enable_intro_card is not None:
        settings.enable_intro_card = update.enable_intro_card
        changed["enable_intro_card"] = update.enable_intro_card
        _persist_env("enable_intro_card", str(update.enable_intro_card).lower())
    if update.enable_outro_card is not None:
        settings.enable_outro_card = update.enable_outro_card
        changed["enable_outro_card"] = update.enable_outro_card
        _persist_env("enable_outro_card", str(update.enable_outro_card).lower())
    if update.outro_card_text is not None:
        settings.outro_card_text = update.outro_card_text
        changed["outro_card_text"] = update.outro_card_text
        _persist_env("outro_card_text", update.outro_card_text)
    if update.scene_engine is not None:
        settings.scene_engine = update.scene_engine
        changed["scene_engine"] = update.scene_engine
        _persist_env("scene_engine", update.scene_engine)
    if update.html_template is not None:
        settings.html_template = update.html_template
        changed["html_template"] = update.html_template
        _persist_env("html_template", update.html_template)

    return {"message": "Settings updated", "changed": changed}
