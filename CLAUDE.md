# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (FastAPI, Python)
```bash
cd backend
source .venv/bin/activate
uvicorn api.app:app --host 0.0.0.0 --port 8888 --reload
```

### Frontend (Next.js 15)
```bash
cd frontend
pnpm dev          # starts on port 3000
pnpm build
pnpm lint
```

### Tests (Playwright E2E)
```bash
cd frontend
pnpm playwright test                        # run all tests
pnpm playwright test tests/pipeline.spec.ts # run specific file
pnpm playwright test --headed               # visible browser
pnpm playwright show-report                 # view HTML report
```

Python deps live in `backend/.venv/`. Always activate before running Python.

## Architecture

**PePeApp** is a local AI video production pipeline: topic → research → script → images/video clips → TTS voiceover → FFmpeg-assembled final video.

```
backend/
  api/app.py            — FastAPI app + WebSocket /ws broadcaster
  api/routes/jobs.py    — job CRUD + per-scene render endpoints
  api/routes/projects.py— project file-system browser + asset server
  api/routes/settings.py— read/write config to backend/.env
  worker/pipeline.py    — orchestrator: run_pipeline() + continue_pipeline()
  worker/research_engine.py — DDGS search → 1 article + 6 key_points
  worker/script_engine.py   — Ollama/OpenAI → 6 scenes, one at a time
  worker/video_engine.py    — ComfyUI clip gen; Pillow placeholder when offline
  worker/tts_engine.py      — edge-tts (default) / piper / faster-qwen3-tts
  worker/assembler.py       — FFmpeg: concat clips + audio → final.mp4
  models/schemas.py         — Pydantic: JobProgress, JobStatus, Script, Scene
  config.py                 — Settings via pydantic-settings, env prefix PEPE_

frontend/
  src/app/page.tsx          — single-page React app (Dashboard / Projects / Settings tabs)
  src/app/[...slug]/        — catch-all route (URL cosmetics only, no SSR pages)
  tests/                    — Playwright E2E tests
```

### Job lifecycle
`PENDING → RESEARCHING → SCRIPTING → RENDERING → TTS → ASSEMBLING → PREVIEW → COMPLETED`
Also: `CANCELLING → CANCELLED`, `FAILED`.

Jobs live in `_jobs: dict[str, JobProgress]` in memory. On restart, `get_job()` reconstructs them from disk (`metadata.json` + `script_*.json`).

Project folders: `projects/<topic-slug>_<YYYYMMDD_HHMMSS>/`
Key files: `research.json`, `script_01.json`, `clips/scene_XX.png|mp4`, `audio/scene_XX.wav`, `subtitles/full.srt`, `final.mp4`.

### Real-time updates
WebSocket at `ws://localhost:8888/ws` pushes `JobProgress` JSON on every state change. Frontend merges by `job_id` into React state — no polling.

### continue_pipeline()
Idempotent resume: checks each output file before running each phase. Safe to call multiple times.

### Script generation
`generate_script()` calls the AI once per scene (6 calls total, 180 s timeout each) and fires `on_scene` after each so the Shot List updates progressively in the UI.

### ComfyUI / video generation
Checks `/system_stats` with 3 s timeout. If offline, generates a Pillow 1080×1920 placeholder PNG. `generate_clip()` always returns the actual path created — callers must use this return value (not the original `output_path`) because the fallback silently changes the extension to `.png`.

### FFmpeg notes
- No libass in the build → no subtitle burning. SRT is saved alongside final video.
- All output: vertical 9:16 (1080×1920), `libx264 preset=fast crf=23`.
- `_run_ffmpeg()` surfaces the last 6 meaningful stderr lines on error.

### TTS
Default: `edge-tts` via Python API (`edge_tts.Communicate`). Saves `.mp3` → ffmpeg converts to `.wav`. Default voice: `vi-VN-HoaiMyNeural`.

## Key patterns

- `on_progress(step: str, pct: int)` callbacks thread through every worker function for granular WS updates.
- All `generate_clip()` callers must use the **return value** as the path, not the original `output_path` passed in — ComfyUI fallback changes the extension.
- Error strings: `str(e) or f"{type(e).__name__} (no message)"` guards against empty httpx exceptions.
- Frontend shows `<img>` for `.png/.jpg` files and `<video>` for `.mp4/.webm/.mov` — checked by regex on the filename.
