# PePeApp: Local AI Video Production Factory

> An end-to-end automated system that transforms news articles and ideas into 60-second short videos with AI voiceover and subtitles, then auto-publishes to social media. **100% local processing on Mac M4.**

See full implementation plan in the artifact: `implementation_plan.md`

## Quick Reference

### Tech Stack
- **Orchestration**: n8n (local) + Python 3.12
- **LLM**: Ollama → Qwen 2.5 7B/14B
- **Video Gen**: ComfyUI → SVD XT / AnimateDiff
- **TTS**: faster-qwen3-tts (https://github.com/andimarafioti/faster-qwen3-tts)
- **Video Editor**: FFmpeg + MoviePy
- **Dashboard**: Next.js 15 + Tailwind CSS + Framer Motion + Socket.io
- **Publishing**: YouTube API / TikTok API / Facebook Graph API

### Pipeline Flow
```
News/Idea → Ollama (Script) → ComfyUI (6x 10s Clips) → TTS (Voiceover) → FFmpeg (Merge) → Preview → Publish
```

### Project Storage
```
projects/{project-name}/
├── script.json
├── clips/          # 6 individual 10s clips
├── audio/          # Voice-over per scene
├── subtitles/
├── final.mp4       # Merged 60s video
└── metadata.json
```
