"""
Assembler — Uses FFmpeg to merge clips + audio + subtitles into a final video.
"""
import asyncio
import json
from pathlib import Path
from config import settings


async def generate_srt(scenes: list[dict], output_path: Path) -> str:
    """Generate an SRT subtitle file from scene data."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, scene in enumerate(scenes):
        start_sec = i * scene.get("duration_seconds", 10)
        end_sec = start_sec + scene.get("duration_seconds", 10)
        start_ts = _srt_timestamp(start_sec)
        end_ts = _srt_timestamp(end_sec)
        lines.append(f"{i + 1}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(scene.get("subtitle_text", ""))
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


def _srt_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def merge_clips(
    project_dir: Path,
    scenes: list[dict],
    on_progress=None,
) -> str:
    """
    Merge individual clips + audio + subtitles into a final video.

    Expected project structure:
        project_dir/clips/scene_01.mp4, scene_02.mp4, ...
        project_dir/audio/scene_01.wav, scene_02.wav, ...
        project_dir/subtitles/full.srt

    Args:
        project_dir: Path to the project folder
        scenes: List of scene dicts
        on_progress: async callback(step, pct)

    Returns:
        Path to the final merged video
    """
    clips_dir = project_dir / "clips"
    audio_dir = project_dir / "audio"
    subs_dir = project_dir / "subtitles"
    subs_dir.mkdir(parents=True, exist_ok=True)
    final_path = project_dir / "final.mp4"

    if on_progress:
        await on_progress("Generating subtitles...", 5)

    # Step 1: Generate SRT
    srt_path = subs_dir / "full.srt"
    await generate_srt(scenes, srt_path)

    if on_progress:
        await on_progress("Concatenating clips...", 15)

    # Step 2: Create concat file for video clips
    concat_file = project_dir / "concat_list.txt"
    clip_entries = []
    for i in range(len(scenes)):
        clip_path = clips_dir / f"scene_{i+1:02d}.mp4"
        if clip_path.exists():
            clip_entries.append(f"file '{clip_path}'")
        else:
            # Try .png as fallback (still image → will be converted to video)
            img_path = clips_dir / f"scene_{i+1:02d}.png"
            if img_path.exists():
                # Convert still image to 10s video clip
                tmp_clip = clips_dir / f"scene_{i+1:02d}_from_img.mp4"
                duration = scenes[i].get("duration_seconds", 10)
                await _run_ffmpeg([
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(img_path),
                    "-c:v", "libx264", "-t", str(duration),
                    "-pix_fmt", "yuv420p", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                    str(tmp_clip),
                ])
                clip_entries.append(f"file '{tmp_clip}'")

    concat_file.write_text("\n".join(clip_entries), encoding="utf-8")

    # Step 3: Concatenate video clips
    merged_video = project_dir / "merged_video.mp4"
    await _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(merged_video),
    ])

    if on_progress:
        await on_progress("Merging audio tracks...", 50)

    # Step 4: Concatenate audio files
    audio_concat = project_dir / "audio_concat.txt"
    audio_entries = []
    for i in range(len(scenes)):
        audio_path = audio_dir / f"scene_{i+1:02d}.wav"
        if audio_path.exists():
            audio_entries.append(f"file '{audio_path}'")

    merged_audio = project_dir / "merged_audio.wav"
    if audio_entries:
        audio_concat.write_text("\n".join(audio_entries), encoding="utf-8")
        await _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(audio_concat),
            "-c", "copy",
            str(merged_audio),
        ])

    if on_progress:
        await on_progress("Adding audio and subtitles...", 75)

    # Step 5: Combine video + audio + subtitles into final
    cmd = [
        "ffmpeg", "-y",
        "-i", str(merged_video),
    ]
    if merged_audio.exists():
        cmd += ["-i", str(merged_audio)]

    # Video filter: scale to vertical 1080x1920 + burn subtitles
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    if srt_path.exists():
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf += f",subtitles='{srt_escaped}':force_style='FontSize=22,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2'"

    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "23"]

    if merged_audio.exists():
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        cmd += ["-an"]

    cmd.append(str(final_path))
    await _run_ffmpeg(cmd)

    # Cleanup temp files
    for f in [concat_file, audio_concat, merged_video, merged_audio]:
        if f.exists():
            f.unlink()

    if on_progress:
        await on_progress("Assembly complete!", 100)

    return str(final_path)


async def _run_ffmpeg(cmd: list[str]):
    """Run an FFmpeg command asynchronously."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {stderr.decode()[:500]}")
