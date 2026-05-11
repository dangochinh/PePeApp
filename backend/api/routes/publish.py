"""
Publish API — AI metadata generation + mock publish to social platforms.
"""
import json
import time
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import PROJECTS_DIR

router = APIRouter()


class PublishRequest(BaseModel):
    title: str
    description: str
    hashtags: list[str]
    platforms: list[str]  # "youtube" | "tiktok" | "facebook"


@router.post("/{project_name}/generate-metadata")
async def generate_metadata(project_name: str):
    """Use AI to generate title, description, and hashtags from the project script."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    scripts = []
    for f in sorted(project_dir.glob("script_*.json")):
        scripts.append(json.loads(f.read_text(encoding="utf-8")))
    if not scripts:
        raise HTTPException(status_code=400, detail="No script found — run pipeline first")

    script = scripts[0]
    topic = script.get("topic", "") or script.get("title", "")
    scenes = script.get("scenes", [])
    narrations = " ".join(s.get("narration_text", "") for s in scenes)[:600]

    prompt = f"""Bạn là chuyên gia marketing mạng xã hội viral.
Chủ đề video: "{topic}"
Nội dung: {narrations}

Tạo metadata cực kỳ hấp dẫn để video đạt views tối đa trên YouTube Shorts / TikTok / Facebook Reels.

Trả về ĐÚNG JSON này, không giải thích gì thêm:
{{
  "title": "Tiêu đề kéo view, tối đa 80 ký tự, dùng số và emoji phù hợp, tiếng Việt",
  "description": "Mô tả 3-4 câu tiếng Việt: câu 1 hook, câu 2-3 nội dung chính, câu 4 call-to-action. Kết bằng lời kêu gọi comment/share.",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"]
}}

Hashtags: 10 tag, không có dấu #, mix tiếng Việt và tiếng Anh, 5 tag chuyên ngành + 5 tag viral chung (shorts, viral, trending, fyp, xuhuong)."""

    from worker.ai_utils import call_ai
    try:
        raw = await call_ai(prompt, "You are a viral social media marketing expert.", timeout=60.0)
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        # Sanitize
        data["hashtags"] = [h.lstrip("#").strip() for h in data.get("hashtags", []) if h.strip()][:10]
        return data
    except Exception as e:
        print(f"[publish] AI metadata failed: {e}")
        slug = topic.replace(" ", "")[:20]
        return {
            "title": f"🔥 {topic[:70]}",
            "description": f"Cập nhật mới nhất về {topic}! Xem ngay để không bỏ lỡ thông tin quan trọng. 👇 Comment ý kiến của bạn bên dưới nhé!",
            "hashtags": [slug, "Vietnam", "TinTuc", "KienThuc", "HocHoi", "shorts", "viral", "trending", "fyp", "xuhuong"],
        }


@router.post("/{project_name}/publish")
async def publish_video(project_name: str, req: PublishRequest):
    """Mock publish final.mp4 to selected social platforms."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    final_path = project_dir / "final.mp4"
    if not final_path.exists():
        raise HTTPException(status_code=400, detail="final.mp4 not found — assemble the video first")

    file_size_mb = round(final_path.stat().st_size / 1024 / 1024, 1)
    ts = int(time.time())
    results: dict = {}

    PLATFORM_META = {
        "youtube": {
            "name": "YouTube Shorts",
            "icon": "🎬",
            "color": "#FF0000",
            "id_prefix": "yt",
            "url_tpl": "https://youtube.com/shorts/{vid}",
            "max_mb": 256,
        },
        "tiktok": {
            "name": "TikTok",
            "icon": "📱",
            "color": "#00F2EA",
            "id_prefix": "tt",
            "url_tpl": "https://tiktok.com/@channel/video/{vid}",
            "max_mb": 287,
        },
        "facebook": {
            "name": "Facebook Reels",
            "icon": "💙",
            "color": "#1877F2",
            "id_prefix": "fb",
            "url_tpl": "https://facebook.com/reel/{vid}",
            "max_mb": 1024,
        },
    }

    for platform in req.platforms:
        await asyncio.sleep(0.4)  # simulate network latency
        meta = PLATFORM_META.get(platform)
        if not meta:
            continue
        video_id = f"{meta['id_prefix']}_{ts}_{platform[:2]}"
        results[platform] = {
            "status": "success",
            "platform": meta["name"],
            "icon": meta["icon"],
            "video_id": video_id,
            "url": meta["url_tpl"].format(vid=video_id),
            "file_size_mb": file_size_mb,
            "title": req.title,
            "message": f"✅ {meta['name']}: uploaded {file_size_mb} MB — mock",
        }

    return {
        "project": project_name,
        "title": req.title,
        "platforms_published": len(results),
        "results": results,
    }
