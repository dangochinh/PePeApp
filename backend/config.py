from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
CONFIG_DIR = BASE_DIR / "config"


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8888
    debug: bool = True

    # Ollama / Local AI
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # Cloud AI (OpenAI / DeepSeek Cloud)
    use_cloud_ai: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # ComfyUI
    comfyui_base_url: str = "http://127.0.0.1:8188"
    video_model: str = "svd_xt"  # svd_xt | cogvideox | animatediff

    # TTS
    tts_engine: str = "edge-tts"  # faster-qwen3-tts | piper | edge-tts
    tts_model_path: str = ""
    tts_ref_audio: str = ""
    tts_voice: str = "default"

    # Video
    output_format: str = "vertical"  # vertical (9:16) | horizontal (16:9)
    scenes_per_video: int = 6
    scene_duration_seconds: int = 10

    # Research
    search_results_per_topic: int = 5

    # Social Publishing (Placeholders/API Keys)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
    
    tiktok_access_token: str = ""
    tiktok_session_id: str = ""
    
    facebook_access_token: str = ""
    facebook_page_id: str = ""

    class Config:
        env_file = ".env"
        env_prefix = "PEPE_"


settings = Settings()
