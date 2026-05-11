"""
PePeApp — FastAPI Backend
Main application with REST API + WebSocket for real-time progress.
"""
import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, PROJECTS_DIR
from api.routes.jobs import router as jobs_router
from api.routes.projects import router as projects_router
from api.routes.settings_route import router as settings_router
from api.routes.services import router as services_router
from api.routes.publish import router as publish_router


# WebSocket connections for real-time updates
ws_clients: set[WebSocket] = set()


async def broadcast_progress(data: dict):
    """Broadcast job progress to all connected WebSocket clients."""
    global ws_clients
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    ws_clients -= dead


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"PePeApp Backend starting on port {settings.port}")
    print(f"   Ollama: {settings.ollama_base_url} ({settings.ollama_model})")
    print(f"   Draw Things: {settings.draw_things_base_url}")
    print(f"   ComfyUI I2V: {settings.comfyui_base_url}")
    print(f"   TTS Engine: {settings.tts_engine}")
    print(f"   Projects dir: {PROJECTS_DIR}")
    yield
    # Shutdown
    print("PePeApp Backend shutting down")


app = FastAPI(
    title="PePeApp",
    description="Local AI Video Production Factory",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(jobs_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(projects_router, prefix="/api/projects", tags=["Projects"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])
app.include_router(services_router, prefix="/api/services", tags=["Services"])
app.include_router(publish_router, prefix="/api/publish", tags=["Publish"])

# Serve generated videos/images statically
if PROJECTS_DIR.exists():
    app.mount("/projects", StaticFiles(directory=str(PROJECTS_DIR)), name="projects")


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "name": "PePeApp"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global ws_clients
    await websocket.accept()
    ws_clients.add(websocket)
    try:
        while True:
            # Keep connection alive, receive pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host=settings.host, port=settings.port, reload=True)
