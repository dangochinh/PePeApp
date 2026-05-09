"""
TTS Engine — Abstraction layer supporting multiple backends:
  - faster-qwen3-tts (NVIDIA CUDA, best quality, voice cloning)
  - Piper TTS (CPU-native, works on Mac M4, lighter)

The active engine is controlled by settings.tts_engine.
"""
import asyncio
import subprocess
from pathlib import Path
from config import settings


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

    if engine == "faster-qwen3-tts":
        await _generate_faster_qwen3(text, output_path, scene_number)
    elif engine == "piper":
        await _generate_piper(text, output_path, scene_number)
    elif engine == "edge-tts":
        await _generate_edge_tts(text, output_path, scene_number)
    else:
        raise ValueError(f"Unknown TTS engine: {engine}")

    if on_progress:
        await on_progress(f"Voiceover scene {scene_number} done", 100)

    return str(output_path)


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
    voice = settings.tts_voice or "vi-VN-HoaiMyNeural"
    import sys
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--text", text,
        "--write-media", str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Edge-TTS failed: {stderr.decode()}")
