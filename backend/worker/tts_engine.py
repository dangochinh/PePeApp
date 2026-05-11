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
