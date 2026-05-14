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
    ollama_model: str = "qwen2.5:32b"

    # Cloud AI (OpenAI / DeepSeek Cloud)
    use_cloud_ai: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Anthropic / Claude Cloud
    anthropic_api_key: str = ""
    cloud_ai_api_key: str = ""   # alias: PEPE_CLOUD_AI_API_KEY also works
    claude_model: str = "claude-haiku-4-5-20251001"

    # Draw Things (image generation)
    draw_things_base_url: str = "http://127.0.0.1:7860"

    # ComfyUI (I2V — image → video, optional)
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_checkpoint: str = "illustriousXL.safetensors"
    comfyui_motion_module: str = "mm_sdxl_v10_beta.ckpt"
    comfyui_i2v_frames: int = 16   # animation frames (8fps × 16 = 2s loop)
    comfyui_i2v_fps: int = 8
    comfyui_i2v_denoise: float = 0.70  # how much to animate (0.5=subtle, 0.85=wild)

    # TTS
    tts_engine: str = "vieneu"  # vieneu | edge-tts | piper | faster-qwen3-tts | elevenlabs
    tts_model_path: str = ""
    tts_ref_audio: str = ""
    tts_voice: str = "default"

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"   # Adam — multilingual, good for narration
    elevenlabs_model: str = "eleven_turbo_v2_5"           # fast, multilingual incl. Vietnamese

    # Video
    output_format: str = "vertical"  # vertical (9:16) | horizontal (16:9)
    scenes_per_video: int = 6
    scene_duration_seconds: int = 10

    # Image generation quality
    draw_things_steps: int = 20       # 10–50; more = better quality, slower
    draw_things_cfg: float = 5.0      # 1–12; higher = more prompt adherence
    image_style: str = "cinematic"    # cinematic | anime | watercolor | oil_painting | neon | photorealistic

    # Assembly
    transition_style: str = "auto"    # auto (random) | fade | slideleft | slideup | wipeleft | dissolve | pixelize
    ken_burns: bool = True            # Ken Burns zoom-pan effect on PNG still clips
    color_grade: str = "none"         # none | warm | cool | noir | vibrant | muted | golden

    # Background music
    bg_music_path: str = ""           # path to .mp3/.wav file, empty = disabled
    bg_music_volume: float = 0.35     # 0.0–1.0 background level; sidechaincompress ducks it under voice

    # Phase 5 — Visual Consistency
    enable_upscale: bool = True            # Upscale PNG to 1080x1920 (Real-ESRGAN if binary found, else PIL Lanczos)
    use_img2img_ref: bool = False          # Pass scene n-1 image as img2img reference for scene n
    img2img_denoising: float = 0.35       # img2img denoising strength (0.2=very similar, 0.6=more creative)

    # Phase 6 — Text-to-Video
    t2v_engine: str = "none"              # none | comfyui_wan | replicate
    replicate_api_key: str = ""
    replicate_t2v_model: str = "wan-ai/wan2.1-i2v-480p"  # Replicate model slug
    wan_model_name: str = "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors"  # ComfyUI Wan2.1 model file
    t2v_num_frames: int = 81              # frames (16fps × 81 ≈ 5s)
    t2v_fps: int = 16

    # Branding overlay
    watermark_path: str = ""               # path to PNG logo, empty = disabled
    watermark_position: str = "topright"   # topleft | topright | bottomleft | bottomright
    watermark_opacity: float = 0.7         # 0.0–1.0
    enable_intro_card: bool = False        # prepend 3-second title card
    enable_outro_card: bool = False        # append 3-second CTA card
    outro_card_text: str = "Like · Share · Follow!"

    # Scene Engine (2.0)
    scene_engine: str = "drawthings"  # drawthings | html
    html_template: str = "auto"       # auto | dark | gradient | minimal | bold | news | cinematic | stats | how
    html_animated: bool = True        # True = record animated MP4 via Playwright; False = static PNG
    pexels_api_key: str = ""          # Pexels API key for background photos/videos (free at pexels.com/api)
    html_use_bg_image: bool = False   # Fetch Pexels photo as scene background (requires pexels_api_key)
    pexels_video_enable: bool = True  # Use Pexels VIDEO backgrounds (looping, played during Playwright recording)

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
        extra = "ignore"


settings = Settings()
