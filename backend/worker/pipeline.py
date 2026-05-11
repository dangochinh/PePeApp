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
from worker.video_engine import generate_clip, generate_video_from_image, generate_t2v
from worker.tts_engine import generate_audio
from worker.assembler import merge_clips
from worker.service_control import start_draw_things, stop_draw_things, release_ollama_model


# In-memory job store (will be replaced with SQLite later)
_jobs: dict[str, JobProgress] = {}
_pipeline_tasks: dict[str, asyncio.Task] = {}


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
                    # Recover any asset paths from disk that weren't saved before restart
                    clips_dir = d / "clips"
                    audio_dir = d / "audio"
                    for script in scripts:
                        for scene in script.scenes:
                            n = scene.scene_number
                            if not scene.image_path and not scene.clip_path:
                                for suffix in ("_sub.png", ".png"):
                                    p = clips_dir / f"scene_{n:02d}{suffix}"
                                    if p.exists():
                                        scene.image_path = str(p)
                                        scene.clip_path = str(p)
                                        break
                            if not scene.video_path:
                                mp4 = clips_dir / f"scene_{n:02d}.mp4"
                                if mp4.exists():
                                    scene.video_path = str(mp4)
                            if not scene.audio_path:
                                wav = audio_dir / f"scene_{n:02d}.wav"
                                if wav.exists():
                                    scene.audio_path = str(wav)
                    job.has_final = (d / "final.mp4").exists()

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
    script_style: str = "4wh",
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
        if job.status in (JobStatus.CANCELLING, JobStatus.CANCELLED):
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

        if len(articles) == 0:
            raise Exception("No articles found for this topic. Please try a different keyword or try again later.")

        article = articles[0]
        await update(JobStatus.RESEARCHING, f"🔍 Selected article: {article.get('title', 'Untitled')}", 15)
        kps = article.get("key_points", [])
        for i, kp in enumerate(kps[:6]):
            await update(JobStatus.RESEARCHING, f"  └ [{i+1}] {kp}", 15)

        # Save research results
        (project_dir / "research.json").write_text(
            json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── Phase 2: Generate script (1 article → 6 scenes, streamed) ──
        article = articles[0]
        await update(JobStatus.SCRIPTING, f"✍️ Generating script from: {article.get('title', '')[:50]}...", 15)

        # Pre-populate an empty script so the Shot List panel appears immediately
        from models.schemas import Script as ScriptModel
        partial_script = ScriptModel(
            title=article.get("title", topic),
            topic=topic,
            source_url=article.get("url"),
            source_summary=article.get("summary", ""),
            scenes=[],
        )
        job.scripts = [partial_script]
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))

        async def script_update(step: str, pct: int):
            await update(JobStatus.SCRIPTING, step, 15 + int(pct * 0.15))

        script_path = project_dir / "script_01.json"

        async def on_scene_done(scene):
            partial_script.scenes.append(scene)
            job.scripts = [partial_script]
            # Persist partial script so crash/cancel doesn't lose completed scenes
            script_path.write_text(partial_script.model_dump_json(indent=2), encoding="utf-8")
            if ws_callback:
                await ws_callback(job.model_dump(mode="json", exclude_none=True))

        script = await generate_script(article, topic, on_progress=script_update, on_scene=on_scene_done, style=script_style, image_style=settings.image_style)
        scripts = [script]

        # Final write with complete script (on_scene_done already wrote partials)
        script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        await update(JobStatus.SCRIPTING, f"✅ Script done — {len(script.scenes)} scenes", 30)

        primary_script = script
        job.scripts = scripts

        # ── Phase 3a: Generate still images ──
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        total = len(primary_script.scenes)

        # Scripting is done — free Ollama model from RAM before image gen
        await update(JobStatus.RENDERING, "🧹 Releasing Ollama model from RAM...", 30)
        await release_ollama_model()

        if settings.scene_engine == "html":
            # HTML/CSS engine — no external service needed
            if settings.html_animated:
                from worker.html_engine import render_scene_to_video
                await update(JobStatus.RENDERING, f"🎬 HTML animated ({settings.html_template})...", 30)
                for i, scene in enumerate(primary_script.scenes):
                    mp4_path = clips_dir / f"scene_{i+1:02d}.mp4"
                    try:
                        async def _vid_prog(msg: str, _: int, _i=i):
                            await update(JobStatus.RENDERING, msg, 30 + int((_i / total) * 20))
                        result = await render_scene_to_video(
                            scene=scene,
                            title=primary_script.title,
                            output_path=mp4_path,
                            template=settings.html_template,
                            on_progress=_vid_prog,
                        )
                        scene.video_path = str(result)
                        scene.clip_path = str(result)
                        scene.status = "rendered"
                    except Exception as e:
                        scene.status = f"failed: {e}"
                        print(f"HTML video error scene {i+1}: {e}")
                    pct = 30 + int((i + 1) / total * 20)
                    await update(JobStatus.RENDERING, f"🎬 HTML scene {i+1}/{total} ready", pct)
            else:
                from worker.html_engine import render_scene_to_png
                await update(JobStatus.RENDERING, f"🎨 HTML engine ({settings.html_template} template)...", 30)
                for i, scene in enumerate(primary_script.scenes):
                    png_path = clips_dir / f"scene_{i+1:02d}.png"
                    try:
                        async def _html_prog(msg: str, _: int, _i=i):
                            await update(JobStatus.RENDERING, msg, 30 + int((_i / total) * 20))
                        result = await render_scene_to_png(
                            scene=scene,
                            title=primary_script.title,
                            output_path=png_path,
                            template=settings.html_template,
                            on_progress=_html_prog,
                        )
                        scene.image_path = str(result)
                        scene.clip_path = str(result)
                        scene.status = "image_ready"
                    except Exception as e:
                        scene.status = f"failed: {e}"
                        print(f"HTML render error scene {i+1}: {e}")
                    pct = 30 + int((i + 1) / total * 20)
                    await update(JobStatus.RENDERING, f"🖼️ HTML scene {i+1}/{total} ready", pct)
        else:
            # DrawThings engine
            async def _dt_status(msg: str):
                await update(JobStatus.RENDERING, f"🖼️ {msg}", 30)
            await update(JobStatus.RENDERING, "Starting Draw Things...", 30)
            await start_draw_things(on_status=_dt_status)

            prev_image: Path | None = None
            for i, scene in enumerate(primary_script.scenes):
                png_path = clips_dir / f"scene_{i+1:02d}.png"
                try:
                    result = await generate_clip(
                        visual_prompt=scene.visual_prompt,
                        output_path=png_path,
                        scene_number=i + 1,
                        seed=scene.seed,
                        image_style=scene.image_style,
                        ref_image_path=prev_image,
                    )
                    scene.image_path = result
                    scene.clip_path = result
                    scene.status = "image_ready"
                    prev_image = Path(result)
                except Exception as e:
                    scene.status = f"failed: {e}"
                pct = 30 + int((i + 1) / total * 20)
                await update(JobStatus.RENDERING, f"🖼️ Image {i+1}/{total} ready", pct)

            await update(JobStatus.RENDERING, "Stopping Draw Things to free resources...", 50)
            stop_draw_things()

        # Persist paths so they survive a server restart
        script_path.write_text(primary_script.model_dump_json(indent=2), encoding="utf-8")

        # ── Phase 3b: Animate still images → video clips ──
        # Uses T2V engine (Phase 6) if configured, else falls back to ComfyUI AnimateDiff.
        await update(JobStatus.RENDERING, f"Animating clips (engine: {settings.t2v_engine})...", 50)
        for i, scene in enumerate(primary_script.scenes):
            if not scene.image_path:
                continue
            mp4_path = clips_dir / f"scene_{i+1:02d}.mp4"
            try:
                async def _t2v_prog(msg: str, scene_pct: int, _i=i):
                    base = 50 + int(_i / total * 5)
                    await update(JobStatus.RENDERING, f"🎬 {msg}", base + int(scene_pct / total / 20))

                result = await generate_t2v(
                    image_path=Path(scene.image_path),
                    visual_prompt=scene.visual_prompt,
                    output_path=mp4_path,
                    scene_number=i + 1,
                    on_progress=_t2v_prog,
                )
                if not result:
                    # Fall back to ComfyUI AnimateDiff
                    result = await generate_video_from_image(
                        image_path=Path(scene.image_path),
                        visual_prompt=scene.visual_prompt,
                        output_path=mp4_path,
                        scene_number=i + 1,
                    )
                if result:
                    scene.video_path = result
                    scene.status = "rendered"
            except Exception as e:
                print(f"I2V warning scene {i+1}: {e}")

            pct = 50 + int((i + 1) / total * 5)
            await update(JobStatus.RENDERING, f"🎬 Video {i+1}/{total} done", pct)

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

        # Persist audio paths
        script_path.write_text(primary_script.model_dump_json(indent=2), encoding="utf-8")

        # ── Generate SRT early so it's available before assembly ──
        from worker.assembler import generate_srt
        subs_dir = project_dir / "subtitles"
        subs_dir.mkdir(exist_ok=True)
        await generate_srt([s.model_dump() for s in primary_script.scenes], subs_dir / "full.srt", audio_dir=audio_dir)

        # ── Phase 5: Assemble final video ──
        await update(JobStatus.ASSEMBLING, "Merging everything...", 75)
        scenes_data = [s.model_dump() for s in primary_script.scenes]
        final_path = await merge_clips(project_dir, scenes_data)

        job.has_final = True

        # Save final metadata
        metadata = {
            "job_id": job_id,
            "topic": topic,
            "project_name": project_name,
            "scripts_count": len(scripts),
            "primary_script": primary_script.title,
            "final_video": final_path,
            "status": "completed",
            "created_at": datetime.now().isoformat(),
        }
        (project_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        await update(JobStatus.COMPLETED, "✅ Final video ready!", 100)
        return job_id

    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED
        job.error = "Stopped by user"
        job.current_step = "🛑 Stopped"
        job.logs.append("🛑 Stopped by user")
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise

    except Exception as e:
        err_msg = str(e) or f"{type(e).__name__} (no message)"
        job.status = JobStatus.FAILED
        job.error = err_msg
        job.current_step = f"❌ Failed: {err_msg[:120]}"
        job.logs.append(f"❌ {type(e).__name__}: {err_msg[:280]}")
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise


async def continue_pipeline(job_id: str, ws_callback=None) -> str:
    """
    Resume a pipeline from where it left off.
    Skips phases whose output files already exist on disk.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    project_dir = Path(job.project_dir)
    meta = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))
    topic = meta.get("topic", "")
    project_name = project_dir.name

    # Reset to running state
    job.error = None
    job.logs = job.logs or []
    _jobs[job_id] = job

    async def update(status: JobStatus, step: str, pct: int):
        job.status = status
        job.current_step = step
        job.progress_pct = pct
        job.updated_at = datetime.now()
        if not job.logs or job.logs[-1] != step:
            job.logs.append(step)
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))

    try:
        await update(JobStatus.RESEARCHING, "▶ Resuming pipeline...", 1)

        # ── Phase 1: Research ──
        research_path = project_dir / "research.json"
        if research_path.exists():
            articles = json.loads(research_path.read_text(encoding="utf-8"))
            await update(JobStatus.SCRIPTING, f"✅ Research done — {len(articles)} articles loaded", 15)
        else:
            async def research_update(step: str, pct: int):
                await update(JobStatus.RESEARCHING, step, 5 + int(pct * 0.1))
            await update(JobStatus.RESEARCHING, "Searching the web...", 5)
            articles = await research_topic(topic, on_progress=research_update)
            if not articles:
                raise Exception("No articles found. Try a different keyword.")
            await update(JobStatus.RESEARCHING, f"🔍 Found {len(articles)} articles", 15)
            for i, article in enumerate(articles):
                await update(JobStatus.RESEARCHING, f"  └ [{i+1}] {article.get('title', 'Untitled')}", 15)
            research_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")

        # ── Phase 2: Scripts ──
        from models.schemas import Script
        script_files = sorted(project_dir.glob("script_*.json"))
        if script_files:
            scripts = [Script.model_validate_json(f.read_text(encoding="utf-8")) for f in script_files]
            job.scripts = scripts
            await update(JobStatus.RENDERING, f"✅ Scripts done — {len(scripts)} scripts loaded", 30)
        else:
            await update(JobStatus.SCRIPTING, f"Generating scripts for {len(articles)} articles...", 15)
            scripts = []
            for i, article in enumerate(articles):
                title = article.get("title", "Untitled")

                async def script_update(step: str, pct: int, _i=i):
                    base = 15 + int(_i / len(articles) * 15)
                    await update(JobStatus.SCRIPTING, step, base + int(pct * (15 / len(articles)) / 100))

                await update(JobStatus.SCRIPTING, f"✍️ Script {i+1}/{len(articles)}: {title[:40]}...", 15 + int(i / len(articles) * 15))
                script = await generate_script(article, topic, on_progress=script_update, image_style=settings.image_style)
                scripts.append(script)
                (project_dir / f"script_{i+1:02d}.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
                await update(JobStatus.SCRIPTING, f"✅ Script {i+1}/{len(articles)} done ({len(script.scenes)} scenes)", 15 + int((i + 1) / len(articles) * 15))
            job.scripts = scripts

        primary_script = job.scripts[0]

        # ── Phase 3: Video clips (skip existing) ──
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(exist_ok=True)

        needs_render = [
            i for i, scene in enumerate(primary_script.scenes)
            if not (clips_dir / f"scene_{i+1:02d}.png").exists()
            and not (clips_dir / f"scene_{i+1:02d}.mp4").exists()
        ]
        if not needs_render:
            await update(JobStatus.TTS, f"✅ All {len(primary_script.scenes)} clips already rendered", 55)
        elif settings.scene_engine == "html":
            await release_ollama_model()
            if settings.html_animated:
                from worker.html_engine import render_scene_to_video
                await update(JobStatus.RENDERING, f"🎬 HTML animated — {len(needs_render)} scenes...", 30)
                for idx, i in enumerate(needs_render):
                    scene = primary_script.scenes[i]
                    mp4_path = clips_dir / f"scene_{i+1:02d}.mp4"
                    try:
                        result = await render_scene_to_video(
                            scene=scene,
                            title=primary_script.title,
                            output_path=mp4_path,
                            template=settings.html_template,
                        )
                        scene.clip_path = str(result)
                        scene.video_path = str(result)
                        scene.status = "rendered"
                    except Exception as e:
                        scene.status = f"failed: {e}"
                        print(f"HTML video error scene {i+1}: {e}")
                    pct = 30 + int((idx + 1) / len(needs_render) * 25)
                    await update(JobStatus.RENDERING, f"🎬 HTML scene {i+1}/{len(primary_script.scenes)} ready", pct)
            else:
                from worker.html_engine import render_scene_to_png
                await update(JobStatus.RENDERING, f"🎨 HTML engine ({settings.html_template}) — {len(needs_render)} scenes...", 30)
                for idx, i in enumerate(needs_render):
                    scene = primary_script.scenes[i]
                    clip_path = clips_dir / f"scene_{i+1:02d}.png"
                    try:
                        result = await render_scene_to_png(
                            scene=scene,
                            title=primary_script.title,
                            output_path=clip_path,
                            template=settings.html_template,
                        )
                        scene.clip_path = str(result)
                        scene.image_path = str(result)
                        scene.status = "image_ready"
                    except Exception as e:
                        scene.status = f"failed: {e}"
                        print(f"HTML render error scene {i+1}: {e}")
                    pct = 30 + int((idx + 1) / len(needs_render) * 25)
                    await update(JobStatus.RENDERING, f"🖼️ HTML scene {i+1}/{len(primary_script.scenes)} ready", pct)
        else:
            await update(JobStatus.RENDERING, f"Starting Draw Things for {len(needs_render)} missing clips...", 30)
            await release_ollama_model()

            async def _dt_status_cont(msg: str):
                await update(JobStatus.RENDERING, f"🖼️ {msg}", 30)

            await start_draw_things(on_status=_dt_status_cont)

            prev_image_cont: Path | None = None
            for idx, i in enumerate(needs_render):
                scene = primary_script.scenes[i]
                clip_path = clips_dir / f"scene_{i+1:02d}.png"
                if i > 0:
                    prev_png = clips_dir / f"scene_{i:02d}.png"
                    if prev_png.exists():
                        prev_image_cont = prev_png
                try:
                    result = await generate_clip(
                        visual_prompt=scene.visual_prompt,
                        output_path=clip_path,
                        scene_number=i + 1,
                        seed=scene.seed,
                        image_style=scene.image_style,
                        ref_image_path=prev_image_cont,
                    )
                    scene.clip_path = result
                    scene.status = "rendered"
                    prev_image_cont = Path(result)
                except Exception as e:
                    scene.status = f"failed: {e}"
                pct = 30 + int((idx + 1) / len(needs_render) * 25)
                await update(JobStatus.RENDERING, f"Clip {i+1}/{len(primary_script.scenes)}", pct)

            await update(JobStatus.RENDERING, "Stopping Draw Things to free resources...", 55)
            stop_draw_things()

        # Populate clip_path for already-rendered scenes
        for i, scene in enumerate(primary_script.scenes):
            png = clips_dir / f"scene_{i+1:02d}.png"
            mp4 = clips_dir / f"scene_{i+1:02d}.mp4"
            if not scene.clip_path and png.exists():
                scene.clip_path = str(png)
            if not scene.video_path and mp4.exists():
                scene.video_path = str(mp4)

        # ── Phase 4: Audio (skip existing) ──
        audio_dir = project_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        needs_audio = [
            i for i in range(len(primary_script.scenes))
            if not (audio_dir / f"scene_{i+1:02d}.wav").exists()
        ]
        if not needs_audio:
            await update(JobStatus.ASSEMBLING, f"✅ All {len(primary_script.scenes)} audio tracks ready", 70)
        else:
            await update(JobStatus.TTS, f"Generating {len(needs_audio)} missing audio tracks...", 55)
            for idx, i in enumerate(needs_audio):
                scene = primary_script.scenes[i]
                audio_path = audio_dir / f"scene_{i+1:02d}.wav"
                try:
                    await generate_audio(text=scene.narration_text, output_path=audio_path, scene_number=i + 1)
                    scene.audio_path = str(audio_path)
                except Exception as e:
                    print(f"TTS warning scene {i+1}: {e}")
                pct = 55 + int((idx + 1) / len(needs_audio) * 15)
                await update(JobStatus.TTS, f"Audio {i+1}/{len(primary_script.scenes)}", pct)

        for i, scene in enumerate(primary_script.scenes):
            wav = audio_dir / f"scene_{i+1:02d}.wav"
            if not scene.audio_path and wav.exists():
                scene.audio_path = str(wav)

        # ── Generate SRT early ──
        from worker.assembler import generate_srt
        subs_dir = project_dir / "subtitles"
        subs_dir.mkdir(exist_ok=True)
        srt_path = subs_dir / "full.srt"
        if not srt_path.exists():
            await generate_srt([s.model_dump() for s in primary_script.scenes], srt_path, audio_dir=audio_dir)

        # ── Phase 5: Assembly ──
        if (project_dir / "final.mp4").exists():
            job.has_final = True
            await update(JobStatus.COMPLETED, "✅ Final video already exists!", 100)
        else:
            await update(JobStatus.ASSEMBLING, "Merging everything...", 75)
            scenes_data = [s.model_dump() for s in primary_script.scenes]
            final_path = await merge_clips(project_dir, scenes_data)
            job.has_final = True
            meta.update({"scripts_count": len(job.scripts), "primary_script": primary_script.title, "final_video": final_path, "status": "completed"})
            (project_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            await update(JobStatus.COMPLETED, "✅ Final video ready!", 100)

        return job_id

    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED
        job.error = "Stopped by user"
        job.current_step = "🛑 Stopped"
        job.logs.append("🛑 Stopped by user")
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise

    except Exception as e:
        err_msg = str(e) or f"{type(e).__name__} (no message)"
        job.status = JobStatus.FAILED
        job.error = err_msg
        job.current_step = f"❌ Failed: {err_msg[:120]}"
        job.logs.append(f"❌ {type(e).__name__}: {err_msg[:280]}")
        job.updated_at = datetime.now()
        if ws_callback:
            await ws_callback(job.model_dump(mode="json", exclude_none=True))
        raise
