"""
Projects API — Browse projects, preview clips and videos.
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from config import PROJECTS_DIR, BASE_DIR

MUSIC_DIR = BASE_DIR / "backend" / "assets" / "music"

router = APIRouter()


@router.get("/list")
async def list_projects():
    """List all projects with metadata."""
    projects = []
    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir(), reverse=True):
            if d.is_dir():
                meta_path = d / "metadata.json"
                meta = {}
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                
                # Fallback job_id for interaction
                if "job_id" not in meta:
                    meta["job_id"] = d.name
                
                projects.append({
                    "name": d.name,
                    "path": str(d),
                    "has_final": (d / "final.mp4").exists(),
                    "clips_count": len(list((d / "clips").glob("*"))) if (d / "clips").exists() else 0,
                    **meta,
                })
    return projects


@router.get("/{project_name}/load")
async def load_project_full(project_name: str):
    """Load full project state — scripts + real asset status from disk."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    meta: dict = {}
    meta_path = project_dir / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    job_id = meta.get("job_id", project_name)
    clips_dir = project_dir / "clips"
    audio_dir = project_dir / "audio"

    scripts = []
    for f in sorted(project_dir.glob("script_*.json")):
        script_data = json.loads(f.read_text(encoding="utf-8"))
        for scene in script_data.get("scenes", []):
            n = scene.get("scene_number", 1)
            prefix = f"scene_{n:02d}"
            vp_found = next(iter(sorted(clips_dir.glob(f"{prefix}*.mp4"))), None) if clips_dir.exists() else None
            scene["video_path"] = str(vp_found) if vp_found else None
            ip_found = None
            for ext in ("png", "jpg", "jpeg"):
                ip = clips_dir / f"{prefix}.{ext}"
                if ip.exists():
                    ip_found = str(ip)
                    break
            if not ip_found and clips_dir.exists():
                ip_found_path = next(iter(sorted(clips_dir.glob(f"{prefix}*.png"))), None) or \
                                next(iter(sorted(clips_dir.glob(f"{prefix}*.jpg"))), None)
                ip_found = str(ip_found_path) if ip_found_path else None
            scene["clip_path"] = ip_found
            scene["image_path"] = ip_found
            ap = audio_dir / f"scene_{n:02d}.wav"
            scene["audio_path"] = str(ap) if ap.exists() else None
        scripts.append(script_data)

    clips_count = len(list(clips_dir.glob("*"))) if clips_dir.exists() else 0
    has_final = (project_dir / "final.mp4").exists()

    return {
        "job_id": job_id,
        "name": project_name,
        "status": "completed" if has_final else "preview",
        "progress_pct": 100,
        "current_step": f"Loaded — {clips_count} clips, {len(scripts)} scripts",
        "logs": [],
        "project_dir": str(project_dir),
        "has_final": has_final,
        "clips_count": clips_count,
        "scripts": scripts,
    }


@router.get("/{project_name}/metadata")
async def get_project_metadata(project_name: str):
    """Get project metadata."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    meta_path = project_dir / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"name": project_name}


@router.get("/{project_name}/clips")
async def list_clips(project_name: str):
    """List all clips in a project."""
    clips_dir = PROJECTS_DIR / project_name / "clips"
    if not clips_dir.exists():
        return []
    return [
        {"name": f.name, "size": f.stat().st_size, "url": f"/projects/{project_name}/clips/{f.name}"}
        for f in sorted(clips_dir.iterdir())
        if f.is_file()
    ]


@router.get("/{project_name}/clip/{filename}")
async def serve_clip(project_name: str, filename: str):
    """Serve a single clip for preview."""
    clip_path = PROJECTS_DIR / project_name / "clips" / filename
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/png"
    return FileResponse(clip_path, media_type=media_type)


@router.get("/{project_name}/audio/{filename}")
async def serve_audio(project_name: str, filename: str):
    """Serve a TTS audio file for preview."""
    audio_path = PROJECTS_DIR / project_name / "audio" / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    media_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(audio_path, media_type=media_type)


@router.get("/{project_name}/final")
async def serve_final_video(project_name: str):
    """Serve the final merged video for preview."""
    final_path = PROJECTS_DIR / project_name / "final.mp4"
    if not final_path.exists():
        raise HTTPException(status_code=404, detail="Final video not found")
    return FileResponse(final_path, media_type="video/mp4")


@router.post("/{project_name}/open-folder")
async def open_project_folder(project_name: str):
    """Reveal project folder in Finder (macOS) or file explorer."""
    import subprocess, platform
    project_dir = PROJECTS_DIR / project_name
    final_path = project_dir / "final.mp4"
    target = final_path if final_path.exists() else project_dir
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(target)])
        elif platform.system() == "Windows":
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(project_dir)])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"opened": str(target)}


@router.get("/{project_name}/scripts")
async def list_scripts(project_name: str):
    """List all scripts in a project."""
    project_dir = PROJECTS_DIR / project_name
    scripts = []
    for f in sorted(project_dir.glob("script_*.json")):
        scripts.append(json.loads(f.read_text(encoding="utf-8")))
    return scripts


@router.delete("/{project_name}")
async def delete_project(project_name: str):
    """Delete a project and all its assets."""
    import shutil
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project is currently in progress
    from worker.pipeline import _jobs
    for job in _jobs.values():
        if job.project_dir and Path(job.project_dir).resolve() == project_dir.resolve():
            if job.status not in ["completed", "failed", "cancelled"]:
                raise HTTPException(status_code=400, detail="Cannot delete a project that is currently in progress")
    
    try:
        shutil.rmtree(project_dir)
        return {"message": f"Project {project_name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


# ── Background Music ──────────────────────────────────────────────────────────

@router.get("/music/list")
async def list_music():
    """List all available background music files."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    tracks = []
    for f in sorted(MUSIC_DIR.iterdir()):
        if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg") and f.is_file():
            tracks.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
            })
    return tracks


@router.post("/music/upload")
async def upload_music(file: UploadFile = File(...)):
    """Upload a background music file to the music library."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in (".mp3", ".wav", ".m4a", ".ogg"):
        raise HTTPException(status_code=400, detail="Only mp3/wav/m4a/ogg allowed")
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    dest = MUSIC_DIR / file.filename
    dest.write_bytes(await file.read())
    return {"name": file.filename, "path": str(dest)}


@router.delete("/music/{filename}")
async def delete_music(filename: str):
    """Delete a background music file."""
    target = MUSIC_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    target.unlink()
    return {"deleted": filename}
