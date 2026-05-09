"""
Publisher — Upload final videos to social media platforms.
Supports: YouTube, TikTok, Facebook Pages.
"""
import asyncio
import json
from pathlib import Path


async def publish_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    targets: list[str],
    on_progress=None,
) -> dict:
    """
    Publish a video to one or more social media platforms.

    Args:
        video_path: Absolute path to the final .mp4
        title: Video title
        description: Video description
        tags: List of hashtags/tags
        targets: List of platform names ("youtube", "tiktok", "facebook")
        on_progress: async callback(step, pct)

    Returns:
        Dict of {platform: {"status": "ok"|"error", "url": "...", "error": "..."}}
    """
    results = {}

    for platform in targets:
        if on_progress:
            await on_progress(f"Publishing to {platform}...", 10)

        try:
            if platform == "youtube":
                url = await _publish_youtube(video_path, title, description, tags)
                results["youtube"] = {"status": "ok", "url": url}

            elif platform == "tiktok":
                url = await _publish_tiktok(video_path, title, tags)
                results["tiktok"] = {"status": "ok", "url": url}

            elif platform == "facebook":
                url = await _publish_facebook(video_path, title, description)
                results["facebook"] = {"status": "ok", "url": url}

            else:
                results[platform] = {"status": "error", "error": f"Unknown platform: {platform}"}

        except Exception as e:
            results[platform] = {"status": "error", "error": str(e)}

    if on_progress:
        await on_progress("Publishing complete", 100)

    return results


async def _publish_youtube(video_path: str, title: str, description: str, tags: list[str]) -> str:
    """
    Upload to YouTube via YouTube Data API v3.
    Requires: pip install google-api-python-client google-auth-oauthlib
    OAuth2 credentials must be configured in config/social_accounts.yaml
    """
    # TODO: Implement YouTube upload
    # 1. Load OAuth2 credentials from config
    # 2. Build youtube service
    # 3. Upload video with metadata
    # 4. Return video URL
    raise NotImplementedError(
        "YouTube publishing not yet configured. "
        "Set up OAuth2 credentials in config/social_accounts.yaml"
    )


async def _publish_tiktok(video_path: str, title: str, tags: list[str]) -> str:
    """
    Upload to TikTok via Content Posting API or Playwright automation.
    """
    # TODO: Implement TikTok upload
    # Option A: TikTok Content Posting API (requires app approval)
    # Option B: Playwright browser automation (easier, less stable)
    raise NotImplementedError(
        "TikTok publishing not yet configured. "
        "Set up API credentials in config/social_accounts.yaml"
    )


async def _publish_facebook(video_path: str, title: str, description: str) -> str:
    """
    Upload to Facebook Page via Graph API.
    Requires: Page access token with publish_video permission.
    """
    # TODO: Implement Facebook upload
    # 1. Load page access token from config
    # 2. Upload video via Graph API
    # 3. Return post URL
    raise NotImplementedError(
        "Facebook publishing not yet configured. "
        "Set up Page access token in config/social_accounts.yaml"
    )
