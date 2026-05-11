"""
Services API — Health checks and process control for backend AI components.
"""
import asyncio
import subprocess
import sys
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter

from config import settings
from worker.service_control import _DT_ENABLE_SCRIPT, _launch_draw_things, _is_draw_things_running

router = APIRouter()

# Track subprocess PIDs for services we launched
_service_procs: dict[str, subprocess.Popen] = {}


async def _check_url(url: str, path: str = "/", timeout: float = 2.5) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"{url}{path}")
            return r.status_code < 500
    except Exception:
        return False


async def _get_ollama_status() -> dict:
    base = settings.ollama_base_url
    online = await _check_url(base, "/api/tags")
    busy = False
    if online:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{base}/api/ps")
                if r.status_code == 200:
                    data = r.json()
                    busy = bool(data.get("models"))
        except Exception:
            pass
    return {
        "id": "ollama",
        "name": "Ollama (LLM)",
        "online": online,
        "busy": busy,
        "url": base,
        "model": settings.ollama_model,
        "process": "busy" if busy else ("online" if online else "offline"),
    }


async def _get_draw_things_status() -> dict:
    base = settings.draw_things_base_url
    online = await _check_url(base, "/")
    busy = False
    if online:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{base}/")
                if r.status_code == 200:
                    data = r.json()
                    busy = data.get("progress", 0) > 0
        except Exception:
            pass
    return {
        "id": "draw_things",
        "name": "Draw Things (Image)",
        "online": online,
        "busy": busy,
        "url": base,
        "process": "busy" if busy else ("online" if online else "offline"),
        "hint": None if online else "Click ▶ Start — or open Draw Things manually to activate the API server",
    }


async def _get_comfyui_status() -> dict:
    base = settings.comfyui_base_url
    online = await _check_url(base, "/system_stats")
    busy = False
    if online:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{base}/prompt")
                if r.status_code == 200:
                    data = r.json()
                    queue = data.get("exec_info", {})
                    busy = queue.get("queue_remaining", 0) > 0
        except Exception:
            pass
    return {
        "id": "comfyui",
        "name": "ComfyUI (I2V)",
        "online": online,
        "busy": busy,
        "url": base,
        "process": "busy" if busy else ("online" if online else "offline"),
    }


async def _get_tts_status() -> dict:
    engine = settings.tts_engine
    online = False
    busy = False

    if engine == "vieneu":
        try:
            import vieneu  # noqa: F401
            online = True
        except ImportError:
            online = False
    elif engine == "edge-tts":
        try:
            import edge_tts  # noqa: F401
            online = True
        except ImportError:
            online = False
    elif engine == "faster-qwen3-tts":
        try:
            import faster_qwen3_tts  # noqa: F401
            online = True
        except ImportError:
            online = False
    elif engine == "piper":
        online = bool(settings.tts_model_path)

    return {
        "id": "tts",
        "name": f"TTS ({engine})",
        "online": online,
        "busy": busy,
        "url": None,
        "engine": engine,
        "process": "online" if online else "offline",
    }


@router.get("/status")
async def get_services_status():
    """Check health of all AI backend components concurrently."""
    results = await asyncio.gather(
        _get_ollama_status(),
        _get_draw_things_status(),
        _get_comfyui_status(),
        _get_tts_status(),
        return_exceptions=True,
    )
    services = []
    for r in results:
        if isinstance(r, Exception):
            services.append({"id": "unknown", "name": "Error", "online": False, "busy": False, "process": "error"})
        else:
            services.append(r)
    return {"services": services, "checked_at": datetime.now().isoformat()}


@router.post("/{service_id}/start")
async def start_service(service_id: str):
    """Attempt to start a service."""
    import platform
    is_mac = platform.system() == "Darwin"

    if service_id == "tts":
        return {"status": "ok", "message": "TTS is a Python library — no external process to start"}

    if service_id == "draw_things" and is_mac:
        # Launch Draw Things (writes pref keys first) then return immediately.
        # The pipeline's start_draw_things() handles the rest: it watches for
        # the app becoming frontmost (user clicks Dock icon) and then uses
        # AppleScript to click the API Enable toggle in Settings.
        already = _is_draw_things_running()
        if not already:
            _launch_draw_things()
        return {
            "status": "started" if not already else "already_running",
            "message": (
                "Draw Things is open — click it in the Dock once to enable the API server"
                if not already else
                "Draw Things is running — click it in the Dock once to enable the API server"
            ),
        }

    cmds: dict[str, list[str]] = {
        "ollama": ["ollama", "serve"],
        "comfyui": ["open", "-a", "ComfyUI"] if is_mac else [],
    }

    cmd = cmds.get(service_id)
    if not cmd:
        return {"status": "error", "message": f"Unknown service: {service_id}"}

    existing = _service_procs.get(service_id)
    if existing and existing.poll() is None:
        return {"status": "already_running", "message": f"{service_id} is already running"}

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _service_procs[service_id] = proc
        return {"status": "started", "pid": proc.pid, "message": f"{service_id} start command sent"}
    except FileNotFoundError:
        return {"status": "error", "message": f"Command not found: {cmd[0]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/{service_id}/stop")
async def stop_service(service_id: str):
    """Force-kill a service process."""
    kill_patterns: dict[str, str] = {
        "ollama": "ollama",
        "draw_things": "DrawThings",
        "comfyui": "ComfyUI",
    }

    if service_id == "tts":
        return {"status": "ok", "message": "TTS is a Python library — no process to kill"}

    pattern = kill_patterns.get(service_id)
    if not pattern:
        return {"status": "error", "message": f"Unknown service: {service_id}"}

    # Kill our tracked proc first
    proc = _service_procs.pop(service_id, None)
    if proc and proc.poll() is None:
        proc.terminate()

    # Also try pkill for any externally launched process
    try:
        subprocess.run(["pkill", "-f", pattern], capture_output=True)
    except Exception:
        pass

    return {"status": "stopped", "message": f"{service_id} stop signal sent"}
