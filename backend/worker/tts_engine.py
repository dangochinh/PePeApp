"""
TTS Engine — Abstraction layer supporting multiple backends:
  - vieneu       (Mac M4 native via Metal/GGUF, Vietnamese-native, default)
  - edge-tts     (cloud, no install, Vietnamese supported)
  - piper        (CPU-native, offline)
  - faster-qwen3-tts (NVIDIA CUDA only)

The active engine is controlled by settings.tts_engine.
"""
import asyncio
import subprocess
from pathlib import Path
from config import settings

# ── VieNeu singleton — load once, reuse forever ─────────────────────────────
_vieneu_instance = None
_vieneu_loading = False

async def _get_vieneu():
    global _vieneu_instance, _vieneu_loading
    if _vieneu_instance is not None:
        return _vieneu_instance
    if _vieneu_loading:
        # Wait for the other coroutine that's already loading it
        while _vieneu_loading:
            await asyncio.sleep(0.5)
        return _vieneu_instance

    _vieneu_loading = True
    try:
        from vieneu import Vieneu
        loop = asyncio.get_event_loop()
        _vieneu_instance = await loop.run_in_executor(
            None,
            lambda: Vieneu(mode="turbo", emotion="storytelling"),
        )
        return _vieneu_instance
    finally:
        _vieneu_loading = False


async def generate_audio(
    text: str,
    output_path: Path,
    scene_number: int = 1,
    on_progress=None,
) -> str:
    """
    Generate voiceover audio from text using the configured TTS engine.

    Args:
        text: Narration text to synthesize
        output_path: Path to save the WAV file
        scene_number: For progress reporting
        on_progress: async callback(step, pct)

    Returns:
        Path to the generated WAV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = settings.tts_engine

    if on_progress:
        await on_progress(f"Generating voiceover for scene {scene_number} [{engine}]...", 10)

    try:
        if engine == "vieneu":
            await _generate_vieneu(text, output_path, scene_number)
        elif engine == "faster-qwen3-tts":
            await _generate_faster_qwen3(text, output_path, scene_number)
        elif engine == "piper":
            await _generate_piper(text, output_path, scene_number)
        elif engine == "elevenlabs":
            await _generate_elevenlabs(text, output_path, scene_number)
        elif engine == "edge-tts":
            await _generate_edge_tts(text, output_path, scene_number)
        else:
            raise ValueError(f"Unknown TTS engine: {engine}")
    except (FileNotFoundError, ImportError, Exception) as e:
        if engine != "edge-tts" and not isinstance(e, RuntimeError):
            print(f"TTS engine '{engine}' failed ({e}), falling back to edge-tts")
            await _generate_edge_tts(text, output_path, scene_number)
        else:
            raise

    if on_progress:
        await on_progress(f"Voiceover scene {scene_number} done", 100)

    return str(output_path)


async def _generate_vieneu(text: str, output_path: Path, scene_number: int):
    """VieNeu Turbo — Vietnamese-native, runs on Mac M4 via Metal."""
    tts = await _get_vieneu()
    loop = asyncio.get_event_loop()

    def _infer_and_save():
        audio = tts.infer(text=text)
        tts.save(audio, str(output_path))

    await loop.run_in_executor(None, _infer_and_save)
    if not output_path.exists():
        raise RuntimeError(f"VieNeu produced no output for scene {scene_number}")


async def _generate_faster_qwen3(text: str, output_path: Path, scene_number: int):
    """Use faster-qwen3-tts CLI (requires NVIDIA CUDA)"""
    model = settings.tts_model_path or "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    ref_audio = settings.tts_ref_audio

    cmd = [
        "faster-qwen3-tts", "clone" if ref_audio else "custom",
        "--model", model,
        "--text", text,
        "--language", "Vietnamese",
        "--output", str(output_path),
    ]
    if ref_audio:
        cmd += ["--ref-audio", ref_audio]
    else:
        cmd += ["--speaker", settings.tts_voice or "aiden"]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"faster-qwen3-tts failed: {stderr.decode()}")


async def _generate_piper(text: str, output_path: Path, scene_number: int):
    """Use Piper TTS — CPU-native, great for Mac M4"""
    # Piper reads from stdin, writes WAV to stdout
    # Install: pip install piper-tts  OR  brew install piper-tts
    voice = settings.tts_voice or "vi_VN-vivos-medium"  # Vietnamese voice

    proc = await asyncio.create_subprocess_exec(
        "piper",
        "--model", voice,
        "--output_file", str(output_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=text.encode("utf-8"))
    if proc.returncode != 0:
        raise RuntimeError(f"Piper TTS failed: {stderr.decode()}")
async def _generate_edge_tts(text: str, output_path: Path, scene_number: int):
    import edge_tts

    voice = settings.tts_voice
    if not voice or voice in ("default", ""):
        voice = "vi-VN-HoaiMyNeural"

    # edge_tts outputs MP3 — save to temp then convert to WAV via ffmpeg
    mp3_path = output_path.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(mp3_path))

    # Convert MP3 → WAV so assembler can concat uniformly
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(mp3_path), str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    mp3_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        err_lines = stderr.decode(errors="replace").splitlines()
        raise RuntimeError(f"ffmpeg mp3→wav failed: {chr(10).join(err_lines[-4:])}")


# ---------------------------------------------------------------------------
# Word-level timing support
# ---------------------------------------------------------------------------

async def _audio_duration(audio_path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except ValueError:
        return 5.0


def _estimate_word_timings(text: str, duration: float) -> list[dict]:
    """Distribute words proportionally by character count over duration."""
    import re
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return []
    weights = [max(1, len(re.sub(r"[^\w]", "", w))) for w in words]
    total = sum(weights)
    lead = min(0.2, duration * 0.03)   # small lead-in silence
    avail = duration - lead
    t, result = lead, []
    for w, wt in zip(words, weights):
        wd = (wt / total) * avail
        result.append({"word": w, "start": round(t, 3), "duration": round(wd, 3)})
        t += wd
    return result


async def generate_audio_with_word_timings(
    text: str,
    output_path: Path,
    scene_number: int = 1,
) -> tuple[str, list[dict]]:
    """
    Generate TTS audio and return per-word timing data.
    edge-tts: uses real WordBoundary events.
    Others: generate normally then estimate timings from audio duration.
    Returns (wav_path, [{"word", "start", "duration"}, ...])
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    engine = settings.tts_engine

    if engine == "edge-tts":
        return await _edge_tts_with_timings(text, output_path, scene_number)
    if engine == "elevenlabs":
        return await _elevenlabs_with_timings(text, output_path, scene_number)

    # All other engines: generate audio normally, then estimate
    await generate_audio(text, output_path, scene_number)
    dur = await _audio_duration(output_path)
    return str(output_path), _estimate_word_timings(text, dur)


async def _generate_elevenlabs(text: str, output_path: Path, scene_number: int):
    """ElevenLabs TTS — cloud, multilingual including Vietnamese."""
    _, _ = await _elevenlabs_with_timings(text, output_path, scene_number)


async def _elevenlabs_with_timings(
    text: str, output_path: Path, scene_number: int
) -> tuple[str, list[dict]]:
    """ElevenLabs TTS with character-aligned word timings."""
    import base64
    import httpx

    api_key = settings.elevenlabs_api_key
    if not api_key:
        raise RuntimeError("ElevenLabs API key not set (PEPE_ELEVENLABS_API_KEY)")

    voice_id = settings.elevenlabs_voice_id
    model_id = settings.elevenlabs_model

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.80,
            "style": 0.30,
            "use_speaker_boost": True,
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs API error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()

    # Decode audio
    audio_bytes = base64.b64decode(data["audio_base64"])
    mp3_path = output_path.with_suffix(".mp3")
    mp3_path.write_bytes(audio_bytes)

    # Convert MP3 → WAV
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(mp3_path), str(output_path),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    mp3_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mp3→wav: {stderr.decode()[-300:]}")

    # Parse character-level alignment → word-level timings
    alignment = data.get("alignment", {})
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    word_events: list[dict] = []
    if chars and starts and ends:
        word_chars: list[str] = []
        word_start = 0.0
        word_end = 0.0
        for ch, s, e in zip(chars, starts, ends):
            if ch in (" ", "\t", "\n") and word_chars:
                word_events.append({
                    "word": "".join(word_chars),
                    "start": round(word_start, 3),
                    "duration": round(word_end - word_start, 3),
                })
                word_chars = []
            elif ch not in (" ", "\t", "\n"):
                if not word_chars:
                    word_start = s
                word_chars.append(ch)
                word_end = e
        if word_chars:
            word_events.append({
                "word": "".join(word_chars),
                "start": round(word_start, 3),
                "duration": round(word_end - word_start, 3),
            })

    if not word_events:
        dur = await _audio_duration(output_path)
        word_events = _estimate_word_timings(text, dur)

    return str(output_path), word_events


async def _edge_tts_with_timings(
    text: str, output_path: Path, scene_number: int
) -> tuple[str, list[dict]]:
    import edge_tts, io, aiofiles

    voice = settings.tts_voice
    if not voice or voice in ("default", ""):
        voice = "vi-VN-HoaiMyNeural"

    mp3_path = output_path.with_suffix(".mp3")
    word_events: list[dict] = []

    communicate = edge_tts.Communicate(text, voice)
    async with aiofiles.open(str(mp3_path), "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # edge-tts offset/duration are in 100-nanosecond ticks
                word_events.append({
                    "word":     chunk["text"],
                    "start":    round(chunk["offset"]   / 10_000_000, 3),
                    "duration": round(chunk["duration"] / 10_000_000, 3),
                })

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(mp3_path), str(output_path),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    mp3_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mp3→wav: {stderr.decode()[-300:]}")

    if not word_events:
        dur = await _audio_duration(output_path)
        word_events = _estimate_word_timings(text, dur)

    return str(output_path), word_events
