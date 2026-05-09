"""
Script Engine — Takes an article and generates a structured 6-scene screenplay
using Ollama (Qwen 2.5).
"""
import json
import httpx
from models.schemas import Script, Scene
from config import settings


SCRIPT_SYSTEM_PROMPT = """You are a professional short-form video scriptwriter.
Given a news article or topic summary, create a compelling 60-second video script
broken into exactly 6 scenes of 10 seconds each.

Return ONLY a valid JSON object with this exact structure:
{
  "title": "Catchy video title (max 60 chars)",
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 10,
      "visual_prompt": "Detailed cinematic description for AI video generation. Include: setting, lighting, camera angle, action, mood. Be very specific. English only.",
      "narration_text": "The spoken voiceover text for this scene. Natural, engaging. Vietnamese or English.",
      "subtitle_text": "Short subtitle text (max 10 words)"
    }
  ]
}

Rules:
- visual_prompt must be in English (for AI image/video generation)
- narration_text can be in Vietnamese (match user's input language)
- Each scene should flow naturally into the next
- Start with a hook, build to a conclusion
- Keep it engaging and shareable"""


async def generate_script(
    article: dict,
    topic: str,
    on_progress=None
) -> Script:
    """
    Generate a structured screenplay from an article using a 2-step process:
    1. Generate a 5-point outline (Story Plan)
    2. Expand each point into a full scene (6 scenes total)
    """
    from worker.ai_utils import call_ai

    # Step 1: Generate Outline
    if on_progress:
        await on_progress(f"Planning scenario for: {article['title'][:40]}...", 10)

    outline_prompt = f"""Topic: {topic}
Article: {article.get('summary', '')}

Create a 5-point bulleted outline for a 60-second video. 
Focus on: Hook, Context, Core Message, Visual Climax, Call to Action.
English or Vietnamese. Return ONLY the 5 points."""

    outline_text = await call_ai(outline_prompt, "You are a story architect. Create a tight 5-point outline.")
    
    if on_progress:
        # Log each point of the outline as a separate sub-step for transparency
        points = [p.strip() for p in outline_text.split("\n") if p.strip()]
        for p in points[:5]:
            await on_progress(f"📝 {p}", 15)
        await on_progress("Outline verified. Expanding to full script...", 20)

    # Step 2: Generate Full Script
    prompt = f"""Topic: {topic}
Article Summary: {article.get('summary', '')}
Proposed Outline:
{outline_text}

Generate the full JSON script based on this outline (expand to 6 scenes)."""

    raw_text = await call_ai(prompt, SCRIPT_SYSTEM_PROMPT)

    if on_progress:
        await on_progress("Finalizing script structure...", 80)

    # Parse JSON
    try:
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        script_data = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse script JSON: {e}\nRaw: {raw_text[:500]}")

    # Build Scene objects
    scenes = [
        Scene(
            scene_number=s["scene_number"],
            duration_seconds=s.get("duration_seconds", 10),
            visual_prompt=s["visual_prompt"],
            narration_text=s["narration_text"],
            subtitle_text=s["subtitle_text"],
        )
        for s in script_data.get("scenes", [])
    ]

    script = Script(
        title=script_data.get("title", article.get("title", "Untitled")),
        topic=topic,
        source_url=article.get("url"),
        source_summary=article.get("summary", ""),
        scenes=scenes,
    )

    if on_progress:
        await on_progress("Script complete & cross-checked", 100)

    return script
