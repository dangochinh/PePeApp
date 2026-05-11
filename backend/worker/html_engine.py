"""
HTML Engine — render each scene as an HTML/CSS card → 1080×1920 PNG screenshot.
Replaces DrawThings as the image source in the 2.0 branch.

Templates:
  dark        — dark gradient, accent bar, large headline
  gradient    — vivid full-bleed gradient, bold white text
  minimal     — clean white card, black typography
  bold        — oversized single word / phrase, colour pop
  news        — news-card layout with category badge + body text
  cinematic   — film-strip look, letter-box bars, muted tones
"""
import asyncio
import hashlib
import re
import textwrap
from pathlib import Path
from typing import Callable

from models.schemas import Scene

# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------

_PALETTES = [
    ("#0f0c29", "#302b63", "#24243e", "#e040fb"),   # deep purple
    ("#0a0a0a", "#1a1a2e", "#16213e", "#00d4ff"),   # midnight blue
    ("#1a1a1a", "#2d1b69", "#11998e", "#38ef7d"),   # teal emerald
    ("#200122", "#6f0000", "#cc2b5e", "#ff6b6b"),   # crimson
    ("#0d0d0d", "#1b4332", "#40916c", "#95d5b2"),   # forest
    ("#0a0a0a", "#1a1a1a", "#f7971e", "#ffd200"),   # gold / sunrise
    ("#12012c", "#1e014f", "#7b2ff7", "#e040fb"),   # neon violet
    ("#001219", "#005f73", "#0a9396", "#94d2bd"),   # ocean depth
]


def _palette_for(seed_text: str) -> tuple[str, str, str, str]:
    idx = int(hashlib.md5(seed_text.encode()).hexdigest(), 16) % len(_PALETTES)
    return _PALETTES[idx]


def _darken(hex_color: str, factor: float = 0.6) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r * factor), int(g * factor), int(b * factor)
    )


# ---------------------------------------------------------------------------
# HTML template builders
# ---------------------------------------------------------------------------

_COMMON_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  width: 1080px; height: 1920px; overflow: hidden;
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}
"""

_SCENE_ICONS = ["💡", "🔍", "📊", "🎯", "🚀", "✅", "⚡", "🌟", "🔥", "💎"]


def _scene_icon(scene_number: int) -> str:
    return _SCENE_ICONS[(scene_number - 1) % len(_SCENE_ICONS)]


def _split_headline(text: str, max_chars: int = 40) -> list[str]:
    """Break text into display lines with max_chars each."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _html_dark(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    icon = _scene_icon(scene.scene_number)
    lines = _split_headline(scene.subtitle_text, 38)
    headline_html = "<br>".join(f'<span class="hl-line">{ln}</span>' for ln in lines)
    narration = textwrap.shorten(scene.narration_text, width=220, placeholder="…")
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: linear-gradient(160deg, {bg1} 0%, {bg2} 60%, #000 100%);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 80px 60px;
}}
.accent-top {{ width: 120px; height: 6px; background: {accent}; border-radius: 3px; margin-bottom: 60px; }}
.icon {{ font-size: 96px; margin-bottom: 48px; filter: drop-shadow(0 0 24px {accent}88); }}
.headline {{
  text-align: center; color: #fff;
  font-size: 82px; font-weight: 900; line-height: 1.15;
  letter-spacing: -1px; margin-bottom: 48px;
  text-shadow: 0 4px 32px rgba(0,0,0,.7);
}}
.narration {{
  text-align: center; color: rgba(255,255,255,.72);
  font-size: 44px; font-weight: 400; line-height: 1.5;
  max-width: 900px;
}}
.badge {{
  position: absolute; bottom: 80px; right: 80px;
  background: {accent}22; border: 2px solid {accent}66;
  color: {accent}; font-size: 34px; font-weight: 700;
  padding: 14px 28px; border-radius: 40px;
  letter-spacing: 1px;
}}
.scene-num {{
  position: absolute; top: 80px; left: 80px;
  color: rgba(255,255,255,.35); font-size: 32px; font-weight: 600; letter-spacing: 4px;
}}
</style></head><body>
<span class="scene-num">SCENE {scene.scene_number:02d}</span>
<div class="accent-top"></div>
<div class="icon">{icon}</div>
<div class="headline">{headline_html}</div>
<div class="narration">{narration}</div>
<div class="badge">{title[:28]}</div>
</body></html>"""


def _html_gradient(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    lines = _split_headline(scene.subtitle_text, 30)
    headline_html = "".join(f'<div class="line">{ln}</div>' for ln in lines)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: linear-gradient(145deg, {bg1} 0%, {accent}aa 50%, {bg2} 100%);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 80px 60px; gap: 40px;
}}
.line {{
  color: #fff; font-size: 100px; font-weight: 900;
  text-align: center; line-height: 1.1;
  text-shadow: 0 8px 40px rgba(0,0,0,.6);
  letter-spacing: -2px;
}}
.divider {{ width: 200px; height: 8px; background: rgba(255,255,255,.6); border-radius: 4px; }}
.sub {{
  color: rgba(255,255,255,.85); font-size: 50px; font-weight: 500;
  text-align: center; line-height: 1.4; max-width: 900px;
}}
.num {{
  position: absolute; top: 60px; left: 50%; transform: translateX(-50%);
  color: rgba(255,255,255,.4); font-size: 28px; letter-spacing: 8px; font-weight: 700;
}}
</style></head><body>
<span class="num">·  {scene.scene_number}  ·</span>
{headline_html}
<div class="divider"></div>
<div class="sub">{textwrap.shorten(scene.narration_text, 180, placeholder="…")}</div>
</body></html>"""


def _html_minimal(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    lines = _split_headline(scene.subtitle_text, 35)
    headline_html = "<br>".join(lines)
    narration_lines = textwrap.wrap(scene.narration_text, 46)[:6]
    narration_html = "".join(f"<p>{l}</p>" for l in narration_lines)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: #fafafa;
  display: flex; flex-direction: column; justify-content: center;
  padding: 120px 90px;
}}
.num {{ color: {accent}; font-size: 36px; font-weight: 800; letter-spacing: 6px; margin-bottom: 48px; }}
.bar {{ width: 80px; height: 8px; background: {accent}; border-radius: 4px; margin-bottom: 72px; }}
.headline {{
  color: #111; font-size: 86px; font-weight: 900; line-height: 1.1;
  letter-spacing: -2px; margin-bottom: 64px;
}}
.narration p {{
  color: #444; font-size: 46px; line-height: 1.6; margin-bottom: 8px;
}}
.footer {{
  position: absolute; bottom: 90px; left: 90px;
  color: {accent}; font-size: 32px; font-weight: 700; letter-spacing: 2px;
}}
</style></head><body>
<div class="num">0{scene.scene_number}</div>
<div class="bar"></div>
<div class="headline">{headline_html}</div>
<div class="narration">{narration_html}</div>
<div class="footer">{title[:32]}</div>
</body></html>"""


def _html_bold(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    words = scene.subtitle_text.split()
    big = " ".join(words[:4]).upper()
    rest = " ".join(words[4:])
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: {bg1};
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 80px;
}}
.big {{
  color: {accent}; font-size: 160px; font-weight: 900;
  text-align: center; line-height: 0.95; letter-spacing: -4px;
  text-transform: uppercase;
  text-shadow: 0 0 60px {accent}55;
  margin-bottom: 60px;
}}
.rest {{
  color: rgba(255,255,255,.8); font-size: 60px; font-weight: 500;
  text-align: center; line-height: 1.35; max-width: 900px;
}}
.line-top, .line-bot {{
  width: 100%; height: 6px; background: linear-gradient(90deg, transparent, {accent}, transparent);
  position: absolute;
}}
.line-top {{ top: 100px; }}
.line-bot {{ bottom: 100px; }}
.scene-badge {{
  position: absolute; top: 80px; right: 80px;
  color: rgba(255,255,255,.3); font-size: 28px; letter-spacing: 4px;
}}
</style></head><body>
<div class="line-top"></div>
<span class="scene-badge">S{scene.scene_number:02d}</span>
<div class="big">{big}</div>
<div class="rest">{rest}</div>
<div class="line-bot"></div>
</body></html>"""


def _html_news(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    # Category derived from scene number label pattern (WHAT/WHY/WHO/HOW/WHEN/IMPACT)
    labels = ["WHAT", "WHY", "WHO", "HOW", "WHEN", "KEY POINT"]
    category = labels[(scene.scene_number - 1) % len(labels)]
    narration_paras = textwrap.wrap(scene.narration_text, 44)[:5]
    paras_html = "".join(f"<p>{p}</p>" for p in narration_paras)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: linear-gradient(180deg, #0a0a0a 0%, #111 100%);
  padding: 0;
}}
.header {{
  background: {accent};
  padding: 60px 80px 50px;
}}
.category {{
  color: rgba(0,0,0,.7); font-size: 30px; font-weight: 800;
  letter-spacing: 6px; text-transform: uppercase; margin-bottom: 20px;
}}
.headline {{
  color: #fff; font-size: 76px; font-weight: 900;
  line-height: 1.1; letter-spacing: -1.5px;
  text-shadow: 0 3px 20px rgba(0,0,0,.5);
}}
.body {{
  padding: 70px 80px;
}}
.body p {{
  color: rgba(255,255,255,.78); font-size: 48px; line-height: 1.6;
  margin-bottom: 16px;
}}
.footer {{
  position: absolute; bottom: 0; left: 0; right: 0;
  background: {accent}22; border-top: 2px solid {accent}44;
  padding: 36px 80px;
  display: flex; align-items: center; justify-content: space-between;
}}
.footer-title {{ color: {accent}; font-size: 36px; font-weight: 800; }}
.footer-num {{ color: rgba(255,255,255,.4); font-size: 32px; }}
</style></head><body>
<div class="header">
  <div class="category">{category}</div>
  <div class="headline">{scene.subtitle_text}</div>
</div>
<div class="body">{paras_html}</div>
<div class="footer">
  <span class="footer-title">{title[:28]}</span>
  <span class="footer-num">{scene.scene_number} / 6</span>
</div>
</body></html>"""


def _html_cinematic(scene: Scene, title: str, accent: str, bg1: str, bg2: str) -> str:
    lines = _split_headline(scene.subtitle_text, 32)
    headline_html = "<br>".join(lines)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{
  background: linear-gradient(180deg, {bg1} 0%, #050505 100%);
  display: flex; flex-direction: column; justify-content: center;
  padding: 0 80px;
  position: relative;
}}
.letter-box {{
  position: absolute; left: 0; right: 0; height: 220px;
  background: #000;
}}
.letter-box.top {{ top: 0; }}
.letter-box.bot {{ bottom: 0; }}
.content {{
  display: flex; flex-direction: column; align-items: flex-start;
  padding: 0 20px;
}}
.rule {{ width: 120px; height: 4px; background: {accent}; margin-bottom: 60px; }}
.headline {{
  color: #fff; font-size: 88px; font-weight: 900; line-height: 1.08;
  letter-spacing: -2px; margin-bottom: 60px;
  text-shadow: 0 2px 24px rgba(0,0,0,.8);
}}
.narration {{
  color: rgba(255,255,255,.6); font-size: 42px; line-height: 1.6;
}}
.corner {{
  position: absolute; bottom: 240px; right: 80px;
  color: rgba(255,255,255,.25); font-size: 28px; letter-spacing: 4px;
  font-style: italic;
}}
</style></head><body>
<div class="letter-box top"></div>
<div class="content">
  <div class="rule"></div>
  <div class="headline">{headline_html}</div>
  <div class="narration">{textwrap.shorten(scene.narration_text, 200, placeholder="…")}</div>
</div>
<div class="corner">{title[:24]}</div>
<div class="letter-box bot"></div>
</body></html>"""


_TEMPLATE_MAP = {
    "dark": _html_dark,
    "gradient": _html_gradient,
    "minimal": _html_minimal,
    "bold": _html_bold,
    "news": _html_news,
    "cinematic": _html_cinematic,
}

AVAILABLE_TEMPLATES = list(_TEMPLATE_MAP.keys())


def build_html(scene: Scene, title: str, template: str) -> str:
    bg1, bg2, bg3, accent = _palette_for(title + str(scene.scene_number))
    fn = _TEMPLATE_MAP.get(template, _html_dark)
    return fn(scene, title, accent, bg1, bg2)


# ---------------------------------------------------------------------------
# Screenshot with Playwright
# ---------------------------------------------------------------------------

async def render_scene_to_png(
    scene: Scene,
    title: str,
    output_path: Path,
    template: str = "dark",
    on_progress: Callable[[str, int], None] | None = None,
) -> Path:
    """Render one scene card to a 1080×1920 PNG via headless Chromium."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from e

    if on_progress:
        on_progress(f"🖼️ HTML render scene {scene.scene_number}", 0)

    html = build_html(scene, title, template)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await page.set_content(html, wait_until="networkidle")
        # Brief pause for any CSS transitions to settle
        await asyncio.sleep(0.1)
        await page.screenshot(path=str(output_path), full_page=False)
        await browser.close()

    if on_progress:
        on_progress(f"🖼️ HTML render scene {scene.scene_number} ready", 100)

    return output_path


async def render_all_scenes(
    scenes: list[Scene],
    title: str,
    clips_dir: Path,
    template: str = "dark",
    on_progress: Callable[[str, int], None] | None = None,
) -> list[Path]:
    """Render all scenes sequentially, return list of PNG paths."""
    paths = []
    for i, scene in enumerate(scenes):
        out = clips_dir / f"scene_{scene.scene_number:02d}.png"
        pct = int(i / len(scenes) * 100)
        path = await render_scene_to_png(scene, title, out, template, on_progress)
        paths.append(path)
    return paths
