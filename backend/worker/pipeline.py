"""
Pipeline — Main orchestrator that ties all engines together.
Input: user topic → Output: final video ready for publishing.
Processes one video at a time (sequential).
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from config import settings, PROJECTS_DIR
from models.schemas import JobStatus, JobProgress
from worker.research_engine import research_topic
from worker.script_engine import generate_script
from worker.video_engine import generate_clip
from worker.tts_engine import generate_audio
from worker.assembler import merge_clips


# In-memory job store (will be replaced with SQLite later)
_jobs: dict[str, JobProgress] = {}


def get_job(job_id: str) -> JobProgress | None:
    if job_id in _jobs:
        return _jobs[job_id]
        
    # Attempt to load from disk for rerun/manual operations after restart
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir():
            # Check directory name as fallback job_id
            is_match = False
            meta = {}
            meta_path = d / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("job_id") == job_id:
                    is_match = True
            
            if not is_match and d.name == job_id:
                is_match = True
                
            if is_match:
                from models.schemas import Script
                # Reconstruct basic job
                job = JobProgress(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    progress_pct=100,
                    current_step="Loaded from history",
                    project_dir=str(d),
                )
                scripts = []
                for f in sorted(d.glob("script_*.json")):
                    scripts.append(Script.model_validate_json(f.read_text(encoding="utf-8")))
                if scripts:
                    job.scripts = scripts
                
                _jobs[job_id] = job
                return job
    return None


def list_jobs() -> list[JobProgress]:
    return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def init_pipeline(topic: str, job_id: str | None = None) -> tuple[str, JobProgress]:
    if not job_id:
        job_id = str(uuid.uuid4())[:8]

    # Create project directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c in "-_ " else "" for c in topic)[:40].strip().replace(" ", "-")
    project_name = f"{safe_topic}_{timestamp}"
    project_dir = PROJECTS_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Initialize job
    job = JobProgress(
        job_id=job_id,
        status=JobStatus.PENDING,
        project_dir=str(project_dir),
        current_step="Initializing...",
    )
    _jobs[job_id] = job

    # Save initial metadata
    metadata = {
        "job_id": job_id,
        "topic": topic,
        "project_name": project_name,
        "status": "in_progress",
        "created_at": datetime.now().isoformat(),
    }
    (project_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return job_id, job


async def run_pipeline(
    topic: str,
    job_id: str | None = None,
    auto_publish: bool = False,
    ws_callback=None,
) -> str:
    """
    Full pipeline: Topic → Research → Script → Video → TTS → Assemble
    """
    if job_id and job_id in _jobs:
        job = _jobs[job_id]
        project_dir = Path(job.project_dir)
        project_name = project_dir.name
    else:
        job_id, job = init_pipeline(topic, job_id)
        project_dir = Path(job.project_dir)
        project_name = project_dir.name

    async def update(status: JobStatus, step: str, pct: int):
        # Allow cancellation
        if job.status == JobStatus.FAILED:
            raise asyncio.CancelledError("Job was cancelled by the user.")
            
        job.status = status
        job.current_step = step
        job.progress_pct = pct
        job.updated_at = datetime.now()
        
        # Add to logs if it's a new unique step
        if not job.logs or job.logs[-1] != step:
            job.logs.append(step)
            
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))

    try:
        # ── Phase 1: Research ──
        async def research_update(step: str, pct: int):
            # Scale research progress from 5% to 15%
            scaled_pct = 5 + int(pct * 0.1)
            await update(JobStatus.RESEARCHING, step, scaled_pct)
            
        await update(JobStatus.RESEARCHING, "Starting research phase...", 5)
        articles = await research_topic(topic, on_progress=research_update)

        await update(JobStatus.RESEARCHING, f"🔍 Found {len(articles)} relevant articles:", 15)
        if len(articles) == 0:
            raise Exception("No articles found for this topic. Please try a different keyword or try again later.")
            
        for i, article in enumerate(articles):
            title = article.get('title', 'Untitled')
            await update(JobStatus.RESEARCHING, f"  └ [{i+1}] {title}", 15)

        # Save research results
        (project_dir / "research.json").write_text(
            json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── Phase 2: Generate scripts (one per article) ──
        await update(JobStatus.SCRIPTING, f"Starting script generation for {len(articles)} articles...", 15)
        scripts = []
        for i, article in enumerate(articles):
            title = article.get("title", "Untitled")
            
            async def script_update(step: str, pct: int):
                # Calculate the percentage within the 15% scripting phase slice
                base_pct = 15 + int((i) / len(articles) * 15)
                slice_pct = int(pct * (15 / len(articles)) / 100)
                await update(JobStatus.SCRIPTING, step, base_pct + slice_pct)

            await update(JobStatus.SCRIPTING, f"✍️ Generating script {i+1}/{len(articles)}: {title[:40]}...", 15 + int(i / len(articles) * 15))
            script = await generate_script(article, topic, on_progress=script_update)
            scripts.append(script)

            # Save individual script
            script_path = project_dir / f"script_{i+1:02d}.json"
            script_path.write_text(
                script.model_dump_json(indent=2), encoding="utf-8"
            )
            pct = 15 + int((i + 1) / len(articles) * 15)
            await update(JobStatus.SCRIPTING, f"✅ Script {i+1}/{len(articles)} completed ({len(script.scenes)} scenes)", pct)

        # For now, process the FIRST script as the primary video
        primary_script = scripts[0]
        job.scripts = scripts

        # ── Phase 3: Generate video clips ──
        await update(JobStatus.RENDERING, "Rendering video clips...", 30)
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(exist_ok=True)

        for i, scene in enumerate(primary_script.scenes):
            clip_path = clips_dir / f"scene_{i+1:02d}.png"  # Images first, ComfyUI output
            try:
                await generate_clip(
                    visual_prompt=scene.visual_prompt,
                    output_path=clip_path,
                    scene_number=i + 1,
                )
                scene.clip_path = str(clip_path)
                scene.status = "rendered"
            except Exception as e:
                scene.status = f"failed: {e}"

            pct = 30 + int((i + 1) / len(primary_script.scenes) * 25)
            await update(JobStatus.RENDERING, f"Clip {i+1}/{len(primary_script.scenes)}", pct)

        # ── Phase 4: Generate voiceover ──
        await update(JobStatus.TTS, "Generating voiceover...", 55)
        audio_dir = project_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        for i, scene in enumerate(primary_script.scenes):
            audio_path = audio_dir / f"scene_{i+1:02d}.wav"
            try:
                await generate_audio(
                    text=scene.narration_text,
                    output_path=audio_path,
                    scene_number=i + 1,
                )
                scene.audio_path = str(audio_path)
            except Exception as e:
                print(f"TTS warning scene {i+1}: {e}")

            pct = 55 + int((i + 1) / len(primary_script.scenes) * 15)
            await update(JobStatus.TTS, f"Audio {i+1}/{len(primary_script.scenes)}", pct)

        # ── Phase 5: Assemble final video ──
        await update(JobStatus.ASSEMBLING, "Merging everything...", 75)
        scenes_data = [s.model_dump() for s in primary_script.scenes]
        final_path = await merge_clips(project_dir, scenes_data)

        await update(JobStatus.PREVIEW, "Ready for preview!", 95)

        # Save final metadata
        metadata = {
            "job_id": job_id,
            "topic": topic,
            "project_name": project_name,
            "scripts_count": len(scripts),
            "primary_script": primary_script.title,
            "final_video": final_path,
            "status": "preview",
            "created_at": datetime.now().isoformat(),
        }
        (project_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        await update(JobStatus.PREVIEW, "Video ready for preview!", 100)
        return job_id

    except asyncio.CancelledError:
        job.status = JobStatus.FAILED
        job.error = "Cancelled by user"
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise
