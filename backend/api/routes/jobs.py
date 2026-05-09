"""
Jobs API — Create, list, and manage video generation jobs.
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from models.schemas import JobCreateRequest, JobProgress, JobStatus
from worker.pipeline import run_pipeline, get_job, list_jobs, _jobs

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_job(req: JobCreateRequest, background_tasks: BackgroundTasks):
    """Create a new video generation job from a topic prompt."""
    import uuid
    job_id = str(uuid.uuid4())[:8]

    # Pre-initialize job synchronously so it shows up in /list immediately
    from worker.pipeline import init_pipeline
    from pathlib import Path
    job_id, job = init_pipeline(req.topic, job_id)
    project_name = Path(job.project_dir).name
    
    # Start pipeline in background
    background_tasks.add_task(
        _run_job_async, req.topic, job_id, req.auto_publish
    )

    return {
        "job_id": job_id,
        "project_name": project_name,
        "topic": req.topic,
        "status": "pending",
        "message": f"Job created. Research starting for: {req.topic}"
    }


async def _run_job_async(topic: str, job_id: str, auto_publish: bool):
    """Wrapper to run pipeline in background task."""
    try:
        # Import broadcast function from app module
        from api.app import broadcast_progress
        await run_pipeline(
            topic=topic,
            job_id=job_id,
            auto_publish=auto_publish,
            ws_callback=broadcast_progress,
        )
    except Exception as e:
        print(f"Job {job_id} failed: {e}")


@router.get("/list")
async def get_all_jobs():
    """List all jobs, newest first."""
    jobs = list_jobs()
    return [j.model_dump(mode="json", exclude_none=True) for j in jobs]


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json", exclude_none=True)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.FAILED
    job.error = "Cancelled by user"
    return {"job_id": job_id, "status": "cancelled"}


@router.post("/{job_id}/render-audio/{scene_idx}")
async def render_audio_manual(job_id: str, scene_idx: int, background_tasks: BackgroundTasks):
    """Manually generate voiceover for a single scene."""
    job = get_job(job_id)
    if not job or not job.scripts:
        raise HTTPException(status_code=404, detail="Job or scripts not found")
    
    script = job.scripts[0]
    if scene_idx >= len(script.scenes):
        raise HTTPException(status_code=400, detail="Invalid scene index")
    
    scene = script.scenes[scene_idx]
    background_tasks.add_task(_render_manual_task, job_id, scene, scene_idx, "audio")
    return {"message": "Audio generation queued"}


@router.post("/{job_id}/render-scene/{scene_idx}")
async def render_scene_manual(job_id: str, scene_idx: int, background_tasks: BackgroundTasks):
    """Manually render a single scene (image)."""
    job = get_job(job_id)
    if not job or not job.scripts:
        raise HTTPException(status_code=404, detail="Job or scripts not found")
    
    script = job.scripts[0]  # Primary script
    if scene_idx >= len(script.scenes):
        raise HTTPException(status_code=400, detail="Invalid scene index")
    
    scene = script.scenes[scene_idx]
    background_tasks.add_task(_render_manual_task, job_id, scene, scene_idx, "image")
    return {"message": "Image render queued"}


@router.post("/{job_id}/render-video/{scene_idx}")
async def render_video_manual(job_id: str, scene_idx: int, background_tasks: BackgroundTasks):
    """Manually render a single scene to video (10s)."""
    job = get_job(job_id)
    if not job or not job.scripts:
        raise HTTPException(status_code=404, detail="Job or scripts not found")
    
    script = job.scripts[0]
    if scene_idx >= len(script.scenes):
        raise HTTPException(status_code=400, detail="Invalid scene index")
    
    scene = script.scenes[scene_idx]
    background_tasks.add_task(_render_manual_task, job_id, scene, scene_idx, "video")
    return {"message": "Video render queued"}


@router.post("/{job_id}/rerun")
async def rerun_job(job_id: str, background_tasks: BackgroundTasks):
    """Rerun the rendering phase only, keeping existing topic and script."""
    job = get_job(job_id)
    if not job or not job.scripts:
        raise HTTPException(status_code=404, detail="Job or scripts not found")
    
    background_tasks.add_task(_rerun_render_only_task, job_id)
    return {"message": "Full render rerun queued"}


async def _rerun_render_only_task(job_id: str):
    """Background task to re-render all scenes in a job."""
    from api.app import broadcast_progress
    from worker.video_engine import generate_clip
    from pathlib import Path
    
    job = get_job(job_id)
    script = job.scripts[0]
    project_dir = Path(job.project_dir)
    num_scenes = len(script.scenes)

    for i, scene in enumerate(script.scenes):
        output_path = project_dir / "clips" / f"scene_{i+1:02d}.mp4"
        
        async def update_progress(step: str, pct: int):
            # Global progress is a mix of current scene index and scene-specific progress
            global_pct = int(((i / num_scenes) * 100) + (pct / num_scenes))
            job.current_step = f"Rerunning Render {i+1}/{num_scenes}: {step}"
            job.progress_pct = global_pct
            await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

        try:
            await generate_clip(
                visual_prompt=scene.visual_prompt,
                output_path=output_path,
                scene_number=i + 1,
                mode="video",
                on_progress=update_progress
            )
            scene.video_path = str(output_path)
            scene.status = "rendered"
        except Exception as e:
            print(f"Failed to render scene {i+1}: {e}")
            continue

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    job.current_step = "All scenes re-rendered successfully!"
    await broadcast_progress(job.model_dump(mode="json", exclude_none=True))


async def _render_manual_task(job_id: str, scene, scene_idx: int, mode: str):
    """Task for manual rendering (audio, image, or video)."""
    from api.app import broadcast_progress
    from worker.video_engine import generate_clip
    from worker.tts_engine import generate_audio
    from pathlib import Path
    
    job = get_job(job_id)
    project_dir = Path(job.project_dir)
    
    if mode == "audio":
        ext = "wav"
        output_path = project_dir / "audio" / f"scene_{scene_idx+1:02d}.{ext}"
    else:
        ext = "png" if mode == "image" else "mp4"
        output_path = project_dir / "clips" / f"scene_{scene_idx+1:02d}.{ext}"
    
    async def update_progress(step: str, pct: int):
        job.current_step = f"Manual {mode}: {step}"
        job.progress_pct = pct
        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    try:
        if mode == "audio":
            await generate_audio(
                text=scene.narration_text,
                output_path=output_path,
                scene_number=scene_idx + 1,
                on_progress=update_progress
            )
            scene.audio_path = str(output_path)
        else:
            await generate_clip(
                visual_prompt=scene.visual_prompt,
                output_path=output_path,
                scene_number=scene_idx + 1,
                mode=mode,
                on_progress=update_progress
            )
            if mode == "image":
                scene.clip_path = str(output_path)
            else:
                scene.video_path = str(output_path)
        
        await update_progress(f"{mode.capitalize()} done!", 100)
    except Exception as e:
        await update_progress(f"Failed: {e}", 0)

