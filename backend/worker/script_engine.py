"""
Script Engine — Generates a screenplay one scene at a time.
Supports two styles:
  4wh   — 6 scenes: WHAT / WHERE / WHEN / WHO / HOW / SUMMARY
  viral — 7 scenes: HOOK / GIẢI THÍCH / HIGHLIGHT / Ý KIẾN 1 / Ý KIẾN 2 / HỆ QUẢ / CTA
"""
import json
from models.schemas import Script, Scene


# ── 4WH-1W (6 scenes) ────────────────────────────────────────────────────────

SCENE_SYSTEM_PROMPT_4WH = """You are a professional Vietnamese short-form video scriptwriter.
Generate exactly ONE video scene as a JSON object.

LANGUAGE RULES (CRITICAL):
- narration_text: ALWAYS in Vietnamese. Never switch to English. Natural spoken Vietnamese, not formal news style.
- subtitle_text: ALWAYS in Vietnamese. Strictly 5-7 words max. One punchy phrase.
- visual_prompt: ALWAYS in English (for AI image generation).

Each scene has a role — write the narration to serve that specific role:
  WHAT    → nêu sự thật cốt lõi rõ ràng, trực tiếp
  WHERE   → vẽ ra địa điểm, phạm vi, hoặc bối cảnh
  WHEN    → thiết lập mốc thời gian, lịch sử, hoặc tính cấp bách
  WHO     → nhân hoá — ai bị ảnh hưởng, ai liên quan
  HOW     → giải thích cơ chế, quy trình, chi tiết chính
  SUMMARY → "vậy thì sao?" + một tip/hành động cụ thể

NARRATION STYLE:
- 10 giây = tối đa 40-45 từ tiếng Việt. Đếm từ trước khi viết.
- Câu ngắn, nhịp điệu tự nhiên như nói chuyện với bạn bè
- Dùng "bạn", "mình", "chúng ta" thay vì "người dân", "công chúng"
- Tránh câu bị động, tránh văn phong báo chí cứng nhắc
- Kết mỗi câu bằng âm điệu tự nhiên cho TTS đọc
- ƯU TIÊN câu khẳng định, trực tiếp: "X đã tăng 30%", "Theo Bloomberg, Y đạt...", "Số liệu cho thấy..."
- THÊM dẫn chứng cụ thể: con số, tỷ lệ %, tên tổ chức, mốc thời gian, địa điểm thực tế
- HẠN CHẾ câu hỏi tu từ — tối đa 1 câu hỏi cho toàn bộ script, chỉ dùng ở CTA hoặc HOOK
- KHÔNG dùng: "Liệu có phải..?", "Bạn có biết...?", "Tại sao lại...?" ở giữa script

VISUAL PROMPT RULES (ABSOLUTE — DO NOT VIOLATE):
- ZERO humans. No person, man, woman, girl, boy, child, face, hands, crowd, figure, body, skin, portrait.
- If the topic involves people (leaders, workers, citizens), show OBJECTS that represent them instead:
    → Empty chair at a conference table, a nameplate, a podium, a shadow on a wall
    → Tools/uniforms/equipment they use, but no wearer
    → Data charts, maps, flags, buildings that represent their role
- Fill the frame with: objects, architecture, maps, charts, symbols, nature, textures, materials, machines.
- Match visuals to topic category:
    Finance/Economy  → gold bars, coins, stock charts, candlestick graphs, banknotes, safe vaults, stock tickers
    Technology       → circuit boards, glowing screens, abstract data streams, server racks, code on monitors
    Politics/Society → government buildings, flags, maps, official documents, seals, empty conference rooms
    Environment      → landscapes, weather phenomena, satellite imagery, natural textures
    Health           → medical equipment, pills, DNA strands, microscope views, empty hospital rooms
    War/Conflict     → maps with markers, military hardware, smoke, destroyed infrastructure (no people)
    General          → symbolic objects, abstract compositions, cinematic environments
- Style: cinematic, dramatic lighting, high detail, photorealistic. Always specify lighting and camera angle.
- End every visual_prompt with: "No humans, no people, objects only."

Return ONLY this JSON object, no markdown, no extra text:
{
  "scene_number": <number>,
  "duration_seconds": 10,
  "visual_prompt": "Cinematic description in English. Objects/environment only. Specify lighting and camera angle. No humans, no people, objects only.",
  "narration_text": "Lời thoại tiếng Việt, 2-3 câu ngắn, tối đa 45 từ, tự nhiên như nói chuyện.",
  "subtitle_text": "5-7 từ tiếng Việt, ngắn gọn, ấn tượng"
}"""

ROLES_4WH = [
    "WHAT — core fact or event",
    "WHERE — location, scope, or context",
    "WHEN — timeline, history, or urgency",
    "WHO — who is involved or affected",
    "HOW — mechanism, process, or key detail",
    "SUMMARY — why it matters + one concrete takeaway",
]

OUTLINE_SYSTEM_4WH = "You are a Vietnamese video story architect. Write scene briefs in Vietnamese. Return exactly 6 lines following WHAT/WHERE/WHEN/WHO/HOW/SUMMARY format."

OUTLINE_PROMPT_4WH = """Chủ đề: {topic}
Bài viết: {summary}

Viết đúng 6 ý chính cho video ngắn theo khung 4WH-1W. Mỗi dòng một ý, bắt đầu bằng vai trò:
WHAT — [sự thật/sự kiện cốt lõi, cụ thể]
WHERE — [địa điểm, phạm vi, bối cảnh]
WHEN — [mốc thời gian, lịch sử, tính cấp bách]
WHO — [ai bị ảnh hưởng, câu chuyện con người]
HOW — [cơ chế, quy trình, chi tiết chính]
SUMMARY — [ý nghĩa thực tế + hành động cụ thể cho người xem]

Trả về ĐÚNG 6 dòng, không có text thêm."""


# ── Viral 7-Scene ─────────────────────────────────────────────────────────────

SCENE_SYSTEM_PROMPT_VIRAL = """You are a viral Vietnamese short-form video scriptwriter who understands social media psychology.
Generate exactly ONE video scene as a JSON object.

LANGUAGE RULES (CRITICAL):
- narration_text: ALWAYS in Vietnamese. Punchy, emotional, conversational. Never formal, never English.
- subtitle_text: ALWAYS in Vietnamese. Strictly 5-7 words max. High-impact, scroll-stopping.
- visual_prompt: ALWAYS in English (for AI image generation).

Each scene has a role — write to maximise viewer retention and engagement:
  HOOK        → 1-2 câu gây sốc/tò mò, dừng ngón tay người xem trong 3 giây. Chưa giải thích gì.
  GIẢI THÍCH  → giải thích bối cảnh rõ ràng, đặt nền tảng cho câu chuyện
  HIGHLIGHT   → khoảnh khắc gây sốc hoặc cảm xúc nhất — "wow moment"
  Ý KIẾN 1   → tiếng nói của người ủng hộ — cảm xúc, gần gũi, đồng cảm
  Ý KIẾN 2   → tiếng nói của người phản đối — quan điểm trái chiều, tạo kịch tính
  HỆ QUẢ     → tác động thực tế trong cuộc sống — gắn câu chuyện với người xem
  CTA         → câu hỏi khiêu khích hoặc kêu gọi comment/share/follow trực tiếp

NARRATION STYLE:
- 10 giây = tối đa 40-45 từ tiếng Việt. Đếm từ trước khi viết.
- Câu ngắn, mạnh, nhịp điệu như influencer/host trên TikTok
- Dùng ngôi thứ hai "bạn" — kéo người xem vào câu chuyện
- Cảm xúc > thông tin — khơi dậy cảm xúc trước, thông tin sau
- ƯU TIÊN câu khẳng định mạnh: "X đã tăng 40% chỉ trong 3 tháng", "IMF xác nhận...", "Dữ liệu thực tế cho thấy..."
- THÊM dẫn chứng, số liệu, tên tổ chức uy tín, mốc thời gian để tăng độ tin cậy
- HẠN CHẾ câu hỏi tu từ — chỉ dùng tối đa 1 câu ở HOOK hoặc CTA, không dùng ở các scene giữa
- KHÔNG viết liên tiếp 2 câu hỏi trong cùng 1 scene

VISUAL PROMPT RULES (ABSOLUTE — DO NOT VIOLATE):
- ZERO humans. No person, man, woman, girl, boy, child, face, hands, crowd, figure, body, skin, portrait.
- If the topic involves people (leaders, workers, citizens), show OBJECTS that represent them instead:
    → Empty chair at a conference table, a nameplate, a podium, a shadow on a wall
    → Tools/uniforms/equipment they use, but no wearer
    → Data charts, maps, flags, buildings that represent their role
- Fill the frame with: objects, architecture, maps, charts, symbols, nature, textures, materials, machines.
- Match visuals to topic category:
    Finance/Economy  → gold bars, coins, stock charts, candlestick graphs, banknotes, safe vaults, stock tickers
    Technology       → circuit boards, glowing screens, abstract data streams, server racks, code on monitors
    Politics/Society → government buildings, flags, maps, official documents, seals, empty conference rooms
    Environment      → landscapes, weather phenomena, satellite imagery, natural textures
    Health           → medical equipment, pills, DNA strands, microscope views, empty hospital rooms
    War/Conflict     → maps with markers, military hardware, smoke, destroyed infrastructure (no people)
    General          → symbolic objects, abstract compositions, cinematic environments
- Style: cinematic, dramatic lighting, high detail, photorealistic. Always specify lighting and camera angle.
- End every visual_prompt with: "No humans, no people, objects only."

Return ONLY this JSON object, no markdown, no extra text:
{
  "scene_number": <number>,
  "duration_seconds": 10,
  "visual_prompt": "Cinematic description in English. Objects/environment only. Specify lighting and camera angle. No humans, no people, objects only.",
  "narration_text": "Lời thoại tiếng Việt, 2-3 câu ngắn, tối đa 45 từ, đúng phong cách vai trò.",
  "subtitle_text": "5-7 từ tiếng Việt, cực kỳ ấn tượng"
}"""

ROLES_VIRAL = [
    "HOOK — shocking or curious opening that stops the scroll",
    "GIẢI THÍCH — background and context, why this matters",
    "HIGHLIGHT — the most surprising or emotional peak moment",
    "Ý KIẾN 1 — supporters' perspective, emotional and relatable",
    "Ý KIẾN 2 — critics' perspective, contrasting view, creates tension",
    "HỆ QUẢ — real-world impact and consequences",
    "CTA — provocative question or call to comment/share/follow",
]

OUTLINE_SYSTEM_VIRAL = "Bạn là chiến lược gia nội dung viral. Viết ý chính bằng tiếng Việt. Trả về đúng 7 dòng theo format HOOK/GIẢI THÍCH/HIGHLIGHT/Ý KIẾN 1/Ý KIẾN 2/HỆ QUẢ/CTA."

OUTLINE_PROMPT_VIRAL = """Chủ đề: {topic}
Bài viết: {summary}

Viết đúng 7 ý chính cho video viral ngắn. Mỗi dòng một ý, bằng tiếng Việt:
HOOK — [câu mở đầu gây sốc/tò mò cực mạnh, dừng ngón tay người xem]
GIẢI THÍCH — [giải thích bối cảnh rõ ràng, thú vị]
HIGHLIGHT — [khoảnh khắc gây sốc hoặc cảm xúc nhất của câu chuyện]
Ý KIẾN 1 — [quan điểm cảm xúc của người ủng hộ, gần gũi]
Ý KIẾN 2 — [quan điểm phản đối tạo kịch tính, tranh luận]
HỆ QUẢ — [tác động thực tế, gắn với cuộc sống người xem]
CTA — [câu hỏi khiêu khích hoặc kêu gọi hành động mạnh]

Trả về ĐÚNG 7 dòng, không có text thêm."""


# ── Shared ────────────────────────────────────────────────────────────────────

_CATEGORY_KEYWORDS = {
    "finance": ["tài chính", "kinh tế", "chứng khoán", "cổ phiếu", "ngân hàng", "lãi suất", "lạm phát", "gdp", "đầu tư", "bitcoin", "crypto", "tiền tệ", "forex", "vàng", "gold", "stock", "finance", "economy", "inflation", "investment", "market", "tài sản", "asset"],
    "technology": ["công nghệ", "ai", "trí tuệ nhân tạo", "phần mềm", "robot", "tự động", "blockchain", "dữ liệu", "chip", "bán dẫn", "internet", "smartphone", "tech", "software", "hardware", "digital", "cyber", "hack", "startup", "silicon"],
    "politics": ["chính trị", "chính phủ", "quốc hội", "bầu cử", "đảng", "tổng thống", "thủ tướng", "ngoại giao", "hiệp định", "luật", "pháp lý", "quy định", "chính sách", "politics", "government", "election", "law", "policy", "sanction", "treaty"],
    "war": ["chiến tranh", "xung đột", "quân sự", "vũ khí", "tấn công", "tên lửa", "drone", "nato", "iran", "ukraine", "russia", "israel", "hamas", "war", "conflict", "military", "missile", "bomb", "attack", "troops"],
    "environment": ["môi trường", "khí hậu", "biến đổi khí hậu", "thiên tai", "lũ lụt", "hạn hán", "năng lượng tái tạo", "solar", "wind", "carbon", "climate", "environment", "disaster", "earthquake", "typhoon"],
    "health": ["sức khỏe", "y tế", "bệnh viện", "vaccine", "dịch bệnh", "thuốc", "ung thư", "covid", "virus", "bác sĩ", "health", "medicine", "disease", "hospital", "cancer", "drug", "pandemic"],
}

_CATEGORY_VISUALS = {
    "finance": "Close-up of gold bullion bars stacked on a vault shelf, dramatic side lighting casting sharp shadows, shallow depth of field, cinematic color grade. No humans, no people, objects only.",
    "technology": "Abstract digital data streams flowing through glowing fiber optic cables, dark background with neon blue and cyan light trails, macro shot, cinematic. No humans, no people, objects only.",
    "politics": "Ornate government building exterior at golden hour, wide establishing shot, flags on poles, dramatic cloud backdrop, photorealistic. No humans, no people, objects only.",
    "war": "Military map spread on a table with location markers and tactical overlays, low dramatic lighting from above, top-down angle, cinematic. No humans, no people, objects only.",
    "environment": "Sweeping aerial view of a lush green landscape meeting industrial smog at the horizon, golden hour, dramatic sky with storm clouds, photorealistic. No humans, no people, objects only.",
    "health": "Modern medical laboratory with rows of test tubes and microscope equipment, cool blue-white lighting, shallow depth of field, clinical atmosphere. No humans, no people, objects only.",
    "general": "Dramatic abstract composition of symbolic objects on a dark cinematic background, moody directional lighting, photorealistic, high detail. No humans, no people, objects only.",
}


def _detect_category(topic: str) -> str:
    t = topic.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return category
    return "general"


def _fallback_visual(topic: str, point: str) -> str:
    category = _detect_category(topic)
    return _CATEGORY_VISUALS[category]


def _parse_scene(raw: str) -> dict:
    raw = raw.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]
    return json.loads(raw)


async def generate_script(
    article: dict,
    topic: str,
    on_progress=None,
    on_scene=None,
    style: str = "4wh",
    image_style: str = "",
) -> Script:
    from worker.ai_utils import call_ai

    from config import settings as _settings
    effective_style = (image_style or _settings.image_style).lower().replace(" ", "_")

    is_viral = style == "viral"
    target_scenes = 7 if is_viral else 6
    _base_prompt = SCENE_SYSTEM_PROMPT_VIRAL if is_viral else SCENE_SYSTEM_PROMPT_4WH
    # Inject style hint so AI tailors visual_prompt wording to the chosen aesthetic
    _style_hints = {
        "cinematic": "cinematic film, dramatic lighting, 35mm lens",
        "anime": "anime illustration, cel shading, vibrant 2D art",
        "watercolor": "watercolor painting, soft brushstrokes, pastel tones",
        "oil_painting": "oil painting, thick brushstrokes, classical art",
        "neon": "neon cyberpunk, glowing colors, dark background",
        "photorealistic": "ultra-photorealistic DSLR photo, 8K",
    }
    _hint = _style_hints.get(effective_style, "cinematic film")
    system_prompt = _base_prompt + f"\n\nACTIVE IMAGE STYLE: {effective_style} — all visual_prompt descriptions MUST match this aesthetic: {_hint}."
    roles = ROLES_VIRAL if is_viral else ROLES_4WH
    outline_system = OUTLINE_SYSTEM_VIRAL if is_viral else OUTLINE_SYSTEM_4WH
    outline_tpl = OUTLINE_PROMPT_VIRAL if is_viral else OUTLINE_PROMPT_4WH

    title = article.get("title", topic)
    summary = article.get("summary", "")
    key_points: list[str] = article.get("key_points") or []

    VALID_PREFIXES = ("WHAT", "WHERE", "WHEN", "WHO", "HOW", "SUMMARY", "HOOK", "GIẢI THÍCH", "HIGHLIGHT", "Ý KIẾN", "HỆ QUẢ", "CTA")
    valid_kp = [kp for kp in key_points if any(kp.upper().startswith(p.upper()) for p in VALID_PREFIXES)]

    if len(valid_kp) >= target_scenes:
        points = valid_kp[:target_scenes]
    else:
        if on_progress:
            await on_progress(f"Planning {'viral' if is_viral else '4WH'} outline for: {title[:40]}...", 5)

        outline_prompt = outline_tpl.format(topic=topic, summary=summary[:400])
        try:
            outline_raw = await call_ai(outline_prompt, outline_system, timeout=120.0)
            points = [p.lstrip("-•* ").strip() for p in outline_raw.strip().split("\n") if p.strip()][:target_scenes]
            while len(points) < target_scenes:
                points.append(roles[len(points)])
        except Exception as e:
            raise RuntimeError(f"AI outline call failed: {type(e).__name__}: {e or '(no message)'}") from e

        if on_progress:
            for p in points:
                await on_progress(f"📝 {p}", 10)

    scenes: list[Scene] = []
    context_lines: list[str] = []

    for i, point in enumerate(points):
        scene_num = i + 1
        role = roles[i] if i < len(roles) else point
        if on_progress:
            await on_progress(f"✍️ Scene {scene_num}/{target_scenes}: {point[:50]}...", 15 + int(i / target_scenes * 70))

        context_block = ""
        if context_lines:
            context_block = "Các scene trước (giữ nhất quán giọng điệu tiếng Việt, câu khẳng định, có số liệu/dẫn chứng):\n" + "\n".join(context_lines)

        prompt = f"""Chủ đề: {topic}
Bài viết: {title}
Tóm tắt: {summary[:300]}
{context_block}

Viết scene {scene_num}/{target_scenes}.
Vai trò: {role}
Nội dung cần truyền tải: "{point}"

scene_number phải là {scene_num}. Narration và subtitle PHẢI bằng tiếng Việt."""

        try:
            raw = await call_ai(prompt, system_prompt, timeout=300.0)
            data = _parse_scene(raw)
        except Exception as e:
            print(f"AI scene {scene_num} failed ({type(e).__name__}), using fallback")
            # Strip "ROLE — " prefix so the narration doesn't start with "WHAT —"
            narration_fallback = point.split(" — ", 1)[-1].strip() if " — " in point else point
            data = {
                "scene_number": scene_num,
                "duration_seconds": 10,
                "visual_prompt": _fallback_visual(topic, point),
                "narration_text": narration_fallback,
                "subtitle_text": " ".join(narration_fallback.split()[:7]),
            }

        vp = data.get("visual_prompt", "")
        no_people_suffix = "No humans, no people, objects only."
        if no_people_suffix.lower() not in vp.lower():
            vp = f"{vp.rstrip('. ')}. {no_people_suffix}"

        scene = Scene(
            scene_number=data.get("scene_number", scene_num),
            duration_seconds=data.get("duration_seconds", 10),
            visual_prompt=vp,
            narration_text=data.get("narration_text", point),
            subtitle_text=data.get("subtitle_text", " ".join(point.split()[:7])),
            image_style=effective_style,
        )
        scenes.append(scene)
        context_lines.append(f"  Scene {scene_num} [{role.split('—')[0].strip()}]: {scene.narration_text[:100]}")

        if on_scene:
            await on_scene(scene)
        if on_progress:
            await on_progress(f"✅ Scene {scene_num}/{target_scenes} done", 15 + int(scene_num / target_scenes * 70))

    script = Script(
        title=title,
        topic=topic,
        source_url=article.get("url"),
        source_summary=summary,
        scenes=scenes,
    )

    if on_progress:
        await on_progress(f"Script complete — {target_scenes} scenes ready", 100)

    return script
