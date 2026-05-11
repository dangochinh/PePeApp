"""
HTML Engine 2.0 — render each scene as an HTML/CSS card → 1080×1920 PNG.

Improvements over 1.0:
  - Be Vietnam Pro font (Google Fonts, Vietnamese-optimized)
  - Per-scene auto layout: detects what/why/who/how/stats/cta from content
  - Stats extraction: big-number callout when narration has key figures
  - "how" template: numbered step layout
  - Optional Pexels photo background (base64-embedded, needs pexels_api_key)
  - "auto" template mode (default): picks best layout per scene automatically

Templates:
  auto       — smart dispatch based on scene content (default)
  dark       — dark gradient, icon emoji, headline + narration
  gradient   — vivid full-bleed gradient, oversized headline
  minimal    — clean white card, left-aligned typography
  bold       — 4-word impact + rest of headline
  news       — news-card layout with WHAT/WHY/WHO... badge
  cinematic  — letterbox bars, left-aligned dramatic title
  stats      — big number callout with context narration
  how        — numbered step list layout
"""
import asyncio
import base64
import hashlib
import re
import textwrap
from pathlib import Path
from typing import Callable

from models.schemas import Scene

# ---------------------------------------------------------------------------
# Google Fonts
# ---------------------------------------------------------------------------

_FONT_URL = "https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,500;0,700;0,900;1,400&display=swap"

_COMMON_CSS = f"""
@import url('{_FONT_URL}');
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  width: 1080px; height: 1920px; overflow: hidden;
  font-family: 'Be Vietnam Pro', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}
"""

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_PALETTES = [
    ("#0f0c29", "#302b63", "#e040fb"),   # deep purple
    ("#0a0a0a", "#1a1a2e", "#00d4ff"),   # midnight blue
    ("#1a1a1a", "#2d1b69", "#38ef7d"),   # teal emerald
    ("#200122", "#6f0000", "#ff6b6b"),   # crimson
    ("#0d0d0d", "#1b4332", "#95d5b2"),   # forest
    ("#0a0a0a", "#111111", "#ffd200"),   # gold
    ("#12012c", "#1e014f", "#e040fb"),   # neon violet
    ("#001219", "#005f73", "#94d2bd"),   # ocean depth
]

_SCENE_ICONS = ["💡", "🔍", "📊", "🎯", "🚀", "✅", "⚡", "🌟", "🔥", "💎"]


def _palette(seed: str):
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(_PALETTES)
    return _PALETTES[idx]   # (bg1, bg2, accent)


def _scene_icon(n: int) -> str:
    return _SCENE_ICONS[(n - 1) % len(_SCENE_ICONS)]


def _wrap_headline(text: str, max_chars: int = 38) -> str:
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
    return "<br>".join(lines) if lines else text


def _bg_css(bg_image: str | None, bg1: str, bg2: str) -> str:
    if bg_image:
        return f"background: url({bg_image}) center/cover no-repeat; position: relative;"
    return f"background: linear-gradient(160deg, {bg1} 0%, {bg2} 60%, #000 100%);"


def _overlay(bg_image: str | None) -> str:
    if bg_image:
        return '<div style="position:absolute;inset:0;background:rgba(0,0,0,.62);z-index:0;"></div>'
    return ""


def _z() -> str:
    return "position: relative; z-index: 1;"


# ---------------------------------------------------------------------------
# Stats extraction
# ---------------------------------------------------------------------------

_STAT_RE = [
    re.compile(r'(\d[\d\.,]*)\s*(%)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(lần)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(tỷ|triệu|nghìn|tháng|năm|ngày)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(billion|million|thousand|times)', re.I),
    re.compile(r'\b(\d{4})\b'),                             # year
    re.compile(r'(\d[\d\.,]+)\s*x\b', re.I),
]


def _extract_stat(text: str) -> tuple[str, str] | None:
    for rx in _STAT_RE:
        m = rx.search(text)
        if m:
            number = m.group(1)
            unit = m.group(2) if rx.groups >= 2 and m.lastindex >= 2 else ""
            return number, unit
    return None


# ---------------------------------------------------------------------------
# Scene type detection
# ---------------------------------------------------------------------------

_TYPE_KW: dict[str, list[str]] = {
    "cta":  ["hãy bắt đầu", "ngay hôm nay", "subscribe", "follow", "kết luận",
             "tóm lại", "bắt đầu ngay", "chia sẻ", "như vậy", "tóm tắt"],
    "how":  ["cách ", "như thế nào", "bằng cách", " bước ", "làm gì", "how to",
             "bước 1", "đầu tiên", "tiếp theo", "thứ nhất"],
    "why":  ["tại sao", "lý do", "nguyên nhân", "vì sao", "why", "bởi vì"],
    "who":  [" ai ", "đối tượng", "dành cho", "who", "người như"],
    "what": ["là gì", "what is", "khái niệm", "định nghĩa", "giới thiệu"],
}

_SCENE_NUMBER_FALLBACK = {1: "what", 2: "why", 3: "who", 4: "how", 5: "stats", 6: "cta"}


def detect_scene_type(scene: Scene) -> str:
    text = (scene.subtitle_text + " " + scene.narration_text).lower()
    if _extract_stat(scene.narration_text):
        return "stats"
    for t, keywords in _TYPE_KW.items():
        if any(kw in text for kw in keywords):
            return t
    return _SCENE_NUMBER_FALLBACK.get(scene.scene_number, "generic")


def _auto_template(scene: Scene) -> str:
    t = detect_scene_type(scene)
    return {
        "what":    "news",
        "why":     "gradient",
        "who":     "minimal",
        "how":     "how",
        "stats":   "stats",
        "cta":     "bold",
        "generic": "dark",
    }.get(t, "dark")


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

def _html_dark(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
               bg_image: str | None = None) -> str:
    icon = _scene_icon(scene.scene_number)
    hl = _wrap_headline(scene.subtitle_text, 36)
    narr = textwrap.shorten(scene.narration_text, 200, placeholder="…")
    bg = _bg_css(bg_image, bg1, bg2)
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {bg} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px; }}
.sn {{ {z} color:rgba(255,255,255,.3); font-size:28px; letter-spacing:6px;
  font-weight:700; position:absolute; top:80px; left:80px; }}
.accent {{ {z} width:100px; height:6px; background:{accent}; border-radius:3px; margin-bottom:56px; }}
.icon {{ {z} font-size:96px; margin-bottom:44px; filter:drop-shadow(0 0 24px {accent}88); }}
.hl {{ {z} color:#fff; font-size:80px; font-weight:900; line-height:1.1;
  text-align:center; margin-bottom:44px; text-shadow:0 4px 32px rgba(0,0,0,.7); }}
.narr {{ {z} color:rgba(255,255,255,.72); font-size:42px; line-height:1.55;
  text-align:center; max-width:900px; }}
.badge {{ {z} position:absolute; bottom:80px; right:80px;
  background:{accent}22; border:2px solid {accent}66; color:{accent};
  font-size:30px; font-weight:700; padding:12px 24px; border-radius:40px; }}
</style></head><body>
{ov}
<span class="sn">SCENE {scene.scene_number:02d}</span>
<div class="accent"></div>
<div class="icon">{icon}</div>
<div class="hl">{hl}</div>
<div class="narr">{narr}</div>
<div class="badge">{title[:26]}</div>
</body></html>"""


def _html_gradient(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                   bg_image: str | None = None) -> str:
    lines = [f'<div class="line">{ln}</div>'
             for ln in _wrap_headline(scene.subtitle_text, 28).split("<br>")]
    sub = textwrap.shorten(scene.narration_text, 160, placeholder="…")
    bg = _bg_css(bg_image, bg1, bg2)
    if bg_image:
        body_bg = f"background: url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_bg = f"background: linear-gradient(145deg, {bg1} 0%, {accent}aa 50%, {bg2} 100%);"
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_bg} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px; gap:36px; }}
.num {{ {z} position:absolute; top:60px; left:50%; transform:translateX(-50%);
  color:rgba(255,255,255,.4); font-size:26px; letter-spacing:8px; font-weight:700; }}
.line {{ {z} color:#fff; font-size:96px; font-weight:900; text-align:center;
  line-height:1.05; text-shadow:0 8px 40px rgba(0,0,0,.6); letter-spacing:-2px; }}
.div {{ {z} width:180px; height:7px; background:rgba(255,255,255,.55); border-radius:4px; }}
.sub {{ {z} color:rgba(255,255,255,.82); font-size:46px; font-weight:500;
  text-align:center; line-height:1.45; max-width:900px; }}
</style></head><body>
{ov}
<span class="num">·&nbsp;&nbsp;{scene.scene_number}&nbsp;&nbsp;·</span>
{"".join(lines)}
<div class="div"></div>
<div class="sub">{sub}</div>
</body></html>"""


def _html_minimal(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                  bg_image: str | None = None) -> str:
    hl = _wrap_headline(scene.subtitle_text, 32)
    paras = "".join(f"<p>{p}</p>" for p in textwrap.wrap(scene.narration_text, 44)[:5])
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
        text_color = "#fff"
        narr_color = "rgba(255,255,255,.8)"
        bg_overlay = '<div style="position:absolute;inset:0;background:rgba(255,255,255,.08);z-index:0;"></div>'
    else:
        body_style = "background:#fafafa;"
        text_color = "#111"
        narr_color = "#444"
        bg_overlay = ""
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:120px 90px; }}
.num {{ {z} color:{accent}; font-size:34px; font-weight:800;
  letter-spacing:6px; margin-bottom:44px; }}
.bar {{ {z} width:72px; height:7px; background:{accent}; border-radius:4px; margin-bottom:64px; }}
.hl {{ {z} color:{text_color}; font-size:82px; font-weight:900; line-height:1.1;
  letter-spacing:-2px; margin-bottom:56px; }}
.narr p {{ {z} color:{narr_color}; font-size:44px; line-height:1.6; margin-bottom:6px; }}
.foot {{ {z} position:absolute; bottom:90px; left:90px;
  color:{accent}; font-size:30px; font-weight:700; letter-spacing:2px; }}
</style></head><body>
{bg_overlay}
<div class="num">0{scene.scene_number}</div>
<div class="bar"></div>
<div class="hl">{hl}</div>
<div class="narr">{paras}</div>
<div class="foot">{title[:30]}</div>
</body></html>"""


def _html_bold(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
               bg_image: str | None = None) -> str:
    words = scene.subtitle_text.split()
    big = " ".join(words[:4]).upper()
    rest = " ".join(words[4:])
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:{bg1};"
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px; }}
.lt, .lb {{ width:100%; height:6px;
  background:linear-gradient(90deg, transparent, {accent}, transparent);
  position:absolute; {z} }}
.lt {{ top:100px; }} .lb {{ bottom:100px; }}
.sn {{ {z} position:absolute; top:80px; right:80px;
  color:rgba(255,255,255,.3); font-size:26px; letter-spacing:4px; }}
.big {{ {z} color:{accent}; font-size:150px; font-weight:900; text-align:center;
  line-height:0.92; letter-spacing:-4px; text-transform:uppercase;
  text-shadow:0 0 60px {accent}44; margin-bottom:56px; }}
.rest {{ {z} color:rgba(255,255,255,.78); font-size:56px; font-weight:500;
  text-align:center; line-height:1.35; max-width:900px; }}
</style></head><body>
{ov}
<div class="lt"></div>
<span class="sn">S{scene.scene_number:02d}</span>
<div class="big">{big}</div>
<div class="rest">{rest}</div>
<div class="lb"></div>
</body></html>"""


def _html_news(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
               bg_image: str | None = None) -> str:
    labels = ["WHAT", "WHY", "WHO", "HOW", "KHOẢNH KHẮC", "KẾT LUẬN"]
    cat = labels[(scene.scene_number - 1) % len(labels)]
    paras = "".join(f"<p>{p}</p>" for p in textwrap.wrap(scene.narration_text, 42)[:4])
    if bg_image:
        header_bg = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
        header_ov = f'<div style="position:absolute;inset:0;background:{accent}cc;z-index:0;"></div>'
    else:
        header_bg = f"background:{accent};"
        header_ov = ""
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ background:linear-gradient(180deg,#0a0a0a,#111); padding:0; }}
.hdr {{ {header_bg} padding:56px 80px 48px; }}
.cat {{ {z} color:rgba(0,0,0,.65); font-size:28px; font-weight:800;
  letter-spacing:6px; text-transform:uppercase; margin-bottom:18px; }}
.hl {{ {z} color:#fff; font-size:72px; font-weight:900; line-height:1.08;
  letter-spacing:-1.5px; text-shadow:0 3px 20px rgba(0,0,0,.5); }}
.body {{ padding:64px 80px; }}
.body p {{ color:rgba(255,255,255,.76); font-size:46px; line-height:1.6; margin-bottom:14px; }}
.foot {{ position:absolute; bottom:0; left:0; right:0;
  background:{accent}22; border-top:2px solid {accent}44; padding:32px 80px;
  display:flex; align-items:center; justify-content:space-between; }}
.ft {{ color:{accent}; font-size:34px; font-weight:800; }}
.fn {{ color:rgba(255,255,255,.35); font-size:30px; }}
</style></head><body>
<div class="hdr">
  {header_ov}
  <div class="cat">{cat}</div>
  <div class="hl">{scene.subtitle_text}</div>
</div>
<div class="body">{paras}</div>
<div class="foot">
  <span class="ft">{title[:26]}</span>
  <span class="fn">{scene.scene_number} / 6</span>
</div>
</body></html>"""


def _html_cinematic(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                    bg_image: str | None = None) -> str:
    hl = _wrap_headline(scene.subtitle_text, 30)
    narr = textwrap.shorten(scene.narration_text, 180, placeholder="…")
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(180deg,{bg1} 0%,#050505 100%);"
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:0 80px; }}
.lb {{ position:absolute; left:0; right:0; height:200px; background:#000; }}
.lb.t {{ top:0; }} .lb.b {{ bottom:0; }}
.rule {{ {z} width:110px; height:4px; background:{accent}; margin-bottom:56px; }}
.hl {{ {z} color:#fff; font-size:86px; font-weight:900; line-height:1.06;
  letter-spacing:-2px; margin-bottom:56px; text-shadow:0 2px 24px rgba(0,0,0,.8); }}
.narr {{ {z} color:rgba(255,255,255,.6); font-size:40px; line-height:1.6; }}
.corner {{ {z} position:absolute; bottom:220px; right:80px;
  color:rgba(255,255,255,.22); font-size:26px; letter-spacing:4px; font-style:italic; }}
</style></head><body>
{ov}
<div class="lb t"></div>
<div class="rule"></div>
<div class="hl">{hl}</div>
<div class="narr">{narr}</div>
<div class="corner">{title[:22]}</div>
<div class="lb b"></div>
</body></html>"""


def _html_stats(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                bg_image: str | None = None) -> str:
    stat = _extract_stat(scene.narration_text)
    number, unit = stat if stat else ("?", "")
    narr = textwrap.shorten(scene.narration_text, 200, placeholder="…")
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(160deg,{bg1},#000 80%);"
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px; }}
.cat {{ {z} color:{accent}; font-size:28px; font-weight:800; letter-spacing:8px;
  text-transform:uppercase; margin-bottom:60px; }}
.num-wrap {{ {z} text-align:center; margin-bottom:40px; }}
.big {{ display:block; color:{accent}; font-size:240px; font-weight:900;
  line-height:0.9; letter-spacing:-6px;
  text-shadow:0 0 80px {accent}55; }}
.unit {{ display:block; color:rgba(255,255,255,.6); font-size:60px;
  font-weight:700; letter-spacing:2px; margin-top:16px; }}
.div {{ {z} width:160px; height:5px; background:{accent}44; border-radius:3px; margin:48px 0; }}
.hl {{ {z} color:#fff; font-size:56px; font-weight:700; text-align:center;
  line-height:1.3; max-width:860px; margin-bottom:36px; }}
.narr {{ {z} color:rgba(255,255,255,.6); font-size:38px; text-align:center;
  line-height:1.5; max-width:860px; }}
.badge {{ {z} position:absolute; bottom:80px; right:80px;
  color:{accent}; font-size:28px; font-weight:700; letter-spacing:2px; }}
</style></head><body>
{ov}
<div class="cat">SỐ LIỆU · SCENE {scene.scene_number:02d}</div>
<div class="num-wrap">
  <span class="big">{number}</span>
  <span class="unit">{unit}</span>
</div>
<div class="div"></div>
<div class="hl">{scene.subtitle_text}</div>
<div class="narr">{narr}</div>
<div class="badge">{title[:24]}</div>
</body></html>"""


def _html_how(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
              bg_image: str | None = None) -> str:
    # Split narration into up to 4 steps
    raw_steps = [s.strip() for s in re.split(r'[.!;]', scene.narration_text) if s.strip()]
    steps = raw_steps[:4] if raw_steps else [scene.narration_text]
    steps_html = "".join(
        f'<div class="step"><span class="sn">{i+1}</span>'
        f'<span class="st">{textwrap.shorten(s, 80, placeholder="…")}</span></div>'
        for i, s in enumerate(steps)
    )
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(160deg,{bg1} 0%,#0a0a0a 100%);"
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:100px 80px; }}
.cat {{ {z} color:{accent}; font-size:28px; font-weight:800; letter-spacing:6px;
  text-transform:uppercase; margin-bottom:32px; }}
.hl {{ {z} color:#fff; font-size:74px; font-weight:900; line-height:1.1;
  letter-spacing:-1.5px; margin-bottom:64px; }}
.step {{ {z} display:flex; align-items:flex-start; gap:28px; margin-bottom:40px; }}
.sn {{ flex-shrink:0; width:72px; height:72px; border-radius:50%;
  background:{accent}; color:#000; font-size:36px; font-weight:900;
  display:flex; align-items:center; justify-content:center; margin-top:6px; }}
.st {{ color:rgba(255,255,255,.82); font-size:44px; line-height:1.45; }}
.foot {{ {z} position:absolute; bottom:80px; left:80px;
  color:{accent}; font-size:28px; font-weight:700; letter-spacing:3px; }}
</style></head><body>
{ov}
<div class="cat">CÁCH LÀM · HOW TO</div>
<div class="hl">{_wrap_headline(scene.subtitle_text, 30)}</div>
{steps_html}
<div class="foot">{title[:28]}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

_TEMPLATE_MAP = {
    "dark":      _html_dark,
    "gradient":  _html_gradient,
    "minimal":   _html_minimal,
    "bold":      _html_bold,
    "news":      _html_news,
    "cinematic": _html_cinematic,
    "stats":     _html_stats,
    "how":       _html_how,
}

AVAILABLE_TEMPLATES = ["auto"] + list(_TEMPLATE_MAP.keys())


def build_html(scene: Scene, title: str, template: str,
               bg_image: str | None = None) -> str:
    bg1, bg2, accent = _palette(title + str(scene.scene_number))
    tpl = template if template != "auto" else _auto_template(scene)
    fn = _TEMPLATE_MAP.get(tpl, _html_dark)
    return fn(scene, title, accent, bg1, bg2, bg_image)


# ---------------------------------------------------------------------------
# Pexels background image fetch
# ---------------------------------------------------------------------------

async def _fetch_bg_image(keyword: str, cache_dir: Path) -> str | None:
    try:
        from config import settings
        import httpx
    except ImportError:
        return None

    if not settings.pexels_api_key:
        return None

    # Normalise keyword for cache filename
    safe_kw = re.sub(r"[^\w]", "_", keyword)[:40].strip("_")
    cache_file = cache_dir / f"bg_{safe_kw}.jpg"

    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        raw = cache_file.read_bytes()
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": keyword, "per_page": 3, "orientation": "portrait"},
                    headers={"Authorization": settings.pexels_api_key},
                )
                photos = r.json().get("photos", [])
                if not photos:
                    return None
                img_url = photos[0]["src"].get("portrait") or photos[0]["src"]["large"]
                img_r = await client.get(img_url, follow_redirects=True, timeout=20.0)
                raw = img_r.content
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(raw)
        except Exception as e:
            print(f"[html_engine] Pexels fetch failed: {e}")
            return None

    b64 = base64.b64encode(raw).decode()
    return f"data:image/jpeg;base64,{b64}"


# ---------------------------------------------------------------------------
# Screenshot with Playwright
# ---------------------------------------------------------------------------

async def render_scene_to_png(
    scene: Scene,
    title: str,
    output_path: Path,
    template: str = "auto",
    on_progress: Callable[[str, int], None] | None = None,
) -> Path:
    """Render one scene card to a 1080×1920 PNG via headless Chromium."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from exc

    if on_progress:
        on_progress(f"🖼️ HTML render scene {scene.scene_number}", 0)

    # Optional Pexels background
    bg_image: str | None = None
    try:
        from config import settings
        if settings.html_use_bg_image and settings.pexels_api_key:
            cache_dir = output_path.parent.parent / "bg_cache"
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                import tempfile
                cache_dir = Path(tempfile.gettempdir()) / "pepe_bg_cache"
                cache_dir.mkdir(exist_ok=True)
            keyword = scene.visual_prompt.split(",")[0][:60].strip()
            bg_image = await _fetch_bg_image(keyword, cache_dir)
    except Exception as e:
        print(f"[html_engine] bg fetch error: {e}")

    html = build_html(scene, title, template, bg_image=bg_image)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await page.set_content(html, wait_until="networkidle")
        await asyncio.sleep(0.15)   # let web fonts render
        await page.screenshot(path=str(output_path), full_page=False)
        await browser.close()

    if on_progress:
        on_progress(f"🖼️ HTML scene {scene.scene_number} ready", 100)

    return output_path


async def render_all_scenes(
    scenes: list[Scene],
    title: str,
    clips_dir: Path,
    template: str = "auto",
    on_progress: Callable[[str, int], None] | None = None,
) -> list[Path]:
    paths = []
    for scene in scenes:
        out = clips_dir / f"scene_{scene.scene_number:02d}.png"
        path = await render_scene_to_png(scene, title, out, template, on_progress)
        paths.append(path)
    return paths
