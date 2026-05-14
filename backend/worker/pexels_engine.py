"""
pexels_engine.py — Fetch short stock video clips from Pexels as scene backgrounds.

Usage:
    video_path = await fetch_pexels_video(query="bitcoin crypto", cache_dir=..., idx=0)
    # Returns Path to a cached .mp4 (portrait 1080x1920 or nearest), or None on failure.

API docs: https://www.pexels.com/api/documentation/#videos-search
"""
import asyncio
import hashlib
import re
from pathlib import Path

_PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"

# Prefer portrait videos; fallback to landscape (we'll crop)
_ORIENT_PREF = ["portrait", "landscape"]
_MIN_DUR = 5        # seconds — skip clips shorter than this
_MAX_DUR = 60       # seconds — skip very long clips


async def fetch_pexels_video(
    query: str,
    cache_dir: Path,
    idx: int = 0,
    api_key: str = "",
) -> Path | None:
    """
    Search Pexels for a portrait video matching `query`, download and cache it.
    `idx` selects which result to use so different scenes get different clips.
    Returns a Path to the local .mp4 or None on failure.
    """
    if not api_key:
        from config import settings
        api_key = settings.pexels_api_key
    if not api_key:
        return None

    # Normalize query — Pexels works better with short keywords
    kw = _clean_query(query)
    cache_key = hashlib.md5(f"{kw}:{idx}".encode()).hexdigest()[:12]
    cached = cache_dir / f"pexels_{cache_key}.mp4"
    if cached.exists() and cached.stat().st_size > 50_000:
        return cached

    try:
        import httpx
    except ImportError:
        return None

    # Try portrait first, then landscape
    for orient in _ORIENT_PREF:
        url = await _search_video_url(kw, orient, idx, api_key)
        if url:
            break
    if not url:
        return None

    # Download
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(cached, "wb") as f:
                    async for chunk in resp.aiter_bytes(65536):
                        f.write(chunk)
        if cached.stat().st_size < 50_000:
            cached.unlink(missing_ok=True)
            return None
        return cached
    except Exception as e:
        print(f"[pexels] download error: {e}")
        cached.unlink(missing_ok=True)
        return None


async def _search_video_url(query: str, orientation: str, idx: int, api_key: str) -> str | None:
    """Return a download URL for the best-fit video file or None."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _PEXELS_VIDEO_SEARCH,
                headers={"Authorization": api_key},
                params={"query": query, "orientation": orientation, "per_page": 15, "size": "medium"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"[pexels] search error: {e}")
        return None

    videos = data.get("videos", [])
    if not videos:
        return None

    # Filter by duration
    valid = [v for v in videos if _MIN_DUR <= v.get("duration", 0) <= _MAX_DUR]
    if not valid:
        valid = videos  # relax filter

    target = valid[idx % len(valid)]
    files = target.get("video_files", [])
    if not files:
        return None

    # Prefer HD portrait file; fall back to largest available
    def _score(f: dict) -> int:
        w, h = f.get("width", 0), f.get("height", 0)
        q = f.get("quality", "")
        is_portrait = h > w
        is_hd = q in ("hd", "sd") and max(w, h) >= 720
        return (is_portrait * 100) + (is_hd * 10) + max(w, h) // 100

    best = max(files, key=_score)
    return best.get("link")


def _clean_query(raw: str) -> str:
    """Strip visual style instructions, keep only topic keywords (≤40 chars)."""
    # Remove common noise from visual_prompt field
    noise = [
        "cinematic", "dramatic lighting", "high detail", "photorealistic",
        "no humans", "no people", "objects only", "split composition",
        "4k", "8k", "ultra hd", "studio lighting",
    ]
    s = raw.lower()
    for n in noise:
        s = s.replace(n, " ")
    # Keep alpha, numbers, spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    words = s.split()
    # Take first 4 meaningful words
    meaningful = [w for w in words if len(w) > 3][:4]
    return " ".join(meaningful)[:40].strip() or "abstract technology"
