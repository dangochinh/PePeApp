"""
Settings API — Toggle TTS engine, video model, and other config.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from config import settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    tts_engine: Optional[str] = None
    video_model: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    use_cloud_ai: Optional[bool] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
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

@router.get("/")
async def get_settings():
    """Get current settings."""
    return {
        "tts_engine": settings.tts_engine,
        "video_model": settings.video_model,
        "ollama_model": settings.ollama_model,
        "ollama_base_url": settings.ollama_base_url,
        "use_cloud_ai": settings.use_cloud_ai,
        "openai_api_key": settings.openai_api_key,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "comfyui_base_url": settings.comfyui_base_url,
        "tts_voice": settings.tts_voice,
        "scenes_per_video": settings.scenes_per_video,
        "available_tts_engines": ["faster-qwen3-tts", "piper"],
        "available_video_models": ["svd_xt", "cogvideox", "animatediff"],
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

    # Existing...
    if update.use_cloud_ai is not None:
        settings.use_cloud_ai = update.use_cloud_ai
        changed["use_cloud_ai"] = update.use_cloud_ai
    if update.openai_api_key is not None:
        settings.openai_api_key = update.openai_api_key
        changed["openai_api_key"] = update.openai_api_key
    if update.openai_base_url is not None:
        settings.openai_base_url = update.openai_base_url
        changed["openai_base_url"] = update.openai_base_url
    if update.openai_model is not None:
        settings.openai_model = update.openai_model
        changed["openai_model"] = update.openai_model
    if update.ollama_base_url is not None:
        settings.ollama_base_url = update.ollama_base_url
        changed["ollama_base_url"] = update.ollama_base_url
    if update.comfyui_base_url is not None:
        settings.comfyui_base_url = update.comfyui_base_url
        changed["comfyui_base_url"] = update.comfyui_base_url
    
    # Existing...
    if update.tts_engine is not None:
        settings.tts_engine = update.tts_engine
        changed["tts_engine"] = update.tts_engine
    if update.video_model is not None:
        settings.video_model = update.video_model
        changed["video_model"] = update.video_model
    if update.ollama_model is not None:
        settings.ollama_model = update.ollama_model
        changed["ollama_model"] = update.ollama_model

    return {"message": "Settings updated", "changed": changed}
