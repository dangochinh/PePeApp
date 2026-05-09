from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    SCRIPTING = "scripting"
    RENDERING = "rendering"
    TTS = "tts"
    ASSEMBLING = "assembling"
    PREVIEW = "preview"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoModel(str, Enum):
    SVD_XT = "svd_xt"
    COGVIDEOX = "cogvideox"
    ANIMATEDIFF = "animatediff"


class TTSEngine(str, Enum):
    FASTER_QWEN3 = "faster-qwen3-tts"
    PIPER = "piper"


class Scene(BaseModel):
    scene_number: int
    duration_seconds: int = 10
    visual_prompt: str
    narration_text: str
    subtitle_text: str
    clip_path: Optional[str] = None # Legacy/Mixed
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    reference_image_path: Optional[str] = None
    status: str = "pending"


class Script(BaseModel):
    title: str
    topic: str
    source_url: Optional[str] = None
    source_summary: str
    scenes: list[Scene]


class JobCreateRequest(BaseModel):
    topic: str
    video_model: Optional[VideoModel] = None
    tts_engine: Optional[TTSEngine] = None
    auto_publish: bool = False


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    progress_pct: int = 0
    current_step: str = ""
    logs: list[str] = []
    error: Optional[str] = None
    project_dir: Optional[str] = None
    scripts: Optional[list[Script]] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


class PublishTarget(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"


class PublishRequest(BaseModel):
    job_id: str
    targets: list[PublishTarget]
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
