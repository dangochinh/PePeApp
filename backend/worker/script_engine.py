"""
Script Engine — Generates a screenplay one scene at a time.
Supports three styles:
  4wh         — 6 scenes: WHAT / WHERE / WHEN / WHO / HOW / SUMMARY
  viral       — 7 scenes: HOOK / GIẢI THÍCH / HIGHLIGHT / Ý KIẾN 1 / Ý KIẾN 2 / HỆ QUẢ / CTA
  storyteller — 6 scenes: HOOK / BỐI CẢNH / PHƯƠNG PHÁP / BẰNG CHỨNG / HẬU QUẢ / BÀI HỌC
                Best for URL-sourced articles — focuses on cause/effect and exact HOW.
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

# Extended role list for deeper 4WH videos (up to 12 scenes)
ROLES_4WH_EXTENDED = [
    "HOOK — shocking or surprising opener to stop the scroll",
    "WHAT 1 — the core fact or event, stated clearly",
    "WHAT 2 — additional context or nuance about the event",
    "WHERE — location, platform, or environment",
    "WHEN 1 — how it started / historical backdrop",
    "WHEN 2 — current moment, timeline of events",
    "WHO 1 — main actors or entities involved",
    "WHO 2 — who is impacted or affected",
    "HOW 1 — mechanism or process, first layer",
    "HOW 2 — deeper technical detail or second step",
    "IMPACT — real-world consequences and scale",
    "SUMMARY — key takeaway + call to action for viewers",
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

OUTLINE_SYSTEM_4WH_EXTENDED = "You are a Vietnamese video story architect. Write scene briefs in Vietnamese. Return exactly 12 lines following HOOK/WHAT 1/WHAT 2/WHERE/WHEN 1/WHEN 2/WHO 1/WHO 2/HOW 1/HOW 2/IMPACT/SUMMARY format."

OUTLINE_PROMPT_4WH_EXTENDED = """Chủ đề: {topic}
Bài viết: {summary}

Viết đúng 12 ý chính cho video ngắn theo khung 4WH-1W mở rộng. Mỗi dòng một ý, bắt đầu bằng vai trò:
HOOK — [câu mở đầu gây sốc/tò mò cực mạnh, dừng ngón tay người xem]
WHAT 1 — [sự thật cốt lõi, nêu rõ ràng và trực tiếp]
WHAT 2 — [bối cảnh thêm hoặc sắc thái của sự kiện]
WHERE — [địa điểm, nền tảng, môi trường cụ thể]
WHEN 1 — [khởi đầu như thế nào / bối cảnh lịch sử]
WHEN 2 — [thời điểm hiện tại, dòng thời gian]
WHO 1 — [nhân vật/tổ chức chính liên quan]
WHO 2 — [ai bị tác động/ảnh hưởng]
HOW 1 — [cơ chế hoặc quy trình, lớp đầu tiên]
HOW 2 — [chi tiết kỹ thuật sâu hơn hoặc bước thứ hai]
IMPACT — [hậu quả thực tế và quy mô cụ thể]
SUMMARY — [bài học chính + lời kêu gọi hành động]

Trả về ĐÚNG 12 dòng, không có text thêm."""


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


# ── Explanation / Comparison (7 scenes) ──────────────────────────────────────

SCENE_SYSTEM_PROMPT_EXPLANATION = """You are a professional Vietnamese short-form video scriptwriter specialising in comparison and explainer videos.
Generate exactly ONE video scene as a JSON object.

LANGUAGE RULES (CRITICAL):
- narration_text: ALWAYS in Vietnamese. Natural spoken style, not formal news. Specific numbers required.
- subtitle_text: ALWAYS in Vietnamese. 2-4 words max. For SO SÁNH scenes: THE COMPARISON CRITERION (e.g. "Giá bán", "Hiệu năng", "Dung lượng pin") — NOT "A vs B".
- visual_prompt: ALWAYS in English (for AI image generation).

COMPARISON SCENE RULES (for SO SÁNH roles — CRITICAL):
- subtitle_text = tên TIÊU CHÍ đang so sánh trong scene này (1-3 từ): "Giá bán" / "Camera" / "Pin" / "Hiệu năng" / "Thị phần"
  → Không dùng "A vs B" — dòng title đã có tên tiêu chí, không cần lặp tên entity
- narration_text MUST start with pairs of numbers in this exact format:
    "[Tên ngắn A]: [số liệu A] [đơn vị] | [Tên ngắn B]: [số liệu B] [đơn vị]"
  IMPORTANT: [Tên ngắn A/B] must be ≤15 characters (short brand/entity name, not a sentence!)
  Examples:
    "Galaxy S26: 1.099 USD | iPhone 16 Pro: 999 USD"
    "GDP Mỹ: 27,4 nghìn tỷ | GDP Trung Quốc: 17,8 nghìn tỷ USD"
    "Tỷ lệ A: 67% | Tỷ lệ B: 33%"
- visual_prompt: show two contrasting objects/symbols side by side representing each entity

NARRATION STYLE:
- 10 giây = tối đa 40-45 từ tiếng Việt. Đếm từ trước khi viết.
- Câu ngắn, sắc bén, đưa ra con số cụ thể ngay lập tức
- Dùng "bạn", "mình", "chúng ta" khi gần gũi hoá thông tin
- ƯU TIÊN: số liệu cụ thể, tên tổ chức, mốc thời gian, kết quả rõ ràng

VISUAL PROMPT RULES (ABSOLUTE):
- ZERO humans. Show symbolic objects for each compared entity.
  → Bitcoin vs Gold: a glowing Bitcoin symbol coin facing a gold bar
  → USA vs China: two country flag textures on contrasting surfaces
  → Two brands: product designs side by side, no people
- Style: cinematic, dramatic lighting, split composition, high detail.
- End with: "No humans, no people, objects only."

Return ONLY this JSON:
{
  "scene_number": <number>,
  "duration_seconds": 10,
  "visual_prompt": "Cinematic composition. Objects only. No humans, no people, objects only.",
  "narration_text": "Lời thoại tiếng Việt, 2-3 câu. SO SÁNH scenes: '[A]: [số] | [B]: [số]' ở đầu narration.",
  "subtitle_text": "5-7 từ tiếng Việt"
}"""

ROLES_EXPLANATION = [
    "HOOK — câu mở đầu gây shock về sự chênh lệch bất ngờ, nêu con số cụ thể ngay",
    "GIỚI THIỆU — đặt vấn đề: so sánh CÁI GÌ với CÁI GÌ, và tại sao người xem cần biết",
    "SO SÁNH 1 — tiêu chí quan trọng nhất: [A]: [số liệu] | [B]: [số liệu]",
    "SO SÁNH 2 — tiêu chí thứ hai: [A]: [số liệu] | [B]: [số liệu]",
    "DỮ LIỆU TỔNG HỢP — tổng hợp xu hướng, dự báo, bức tranh toàn cảnh với số liệu cụ thể",
    "PHÁN QUYẾT — kết luận rõ ràng: ai thắng, vì sao, bài học thực tế cho người xem",
]

ROLES_EXPLANATION_EXTENDED = [
    "HOOK — câu mở đầu gây shock về khoảng cách bất ngờ giữa hai đối tượng, có con số cụ thể",
    "GIỚI THIỆU — đặt vấn đề: so sánh CÁI GÌ với CÁI GÌ, lý do quan trọng với người xem",
    "ĐỐI TƯỢNG A — giới thiệu sâu đối tượng A: nguồn gốc, điểm mạnh, con số tiêu biểu",
    "ĐỐI TƯỢNG B — giới thiệu sâu đối tượng B: nguồn gốc, điểm mạnh, con số tiêu biểu",
    "SO SÁNH 1 — tiêu chí thứ nhất: [A]: [số] | [B]: [số] — ai dẫn đầu và tại sao",
    "SO SÁNH 2 — tiêu chí thứ hai: [A]: [số] | [B]: [số] — phân tích khoảng cách",
    "SO SÁNH 3 — tiêu chí thứ ba: [A]: [số] | [B]: [số] — yếu tố bất ngờ",
    "DỮ LIỆU TỔNG HỢP — toàn bộ số liệu tổng hợp, xu hướng dài hạn, dự báo",
    "ĐIỂM YẾU A — hạn chế, rủi ro, điểm yếu của đối tượng A với số liệu cụ thể",
    "ĐIỂM YẾU B — hạn chế, rủi ro, điểm yếu của đối tượng B với số liệu cụ thể",
    "NGỮ CẢNH — yếu tố bên ngoài tác động lên cả hai, bức tranh toàn ngành",
    "PHÁN QUYẾT — kết luận theo từng tiêu chí + bài học/cảnh báo cho người xem",
]

OUTLINE_SYSTEM_EXPLANATION = """Bạn là chuyên gia phân tích so sánh cho video ngắn. Viết outline bằng tiếng Việt.
Mỗi dòng SO SÁNH PHẢI chứa cặp số liệu cụ thể: "[A]: [số] | [B]: [số]".
Trả về đúng 6 dòng, không thêm gì."""

OUTLINE_PROMPT_EXPLANATION = """Chủ đề so sánh: {topic}
Thông tin: {summary}

Viết đúng 6 ý chính cho video so sánh/giải thích. Mỗi ý PHẢI cụ thể:
HOOK — [câu gây shock về khoảng cách giữa hai đối tượng — nêu con số ngay]
GIỚI THIỆU — [so sánh CÁI GÌ vs CÁI GÌ, lý do quan trọng]
SO SÁNH 1 — [tiêu chí 1: [A]: [số liệu] | [B]: [số liệu]]
SO SÁNH 2 — [tiêu chí 2: [A]: [số liệu] | [B]: [số liệu]]
DỮ LIỆU TỔNG HỢP — [xu hướng tổng thể với số liệu cụ thể]
PHÁN QUYẾT — [ai thắng, vì sao, bài học cụ thể]

Trả về ĐÚNG 6 dòng, không thêm gì."""

OUTLINE_SYSTEM_EXPLANATION_EXTENDED = """Bạn là chuyên gia phân tích so sánh cho video ngắn. Viết outline bằng tiếng Việt.
Mỗi dòng SO SÁNH PHẢI chứa cặp số liệu: "[A]: [số] | [B]: [số]".
Trả về đúng 12 dòng theo format HOOK/GIỚI THIỆU/ĐỐI TƯỢNG A/ĐỐI TƯỢNG B/SO SÁNH 1/SO SÁNH 2/SO SÁNH 3/DỮ LIỆU TỔNG HỢP/ĐIỂM YẾU A/ĐIỂM YẾU B/NGỮ CẢNH/PHÁN QUYẾT."""

OUTLINE_PROMPT_EXPLANATION_EXTENDED = """Chủ đề so sánh: {topic}
Thông tin: {summary}

Viết đúng 12 ý chính cho video so sánh mở rộng:
HOOK — [câu gây shock về khoảng cách bất ngờ, có con số ngay]
GIỚI THIỆU — [so sánh CÁI GÌ vs CÁI GÌ, lý do quan trọng]
ĐỐI TƯỢNG A — [mô tả sâu A: nguồn gốc, điểm mạnh, số tiêu biểu]
ĐỐI TƯỢNG B — [mô tả sâu B: nguồn gốc, điểm mạnh, số tiêu biểu]
SO SÁNH 1 — [[A]: [số] | [B]: [số] — ai dẫn đầu và tại sao]
SO SÁNH 2 — [[A]: [số] | [B]: [số] — phân tích khoảng cách]
SO SÁNH 3 — [[A]: [số] | [B]: [số] — yếu tố bất ngờ]
DỮ LIỆU TỔNG HỢP — [toàn bộ số liệu tổng hợp, xu hướng, dự báo]
ĐIỂM YẾU A — [hạn chế và rủi ro của A, số liệu cụ thể]
ĐIỂM YẾU B — [hạn chế và rủi ro của B, số liệu cụ thể]
NGỮ CẢNH — [yếu tố bên ngoài, bức tranh toàn ngành]
PHÁN QUYẾT — [kết luận từng tiêu chí + bài học/cảnh báo cho người xem]

Trả về ĐÚNG 12 dòng, không thêm gì."""


# ── Storyteller (URL-sourced article, 6 scenes) ──────────────────────────────

SCENE_SYSTEM_PROMPT_STORYTELLER = """Bạn là người kể chuyện tài năng chuyên làm video ngắn viral về tin tức.
Generate đúng MỘT video scene dưới dạng JSON object.

NGÔN NGỮ (BẮT BUỘC):
- narration_text: LUÔN bằng tiếng Việt. Kể chuyện như podcast, không phải đọc báo.
- subtitle_text: LUÔN tiếng Việt. Tối đa 7 từ. Câu hook ngắn gọn.
- visual_prompt: LUÔN tiếng Anh (cho AI image generation).

VAI TRÒ TỪNG SCENE — viết narration ĐỂ PHỤC VỤ VAI TRÒ:
  HOOK        → Câu mở đầu gây sốc/bí ẩn — nêu CÔN SỐ hoặc TÌNH HUỐNG cụ thể. CHƯA giải thích.
  BỐI CẢNH   → Kể rõ ai, ở đâu, ngữ cảnh câu chuyện — thiết lập nhân vật và địa điểm cụ thể.
  PHƯƠNG PHÁP → CHÍNH XÁC họ đã làm gì và NHƯ THẾ NÀO — kỹ thuật, công cụ, cơ chế thực sự.
  BẰNG CHỨNG → Dẫn số liệu cụ thể: tiền bạc, thời gian, phần trăm, tên tổ chức. Không chung chung.
  HẬU QUẢ   → Điều gì xảy ra tiếp theo? Ai bị ảnh hưởng? Quy mô thiệt hại/tác động thực tế?
  BÀI HỌC   → Lý do thực sự tại sao chuyện này xảy ra + bài học/cảnh báo cụ thể cho người xem.

PHONG CÁCH KỂ CHUYỆN:
- 10 giây = tối đa 40-45 từ tiếng Việt. Đếm từ.
- Câu ngắn, nhịp điệu podcast/documentary: "Đây là chuyện thật.", "Không ai ngờ được."
- Dùng ngôi thứ ba cho nhân vật chính, ngôi thứ hai "bạn" khi gắn với người xem
- PHẢI dùng chi tiết cụ thể từ câu chuyện — tên, số, phương pháp — không được trừu tượng
- KHÔNG viết: "vấn đề phức tạp", "nhiều yếu tố", "theo các chuyên gia" (chung chung)
- PHẢI viết: tên cụ thể, số tiền chính xác, kỹ thuật thực sự được dùng
- Nhịp điệu: câu 1 setup, câu 2 twist/detail, câu 3 hook sang scene sau (nếu không phải scene cuối)

VISUAL PROMPT RULES (TUYỆT ĐỐI — KHÔNG VI PHẠM):
- ZERO humans. No person, man, woman, girl, boy, face, hands, crowd, figure, body.
- Thay thế con người bằng vật dụng/công cụ/không gian đại diện:
    Hacker → dark terminal screen with green code, circuit boards, glowing keyboard
    AI/Tech → server racks, neural network visualization, data streams, glowing screens
    Money/Theft → scattered banknotes, digital vault, broken lock icon, crypto wallet UI
    Investigation → police evidence board, document files, magnifying glass over reports
- Style: cinematic, dramatic lighting, high detail. Specify lighting + camera angle.
- End with: "No humans, no people, objects only."

Trả về ĐÚNG JSON này, không markdown:
{
  "scene_number": <number>,
  "duration_seconds": 10,
  "visual_prompt": "Cinematic description. Objects only. No humans, no people, objects only.",
  "narration_text": "Kể chuyện tiếng Việt, 2-3 câu, tối đa 45 từ, cụ thể và sống động.",
  "subtitle_text": "Tối đa 7 từ tiếng Việt, câu hook"
}"""

ROLES_STORYTELLER = [
    "HOOK — shocking opener with a specific number or situation, do not explain yet",
    "BỐI CẢNH — set the scene: who, where, specific context and characters",
    "PHƯƠNG PHÁP — explain EXACTLY what they did and HOW — the real technique or mechanism",
    "BẰNG CHỨNG — hard evidence: exact numbers, org names, timestamps from the article",
    "HẬU QUẢ — real-world consequences: who got hurt, scale of impact, what happened next",
    "BÀI HỌC — root cause + concrete warning or takeaway for the viewer",
]

# Extended storyteller roles for deeper videos (up to 12 scenes)
ROLES_STORYTELLER_EXTENDED = [
    "HOOK — shocking opener with a specific number or situation — do not explain yet",
    "BỐI CẢNH 1 — who is the main actor/entity, their background",
    "BỐI CẢNH 2 — where and when it happened, set the stage",
    "PHƯƠNG PHÁP 1 — first step of how it happened — what tool/technique was introduced",
    "PHƯƠNG PHÁP 2 — the key technical maneuver — how the main action was executed",
    "PHƯƠNG PHÁP 3 — the moment it worked — what the system did in response",
    "BẰNG CHỨNG 1 — primary hard evidence: exact dollar amounts and token counts",
    "BẰNG CHỨNG 2 — timeline and secondary evidence: how fast, what trail was left",
    "HẬU QUẢ 1 — immediate consequences — what happened right after",
    "HẬU QUẢ 2 — broader impact: who else is affected, industry-wide implications",
    "NGUYÊN NHÂN — the root cause: what design flaw or oversight made this possible",
    "BÀI HỌC — concrete lesson + strong warning or call to action for viewers",
]

OUTLINE_SYSTEM_STORYTELLER = """Bạn là story architect cho video ngắn tin tức.
Viết outline bằng tiếng Việt. Trả về đúng 6 dòng theo format HOOK/BỐI CẢNH/PHƯƠNG PHÁP/BẰNG CHỨNG/HẬU QUẢ/BÀI HỌC.
Mỗi dòng PHẢI chứa chi tiết cụ thể (tên, số liệu, kỹ thuật) — không được viết chung chung."""

OUTLINE_PROMPT_STORYTELLER = """Chủ đề: {topic}
Nội dung bài báo: {summary}

Viết đúng 6 ý chính cho video kể chuyện. Mỗi ý PHẢI có chi tiết cụ thể:
HOOK — [câu mở đầu shock với CON SỐ hoặc TÌNH HUỐNG cụ thể — chưa giải thích]
BỐI CẢNH — [ai cụ thể, ở đâu, làm gì — tên/địa điểm thật]
PHƯƠNG PHÁP — [chính xác kỹ thuật/phương pháp đã dùng — chi tiết kỹ thuật thực sự]
BẰNG CHỨNG — [số tiền/số liệu chính xác, tên tổ chức, mốc thời gian từ bài]
HẬU QUẢ — [ai bị ảnh hưởng, thiệt hại cụ thể, điều gì xảy ra tiếp]
BÀI HỌC — [lý do thực sự + cảnh báo/bài học cụ thể cho người xem]

Trả về ĐÚNG 6 dòng, không thêm gì."""

OUTLINE_SYSTEM_STORYTELLER_EXTENDED = """Bạn là story architect cho video ngắn tin tức.
Viết outline bằng tiếng Việt. Trả về đúng 12 dòng theo format:
HOOK / BỐI CẢNH 1 / BỐI CẢNH 2 / PHƯƠNG PHÁP 1 / PHƯƠNG PHÁP 2 / PHƯƠNG PHÁP 3 / BẰNG CHỨNG 1 / BẰNG CHỨNG 2 / HẬU QUẢ 1 / HẬU QUẢ 2 / NGUYÊN NHÂN / BÀI HỌC.
Mỗi dòng PHẢI chứa chi tiết cụ thể (tên, số liệu, kỹ thuật) — không được viết chung chung."""

OUTLINE_PROMPT_STORYTELLER_EXTENDED = """Chủ đề: {topic}
Nội dung bài báo: {summary}

Viết đúng 12 ý chính cho video kể chuyện mở rộng. Mỗi ý PHẢI có chi tiết cụ thể:
HOOK — [câu mở đầu shock với CON SỐ hoặc TÌNH HUỐNG cụ thể — chưa giải thích]
BỐI CẢNH 1 — [nhân vật/tổ chức chính là ai, bối cảnh của họ]
BỐI CẢNH 2 — [ở đâu, khi nào — đặt bối cảnh câu chuyện cụ thể]
PHƯƠNG PHÁP 1 — [bước đầu tiên: công cụ/kỹ thuật nào được dùng]
PHƯƠNG PHÁP 2 — [động tác kỹ thuật chính — hành động chính được thực hiện như thế nào]
PHƯƠNG PHÁP 3 — [khoảnh khắc thành công — hệ thống đã phản ứng như thế nào]
BẰNG CHỨNG 1 — [bằng chứng cứng chính: số tiền và số lượng chính xác]
BẰNG CHỨNG 2 — [dòng thời gian và bằng chứng phụ: nhanh như thế nào, dấu vết để lại]
HẬU QUẢ 1 — [hậu quả ngay lập tức — điều gì xảy ra ngay sau đó]
HẬU QUẢ 2 — [tác động rộng hơn: ai khác bị ảnh hưởng, hàm ý toàn ngành]
NGUYÊN NHÂN — [nguyên nhân gốc rễ: lỗ hổng thiết kế hoặc sơ suất nào tạo điều kiện]
BÀI HỌC — [bài học cụ thể + cảnh báo/kêu gọi hành động mạnh mẽ cho người xem]

Trả về ĐÚNG 12 dòng, không thêm gì."""


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
    is_storyteller = style == "storyteller"
    is_explanation = style == "explanation"
    # Viral is always 7; others respect settings.scenes_per_video (default 6)
    target_scenes = 7 if is_viral else max(6, _settings.scenes_per_video)
    # Pick appropriate roles list (extended for >6 scenes)
    if is_storyteller:
        _base_prompt = SCENE_SYSTEM_PROMPT_STORYTELLER
    elif is_viral:
        _base_prompt = SCENE_SYSTEM_PROMPT_VIRAL
    elif is_explanation:
        _base_prompt = SCENE_SYSTEM_PROMPT_EXPLANATION
    else:
        _base_prompt = SCENE_SYSTEM_PROMPT_4WH
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
    extended = target_scenes > 6
    if is_storyteller:
        roles = ROLES_STORYTELLER_EXTENDED if extended else ROLES_STORYTELLER
        outline_system = OUTLINE_SYSTEM_STORYTELLER_EXTENDED if extended else OUTLINE_SYSTEM_STORYTELLER
        outline_tpl = OUTLINE_PROMPT_STORYTELLER_EXTENDED if extended else OUTLINE_PROMPT_STORYTELLER
    elif is_viral:
        roles = ROLES_VIRAL
        outline_system = OUTLINE_SYSTEM_VIRAL
        outline_tpl = OUTLINE_PROMPT_VIRAL
    elif is_explanation:
        roles = ROLES_EXPLANATION_EXTENDED if extended else ROLES_EXPLANATION
        outline_system = OUTLINE_SYSTEM_EXPLANATION_EXTENDED if extended else OUTLINE_SYSTEM_EXPLANATION
        outline_tpl = OUTLINE_PROMPT_EXPLANATION_EXTENDED if extended else OUTLINE_PROMPT_EXPLANATION
    else:
        roles = ROLES_4WH_EXTENDED if extended else ROLES_4WH
        outline_system = OUTLINE_SYSTEM_4WH_EXTENDED if extended else OUTLINE_SYSTEM_4WH
        outline_tpl = OUTLINE_PROMPT_4WH_EXTENDED if extended else OUTLINE_PROMPT_4WH

    title = article.get("title", topic)
    summary = article.get("summary", "")
    key_points: list[str] = article.get("key_points") or []

    VALID_PREFIXES = ("WHAT", "WHERE", "WHEN", "WHO", "HOW", "SUMMARY",
                      "HOOK", "GIẢI THÍCH", "HIGHLIGHT", "Ý KIẾN", "HỆ QUẢ", "CTA",
                      "BỐI CẢNH", "PHƯƠNG PHÁP", "BẰNG CHỨNG", "HẬU QUẢ", "BÀI HỌC",
                      "GIỚI THIỆU", "SO SÁNH", "DỮ LIỆU", "PHÁN QUYẾT",
                      "ĐỐI TƯỢNG", "ĐIỂM YẾU", "NGỮ CẢNH")
    valid_kp = [kp for kp in key_points if any(kp.upper().startswith(p.upper()) for p in VALID_PREFIXES)]

    # Storyteller/explanation use a longer summary excerpt for richer AI context
    summary_for_outline = summary[:1200] if (is_storyteller or is_explanation) else summary[:400]

    if len(valid_kp) >= target_scenes:
        points = valid_kp[:target_scenes]
    else:
        if on_progress:
            style_lbl = "storyteller" if is_storyteller else "viral" if is_viral else "explanation" if is_explanation else "4WH"
            await on_progress(f"Planning {style_lbl} outline for: {title[:40]}...", 5)

        outline_prompt = outline_tpl.format(topic=topic, summary=summary_for_outline)
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
            lbl = "Các scene trước (giữ nhất quán, cụ thể, có tên/số liệu):" if is_storyteller else "Các scene trước (giữ nhất quán giọng điệu tiếng Việt, câu khẳng định, có số liệu/dẫn chứng):"
            context_block = lbl + "\n" + "\n".join(context_lines)

        summary_for_scene = summary[:1200] if is_storyteller else summary[:300]
        context_label = "Các scene trước (giữ nhất quán, cụ thể, có tên/số liệu):" if is_storyteller else "Các scene trước (giữ nhất quán giọng điệu tiếng Việt, câu khẳng định, có số liệu/dẫn chứng):"

        prompt = f"""Chủ đề: {topic}
Bài viết: {title}
Nội dung bài báo: {summary_for_scene}
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
