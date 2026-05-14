"""
Assembler — FFmpeg merge with xfade transitions + Pillow subtitle burn.

Subtitle strategy: since this FFmpeg build lacks --enable-libfreetype (no drawtext),
we use Pillow to burn subtitle text onto the source PNG before converting to video.
For pre-rendered MP4 clips we skip subtitle burn (Pillow can't easily edit video frames).
"""
import asyncio
import json
from pathlib import Path


TRANSITION_DUR  = 0.4      # seconds overlap between clips

TRANSITION_POOL = [
    "fade", "slideleft", "slideright", "slideup", "slidedown",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "dissolve", "pixelize", "radial",
]

# Scene type → preferred xfade transition
_TYPE_TRANSITION: dict[str, str] = {
    "compare": "wipeleft",    # directional wipe suits side-by-side comparison
    "stats":   "fade",        # clean fade for number reveals
    "how":     "slideup",     # upward for step sequences
    "cta":     "dissolve",    # soft dissolve for CTA finales
    "what":    "slideleft",
    "why":     "fadeblack",
    "generic": "fade",
}


def _pick_transition(scene_transition: str, scene_index: int,
                     scene_type: str = "") -> str:
    """Return the xfade transition name for a given scene."""
    from config import settings
    override = scene_transition.strip() if scene_transition else ""
    if override and override != "auto":
        return override
    global_style = settings.transition_style
    if global_style != "auto":
        return global_style if global_style in TRANSITION_POOL else "fade"
    # Type-matched: use scene_type hint if available
    if scene_type and scene_type in _TYPE_TRANSITION:
        return _TYPE_TRANSITION[scene_type]
    # Deterministic-random fallback per scene index
    return TRANSITION_POOL[scene_index % len(TRANSITION_POOL)]

SUBTITLE_FONT_SIZE = 52    # px on 1080-wide image
SUBTITLE_Y_RATIO   = 0.65  # 65 % down the frame (2/3 of video height)

SCALE_VF = (
    "scale=1080:1920:force_original_aspect_ratio=decrease,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
)

# ── Ken Burns presets ─────────────────────────────────────────────────────────
# Each is a zoompan expression template. {N} = total frames, {W}x{H} = source size.
_KB_PRESETS = [
    # zoom in — center
    "zoompan=z='min(zoom+0.0012,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=25",
    # zoom out — center
    "zoompan=z='if(eq(on,1),1.35,max(zoom-0.0012,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=25",
    # pan left → right + subtle zoom
    "zoompan=z=1.18:x='(iw-iw/zoom)*on/{N}':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps=25",
    # pan right → left + subtle zoom
    "zoompan=z=1.18:x='(iw-iw/zoom)*(1-on/{N})':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps=25",
    # pan top → bottom + subtle zoom
    "zoompan=z=1.18:x='iw/2-iw/zoom/2':y='(ih-ih/zoom)*on/{N}':d=1:s={W}x{H}:fps=25",
    # pan bottom → top + subtle zoom
    "zoompan=z=1.18:x='iw/2-iw/zoom/2':y='(ih-ih/zoom)*(1-on/{N})':d=1:s={W}x{H}:fps=25",
    # diagonal zoom in + pan
    "zoompan=z='min(zoom+0.0008,1.25)':x='(iw-iw/zoom)*on/{N}':y='(ih-ih/zoom)*on/{N}':d=1:s={W}x{H}:fps=25",
    # diagonal zoom out + pan reverse
    "zoompan=z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))':x='(iw-iw/zoom)*(1-on/{N})':y='(ih-ih/zoom)*(1-on/{N})':d=1:s={W}x{H}:fps=25",
]

# ── Color grade presets (FFmpeg vf expressions) ───────────────────────────────
COLOR_GRADES: dict[str, str] = {
    "none":     "",
    "warm":     "curves=r='0/0 0.5/0.58 1/1':g='0/0 0.5/0.5 1/0.95':b='0/0 0.5/0.38 1/0.78'",
    "cool":     "curves=r='0/0 0.5/0.42 1/0.85':g='0/0 0.5/0.5 1/0.95':b='0/0 0.5/0.62 1/1'",
    "noir":     "hue=s=0,curves=all='0/0.05 0.4/0.35 0.7/0.75 1/0.95',eq=contrast=1.25:brightness=-0.04",
    "vibrant":  "eq=saturation=1.7:contrast=1.08",
    "muted":    "eq=saturation=0.55:brightness=0.03,curves=all='0/0.06 1/0.88'",
    "golden":   "curves=r='0/0 0.5/0.62 1/1':g='0/0 0.5/0.52 1/0.95':b='0/0 0.5/0.32 1/0.72',eq=contrast=1.1",
}


def _ken_burns_vf(scene_idx: int, dur: float, W: int, H: int) -> str:
    """Return a full FFmpeg -vf string: Ken Burns zoompan → scale to 1080x1920."""
    from config import settings
    if not settings.ken_burns:
        return SCALE_VF
    N = max(1, int(dur * 25))
    preset = _KB_PRESETS[scene_idx % len(_KB_PRESETS)]
    zoompan = preset.format(N=N, W=W, H=H)
    return f"{zoompan},{SCALE_VF}"

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/opt/homebrew/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


# ── Public API ────────────────────────────────────────────────────────────────

async def bake_scene_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """Merge audio into video → standalone mp4.
    If audio is longer than video, freeze last frame to fill the gap (max wins).
    """
    video_dur = await _get_duration(video_path)
    audio_dur = await _get_duration(audio_path)
    pad = audio_dur - video_dur

    if pad > 0.05:
        # Audio overruns video — freeze last frame for the remaining duration
        await _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad:.3f}",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ])
    else:
        await _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(output_path),
        ])

def _split_narration(text: str, max_chars: int = 42) -> list[str]:
    """Split narration text into subtitle-sized chunks by sentence then by comma."""
    import re
    text = text.strip()
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?。！？…])\s+', text)
    chunks: list[str] = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= max_chars:
            chunks.append(sent)
        else:
            # Split further on comma/semicolon
            parts = re.split(r'(?<=[,，;；])\s*', sent)
            buf = ""
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                test = (buf + " " + part).strip() if buf else part
                if len(test) <= max_chars:
                    buf = test
                else:
                    if buf:
                        chunks.append(buf)
                    buf = part
            if buf:
                chunks.append(buf)
    return chunks or [text]


async def generate_srt(scenes: list[dict], output_path: Path, audio_dir: Path | None = None) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    entry = 1
    t = 0.0
    for scene in scenes:
        n = scene.get("scene_number", 1)
        dur = float(scene.get("duration_seconds", 10))
        # Use actual TTS audio duration when available — much more accurate than fixed 10s
        if audio_dir:
            wav = audio_dir / f"scene_{n:02d}.wav"
            if wav.exists():
                actual = await _get_duration(wav)
                if actual > 0.3:
                    dur = actual
        narration = scene.get("narration_text", "") or scene.get("subtitle_text", "")
        chunks = _split_narration(narration)
        chunk_dur = dur / len(chunks)
        for chunk in chunks:
            lines += [str(entry), f"{_srt_ts(t)} --> {_srt_ts(t + chunk_dur)}", chunk, ""]
            t += chunk_dur
            entry += 1
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


async def merge_clips(project_dir: Path, scenes: list[dict], on_progress=None) -> str:
    clips_dir = project_dir / "clips"
    audio_dir = project_dir / "audio"
    subs_dir  = project_dir / "subtitles"
    subs_dir.mkdir(parents=True, exist_ok=True)
    final_path = project_dir / "final.mp4"

    async def _noop(*_): pass
    _prog = on_progress or _noop

    # 1 ── SRT timed by actual TTS audio durations
    await _prog("Generating subtitles...", 5)
    srt_path = subs_dir / "full.srt"
    await generate_srt(scenes, srt_path, audio_dir=audio_dir)

    # 2 ── Collect clips; burn subtitles onto PNG frames via Pillow
    await _prog("Burning subtitles into frames...", 15)
    ready_clips: list[Path] = []
    tmp_sub_images: list[Path] = []

    for i, scene in enumerate(scenes):
        mp4 = clips_dir / f"scene_{i+1:02d}.mp4"
        png = clips_dir / f"scene_{i+1:02d}.png"
        subtitle = scene.get("subtitle_text", "").strip()
        dur = scene.get("duration_seconds", 10)

        if mp4.exists():
            from config import settings as _s
            # HTML animated clips already contain all text content — skip subtitle overlay
            _html_clip = _s.scene_engine == "html" and _s.html_animated
            if subtitle and not _html_clip:
                # Get actual MP4 dimensions, create overlay PNG, burn via FFmpeg overlay filter
                W, H = await _get_video_dimensions(mp4)
                ovl_png = clips_dir / f"scene_{i+1:02d}_ovl.png"
                _create_subtitle_overlay(ovl_png, subtitle, W, H)
                tmp_sub_images.append(ovl_png)
                subbed_mp4 = clips_dir / f"scene_{i+1:02d}_subbed.mp4"
                await _run_ffmpeg([
                    "ffmpeg", "-y", "-i", str(mp4), "-i", str(ovl_png),
                    "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
                    "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "copy",
                    str(subbed_mp4),
                ])
                tmp_sub_images.append(subbed_mp4)
                ready_clips.append(subbed_mp4)
            else:
                ready_clips.append(mp4)
        elif png.exists():
            # Use actual TTS audio duration so subtitles stay in sync with speech
            wav = audio_dir / f"scene_{i+1:02d}.wav"
            actual_dur = await _get_duration(wav) if wav.exists() else float(dur)
            if actual_dur < 0.3:
                actual_dur = float(dur)

            narration = scene.get("narration_text", "").strip()
            chunks = _split_narration(narration) if narration else ([subtitle] if subtitle else [])

            try:
                from PIL import Image as _PILImage
                with _PILImage.open(png) as _im:
                    _W, _H = _im.size
            except Exception:
                _W, _H = 768, 1344

            tmp_mp4 = clips_dir / f"scene_{i+1:02d}_still.mp4"

            # Step 1: ONE Ken Burns video for the full scene duration (no subtitle baked in).
            # This ensures the animation runs smoothly from start to finish without restarting.
            kb_vf = _ken_burns_vf(i, actual_dur, _W, _H)
            await _run_ffmpeg([
                "ffmpeg", "-y", "-loop", "1", "-framerate", "25", "-i", str(png),
                "-c:v", "libx264", "-t", f"{actual_dur:.3f}",
                "-pix_fmt", "yuv420p", "-vf", kb_vf, str(tmp_mp4),
            ])

            # Step 2: Overlay subtitle chunk(s) using enable='between(t,start,end)'.
            # Subtitle overlays are transparent PNGs composited in one FFmpeg pass.
            if chunks:
                chunk_dur = actual_dur / len(chunks)
                cmd_sub = ["ffmpeg", "-y", "-i", str(tmp_mp4)]
                for j, chunk in enumerate(chunks):
                    # Subtitles are rendered at 1080×1920 (the Ken Burns output size)
                    ovl_png = clips_dir / f"scene_{i+1:02d}_sub_{j}.png"
                    _create_subtitle_overlay(ovl_png, chunk, 1080, 1920)
                    cmd_sub += ["-i", str(ovl_png)]
                    tmp_sub_images.append(ovl_png)

                filter_parts: list[str] = []
                prev = "[0:v]"
                for k in range(len(chunks)):
                    t_start = k * chunk_dur
                    t_end = (k + 1) * chunk_dur
                    out_tag = "[vout]" if k == len(chunks) - 1 else f"[v{k}]"
                    filter_parts.append(
                        f"{prev}[{k+1}:v]overlay=0:0"
                        f":enable='between(t,{t_start:.3f},{t_end:.3f})'"
                        f"{out_tag}"
                    )
                    prev = out_tag

                subbed_mp4 = clips_dir / f"scene_{i+1:02d}_subbed.mp4"
                cmd_sub += [
                    "-filter_complex", ";".join(filter_parts),
                    "-map", "[vout]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    str(subbed_mp4),
                ]
                await _run_ffmpeg(cmd_sub)
                tmp_mp4.unlink(missing_ok=True)
                subbed_mp4.rename(tmp_mp4)
                tmp_sub_images.append(subbed_mp4)

            ready_clips.append(tmp_mp4)

    if not ready_clips:
        raise RuntimeError("No clips found. Render at least one scene first.")

    # 3 ── Concat audio
    await _prog("Merging audio...", 30)
    audio_entries = []
    for i in range(len(scenes)):
        ap = audio_dir / f"scene_{i+1:02d}.wav"
        if ap.exists():
            audio_entries.append(f"file '{ap.resolve()}'")
    merged_audio = project_dir / "merged_audio.wav"
    if audio_entries:
        ac = project_dir / "audio_concat.txt"
        ac.write_text("\n".join(audio_entries), encoding="utf-8")
        await _run_ffmpeg([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(ac), "-c", "copy", str(merged_audio),
        ])
        ac.unlink(missing_ok=True)

    # 4 ── Video: xfade + scale
    await _prog("Applying xfade transitions...", 50)
    durations = [await _get_duration(c) for c in ready_clips]
    video_fx  = project_dir / "video_fx.mp4"
    n         = len(ready_clips)

    if n == 1:
        await _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(ready_clips[0]),
            "-vf", SCALE_VF,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
            str(video_fx),
        ])
    else:
        cmd = ["ffmpeg", "-y"]
        for c in ready_clips:
            cmd += ["-i", str(c)]

        # Build xfade chain: [0:v][1:v]xfade...[xf0]; [xf0][2:v]xfade...[xfout]; ...
        fc: list[str] = []
        cumulative = 0.0
        prev = "[0:v]"
        scene_transitions = [s.get("transition", "") for s in scenes]
        scene_types = [s.get("scene_type", "") for s in scenes]
        for i in range(n - 1):
            cumulative += durations[i]
            offset = max(0.0, cumulative - (i + 1) * TRANSITION_DUR)
            out = "[xfout]" if i == n - 2 else f"[xf{i}]"
            stype = scene_types[i] if i < len(scene_types) else ""
            tr = _pick_transition(scene_transitions[i] if i < len(scene_transitions) else "", i, stype)
            fc.append(
                f"{prev}[{i+1}:v]xfade=transition={tr}"
                f":duration={TRANSITION_DUR:.2f}:offset={offset:.3f}{out}"
            )
            prev = out

        fc.append(f"[xfout]{SCALE_VF}[scaled]")

        cmd += [
            "-filter_complex", ";".join(fc),
            "-map", "[scaled]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
            str(video_fx),
        ]
        await _run_ffmpeg(cmd)

    # 5 ── Pad video to match audio so xfade overlap doesn't cut the last scene
    await _prog("Adding audio...", 80)
    if merged_audio.exists():
        audio_total = await _get_duration(merged_audio)
        video_total = await _get_duration(video_fx)
        pad_needed  = audio_total - video_total
        if pad_needed > 0.05:
            video_padded = project_dir / "video_padded.mp4"
            await _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(video_fx),
                "-vf", f"tpad=stop_mode=clone:stop_duration={pad_needed:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                str(video_padded),
            ])
            video_fx.unlink(missing_ok=True)
            video_padded.rename(video_fx)

    # 6 ── Color grading pass (optional)
    from config import settings as _cfg
    _grade_filter = COLOR_GRADES.get(_cfg.color_grade, "")
    if _grade_filter:
        await _prog(f"Applying color grade: {_cfg.color_grade}...", 85)
        video_graded = project_dir / "video_graded.mp4"
        await _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(video_fx),
            "-vf", _grade_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
            str(video_graded),
        ])
        video_fx.unlink(missing_ok=True)
        video_graded.rename(video_fx)

    # 7 ── Combine video + audio (+ optional background music)
    bg_path = Path(_cfg.bg_music_path) if _cfg.bg_music_path else None
    has_bg = bg_path and bg_path.exists()
    has_voice = merged_audio.exists()

    cmd_fin = ["ffmpeg", "-y", "-i", str(video_fx)]
    if has_voice:
        cmd_fin += ["-i", str(merged_audio)]
    if has_bg:
        cmd_fin += ["-stream_loop", "-1", "-i", str(bg_path)]

    # Normalize audio to 44100 Hz stereo so intro/outro card concat is seamless
    _AUDIO_NORM = ["-ar", "44100", "-ac", "2"]

    if has_voice and has_bg:
        vol = _cfg.bg_music_volume
        cmd_fin += [
            "-filter_complex",
            # Normalize voice to stereo
            f"[1:a]aresample=44100,pan=stereo|FL=FL+0.707*FC|FR=FR+0.707*FC,alimiter=limit=0.95[voice];"
            # Music at configured volume level
            f"[2:a]aresample=44100,volume={vol:.3f}[music_raw];"
            # Split voice: one for output, one for sidechain detector
            f"[voice]asplit=2[voice_out][voice_sc];"
            # Sidechain compress: music ducks when voice is present
            # threshold=0.02 → triggers on quiet speech; ratio=8 → aggressive duck
            # attack=15ms (fast react) release=400ms (slow fade back)
            f"[music_raw][voice_sc]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=400:makeup=1.4[music_duck];"
            # Final mix: ducked music + voice
            f"[voice_out][music_duck]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        ]
    elif has_voice:
        cmd_fin += [
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        ] + _AUDIO_NORM
    else:
        cmd_fin += ["-c:v", "copy", "-an"]

    cmd_fin.append(str(final_path))
    await _run_ffmpeg(cmd_fin)

    # Cleanup temps
    for p in [merged_audio, video_fx]:
        p.unlink(missing_ok=True)
    for c in ready_clips:
        if "_still" in c.name or "_subbed" in c.name:
            c.unlink(missing_ok=True)
    for p in tmp_sub_images:
        p.unlink(missing_ok=True)

    # 8 ── Branding: watermark + intro/outro cards
    wm_path = Path(_cfg.watermark_path) if _cfg.watermark_path else None
    has_wm = wm_path and wm_path.exists()
    if has_wm or _cfg.enable_intro_card or _cfg.enable_outro_card:
        await _prog("Applying branding...", 95)

        # 8a — Watermark overlay
        if has_wm:
            pos_map = {
                "topleft":     "20:20",
                "topright":    "W-w-20:20",
                "bottomleft":  "20:H-h-20",
                "bottomright": "W-w-20:H-h-20",
            }
            pos = pos_map.get(_cfg.watermark_position, "W-w-20:20")
            op  = min(1.0, max(0.0, _cfg.watermark_opacity))
            wm_tmp = project_dir / "final_wm.mp4"
            await _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(final_path), "-i", str(wm_path),
                "-filter_complex",
                f"[1:v]format=rgba,colorchannelmixer=aa={op:.2f}[wm];[0:v][wm]overlay={pos}[out]",
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "copy",
                str(wm_tmp),
            ])
            final_path.unlink(missing_ok=True)
            wm_tmp.rename(final_path)

        # 8b — Intro + outro cards
        card_parts: list[Path] = []
        tmp_cards: list[Path] = []

        if _cfg.enable_intro_card:
            import json as _json2
            meta: dict = {}
            meta_path = project_dir / "metadata.json"
            if meta_path.exists():
                meta = _json2.loads(meta_path.read_text(encoding="utf-8"))
            topic = meta.get("topic", "")
            intro_mp4 = project_dir / "intro_card.mp4"
            await _render_animated_card(intro_mp4, topic, card_type="intro")
            card_parts.append(intro_mp4)
            tmp_cards.append(intro_mp4)

        card_parts.append(final_path)

        if _cfg.enable_outro_card:
            outro_mp4 = project_dir / "outro_card.mp4"
            await _render_animated_card(outro_mp4, _cfg.outro_card_text, card_type="outro")
            card_parts.append(outro_mp4)
            tmp_cards.append(outro_mp4)

        if len(card_parts) > 1:
            branded_tmp = project_dir / "final_branded.mp4"
            concat_txt2 = project_dir / "branded_concat.txt"
            concat_txt2.write_text("\n".join(f"file '{p.resolve()}'" for p in card_parts), encoding="utf-8")
            await _run_ffmpeg([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_txt2),
                "-map", "0:v:0", "-map", "0:a:0",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                str(branded_tmp),
            ])
            concat_txt2.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            branded_tmp.rename(final_path)

        for p in tmp_cards:
            p.unlink(missing_ok=True)

    await _prog("Assembly complete!", 100)
    return str(final_path)


# ── Card / branding generators ────────────────────────────────────────────────

async def _render_animated_card(dst: Path, text: str, card_type: str = "intro") -> None:
    """Render a cinematic animated intro/outro card as MP4 via Playwright."""
    duration = 3.0
    accent = "#f59e0b" if card_type == "intro" else "#10b981"
    bg1 = "#0a0800" if card_type == "intro" else "#001a0d"
    bg2 = "#1a1000" if card_type == "intro" else "#003320"
    label = "PEPE AI" if card_type == "intro" else "LIKE · SHARE · FOLLOW"
    import textwrap as _tw
    short = _tw.shorten(text or "", 60, placeholder="…")

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;700;900&display=swap');
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{width:1080px;height:1920px;overflow:hidden;
  background:linear-gradient(160deg,{bg1} 0%,{bg2} 60%,#000 100%);
  font-family:'Be Vietnam Pro',sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;}}
@keyframes wipeR{{from{{clip-path:inset(0 100% 0 0)}}to{{clip-path:inset(0 0% 0 0)}}}}
@keyframes fadeU{{from{{opacity:0;transform:translateY(40px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes popIn{{0%{{opacity:0;transform:scale(0.7)}}70%{{transform:scale(1.05)}}100%{{opacity:1;transform:scale(1)}}}}
@keyframes scan{{0%{{top:-4px;opacity:.5}}100%{{top:100%;opacity:0}}}}
.scan{{position:absolute;left:0;right:0;height:3px;background:linear-gradient(90deg,transparent,{accent},transparent);
  animation:scan 2.5s linear infinite;z-index:10;}}
.logo{{color:{accent};font-size:32px;font-weight:800;letter-spacing:12px;text-transform:uppercase;
  opacity:0;animation:fadeU 0.5s ease 0.2s forwards;margin-bottom:60px;}}
.bar{{width:120px;height:5px;background:{accent};border-radius:3px;
  animation:wipeR 0.6s cubic-bezier(0.16,1,0.3,1) 0.5s forwards;clip-path:inset(0 100% 0 0);
  margin-bottom:48px;}}
.title{{color:#fff;font-size:{'72px' if len(short) < 40 else '58px'};font-weight:900;
  text-align:center;line-height:1.12;letter-spacing:-2px;max-width:900px;
  text-shadow:0 4px 40px rgba(0,0,0,.8);
  opacity:0;animation:fadeU 0.65s cubic-bezier(0.16,1,0.3,1) 0.7s forwards;
  margin-bottom:52px;}}
.sub{{color:{accent};font-size:30px;font-weight:700;letter-spacing:6px;text-transform:uppercase;
  opacity:0;animation:fadeU 0.5s ease 1.1s forwards;}}
.corner{{position:absolute;width:80px;height:80px;border-color:{accent};border-style:solid;opacity:0.5;}}
.tl{{top:60px;left:60px;border-width:4px 0 0 4px;}}
.tr{{top:60px;right:60px;border-width:4px 4px 0 0;}}
.bl{{bottom:60px;left:60px;border-width:0 0 4px 4px;}}
.br{{bottom:60px;right:60px;border-width:0 4px 4px 0;}}
</style></head><body>
<div class="scan"></div>
<div class="corner tl"></div>
<div class="corner tr"></div>
<div class="corner bl"></div>
<div class="corner br"></div>
<div class="logo">{label}</div>
<div class="bar"></div>
<div class="title">{short}</div>
<div class="sub">{'Khám phá ngay' if card_type == 'intro' else '© PePeApp'}</div>
</body></html>"""

    try:
        from playwright.async_api import async_playwright
        webm_dir = dst.parent / "_webm_card"
        webm_dir.mkdir(exist_ok=True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True,
                args=["--autoplay-policy=no-user-gesture-required"])
            ctx = await browser.new_context(
                viewport={"width": 1080, "height": 1920},
                record_video_dir=str(webm_dir),
                record_video_size={"width": 1080, "height": 1920},
            )
            page = await ctx.new_page()
            await page.set_content(html, wait_until="networkidle")
            await asyncio.sleep(duration + 0.3)
            vid = page.video
            await ctx.close()
            webm = dst.with_suffix(".tmp.webm")
            await vid.save_as(str(webm))
            await browser.close()
        # WebM → h264 MP4 with silent audio
        await _run_ffmpeg([
            "ffmpeg", "-y", "-i", str(webm),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(dst),
        ])
        webm.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(webm_dir, ignore_errors=True)
    except Exception as e:
        print(f"[assembler] animated card failed ({e}), falling back to Pillow card")
        png_tmp = dst.with_suffix(".png")
        _generate_card(png_tmp, text, card_type=card_type)
        await _run_ffmpeg([
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "25", "-t", "3", "-i", str(png_tmp),
            "-f", "lavfi", "-t", "3", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", SCALE_VF, "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(dst),
        ])
        png_tmp.unlink(missing_ok=True)


def _generate_card(dst: Path, text: str, card_type: str = "intro", W: int = 1080, H: int = 1920) -> None:
    """Generate an intro or outro title card PNG using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        Image = ImageDraw = ImageFont = None  # type: ignore

    if Image is None:
        dst.write_bytes(b"")
        return

    img = Image.new("RGB", (W, H), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    # Subtle gradient — horizontal bands
    for y in range(H):
        ratio = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=(int(10 + 25 * ratio), int(10 + 15 * ratio), int(20 + 35 * ratio)),
        )

    accent = (255, 180, 0) if card_type == "intro" else (0, 210, 110)
    draw.rectangle([0, 0, W, 8], fill=accent)
    draw.rectangle([0, H - 8, W, H], fill=accent)

    font_lg = font_sm = None
    for fp in _FONT_CANDIDATES:
        if Path(fp).exists():
            try:
                font_lg = ImageFont.truetype(fp, 72)
                font_sm = ImageFont.truetype(fp, 42)
                break
            except Exception:
                pass
    if font_lg is None:
        font_lg = font_sm = ImageFont.load_default()

    if card_type == "intro":
        label = "PEPE AI"
        lb = draw.textbbox((0, 0), label, font=font_sm)
        draw.text(((W - (lb[2] - lb[0])) // 2, H // 3 - 90), label, font=font_sm, fill=accent)
        if text:
            wrapped = _wrap_text(text, font_lg, draw, int(W * 0.85))
            bboxes = [draw.textbbox((0, 0), ln, font=font_lg) for ln in wrapped]
            lh = max(b[3] - b[1] for b in bboxes) if bboxes else 80
            total = len(wrapped) * lh + (len(wrapped) - 1) * 16
            sy = H // 3 - total // 2
            for idx, (ln, bb) in enumerate(zip(wrapped, bboxes)):
                draw.text(((W - (bb[2] - bb[0])) // 2, sy + idx * (lh + 16)), ln, font=font_lg, fill=(255, 255, 255))
    else:
        if text:
            wrapped = _wrap_text(text, font_lg, draw, int(W * 0.85))
            bboxes = [draw.textbbox((0, 0), ln, font=font_lg) for ln in wrapped]
            lh = max(b[3] - b[1] for b in bboxes) if bboxes else 80
            total = len(wrapped) * lh + (len(wrapped) - 1) * 16
            sy = H // 2 - total // 2
            for idx, (ln, bb) in enumerate(zip(wrapped, bboxes)):
                draw.text(((W - (bb[2] - bb[0])) // 2, sy + idx * (lh + 16)), ln, font=font_lg, fill=(255, 255, 255))
        sub_label = "Like · Share · Subscribe"
        slb = draw.textbbox((0, 0), sub_label, font=font_sm)
        draw.text(((W - (slb[2] - slb[0])) // 2, H * 2 // 3), sub_label, font=font_sm, fill=accent)

    img.save(dst, "PNG")


# ── Subtitle burn via Pillow ──────────────────────────────────────────────────

async def _get_video_dimensions(path: Path) -> tuple[int, int]:
    """Return (width, height) of a video file via ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        for stream in json.loads(stdout).get("streams", []):
            w = stream.get("width")
            h = stream.get("height")
            if w and h:
                return int(w), int(h)
    except Exception:
        pass
    return 1080, 1920


def _create_subtitle_overlay(dst: Path, text: str, W: int, H: int) -> None:
    """Create a transparent PNG at WxH with subtitle text — for overlay onto video."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = None
    font_size = max(24, int(SUBTITLE_FONT_SIZE * W / 1080))
    for fp in _FONT_CANDIDATES:
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    max_w = int(W * 0.90)
    wrapped = _wrap_text(text, font, draw, max_w)

    line_bboxes = [draw.textbbox((0, 0), ln, font=font) for ln in wrapped]
    line_h = max(b[3] - b[1] for b in line_bboxes) if line_bboxes else 0
    gap = 6
    block_h = len(wrapped) * line_h + (len(wrapped) - 1) * gap
    block_w = max(b[2] - b[0] for b in line_bboxes) if line_bboxes else 0

    top_y  = int(H * SUBTITLE_Y_RATIO)
    left_x = (W - block_w) // 2
    pad    = 14

    draw.rectangle(
        [left_x - pad, top_y - pad, left_x + block_w + pad, top_y + block_h + pad],
        fill=(0, 0, 0, 170),
    )
    y = top_y
    for line, bbox in zip(wrapped, line_bboxes):
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_h + gap

    img.save(dst, "PNG")


def _wrap_text(text: str, font, draw, max_width: int) -> list[str]:
    """Simple word-wrap: split text into lines that fit within max_width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


# ── FFmpeg helpers ────────────────────────────────────────────────────────────

def _srt_ts(sec: float) -> str:
    h = int(sec // 3600); m = int((sec % 3600) // 60)
    s = int(sec % 60);    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def _get_duration(path: Path) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        for stream in json.loads(stdout).get("streams", []):
            if "duration" in stream:
                return float(stream["duration"])
    except Exception:
        pass
    return 10.0


async def _run_ffmpeg(cmd: list[str]):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        lines = [l for l in stderr.decode(errors="replace").splitlines() if l.strip()]
        raise RuntimeError("FFmpeg error:\n" + "\n".join(lines[-8:]))
