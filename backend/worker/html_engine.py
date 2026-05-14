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
html, body {{
  width: 1080px; height: 1920px; overflow: hidden;
  font-family: 'Be Vietnam Pro', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}
#sub-line {{
  font-size: 68px !important;
  font-weight: 800 !important;
  line-height: 1.25 !important;
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

# Topic category → (bg1, bg2, accent) — consistent color identity per video
_TOPIC_PALETTES: dict[str, tuple[str, str, str]] = {
    "finance":   ("#0a0800", "#1a1000", "#f59e0b"),   # gold
    "crypto":    ("#03000f", "#0f0028", "#f97316"),   # orange
    "tech":      ("#000d1a", "#001a33", "#06b6d4"),   # cyan
    "ai":        ("#050010", "#0d0028", "#a855f7"),   # violet
    "war":       ("#0d0000", "#1a0500", "#ef4444"),   # red
    "politics":  ("#08000f", "#140020", "#e040fb"),   # purple
    "health":    ("#001a0d", "#003320", "#10b981"),   # emerald
    "science":   ("#000d1a", "#001a2e", "#38bdf8"),   # sky blue
    "sport":     ("#0f0500", "#1f0a00", "#f97316"),   # orange
    "history":   ("#0f0a00", "#1a1200", "#d97706"),   # amber
    "business":  ("#0a0a14", "#141428", "#6366f1"),   # indigo
    "social":    ("#140005", "#28000a", "#f43f5e"),   # rose
}

_TOPIC_KW: dict[str, list[str]] = {
    "crypto":   ["bitcoin", "btc", "ethereum", "crypto", "blockchain", "nft", "defi", "tiền điện tử", "coin"],
    "finance":  ["chứng khoán", "cổ phiếu", "tài chính", "vàng", "usd", "lãi suất", "ngân hàng", "gdp", "kinh tế"],
    "tech":     ["iphone", "samsung", "android", "chip", "cpu", "gpu", "điện thoại", "máy tính", "công nghệ"],
    "ai":       ["ai", "chatgpt", "llm", "trí tuệ nhân tạo", "machine learning", "robot", "openai", "gemini"],
    "war":      ["chiến tranh", "quân sự", "tên lửa", "nato", "ukraine", "israel", "iran", "missile", "war"],
    "politics": ["chính trị", "bầu cử", "tổng thống", "quốc hội", "đảng", "chính phủ", "luật"],
    "health":   ["sức khỏe", "bệnh", "vaccine", "y tế", "thuốc", "ung thư", "covid", "virus"],
    "science":  ["khoa học", "vật lý", "không gian", "nasa", "vũ trụ", "nghiên cứu"],
    "sport":    ["bóng đá", "thể thao", "world cup", "olympic", "nba", "football"],
    "history":  ["lịch sử", "thế kỷ", "đế chế", "cổ đại", "chiến tranh thế giới"],
    "business": ["doanh nghiệp", "startup", "công ty", "ceo", "thị phần", "merger"],
    "social":   ["mạng xã hội", "tiktok", "youtube", "influencer", "trend", "viral"],
}


def _detect_topic_category(topic: str) -> str:
    """Return category key from topic string, or empty string for fallback."""
    t = topic.lower()
    for cat, keywords in _TOPIC_KW.items():
        if any(kw in t for kw in keywords):
            return cat
    return ""


def _palette_for_topic(topic: str) -> tuple[str, str, str]:
    """Return (bg1, bg2, accent) locked to topic category, or hash-based fallback."""
    cat = _detect_topic_category(topic)
    if cat and cat in _TOPIC_PALETTES:
        return _TOPIC_PALETTES[cat]
    idx = int(hashlib.md5(topic.encode()).hexdigest(), 16) % len(_PALETTES)
    return _PALETTES[idx]


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


def _overlay(bg_image: str | None, force: bool = False) -> str:
    """Cinematic overlay: gradient darkening + vignette. Applied when bg exists OR forced."""
    if bg_image or force:
        return (
            '<div style="position:absolute;inset:0;z-index:1;pointer-events:none;'
            'background:linear-gradient(180deg,'
            'rgba(0,0,0,.72) 0%,rgba(0,0,0,.35) 40%,rgba(0,0,0,.35) 60%,rgba(0,0,0,.82) 100%);'
            '"></div>'
            # Vignette layer
            '<div style="position:absolute;inset:0;z-index:1;pointer-events:none;'
            'background:radial-gradient(ellipse at center,'
            'transparent 45%,rgba(0,0,0,.65) 100%);'
            '"></div>'
        )
    return ""


def _z() -> str:
    return "position: relative; z-index: 1;"


# ---------------------------------------------------------------------------
# Stats extraction
# ---------------------------------------------------------------------------

_STAT_RE = [
    re.compile(r'(\d[\d\.,]*)\s*(%)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(lần)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(tỷ|triệu|nghìn|tháng|ngày)', re.I),
    re.compile(r'(\d[\d\.,]*)\s*(billion|million|thousand|times|USD|VND|đô)', re.I),
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


def _extract_all_stats(text: str) -> list[tuple[str, str]]:
    """Extract up to 4 distinct (number, unit) pairs from text."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for rx in _STAT_RE:
        for m in rx.finditer(text):
            number = m.group(1)
            unit = m.group(2) if rx.groups >= 2 and m.lastindex >= 2 else ""
            key = f"{number}{unit}"
            if key not in seen:
                seen.add(key)
                results.append((number, unit))
            if len(results) >= 4:
                return results
    return results


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
    # Compare template ONLY when narration has explicit pipe-format data (A: num | B: num)
    if "| " in scene.narration_text and _PIPE_ITEM_RE.search(scene.narration_text):
        return "compare"
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
        "compare": "compare",
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
    t = textwrap.shorten(title, 40, placeholder="…")
    bg = _bg_css(bg_image, bg1, bg2)
    ov = _overlay(bg_image)
    z = _z()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {bg} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px; }}
.accent {{ {z} width:100px; height:6px; background:{accent}; border-radius:3px; margin-bottom:56px; }}
.icon {{ {z} font-size:96px; margin-bottom:44px; filter:drop-shadow(0 0 24px {accent}88); }}
.hl {{ {z} color:#fff; font-size:80px; font-weight:900; line-height:1.1;
  text-align:center; margin-bottom:44px; text-shadow:0 4px 32px rgba(0,0,0,.7); }}
.narr {{ {z} color:rgba(255,255,255,.72); font-size:42px; line-height:1.55;
  text-align:center; max-width:900px; }}
.badge {{ {z} position:absolute; bottom:80px; right:80px;
  background:{accent}22; border:2px solid {accent}66; color:{accent};
  font-size:30px; font-weight:700; padding:12px 24px; border-radius:40px;
  max-width:640px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
<div class="accent"></div>
<div class="icon">{icon}</div>
<div class="hl">{hl}</div>
<div class="narr">{narr}</div>
<div class="badge">{t}</div>
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
.line {{ {z} color:#fff; font-size:96px; font-weight:900; text-align:center;
  line-height:1.05; text-shadow:0 8px 40px rgba(0,0,0,.6); letter-spacing:-2px; }}
.div {{ {z} width:180px; height:7px; background:rgba(255,255,255,.55); border-radius:4px; }}
.sub {{ {z} color:rgba(255,255,255,.82); font-size:46px; font-weight:500;
  text-align:center; line-height:1.45; max-width:900px; }}
</style></head><body>
{ov}
{"".join(lines)}
<div class="div"></div>
<div class="sub">{sub}</div>
</body></html>"""


def _html_minimal(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                  bg_image: str | None = None) -> str:
    hl = _wrap_headline(scene.subtitle_text, 32)
    t = textwrap.shorten(title, 40, placeholder="…")
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
.bar {{ {z} width:72px; height:7px; background:{accent}; border-radius:4px; margin-bottom:64px; }}
.hl {{ {z} color:{text_color}; font-size:82px; font-weight:900; line-height:1.1;
  letter-spacing:-2px; margin-bottom:56px; }}
.narr p {{ {z} color:{narr_color}; font-size:44px; line-height:1.6; margin-bottom:6px; }}
.foot {{ {z} position:absolute; bottom:90px; left:90px;
  color:{accent}; font-size:30px; font-weight:700; letter-spacing:2px; }}
</style></head><body>
{bg_overlay}
<div class="bar"></div>
<div class="hl">{hl}</div>
<div class="narr">{paras}</div>
<div class="foot">{t}</div>
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
.big {{ {z} color:{accent}; font-size:150px; font-weight:900; text-align:center;
  line-height:0.92; letter-spacing:-4px; text-transform:uppercase;
  text-shadow:0 0 60px {accent}44; margin-bottom:56px; }}
.rest {{ {z} color:rgba(255,255,255,.78); font-size:56px; font-weight:500;
  text-align:center; line-height:1.35; max-width:900px; }}
</style></head><body>
{ov}
<div class="lt"></div>
<div class="big">{big}</div>
<div class="rest">{rest}</div>
<div class="lb"></div>
</body></html>"""


def _html_news(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
               bg_image: str | None = None) -> str:
    labels = ["WHAT", "WHY", "WHO", "HOW", "KHOẢNH KHẮC", "KẾT LUẬN"]
    cat = labels[(scene.scene_number - 1) % len(labels)]
    t = textwrap.shorten(title, 40, placeholder="…")
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
  background:{accent}22; border-top:2px solid {accent}44; padding:32px 80px; }}
.ft {{ color:{accent}; font-size:34px; font-weight:800;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
<div class="hdr">
  {header_ov}
  <div class="cat">{cat}</div>
  <div class="hl">{scene.subtitle_text}</div>
</div>
<div class="body">{paras}</div>
<div class="foot">
  <span class="ft">{t}</span>
</div>
</body></html>"""


def _html_cinematic(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                    bg_image: str | None = None) -> str:
    hl = _wrap_headline(scene.subtitle_text, 30)
    narr = textwrap.shorten(scene.narration_text, 180, placeholder="…")
    t = textwrap.shorten(title, 36, placeholder="…")
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
  color:rgba(255,255,255,.22); font-size:26px; letter-spacing:4px; font-style:italic;
  max-width:500px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
<div class="lb t"></div>
<div class="rule"></div>
<div class="hl">{hl}</div>
<div class="narr">{narr}</div>
<div class="corner">{t}</div>
<div class="lb b"></div>
</body></html>"""


def _html_stats(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                bg_image: str | None = None) -> str:
    stat = _extract_stat(scene.narration_text)
    t = textwrap.shorten(title, 40, placeholder="…")
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(160deg,{bg1},#000 80%);"
    ov = _overlay(bg_image)
    z = _z()
    # No numeric data → highlight-point layout
    if not stat:
        raw = [s.strip() for s in re.split(r'[.!;]', scene.narration_text) if len(s.strip()) > 8]
        points = raw[:4] or [scene.narration_text]
        items_html = "".join(
            f'<div class="pt"><span class="dot">✦</span>'
            f'<span class="ptxt">{textwrap.shorten(p, 80, placeholder="…")}</span></div>'
            for p in points
        )
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:80px; }}
.cat  {{ {z} color:{accent}; font-size:28px; font-weight:800; letter-spacing:8px; margin-bottom:36px; }}
.hl   {{ {z} color:#fff; font-size:56px; font-weight:900; line-height:1.1;
  margin-bottom:52px; text-shadow:0 4px 24px rgba(0,0,0,.8); }}
.pts  {{ {z} display:flex; flex-direction:column; gap:28px; max-width:920px; }}
.pt   {{ display:flex; align-items:flex-start; gap:24px; }}
.dot  {{ color:{accent}; font-size:28px; line-height:1.3; flex-shrink:0; }}
.ptxt {{ color:rgba(255,255,255,.88); font-size:36px; font-weight:600; line-height:1.4; }}
.badge {{ {z} position:absolute; top:80px; right:80px; color:{accent};
  font-size:24px; font-weight:700;
  max-width:520px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
<div class="cat">ĐIỂM NỔI BẬT</div>
<div class="hl">{scene.subtitle_text}</div>
<div class="pts">{items_html}</div>
<div class="badge">{t}</div>
</body></html>"""
    number, unit = stat
    narr = textwrap.shorten(scene.narration_text, 200, placeholder="…")
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
body {{ {body_style} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px; }}
.cat {{ {z} color:{accent}; font-size:28px; font-weight:800; letter-spacing:8px;
  text-transform:uppercase; margin-bottom:60px; }}
.num-wrap {{ {z} text-align:center; margin-bottom:40px; }}
.big {{ display:block; color:{accent}; font-size:240px; font-weight:900;
  line-height:0.9; letter-spacing:-6px; text-shadow:0 0 80px {accent}55; }}
.unit {{ display:block; color:rgba(255,255,255,.6); font-size:60px;
  font-weight:700; letter-spacing:2px; margin-top:16px; }}
.div {{ {z} width:160px; height:5px; background:{accent}44; border-radius:3px; margin:48px 0; }}
.hl {{ {z} color:#fff; font-size:56px; font-weight:700; text-align:center;
  line-height:1.3; max-width:860px; margin-bottom:36px; }}
.narr {{ {z} color:rgba(255,255,255,.6); font-size:38px; text-align:center;
  line-height:1.5; max-width:860px; }}
.badge {{ {z} position:absolute; bottom:80px; right:80px;
  color:{accent}; font-size:28px; font-weight:700;
  max-width:560px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
<div class="cat">SỐ LIỆU</div>
<div class="num-wrap">
  <span class="big">{number}</span>
  <span class="unit">{unit}</span>
</div>
<div class="div"></div>
<div class="hl">{scene.subtitle_text}</div>
<div class="narr">{narr}</div>
<div class="badge">{t}</div>
</body></html>"""


def _html_how(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
              bg_image: str | None = None) -> str:
    # Split narration into up to 4 steps
    raw_steps = [s.strip() for s in re.split(r'[.!;]', scene.narration_text) if s.strip()]
    steps = raw_steps[:4] if raw_steps else [scene.narration_text]
    t = textwrap.shorten(title, 40, placeholder="…")
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
  color:{accent}; font-size:28px; font-weight:700; letter-spacing:3px;
  max-width:700px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
<div class="cat">CÁCH LÀM · HOW TO</div>
<div class="hl">{_wrap_headline(scene.subtitle_text, 30)}</div>
{steps_html}
<div class="foot">{t}</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Chart data extraction & type detection
# ---------------------------------------------------------------------------

_PIPE_ITEM_RE = re.compile(
    r'([^:|\n]{1,30}):\s*([\d,\.]+)\s*([^|\n]{0,18}?)(?:\s*\|\s*|$)',
    re.I,
)


def _extract_comparison_data(
    narration: str, subtitle: str = ""
) -> list[tuple[str, str, str]]:
    """
    Parse '[Label]: [num] [unit] | ...' pipe format from narration.
    Returns list of (label, number_str, unit_str) up to 4 items.
    Labels are truncated to ≤22 chars. Falls back to generic stat extraction.
    """
    matches = _PIPE_ITEM_RE.findall(narration)
    if len(matches) >= 2:
        return [
            (textwrap.shorten(m[0].strip(), 22, placeholder="…"),
             m[1].strip(), m[2].strip().rstrip("| "))
            for m in matches[:4]
        ]
    # Fallback: generic stats, no entity labels
    stats = _extract_all_stats(narration)
    return [("", n, u) for n, u in stats[:4]]


def _parse_cmp_value(s: str) -> float:
    """Strip all separators (. , % space) and parse as float for proportion math."""
    clean = re.sub(r"[,\.\s%]", "", s)
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


# Secondary accent colors for multi-item charts
_CHART_COLORS = ["accent", "#34d399", "#f59e0b", "#e879f9"]


def _detect_chart_type(data: list[tuple[str, str, str]]) -> str:
    """Infer best chart type: hbar | vbar | pie | line."""
    if not data:
        return "hbar"
    units = [d[2].lower() for d in data]
    # All items are percentages → pie/donut
    if len(data) >= 2 and all("%" in u or u.strip() == "%" for u in units):
        return "pie"
    # Labels are years OR plain integers that look like years → line trend chart
    labels_or_nums = [d[0].strip() or d[1].strip() for d in data]
    if len(data) >= 3 and all(re.match(r"^\d{4}$", v) for v in labels_or_nums):
        return "line"
    # 3+ items → vertical bar (cột)
    if len(data) >= 3:
        return "vbar"
    # 2 items → horizontal bar
    return "hbar"


# ---------------------------------------------------------------------------
# Chart renderers: return (chart_html, extra_css, js_code)
# ---------------------------------------------------------------------------

def _chart_hbar(data: list[tuple[str, str, str]], vals: list[float],
                accent: str) -> tuple[str, str, str]:
    """Horizontal bar chart — best for 2 items side by side."""
    max_v = max(vals) if vals else 1
    win_i = vals.index(max(vals)) if vals else 0
    colors = [accent, "rgba(255,255,255,.22)", "#34d399", "#f59e0b"]
    rows = ""
    js = "var g=function(id){return document.getElementById(id);};"
    for i, (lbl, num, unit) in enumerate(data):
        pct = round(vals[i] / max_v * 88) if max_v > 0 else 0
        is_w = (i == win_i)
        bc = accent if is_w else colors[i] if i < len(colors) else "rgba(255,255,255,.22)"
        tc = accent if is_w else "rgba(255,255,255,.52)"
        icon = "🏆 " if is_w else ""
        nm = textwrap.shorten(lbl, 22, placeholder="…") if lbl else num
        dv = f"{num} {unit}".strip()
        rows += (f'<div class="hr"><div class="hl">'
                 f'<span class="hn">{icon}{nm}</span>'
                 f'<span class="hv" style="color:{tc}">{dv}</span></div>'
                 f'<div class="ht"><div class="hf" id="hb{i}" style="background:{bc}"></div></div></div>')
        js += f"setTimeout(function(){{var e=g('hb{i}');if(e)e.style.width='{pct}%';}},{600+i*100});"
    css = (".hrows{display:flex;flex-direction:column;gap:48px;width:100%;}"
           ".hr{display:flex;flex-direction:column;gap:14px;}"
           ".hl{display:flex;justify-content:space-between;align-items:baseline;}"
           ".hn{font-size:36px;font-weight:800;color:rgba(255,255,255,.9);}"
           ".hv{font-size:44px;font-weight:900;letter-spacing:-1px;}"
           ".ht{width:100%;height:32px;background:rgba(255,255,255,.07);border-radius:16px;overflow:hidden;}"
           ".hf{height:100%;border-radius:16px;width:0%;transition:width 1.2s cubic-bezier(0.16,1,0.3,1);}")
    return f'<div class="hrows">{rows}</div>', css, js


def _chart_vbar(data: list[tuple[str, str, str]], vals: list[float],
                accent: str) -> tuple[str, str, str]:
    """Vertical column chart (cột) — best for 3-4 items."""
    max_v = max(vals) if vals else 1
    win_i = vals.index(max(vals)) if vals else 0
    colors = [accent, "rgba(255,255,255,.35)", "#34d399", "#f59e0b"]
    cols = ""
    js = "var g=function(id){return document.getElementById(id);};"
    bar_h = 340  # max bar height px
    for i, (lbl, num, unit) in enumerate(data):
        pct = round(vals[i] / max_v * bar_h) if max_v > 0 else 0
        is_w = (i == win_i)
        bc = accent if is_w else colors[i] if i < len(colors) else "rgba(255,255,255,.3)"
        nm = textwrap.shorten(lbl, 18, placeholder="…") if lbl else num
        dv = f"{num}{unit}".strip()
        icon = "🏆" if is_w else ""
        cols += (f'<div class="vc">'
                 f'<div class="vv" style="color:{bc}">{dv}</div>'
                 f'<div class="vwrap"><div class="vfill" id="vb{i}" style="background:{bc}"></div></div>'
                 f'<div class="vlbl">{nm}{icon}</div></div>')
        js += f"setTimeout(function(){{var e=g('vb{i}');if(e)e.style.height='{pct}px';}},{600+i*130});"
    css = (f".vchart{{display:flex;align-items:flex-end;justify-content:space-around;width:100%;gap:8px;}}"
           f".vc{{display:flex;flex-direction:column;align-items:center;flex:1;gap:8px;}}"
           f".vv{{font-size:28px;font-weight:900;letter-spacing:-1px;}}"
           f".vwrap{{width:100%;max-width:180px;height:{bar_h}px;background:rgba(255,255,255,.07);"
           f"border-radius:12px 12px 0 0;display:flex;align-items:flex-end;overflow:hidden;}}"
           f".vfill{{width:100%;height:0;border-radius:12px 12px 0 0;transition:height 1.2s cubic-bezier(0.16,1,0.3,1);}}"
           f".vlbl{{font-size:24px;font-weight:700;color:rgba(255,255,255,.8);text-align:center;max-width:160px;}}")
    return f'<div class="vchart">{cols}</div>', css, js


def _chart_pie(data: list[tuple[str, str, str]], vals: list[float],
               accent: str) -> tuple[str, str, str]:
    """Pie / donut chart (quạt) — best for 2-3 percentage items."""
    total = sum(vals) if sum(vals) > 0 else 1
    colors = [accent, "rgba(255,255,255,.25)", "#34d399", "#f59e0b"]
    # Build conic-gradient segments
    segs: list[tuple[int, int, str, tuple]] = []
    cur = 0
    for i, (item, v) in enumerate(zip(data, vals)):
        deg = round(v / total * 360)
        segs.append((cur, cur + deg, colors[i % len(colors)], item))
        cur += deg
    conic = ", ".join(f"{c} {s}deg {e}deg" for s, e, c, _ in segs)
    win_i = vals.index(max(vals)) if vals else 0
    win_label = (data[win_i][0] or data[win_i][1]) + data[win_i][2]
    legend = "".join(
        f'<div class="leg"><span class="ldot" style="background:{c}"></span>'
        f'<span class="lname">{d[0] if d[0] else d[1]}</span>'
        f'<span class="lval" style="color:{c}">{d[1]}{d[2]}'
        f'{"&thinsp;🏆" if i == win_i else ""}</span></div>'
        for i, (s, e, c, d) in enumerate(segs)
    )
    css = (f"@keyframes pieIn{{from{{transform:rotate(-90deg) scale(.8);opacity:0}}to{{transform:rotate(-90deg);opacity:1}}}}"
           f".pw{{display:flex;align-items:center;justify-content:space-between;width:100%;gap:40px;}}"
           f".dw{{position:relative;width:360px;height:360px;flex-shrink:0;}}"
           f".donut{{width:100%;height:100%;border-radius:50%;background:conic-gradient({conic});"
           f"animation:pieIn 1.1s cubic-bezier(0.16,1,0.3,1) forwards;}}"
           f".hole{{position:absolute;inset:76px;border-radius:50%;background:rgba(0,0,0,.55);"
           f"display:flex;align-items:center;justify-content:center;flex-direction:column;}}"
           f".hole-n{{font-size:44px;font-weight:900;color:{accent};letter-spacing:-2px;text-align:center;}}"
           f".lgd{{display:flex;flex-direction:column;gap:24px;flex:1;}}"
           f".leg{{display:flex;align-items:center;gap:14px;}}"
           f".ldot{{width:22px;height:22px;border-radius:50%;flex-shrink:0;}}"
           f".lname{{font-size:28px;font-weight:700;color:rgba(255,255,255,.85);flex:1;}}"
           f".lval{{font-size:34px;font-weight:900;letter-spacing:-1px;}}")
    html = (f'<div class="pw">'
            f'<div class="dw"><div class="donut"></div>'
            f'<div class="hole"><span class="hole-n">{win_label}</span></div></div>'
            f'<div class="lgd">{legend}</div></div>')
    return html, css, ""


def _chart_line(data: list[tuple[str, str, str]], vals: list[float],
                max_v: float, accent: str) -> tuple[str, str, str]:
    """Line trend chart (đường) using inline SVG with SMIL animation."""
    n = len(data)
    if n < 2:
        return _chart_hbar(data, vals, accent)
    W, H = 920, 380
    mg = 48
    iw = W - 2 * mg
    ih = H - 2 * mg - 30  # extra bottom for labels
    mx = max(max_v, 1)

    def px(i: int) -> int:
        return mg + round(i / (n - 1) * iw)

    def py(v: float) -> int:
        return mg + ih - round(v / mx * ih)

    pts = " ".join(f"{px(i)},{py(v)}" for i, v in enumerate(vals))
    # Approx path length for dasharray animation
    path_len = int(sum(
        ((px(i + 1) - px(i)) ** 2 + (py(vals[i + 1]) - py(vals[i])) ** 2) ** 0.5
        for i in range(n - 1)
    )) + 200

    # Area fill path
    area = (f"M{px(0)},{py(vals[0])} "
            + " ".join(f"L{px(i)},{py(v)}" for i, v in enumerate(vals))
            + f" L{px(n-1)},{H-mg-30} L{px(0)},{H-mg-30} Z")

    dots = "".join(
        f'<circle cx="{px(i)}" cy="{py(v)}" r="0" fill="{accent}">'
        f'<animate attributeName="r" from="0" to="14" dur="0.4s" fill="freeze" begin="{0.5+i*0.2:.1f}s"/>'
        f'</circle>'
        for i, v in enumerate(vals)
    )
    xlbls = "".join(
        f'<text x="{px(i)}" y="{H-4}" text-anchor="middle" '
        f'fill="rgba(255,255,255,.6)" font-size="22" font-family="Be Vietnam Pro,sans-serif">'
        f'{data[i][0] or data[i][1]}</text>'
        for i in range(n)
    )
    ylbls = "".join(
        f'<text x="{px(i)}" y="{py(v)-20}" text-anchor="middle" '
        f'fill="{accent}" font-size="26" font-weight="bold" font-family="Be Vietnam Pro,sans-serif">'
        f'{data[i][1]}{data[i][2]}</text>'
        for i, v in enumerate(vals)
    )
    html = (f'<svg viewBox="0 0 {W} {H}" style="width:100%;overflow:visible;">'
            f'<defs><linearGradient id="lag" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{accent}" stop-opacity=".32"/>'
            f'<stop offset="100%" stop-color="{accent}" stop-opacity=".0"/>'
            f'</linearGradient></defs>'
            f'<path d="{area}" fill="url(#lag)"/>'
            f'<polyline points="{pts}" fill="none" stroke="{accent}" stroke-width="8" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{path_len}" stroke-dashoffset="{path_len}">'
            f'<animate attributeName="stroke-dashoffset" from="{path_len}" to="0" '
            f'dur="1.6s" calcMode="spline" keySplines="0.16 1 0.3 1" fill="freeze" begin="0.2s"/>'
            f'</polyline>'
            f'{dots}{xlbls}{ylbls}'
            f'</svg>')
    return html, "", ""


# ---------------------------------------------------------------------------
# Compare template — static & animated, auto-dispatches to chart type
# ---------------------------------------------------------------------------

def _compare_body(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                  bg_image: str | None, animated: bool,
                  word_timings: list[dict] | None = None,
                  stk_html: str = "", sub_html: str = "",
                  bottom_pad: str = "80px") -> str:
    """Shared comparison template body."""
    data = _extract_comparison_data(scene.narration_text, scene.subtitle_text)
    if not data or all(d[1] == "?" for d in data):
        # No numeric data — fall back to a "coming soon" minimal layout
        data = [("—", "?", ""), ("—", "?", "")]
    vals = [_parse_cmp_value(d[1]) for d in data]
    max_v = max(vals) if any(v > 0 for v in vals) else 1
    chart_type = _detect_chart_type(data)

    if chart_type == "pie":
        chart_html, chart_css, chart_js = _chart_pie(data, vals, accent)
    elif chart_type == "vbar":
        chart_html, chart_css, chart_js = _chart_vbar(data, vals, accent)
    elif chart_type == "line":
        chart_html, chart_css, chart_js = _chart_line(data, vals, max_v, accent)
    else:
        chart_html, chart_css, chart_js = _chart_hbar(data, vals, accent)

    body_style = (f"background:url({bg_image}) center/cover no-repeat; position:relative;"
                  if bg_image else f"background:linear-gradient(160deg,{bg1} 0%,{bg2} 60%,#000 100%);")
    ov = _overlay(bg_image)
    z = _z()
    td = textwrap.shorten(title, 40, placeholder="…")
    anim_css = _ANIM_CSS if animated else ""
    badge_anim = ' class="a-in" style="animation-delay:0.1s"' if animated else ""
    ttl_anim = ' class="a-up" style="animation-delay:0.25s"' if animated else ""
    chart_anim = ' class="a-up" style="animation-delay:0.5s"' if animated else ""
    script = f"<script>(function(){{{chart_js}}})();</script>" if chart_js else ""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{anim_css}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:80px 80px {bottom_pad}; }}
.badge {{ {z} position:absolute; top:80px; right:80px;
  background:{accent}22; border:2px solid {accent}66; color:{accent};
  font-size:24px; font-weight:700; padding:8px 18px; border-radius:40px;
  max-width:520px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.ttl {{ {z} color:#fff; font-size:56px; font-weight:900; line-height:1.08;
  margin-bottom:64px; text-shadow:0 4px 24px rgba(0,0,0,.8); }}
.chart-wrap {{ {z} width:100%; }}
{chart_css}
</style></head><body>
{ov}
{stk_html}
<div{badge_anim}><div class="badge">{td}</div></div>
<div{ttl_anim}><div class="ttl">{_wrap_headline(scene.subtitle_text, 28)}</div></div>
<div{chart_anim}><div class="chart-wrap">{chart_html}</div></div>
{script}
{_sfx_layer("compare") if animated else ""}
{sub_html}
</body></html>"""


def _html_compare(scene: Scene, title: str, accent: str, bg1: str, bg2: str,
                  bg_image: str | None = None) -> str:
    return _compare_body(scene, title, accent, bg1, bg2, bg_image, animated=False)


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
    "compare":   _html_compare,
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

async def _fetch_bg_image(keyword: str, cache_dir: Path, photo_idx: int = 0) -> str | None:
    # 1 — Local stock library first (DrawThings-generated, topic-matched)
    try:
        from worker.stock_library import detect_category, get_stock_image
        cat = detect_category(keyword)
        local = get_stock_image(cat, photo_idx)
        if local:
            return local
    except Exception as e:
        print(f"[html_engine] stock library lookup failed: {e}")

    # 2 — Pexels fallback
    try:
        from config import settings
        import httpx
    except ImportError:
        return None

    if not settings.pexels_api_key:
        return None

    # Normalise keyword for cache filename — include photo_idx so scenes get different images
    safe_kw = re.sub(r"[^\w]", "_", keyword)[:40].strip("_")
    slot = photo_idx % 15
    cache_file = cache_dir / f"bg_{safe_kw}_{slot}.jpg"

    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        raw = cache_file.read_bytes()
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": keyword, "per_page": 15, "orientation": "portrait"},
                    headers={"Authorization": settings.pexels_api_key},
                )
                photos = r.json().get("photos", [])
                if not photos:
                    return None
                photo = photos[photo_idx % len(photos)]
                img_url = photo["src"].get("portrait") or photo["src"]["large"]
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
            bg_image = await _fetch_bg_image(keyword, cache_dir, photo_idx=scene.scene_number - 1)
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


# ---------------------------------------------------------------------------
# Animated HTML templates (content reveals sequentially over scene duration)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Word-by-word karaoke subtitle overlay
# ---------------------------------------------------------------------------
# Sticker + animation layer
# ---------------------------------------------------------------------------

_TOPIC_STICKERS: dict[str, list[str]] = {
    "crypto":   ["₿", "📈", "💎", "🚀", "💰", "🔥", "⚡", "💹", "🌕"],
    "finance":  ["📊", "💹", "💰", "📈", "🏦", "💡", "⚡", "🎯", "🔑"],
    "tech":     ["🤖", "⚡", "🔬", "💡", "🌐", "🚀", "🔮", "💻", "🛠️"],
    "security": ["🔐", "⚠️", "💻", "🛡️", "🔴", "👾", "⚡", "🕵️", "🔒"],
    "war":      ["⚠️", "🔴", "💥", "🛡️", "⚡", "🌍", "🗺️", "🎯"],
    "default":  ["⚡", "🔥", "💡", "✨", "🌟", "💎", "🚀", "🎯", "🔑"],
}


def _pick_sticker_pool(scene: Scene) -> list[str]:
    text = (scene.narration_text + " " + (scene.subtitle_text or "")).lower()
    if any(w in text for w in ["crypto", "bitcoin", "btc", "eth", "coin", "tiền số",
                                "blockchain", "chứng khoán", "cổ phiếu", "đầu tư"]):
        return _TOPIC_STICKERS["crypto"]
    if any(w in text for w in ["hack", "bảo mật", "security", "cyber", "tấn công", "mã độc"]):
        return _TOPIC_STICKERS["security"]
    if any(w in text for w in ["ai", "trí tuệ", "robot", "tech", "công nghệ",
                                "phần mềm", "chip", "bán dẫn"]):
        return _TOPIC_STICKERS["tech"]
    if any(w in text for w in ["chiến tranh", "conflict", "quân sự", "tên lửa", "bom", "vũ khí"]):
        return _TOPIC_STICKERS["war"]
    if any(w in text for w in ["tài chính", "kinh tế", "lãi suất", "lạm phát", "ngân hàng"]):
        return _TOPIC_STICKERS["finance"]
    return _TOPIC_STICKERS["default"]


def _sticker_layer(scene: Scene, accent: str) -> str:
    """Floating emoji stickers + sweep lines for visual energy."""
    import hashlib as _h
    pool = _pick_sticker_pool(scene)
    seed = int(_h.md5(scene.narration_text[:24].encode()).hexdigest(), 16)

    stickers = []
    for i in range(5):
        emoji = pool[(seed + i * 7) % len(pool)]
        x     = 4 + (seed * (i + 1) * 17 % 82)          # 4–86 %
        delay = round(i * 1.1 + (seed % 4) * 0.3, 1)
        dur   = round(5.0 + (i % 3) * 1.4, 1)
        sz    = 30 + (i % 4) * 12                        # 30–66 px
        op    = round(0.45 + (i % 3) * 0.15, 2)         # 0.45–0.75
        stickers.append(
            f'<div class="stk" style="left:{x}%;'
            f'animation-delay:{delay}s;animation-duration:{dur}s;'
            f'font-size:{sz}px;--sop:{op};">{emoji}</div>'
        )

    # 3 diagonal accent scan lines sweeping down
    scans = "".join(
        f'<div class="scanl" style="animation-delay:{0.6 + i * 2.2:.1f}s;'
        f'animation-duration:{2.8 + i * 0.4:.1f}s;opacity:{0.22 - i * 0.04:.2f};"></div>'
        for i in range(3)
    )

    items = "\n".join(stickers)
    return f"""<div id="stk-wrap" style="position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:50;">
{items}
{scans}
</div>
<style>
.stk{{position:absolute;bottom:-80px;user-select:none;
  animation:stkRise linear infinite;}}
@keyframes stkRise{{
  0%{{transform:translateY(0) rotate(-6deg) scale(0.85);opacity:0;}}
  8%{{opacity:var(--sop,.6);}}
  88%{{opacity:var(--sop,.6);}}
  100%{{transform:translateY(-2060px) rotate(10deg) scale(1.05);opacity:0;}}
}}
.scanl{{position:absolute;left:-8%;right:-8%;height:2px;top:0;
  background:linear-gradient(90deg,transparent,{accent}55 30%,{accent}88 50%,{accent}55 70%,transparent);
  animation:scanDown ease-in-out infinite;}}
@keyframes scanDown{{
  0%{{top:0;opacity:0;}}
  6%{{opacity:1;}}
  90%{{opacity:.6;}}
  100%{{top:106%;opacity:0;}}
}}
</style>"""


# ---------------------------------------------------------------------------

def _sfx_layer(scene_type: str = "generic") -> str:
    """
    Inject subtle sound effects via Web Audio API oscillators.
    No external files needed — pure JS synthesis.
    scene_type: 'stats' → impact thud; 'compare' → whoosh slide; generic → soft chime
    """
    if scene_type == "stats":
        # Deep impact thud when stats animate in
        js = """
(function(){
  try {
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    function thud(t){
      var o=ctx.createOscillator(),g=ctx.createGain();
      o.connect(g);g.connect(ctx.destination);
      o.type='sine';o.frequency.setValueAtTime(120,t);
      o.frequency.exponentialRampToValueAtTime(40,t+0.18);
      g.gain.setValueAtTime(0.28,t);g.gain.exponentialRampToValueAtTime(0.001,t+0.22);
      o.start(t);o.stop(t+0.25);
    }
    thud(ctx.currentTime+0.55);
  } catch(e){}
})();"""
    elif scene_type == "compare":
        # Whoosh sweep when bars grow
        js = """
(function(){
  try {
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    function whoosh(t){
      var buf=ctx.createBuffer(1,ctx.sampleRate*0.4,ctx.sampleRate);
      var d=buf.getChannelData(0);
      for(var i=0;i<d.length;i++) d[i]=(Math.random()*2-1)*Math.pow(1-i/d.length,1.8)*0.18;
      var src=ctx.createBufferSource(),g=ctx.createGain(),f=ctx.createBiquadFilter();
      f.type='bandpass';f.frequency.setValueAtTime(800,t);
      f.frequency.exponentialRampToValueAtTime(4000,t+0.35);
      src.buffer=buf;src.connect(f);f.connect(g);g.connect(ctx.destination);
      g.gain.setValueAtTime(0.6,t);g.gain.exponentialRampToValueAtTime(0.001,t+0.4);
      src.start(t);
    }
    whoosh(ctx.currentTime+0.65);
  } catch(e){}
})();"""
    else:
        # Soft chime on content reveal
        js = """
(function(){
  try {
    var ctx=new(window.AudioContext||window.webkitAudioContext)();
    function chime(freq,t,vol){
      var o=ctx.createOscillator(),g=ctx.createGain();
      o.connect(g);g.connect(ctx.destination);
      o.type='sine';o.frequency.value=freq;
      g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(vol,t+0.04);
      g.gain.exponentialRampToValueAtTime(0.001,t+0.7);
      o.start(t);o.stop(t+0.75);
    }
    var t=ctx.currentTime+0.48;
    chime(880,t,0.09);chime(1320,t+0.08,0.06);chime(1760,t+0.15,0.04);
  } catch(e){}
})();"""
    return f"<script>{js}</script>"


# ---------------------------------------------------------------------------

def _subtitle_layer(word_timings: list[dict], accent: str) -> str:
    """
    Karaoke subtitle: one sentence (≤2 lines) visible at a time.
    All words shown in dimmed white; the current word lights up in accent color.
    """
    if not word_timings:
        return ""
    import json as _json

    def _chunk(words: list[dict], max_w: int = 10) -> list[list[dict]]:
        """Split word list into sentence-sized chunks for display."""
        chunks: list[list[dict]] = []
        cur: list[dict] = []
        for w in words:
            cur.append(w)
            txt = w["word"].rstrip()
            # Break at sentence-ending punctuation (min 3 words to avoid micro-chunks)
            if txt and txt[-1] in ".!?;" and len(cur) >= 3:
                chunks.append(cur)
                cur = []
            elif len(cur) >= max_w:
                # Prefer breaking at the last comma in the chunk
                ci = next(
                    (j for j in range(len(cur) - 1, -1, -1)
                     if cur[j]["word"].rstrip().endswith(",")),
                    -1,
                )
                if ci > 2:
                    chunks.append(cur[: ci + 1])
                    cur = cur[ci + 1 :]
                else:
                    chunks.append(cur)
                    cur = []
        if cur:
            chunks.append(cur)
        return chunks

    raw_chunks = _chunk(word_timings)
    js_chunks = [
        {
            "start": c[0]["start"],
            "words": [{"w": w["word"], "t": w["start"]} for w in c],
        }
        for c in raw_chunks
    ]
    chunks_js = _json.dumps(js_chunks, ensure_ascii=False)

    return f"""<div id="sub-wrap" style="position:absolute;bottom:0;left:0;right:0;
  min-height:310px;padding:40px 64px 72px;
  background:linear-gradient(transparent,rgba(0,0,0,0.95) 28%);
  display:flex;align-items:flex-end;justify-content:center;
  z-index:100;pointer-events:none;">
  <div id="sub-line" style="text-align:center;font-size:68px !important;font-weight:800 !important;
    font-family:'Be Vietnam Pro',sans-serif !important;color:rgba(255,255,255,0.82);
    line-height:1.38;letter-spacing:-0.5px;
    opacity:0;transition:opacity 0.18s ease;
    text-shadow:0 2px 20px rgba(0,0,0,1);max-width:952px;"></div>
</div>
<style>
/* Highlighted word: accent color + subtle pill background */
#sub-line .hl{{
  color:{accent};
  -webkit-text-stroke:0.35px {accent};
  background:rgba(255,255,255,0.10);
  border-radius:12px;
  padding:0 10px;
  margin:0 -2px;
  box-decoration-break:clone;
  -webkit-box-decoration-break:clone;
}}
</style>
<script>
(function(){{
  var chunks={chunks_js};
  var box=document.getElementById('sub-line');
  chunks.forEach(function(chunk,ci){{
    var last=chunk.words[chunk.words.length-1];
    var nextStart=ci+1<chunks.length
      ?chunks[ci+1].start
      :(last.t+0.65);
    setTimeout(function(){{
      box.innerHTML=chunk.words.map(function(w,wi){{
        return '<span id="k'+ci+'_'+wi+'">'+w.w+'</span>';
      }}).join(' ');
      box.style.opacity='1';
      chunk.words.forEach(function(w,wi){{
        setTimeout(function(){{
          chunk.words.forEach(function(_,j){{
            var e=document.getElementById('k'+ci+'_'+j);
            if(e)e.className='';
          }});
          var e=document.getElementById('k'+ci+'_'+wi);
          if(e)e.className='hl';
        }},(w.t-chunk.start)*1000);
      }});
    }},chunk.start*1000);
    setTimeout(function(){{
      box.style.opacity='0';
    }},(nextStart-0.10)*1000);
  }});
}})();
</script>"""


_ANIM_CSS = """
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(44px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: scale(1); }
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-48px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slideLeft {
  from { opacity: 0; transform: translateX(-60px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes slideRight {
  from { opacity: 0; transform: translateX(60px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes wipeRight {
  from { clip-path: inset(0 100% 0 0); opacity:1; }
  to   { clip-path: inset(0 0% 0 0);   opacity:1; }
}
@keyframes wipeUp {
  from { clip-path: inset(100% 0 0 0); opacity:1; }
  to   { clip-path: inset(0% 0 0 0);   opacity:1; }
}
@keyframes popIn {
  0%   { opacity:0; transform: scale(0.7); }
  70%  { transform: scale(1.04); }
  100% { opacity:1; transform: scale(1); }
}
@keyframes scanDown {
  0%   { top:-4px; opacity:0.6; }
  100% { top:100%; opacity:0; }
}
.a-up    { opacity:0; animation: fadeUp   0.65s cubic-bezier(0.16,1,0.3,1) forwards; }
.a-in    { opacity:0; animation: fadeIn   0.5s  cubic-bezier(0.16,1,0.3,1) forwards; }
.a-down  { opacity:0; animation: slideDown 0.6s  cubic-bezier(0.16,1,0.3,1) forwards; }
.a-left  { opacity:0; animation: slideLeft  0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
.a-rgt   { opacity:0; animation: slideRight 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
.a-wipe  { animation: wipeRight 0.7s cubic-bezier(0.16,1,0.3,1) forwards; }
.a-wipeU { animation: wipeUp   0.65s cubic-bezier(0.16,1,0.3,1) forwards; }
.a-pop   { opacity:0; animation: popIn    0.55s cubic-bezier(0.34,1.56,0.64,1) forwards; }
"""


def _estimate_tts_dur(text: str) -> float:
    """Rough TTS duration estimate: ~13 chars/second for Vietnamese."""
    return max(4.0, len(text.strip()) / 13.0)


def _anim_highlight(scene: Scene, title: str,
                    accent: str, bg1: str, bg2: str, bg_image: str | None,
                    word_timings: list[dict] | None = None) -> str:
    """Key-insight view for stats scenes with no extractable numbers."""
    # Split narration into bullet points at sentence boundaries
    raw = [s.strip() for s in re.split(r'[.!;،،]', scene.narration_text) if len(s.strip()) > 8]
    points = raw[:4] or [scene.narration_text]
    has_sub = bool(word_timings)
    bottom_pad = "360px" if has_sub else "80px"
    body_style = (f"background:url({bg_image}) center/cover no-repeat; position:relative;"
                  if bg_image else f"background:linear-gradient(160deg,{bg1},#000 80%);")
    ov = _overlay(bg_image)
    z = _z()
    stk = _sticker_layer(scene, accent)
    tb = textwrap.shorten(title, 40, placeholder="…")
    items_html = "".join(
        f'<div class="pt a-up" style="animation-delay:{0.3 + i * 0.18:.2f}s">'
        f'<span class="dot">✦</span>'
        f'<span class="ptxt">{textwrap.shorten(p, 80, placeholder="…")}</span>'
        f'</div>'
        for i, p in enumerate(points)
    )
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{_ANIM_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:80px 80px {bottom_pad}; }}
.cat  {{ {z} color:{accent}; font-size:24px; font-weight:800; letter-spacing:8px;
  text-transform:uppercase; margin-bottom:36px; }}
.hl   {{ {z} color:#fff; font-size:56px; font-weight:900; line-height:1.1;
  margin-bottom:52px; text-shadow:0 4px 24px rgba(0,0,0,.8); max-width:900px; }}
.pts  {{ {z} display:flex; flex-direction:column; gap:28px; max-width:920px; }}
.pt   {{ display:flex; align-items:flex-start; gap:24px; }}
.dot  {{ color:{accent}; font-size:28px; line-height:1.3; flex-shrink:0; }}
.ptxt {{ color:rgba(255,255,255,.88); font-size:36px; font-weight:600; line-height:1.4; }}
.badge {{ {z} position:absolute; top:80px; right:80px; color:{accent};
  font-size:24px; font-weight:700; letter-spacing:2px;
  max-width:520px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
{stk}
<div class="cat a-in" style="animation-delay:0.1s">ĐIỂM NỔI BẬT</div>
<div class="hl a-up"   style="animation-delay:0.2s">{scene.subtitle_text}</div>
<div class="pts">{items_html}</div>
<div class="badge a-in" style="animation-delay:0.12s">{tb}</div>
{_subtitle_layer(word_timings or [], accent)}
</body></html>"""


def _anim_how(scene: Scene, title: str, duration: float,
              accent: str, bg1: str, bg2: str, bg_image: str | None,
              word_timings: list[dict] | None = None) -> str:
    raw = [s.strip() for s in re.split(r'[.!;]', scene.narration_text) if s.strip()]
    steps = raw[:4] or [scene.narration_text]
    n = len(steps)
    # Step 0 at 0.4s; remaining steps evenly spaced across the duration
    interval = (duration - 0.5) / max(n, 1)
    delays = [0.4 + i * interval for i in range(n)]

    ta = textwrap.shorten(title, 40, placeholder="…")
    steps_html = "".join(
        f'<div class="step a-left" style="animation-delay:{d:.2f}s">'
        f'<span class="sn">{i+1}</span>'
        f'<span class="st">{textwrap.shorten(s, 90, placeholder="…")}</span>'
        f'</div>'
        for i, (s, d) in enumerate(zip(steps, delays))
    )
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(160deg,{bg1} 0%,#0a0a0a 100%);"
    ov = _overlay(bg_image)
    z = _z()
    sub = _subtitle_layer(word_timings or [], accent)
    stk = _sticker_layer(scene, accent)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{_ANIM_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center; padding:100px 80px; }}
.cat {{ {z} color:{accent}; font-size:26px; font-weight:800; letter-spacing:6px;
  text-transform:uppercase; margin-bottom:28px; }}
.hl  {{ {z} color:#fff; font-size:70px; font-weight:900; line-height:1.08;
  letter-spacing:-1.5px; margin-bottom:60px; }}
.step {{ {z} display:flex; align-items:flex-start; gap:24px; margin-bottom:44px; }}
.sn  {{ flex-shrink:0; width:68px; height:68px; border-radius:50%; background:{accent};
  color:#000; font-size:34px; font-weight:900;
  display:flex; align-items:center; justify-content:center; margin-top:4px; }}
.st  {{ color:rgba(255,255,255,.85); font-size:42px; line-height:1.45; }}
.foot {{ {z} position:absolute; bottom:80px; left:80px;
  color:{accent}; font-size:28px; font-weight:700; letter-spacing:3px;
  max-width:700px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
{stk}
<div class="cat a-in" style="animation-delay:0.1s">CÁCH LÀM · HOW TO</div>
<div class="hl a-up"  style="animation-delay:0.2s">{_wrap_headline(scene.subtitle_text, 28)}</div>
{steps_html}
<div class="foot a-in" style="animation-delay:0.15s">{ta}</div>
{sub}
</body></html>"""


def _anim_stats(scene: Scene, title: str, duration: float,
                accent: str, bg1: str, bg2: str, bg_image: str | None,
                word_timings: list[dict] | None = None) -> str:
    all_stats = _extract_all_stats(scene.narration_text)
    # No numeric data → render as highlight-points view
    if not all_stats:
        return _anim_highlight(scene, title, accent, bg1, bg2, bg_image, word_timings)
    has_sub = bool(word_timings)
    count_dur_ms = int(min(duration * 0.35, 2.8) * 1000)
    narr = textwrap.shorten(scene.narration_text, 180, placeholder="…")
    bottom_pad = "360px" if has_sub else "80px"
    if bg_image:
        body_style = f"background:url({bg_image}) center/cover no-repeat; position:relative;"
    else:
        body_style = f"background:linear-gradient(160deg,{bg1},#000 80%);"
    ov = _overlay(bg_image)
    z = _z()
    stk = _sticker_layer(scene, accent)

    # Build stat boxes (multi-stat grid when ≥ 2 found)
    multi = len(all_stats) >= 2
    stat_font = "130px" if multi else "220px"
    unit_font = "44px"  if multi else "56px"

    stat_boxes = "".join(
        f'<div class="sbox a-up" style="animation-delay:{0.3 + j * 0.18:.2f}s">'
        f'<span class="big" id="cnt{j}">0</span>'
        f'<span class="unit">{u}</span>'
        f'</div>'
        for j, (n, u) in enumerate(all_stats)
    )
    targets_js = "[" + ",".join(
        str(float(n.replace(",", "")) if n != "?" else 0)
        for n, _ in all_stats
    ) + "]"

    tb = textwrap.shorten(title, 40, placeholder="…")
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{_ANIM_CSS}
body {{ {body_style} display:flex; flex-direction:column; align-items:center;
  justify-content:center; padding:80px 60px {bottom_pad}; }}
.cat  {{ {z} color:{accent}; font-size:24px; font-weight:800; letter-spacing:8px;
  text-transform:uppercase; margin-bottom:48px; }}
.grid {{ {z} display:flex; gap:40px; justify-content:center; margin-bottom:36px;
  flex-wrap:wrap; }}
.sbox {{ text-align:center; min-width:200px; }}
.big  {{ display:block; color:{accent}; font-size:{stat_font}; font-weight:900;
  line-height:0.88; letter-spacing:-4px; text-shadow:0 0 60px {accent}55; }}
.unit {{ display:block; color:rgba(255,255,255,.55); font-size:{unit_font};
  font-weight:700; letter-spacing:2px; margin-top:10px; }}
.div  {{ {z} width:120px; height:4px; background:{accent}44; border-radius:3px; margin:36px auto; }}
.hl   {{ {z} color:#fff; font-size:52px; font-weight:700; text-align:center;
  line-height:1.28; max-width:880px; margin-bottom:24px; }}
.narr {{ {z} color:rgba(255,255,255,.58); font-size:34px; text-align:center;
  line-height:1.5; max-width:880px; {'display:none;' if has_sub else ''} }}
.badge {{ {z} position:absolute; top:80px; right:80px;
  color:{accent}; font-size:24px; font-weight:700; letter-spacing:2px;
  max-width:560px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{ov}
{stk}
<div class="cat a-in" style="animation-delay:0.1s">SỐ LIỆU</div>
<div class="grid">{stat_boxes}</div>
<div class="div a-in" style="animation-delay:0.45s"></div>
<div class="hl a-up"   style="animation-delay:0.55s">{scene.subtitle_text}</div>
<div class="narr a-up" style="animation-delay:0.75s">{narr}</div>
<div class="badge a-in" style="animation-delay:0.12s">{tb}</div>
<script>
(function(){{
  var targets={targets_js};
  var dur={count_dur_ms};
  function ease(t){{ return 1-Math.pow(1-t,3); }}
  function animate(el,target){{
    var start=null;
    function tick(ts){{
      if(!start)start=ts;
      var t=Math.min((ts-start)/dur,1);
      var v=ease(t)*target;
      el.textContent=Number.isInteger(target)?Math.round(v):v.toFixed(1);
      if(t<1)requestAnimationFrame(tick);
      else el.textContent=target%1===0?Math.round(target):target;
    }}
    requestAnimationFrame(tick);
  }}
  setTimeout(function(){{
    targets.forEach(function(t,i){{
      var el=document.getElementById('cnt'+i);
      if(el)animate(el,t);
    }});
  }},500);
}})();
</script>
{_sfx_layer("stats")}
{_subtitle_layer(word_timings or [], accent)}
</body></html>"""


def _anim_news(scene: Scene, title: str, duration: float,
               accent: str, bg1: str, bg2: str, bg_image: str | None,
               word_timings: list[dict] | None = None) -> str:
    labels = ["WHAT", "WHY", "WHO", "HOW", "KHOẢNH KHẮC", "KẾT LUẬN",
              "HOOK", "BỐI CẢNH", "PHƯƠNG PHÁP", "BẰNG CHỨNG", "HẬU QUẢ", "BÀI HỌC"]
    cat = labels[(scene.scene_number - 1) % len(labels)]
    has_sub = bool(word_timings)
    # Paragraphs hidden when karaoke handles speech; shown as fallback only
    if has_sub:
        paras_html = ""
    else:
        paras = [p for p in textwrap.wrap(scene.narration_text, 42)][:4]
        n = len(paras)
        para_interval = (duration - 1.5) / max(n, 1)
        paras_html = "".join(
            f'<p class="a-up" style="animation-delay:{1.5 + i*para_interval:.2f}s">{p}</p>'
            for i, p in enumerate(paras)
        )
    if bg_image:
        hdr_style = f"background:url({bg_image}) center 20%/cover no-repeat; position:relative;"
        hdr_ov = f'<div style="position:absolute;inset:0;background:{accent}cc;z-index:0;"></div>'
    else:
        hdr_style = f"background:{accent};"
        hdr_ov = ""
    tn = textwrap.shorten(title, 40, placeholder="…")
    z = _z()
    stk = _sticker_layer(scene, accent)
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{_ANIM_CSS}
body {{ background:linear-gradient(180deg,#0a0a0a,#111); padding:0; overflow:hidden; }}
.hdr {{ {hdr_style} padding:56px 80px 48px; }}
.cat {{ {z} color:rgba(0,0,0,.65); font-size:28px; font-weight:800;
  letter-spacing:6px; text-transform:uppercase; margin-bottom:18px; }}
.hl  {{ {z} color:#fff; font-size:70px; font-weight:900; line-height:1.08;
  letter-spacing:-1.5px; text-shadow:0 3px 20px rgba(0,0,0,.5); }}
.body {{ padding:64px 80px {'0' if has_sub else ''}; }}
.body p {{ color:rgba(255,255,255,.76); font-size:44px; line-height:1.6; margin-bottom:14px; }}
.foot {{ position:absolute; bottom:{'310px' if has_sub else '0'}; left:0; right:0;
  background:{accent}22; border-top:2px solid {accent}44; padding:32px 80px; }}
.ft {{ color:{accent}; font-size:34px; font-weight:800;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
</style></head><body>
{stk}
<div class="hdr a-down" style="animation-delay:0.1s">
  {hdr_ov}
  <div class="cat">{cat}</div>
  <div class="hl">{scene.subtitle_text}</div>
</div>
<div class="body">{paras_html}</div>
<div class="foot a-up" style="animation-delay:0.2s">
  <span class="ft">{tn}</span>
</div>
{_subtitle_layer(word_timings or [], accent)}
</body></html>"""


def _anim_dark(scene: Scene, title: str, duration: float,
               accent: str, bg1: str, bg2: str, bg_image: str | None,
               word_timings: list[dict] | None = None) -> str:
    """Cinematic dark card: badge → accent bar → wipe headline → narration/karaoke."""
    icon = _scene_icon(scene.scene_number)
    has_sub = bool(word_timings)
    if has_sub:
        narr_block = ""
    else:
        narr_lines = textwrap.wrap(scene.narration_text, 42)[:3]
        n = len(narr_lines)
        line_interval = (duration - 1.8) / max(n, 1)
        narr_block = '<div class="narr">' + "".join(
            f'<p class="a-up" style="animation-delay:{1.8 + i*line_interval:.2f}s">{ln}</p>'
            for i, ln in enumerate(narr_lines)
        ) + '</div>'
    td = textwrap.shorten(title, 40, placeholder="…")
    body_style = (f"background:url({bg_image}) center/cover no-repeat; position:relative;"
                  if bg_image else f"background:linear-gradient(160deg,{bg1} 0%,{bg2} 60%,#000 100%);")
    ov = _overlay(bg_image, force=not bg_image)
    z = _z()
    stk = _sticker_layer(scene, accent)
    bottom_pad = "340px" if has_sub else "80px"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
{_COMMON_CSS}
{_ANIM_CSS}
body {{ {body_style} display:flex; flex-direction:column; justify-content:center;
  padding:100px 88px {bottom_pad}; }}
.badge {{ {z} display:inline-flex; align-items:center; gap:12px;
  background:rgba(255,255,255,.08); border:1.5px solid {accent}55;
  color:{accent}; font-size:26px; font-weight:800; letter-spacing:2px;
  padding:10px 22px; border-radius:50px; margin-bottom:52px;
  width:fit-content; text-transform:uppercase;
  max-width:520px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.icon {{ font-size:36px; flex-shrink:0; }}
.acbar {{ {z} width:72px; height:5px; background:{accent};
  border-radius:3px; margin-bottom:40px; }}
.hl  {{ {z} color:#fff; font-size:82px; font-weight:900; line-height:1.07;
  letter-spacing:-2px; text-shadow:0 2px 40px rgba(0,0,0,.6);
  margin-bottom:52px; }}
.narr {{ {z} }}
.narr p {{ color:rgba(255,255,255,.75); font-size:42px; font-weight:500;
  line-height:1.55; margin-bottom:10px; }}
</style></head><body>
{ov}
{stk}
<div class="badge a-in"  style="animation-delay:0.1s"><span class="icon">{icon}</span>{td}</div>
<div class="acbar a-wipe" style="animation-delay:0.3s"></div>
<div class="hl a-wipe"   style="animation-delay:0.45s">{_wrap_headline(scene.subtitle_text, 18)}</div>
{narr_block}
{_sfx_layer("generic")}
{_subtitle_layer(word_timings or [], accent)}
</body></html>"""


def _anim_compare(scene: Scene, title: str, duration: float,
                  accent: str, bg1: str, bg2: str, bg_image: str | None,
                  word_timings: list[dict] | None = None) -> str:
    """Animated comparison — auto-selects hbar/vbar/pie/line chart based on data."""
    has_sub = bool(word_timings)
    bottom_pad = "380px" if has_sub else "80px"
    stk = _sticker_layer(scene, accent)
    sub = _subtitle_layer(word_timings or [], accent)
    return _compare_body(
        scene, title, accent, bg1, bg2, bg_image,
        animated=True,
        word_timings=word_timings,
        stk_html=stk,
        sub_html=sub,
        bottom_pad=bottom_pad,
    )


_ANIM_MAP = {
    "compare":   _anim_compare,
    "how":       _anim_how,
    "stats":     _anim_stats,
    "news":      _anim_news,
    "dark":      _anim_dark,
    "gradient":  _anim_dark,   # use generic reveal for others
    "minimal":   _anim_dark,
    "bold":      _anim_dark,
    "cinematic": _anim_dark,
}


def build_animated_html(scene: Scene, title: str, template: str,
                        duration: float, bg_image: str | None = None,
                        word_timings: list[dict] | None = None,
                        bg_video: str | None = None,
                        topic: str = "") -> str:
    """Build HTML with sequential CSS animations timed to `duration` seconds."""
    # Use topic-locked palette so all scenes in a video share the same color identity
    if topic:
        bg1, bg2, accent = _palette_for_topic(topic)
    else:
        bg1, bg2, accent = _palette(title + str(scene.scene_number))
    tpl = template if template != "auto" else _auto_template(scene)
    fn = _ANIM_MAP.get(tpl, _anim_dark)
    html = fn(scene, title, duration, accent, bg1, bg2, bg_image, word_timings)
    # Inject video background if available (replaces CSS background on <body>)
    if bg_video:
        html = _inject_video_bg(html, bg_video)
    return html


def _inject_video_bg(html: str, video_url: str) -> str:
    """Replace body background with a looping <video> element."""
    vid_tag = (
        f'<video autoplay loop muted playsinline disablepictureinpicture '
        f'style="position:fixed;inset:0;width:100%;height:100%;'
        f'object-fit:cover;z-index:-1;filter:brightness(0.45) saturate(0.75);">'
        f'<source src="{video_url}" type="video/mp4"></video>'
    )
    # Remove existing background from body, inject video after <body>
    import re as _re
    html = _re.sub(r'background:[^;}]+[;}]', 'background:transparent;', html, count=1)
    html = html.replace("<body>", f"<body>\n{vid_tag}", 1)
    # Also fix body inline style that has background
    html = _re.sub(
        r'(<body[^>]*style=")([^"]*background:[^;"]+;?)',
        lambda m: m.group(1) + m.group(2).replace(
            m.group(2)[m.group(2).find("background:"):], "background:transparent;"
        ),
        html, count=1,
    )
    return html


# ---------------------------------------------------------------------------
# Animated video rendering via Playwright screen recording
# ---------------------------------------------------------------------------

async def render_scene_to_video(
    scene: Scene,
    title: str,
    output_path: Path,           # target .mp4
    template: str = "auto",
    duration: float | None = None,
    word_timings: list[dict] | None = None,
    on_progress: Callable[[str, int], None] | None = None,
    local_bg_image: str | None = None,  # path to local PNG/JPG → used as HTML background
    topic: str = "",             # video topic for consistent accent color
) -> Path:
    """
    Record the animated HTML scene as an MP4.
    Content elements appear sequentially over the scene duration — no Ken Burns needed.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from exc

    scene_dur = duration or _estimate_tts_dur(scene.narration_text)

    from config import settings as _cfg

    # Resolve background: Pexels VIDEO > local image > Pexels photo > gradient
    bg_image: str | None = None
    bg_video: str | None = None     # file:// URL for <video> background

    if local_bg_image and Path(local_bg_image).exists():
        img_bytes = Path(local_bg_image).read_bytes()
        b64 = base64.b64encode(img_bytes).decode()
        suffix = Path(local_bg_image).suffix.lower().lstrip(".")
        mime = "image/jpeg" if suffix in ("jpg", "jpeg") else "image/png"
        bg_image = f"data:{mime};base64,{b64}"
    else:
        try:
            if _cfg.pexels_api_key:
                cache_dir = output_path.parent.parent / "bg_cache"
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    import tempfile
                    cache_dir = Path(tempfile.gettempdir()) / "pepe_bg_cache"
                    cache_dir.mkdir(exist_ok=True)
                keyword = scene.visual_prompt.split(",")[0][:60].strip()
                # Try video background first (much better visual quality)
                if _cfg.pexels_video_enable:
                    from worker.pexels_engine import fetch_pexels_video
                    vid = await fetch_pexels_video(
                        keyword, cache_dir, idx=scene.scene_number - 1,
                        api_key=_cfg.pexels_api_key,
                    )
                    if vid:
                        bg_video = vid.as_uri()  # file:///...
                # Fall back to static photo if video disabled or failed
                if not bg_video and _cfg.html_use_bg_image:
                    bg_image = await _fetch_bg_image(keyword, cache_dir, photo_idx=scene.scene_number - 1)
        except Exception as e:
            print(f"[html_engine] bg fetch error: {e}")

    html = build_animated_html(scene, title, template, scene_dur, bg_image, word_timings,
                                bg_video=bg_video, topic=topic)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if on_progress:
        on_progress(f"🎬 Recording HTML scene {scene.scene_number}…", 10)

    webm_dir = output_path.parent / f"_webm_{scene.scene_number:02d}"
    webm_dir.mkdir(exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
                "--allow-file-access-from-files",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1080, "height": 1920},
            record_video_dir=str(webm_dir),
            record_video_size={"width": 1080, "height": 1920},
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle")
        # Give video bg a moment to start playing before we begin recording
        if bg_video:
            await asyncio.sleep(0.5)
        # Let animations play; extra 0.4s buffer for last element to settle
        await asyncio.sleep(scene_dur + 0.4)
        video = page.video
        await context.close()
        webm_path = output_path.with_suffix(".tmp.webm")
        await video.save_as(str(webm_path))
        await browser.close()

    # Convert WebM → h264 MP4

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(webm_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg webm→mp4 failed:\n{stderr.decode()[-500:]}")

    webm_path.unlink(missing_ok=True)
    # Clean up temp webm recording dir
    import shutil
    shutil.rmtree(webm_dir, ignore_errors=True)

    if on_progress:
        on_progress(f"🎬 HTML scene {scene.scene_number} video ready", 100)

    return output_path
