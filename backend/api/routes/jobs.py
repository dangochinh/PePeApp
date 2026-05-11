"""
Jobs API — Create, list, and manage video generation jobs.
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from models.schemas import JobCreateRequest, JobProgress, JobStatus
from worker.pipeline import run_pipeline, get_job, list_jobs, _jobs, _pipeline_tasks

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_job(req: JobCreateRequest, background_tasks: BackgroundTasks):
    """Create a new video generation job from a topic prompt."""
    import uuid
    job_id = str(uuid.uuid4())[:8]

    from worker.pipeline import init_pipeline
    from pathlib import Path
    job_id, job = init_pipeline(req.topic, job_id)
    project_name = Path(job.project_dir).name

    # BackgroundTasks runs strictly after the HTTP response is sent — no deadlock risk.
    # The task grabs its own asyncio.Task ref via current_task() so cancel still works.
    background_tasks.add_task(_run_job_async, req.topic, job_id, req.auto_publish, req.script_style)

    return {
        "job_id": job_id,
        "project_name": project_name,
        "topic": req.topic,
        "status": "pending",
        "message": f"Job created. Research starting for: {req.topic}"
    }


async def _run_job_async(topic: str, job_id: str, auto_publish: bool, script_style: str = "4wh"):
    """Wrapper to run pipeline as a background task."""
    # Grab the asyncio Task reference so cancel_job can call task.cancel() on it.
    task = asyncio.current_task()
    if task:
        _pipeline_tasks[job_id] = task
    try:
        from api.app import broadcast_progress
        await run_pipeline(
            topic=topic,
            job_id=job_id,
            auto_publish=auto_publish,
            ws_callback=broadcast_progress,
            script_style=script_style,
        )
    except asyncio.CancelledError:
        pass  # pipeline already handled status update + re-raised; task is done
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
    finally:
        _pipeline_tasks.pop(job_id, None)


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

    # Cancel the asyncio Task immediately — injects CancelledError at current await point
    task = _pipeline_tasks.get(job_id)
    if task and not task.done():
        task.cancel()
    else:
        # No live task — just mark as cancelled directly
        from datetime import datetime
        job.status = JobStatus.CANCELLED
        job.current_step = "🛑 Stopped"
        job.logs.append("🛑 Stopped by user")
        job.updated_at = datetime.now()
        from api.app import broadcast_progress
        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    return {"job_id": job_id, "status": "cancelling"}


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
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.scripts:
        raise HTTPException(status_code=400, detail="No scripts found — use /continue to run the full pipeline first")

    background_tasks.add_task(_rerun_render_only_task, job_id)
    return {"message": "Full render rerun queued"}


@router.post("/{job_id}/assemble")
async def assemble_job(job_id: str, background_tasks: BackgroundTasks):
    """Assemble final video from whatever clips + audio are currently available."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.scripts:
        raise HTTPException(status_code=400, detail="No script found — run pipeline first")
    background_tasks.add_task(_assemble_task, job_id)
    return {"message": "Assembly queued", "job_id": job_id}


async def _assemble_task(job_id: str):
    from api.app import broadcast_progress
    from worker.assembler import merge_clips, generate_srt
    from pathlib import Path
    from datetime import datetime

    job = get_job(job_id)
    project_dir = Path(job.project_dir)
    script = job.scripts[0]
    scenes_data = [s.model_dump() for s in script.scenes]

    async def upd(step: str, pct: int):
        job.current_step = step
        job.progress_pct = pct
        job.updated_at = datetime.now()
        if not job.logs or job.logs[-1] != step:
            job.logs.append(step)
        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    try:
        await upd("🎬 Assembling final video...", 80)
        subs_dir = project_dir / "subtitles"
        subs_dir.mkdir(exist_ok=True)
        await generate_srt(scenes_data, subs_dir / "full.srt", audio_dir=project_dir / "audio")
        final_path = await merge_clips(project_dir, scenes_data, on_progress=upd)
        job.status = __import__("models.schemas", fromlist=["JobStatus"]).JobStatus.COMPLETED
        job.has_final = True
        await upd(f"✅ Final video ready: {Path(final_path).name}", 100)
    except Exception as e:
        import traceback
        print(f"[assemble] {job_id} failed:\n{traceback.format_exc()}")
        await upd(f"❌ Assembly failed: {str(e)[:120]}", job.progress_pct)


@router.post("/{job_id}/continue")
async def continue_job(job_id: str, background_tasks: BackgroundTasks):
    """Resume a partially-completed or failed job from its last checkpoint."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    background_tasks.add_task(_continue_job_async, job_id)
    return {"message": "Pipeline resuming from last completed step", "job_id": job_id}


async def _continue_job_async(job_id: str):
    """Background task to continue a paused/failed pipeline."""
    try:
        from api.app import broadcast_progress
        from worker.pipeline import continue_pipeline
        await continue_pipeline(job_id, ws_callback=broadcast_progress)
    except Exception as e:
        print(f"Continue job {job_id} failed: {e}")


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
            result_path = await generate_clip(
                visual_prompt=scene.visual_prompt,
                output_path=output_path,
                scene_number=i + 1,
                mode="video",
                on_progress=update_progress
            )
            scene.video_path = result_path
            scene.status = "rendered"
        except Exception as e:
            print(f"Failed to render scene {i+1}: {e}")
            continue

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    job.current_step = "All scenes re-rendered successfully!"
    await broadcast_progress(job.model_dump(mode="json", exclude_none=True))


def _find_existing_image(scene, expected_path) -> str | None:
    """Return path to existing image for a scene, checking state then disk."""
    from pathlib import Path
    for p in (scene.image_path, scene.clip_path, str(expected_path)):
        if p and Path(p).exists():
            return p
    # Also scan for any variant extension at the same location
    base = Path(str(expected_path)).with_suffix("")
    for ext in ("png", "jpg", "jpeg"):
        candidate = base.with_suffix(f".{ext}")
        if candidate.exists():
            return str(candidate)
    return None


async def _render_manual_task(job_id: str, scene, scene_idx: int, mode: str):
    """Task for manual rendering (audio, image, or video)."""
    from api.app import broadcast_progress
    from worker.video_engine import generate_clip, generate_video_from_image
    from worker.tts_engine import generate_audio
    from pathlib import Path

    job = get_job(job_id)
    project_dir = Path(job.project_dir)

    clips_dir = project_dir / "clips"
    audio_dir = project_dir / "audio"
    prefix = f"scene_{scene_idx + 1:02d}"

    if mode == "audio":
        output_path = audio_dir / f"{prefix}.wav"
    else:
        # For both image and video, Stage 1 always produces a PNG.
        output_path = clips_dir / f"{prefix}.png"

    mode_label = {"audio": "🎤 TTS", "image": "🖼️ Image", "video": "🎬 Video"}[mode]
    scene_label = f"Scene {scene_idx + 1}"

    def log(msg: str):
        if not job.logs:
            job.logs = []
        if not job.logs or job.logs[-1] != msg:
            job.logs.append(msg)

    async def update_progress(step: str, pct: int):
        job.current_step = f"{mode_label} {scene_label}: {step}"
        job.progress_pct = pct
        log(job.current_step)
        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    log(f"▶ {mode_label} {scene_label}: starting...")
    await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    try:
        if mode == "audio":
            await generate_audio(
                text=scene.narration_text,
                output_path=output_path,
                scene_number=scene_idx + 1,
                on_progress=update_progress,
            )
            scene.audio_path = str(output_path)

        elif mode == "image":
            existing_png = _find_existing_image(scene, output_path)
            if existing_png:
                scene.clip_path = existing_png
                scene.image_path = existing_png
                log(f"ℹ️ Reusing existing image: {Path(existing_png).name}")
                await update_progress("Already rendered", 100)
            else:
                result_path = await generate_clip(
                    visual_prompt=scene.visual_prompt,
                    output_path=output_path,
                    scene_number=scene_idx + 1,
                    mode="image",
                    on_progress=update_progress,
                    seed=scene.seed,
                    image_style=scene.image_style,
                )
                # Overlay subtitle onto PNG after render via transparent overlay
                subtitle = (scene.subtitle_text or "").strip()
                if subtitle and result_path:
                    from worker.assembler import _create_subtitle_overlay, _run_ffmpeg
                    src = Path(result_path)
                    ovl_png = src.with_stem(src.stem + "_ovl")
                    sub_out = src.with_stem(src.stem + "_sub")
                    try:
                        from PIL import Image as _PI
                        with _PI.open(src) as _im:
                            _W, _H = _im.size
                    except Exception:
                        _W, _H = 1080, 1920
                    _create_subtitle_overlay(ovl_png, subtitle, _W, _H)
                    await _run_ffmpeg([
                        "ffmpeg", "-y", "-i", str(src), "-i", str(ovl_png),
                        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
                        "-map", "[v]", "-c:v", "png", str(sub_out),
                    ])
                    ovl_png.unlink(missing_ok=True)
                    result_path = str(sub_out)
                scene.clip_path = result_path
                scene.image_path = result_path

        else:  # video
            # Stage 0 — TTS audio if missing
            audio_path = audio_dir / f"{prefix}.wav"
            existing_audio = scene.audio_path if scene.audio_path and Path(scene.audio_path).exists() else (str(audio_path) if audio_path.exists() else None)
            if existing_audio:
                scene.audio_path = existing_audio
                log(f"ℹ️ Reusing existing audio: {Path(existing_audio).name}")
            else:
                await update_progress("Generating TTS audio...", 5)
                await generate_audio(
                    text=scene.narration_text,
                    output_path=audio_path,
                    scene_number=scene_idx + 1,
                    on_progress=lambda s, p: update_progress(f"TTS: {s}", int(p * 0.2)),
                )
                scene.audio_path = str(audio_path)
                log(f"✅ TTS audio generated")

            # Stage 1 — Use existing PNG if available, otherwise generate via Draw Things
            existing_png = _find_existing_image(scene, output_path)
            if existing_png:
                png_path = existing_png
                scene.clip_path = png_path
                scene.image_path = png_path
                log(f"ℹ️ Reusing existing image: {Path(png_path).name}")
                await update_progress("Reusing existing image", 25)
            else:
                png_path = await generate_clip(
                    visual_prompt=scene.visual_prompt,
                    output_path=output_path,
                    scene_number=scene_idx + 1,
                    mode="image",
                    on_progress=update_progress,
                    seed=scene.seed,
                    image_style=scene.image_style,
                )
                scene.clip_path = png_path
                scene.image_path = png_path

            # Stage 2 — Animate PNG → MP4 via ComfyUI (optional)
            mp4_path = await generate_video_from_image(
                image_path=Path(png_path),
                visual_prompt=scene.visual_prompt,
                output_path=clips_dir / f"{prefix}.mp4",
                scene_number=scene_idx + 1,
                on_progress=update_progress,
            )
            if mp4_path:
                scene.video_path = mp4_path
            else:
                # ComfyUI offline — surface the PNG as a still-video placeholder
                scene.video_path = None
                log(f"ℹ️ ComfyUI offline — image saved, no MP4 generated")

        log(f"✅ {mode_label} {scene_label}: done")
        job.current_step = f"✅ {mode_label} {scene_label}: done"

        # Persist updated scene paths to disk so they survive server restart
        if job.scripts and job.project_dir:
            from pathlib import Path as _Path
            script_path = _Path(job.project_dir) / "script_01.json"
            script_path.write_text(job.scripts[0].model_dump_json(indent=2), encoding="utf-8")

        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

    except Exception as e:
        import traceback
        err = str(e) or f"{type(e).__name__} (no message)"
        full_err = traceback.format_exc()
        print(f"[render_manual] {mode_label} {scene_label} FAILED:\n{full_err}")
        log(f"❌ {mode_label} {scene_label}: {err[:300]}")
        job.current_step = f"❌ {mode_label} {scene_label}: {err[:120]}"
        await broadcast_progress(job.model_dump(mode="json", exclude_none=True))

