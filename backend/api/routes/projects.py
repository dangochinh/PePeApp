"""
Projects API — Browse projects, preview clips and videos.
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from config import PROJECTS_DIR

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


@router.get("/{project_name}/final")
async def serve_final_video(project_name: str):
    """Serve the final merged video for preview."""
    final_path = PROJECTS_DIR / project_name / "final.mp4"
    if not final_path.exists():
        raise HTTPException(status_code=404, detail="Final video not found")
    return FileResponse(final_path, media_type="video/mp4")


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
