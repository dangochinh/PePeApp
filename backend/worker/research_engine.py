"""
Research Engine — Two modes:
  1. URL mode  : scrape the article directly → richer, story-specific key points
  2. Search mode: DuckDuckGo → top-3 articles (distinct domains) → scrape + fact extract → AI synthesis
"""
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import settings


# ---------------------------------------------------------------------------
# URL scraping
# ---------------------------------------------------------------------------

async def _scrape_url(url: str) -> str:
    """Fetch a URL and return clean article text (up to ~6000 chars)."""
    import httpx
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "lxml")

    # Remove noise tags
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "button", "noscript", "iframe",
                     "figure", "figcaption", "picture", "video", "audio",
                     "advertisement", "ads", "ad"]):
        tag.decompose()

    # Prefer article/main content selectors (common on Vietnamese news sites)
    selectors = [
        "article", '[class*="article-body"]', '[class*="article-content"]',
        '[class*="post-content"]', '[class*="entry-content"]',
        '[class*="content-detail"]', '[id*="article-body"]',
        "main", '[role="main"]',
    ]
    body_text = ""
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            body_text = el.get_text(separator=" ", strip=True)
            if len(body_text) > 400:
                break

    if not body_text or len(body_text) < 200:
        body_text = soup.get_text(separator=" ", strip=True)

    # Collapse whitespace and cap length
    import re
    body_text = re.sub(r"\s{2,}", " ", body_text).strip()
    return body_text[:7000]


RESEARCH_SYSTEM_URL = """Bạn là biên tập viên video chuyên sâu.
Nhiệm vụ: đọc bài báo và extract 6 key points cụ thể cho video ngắn kể câu chuyện.

YÊU CẦU KEY POINTS:
- Mỗi key point PHẢI chứa thông tin cụ thể từ bài: tên, số liệu, phương pháp, địa điểm
- TUYỆT ĐỐI KHÔNG viết chung chung kiểu "sự việc xảy ra" hay "vấn đề phức tạp"
- Trả lời rõ: AI/hacker/công ty CỤ THỂ nào? Phương pháp KỸ THUẬT là gì? Con số CHÍNH XÁC?
- Key points theo thứ tự narrative: HOOK → BỐI CẢNH → PHƯƠNG PHÁP → BẰNG CHỨNG → HẬU QUẢ → BÀI HỌC
- Viết bằng tiếng Việt, ngắn gọn, mỗi key point 1-2 câu súc tích

Trả về JSON không markdown:
{
  "title": "Tiêu đề ngắn gọn, ấn tượng",
  "url": "<url gốc>",
  "summary": "2-3 câu tóm tắt câu chuyện cốt lõi với đầy đủ chi tiết",
  "key_points": [
    "HOOK — <câu mở đầu shock/bí ẩn, bao gồm con số hoặc detail gây tò mò>",
    "BỐI CẢNH — <ai, ở đâu, bối cảnh cụ thể>",
    "PHƯƠNG PHÁP — <chính xác họ đã làm GÌ và NHƯ THẾ NÀO — kỹ thuật cụ thể>",
    "BẰNG CHỨNG — <số liệu, tên tổ chức, mốc thời gian cụ thể từ bài>",
    "HẬU QUẢ — <tác động thực tế, ai bị ảnh hưởng, phạm vi>",
    "BÀI HỌC — <nguyên nhân gốc rễ và bài học thực tế>"
  ]
}"""


async def research_from_url(url: str, on_progress=None) -> list[dict]:
    """Scrape a URL directly and extract story-specific key points via AI."""
    if on_progress:
        await on_progress(f"📰 Scraping article: {url[:60]}...", 10)

    try:
        article_text = await _scrape_url(url)
    except Exception as e:
        if on_progress:
            await on_progress(f"⚠️ Scrape failed ({e}), falling back to search...", 15)
        return []

    if on_progress:
        await on_progress(f"✅ Scraped {len(article_text):,} chars — analyzing...", 25)

    prompt = f"""URL: {url}

Nội dung bài báo:
{article_text}

Extract 6 key points storyteller cho video ngắn. Tập trung vào: ai làm gì, như thế nào, con số cụ thể."""

    from worker.ai_utils import call_ai_stream
    raw_text = ""

    async def on_token(accumulated: str):
        import time
        pass  # No need to stream for URL research

    if on_progress:
        await on_progress("🤖 AI đang phân tích bài báo...", 40)

    try:
        raw_text = await call_ai_stream(prompt, RESEARCH_SYSTEM_URL, on_chunk=on_token)
    except Exception as e:
        if on_progress:
            await on_progress(f"AI analysis failed: {e}", 50)
        return [{
            "title": url.split("/")[-1][:60],
            "url": url,
            "summary": article_text[:300],
            "key_points": [],
        }]

    try:
        raw_text = raw_text.strip()
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        article = json.loads(raw_text.strip())
        if isinstance(article, list):
            article = article[0]
        article["url"] = url  # Ensure original URL is preserved
    except Exception:
        article = {
            "title": url.split("/")[-1][:60],
            "url": url,
            "summary": article_text[:300],
            "key_points": [],
        }

    if on_progress:
        await on_progress("✅ Article analysis complete", 100)

    return [article]


RESEARCH_SYSTEM_PROMPT = """You are a research assistant for a short-video production studio.
Your job: given a topic and multi-source research material, produce exactly 6 scene briefs using the 4WH-1W framework.

FRAMEWORK (6 scenes in order):
  Scene 1 — WHAT   : What is happening / what is the core fact or event?
  Scene 2 — WHERE  : Where does this happen? Location, context, scope.
  Scene 3 — WHEN   : When / timeline — history, current moment, or forecast.
  Scene 4 — WHO    : Who is involved, affected, or driving this?
  Scene 5 — HOW    : How does it work, develop, or unfold? Mechanism or detail.
  Scene 6 — SUMMARY: Why it matters + one concrete takeaway or call-to-action for the viewer.

RULES:
- Embed SPECIFIC facts: real names, exact numbers, concrete dates from the sources.
- Stay strictly on the given topic. Do NOT drift to tangentially related subjects.
- Each key_point must be a single, self-contained fact or angle — vivid enough to fill a 10-second narrated video scene.
- Write key_points in the SAME LANGUAGE as the topic (Vietnamese topic → Vietnamese key_points).
- key_points must follow the WHAT / WHERE / WHEN / WHO / HOW / SUMMARY order exactly.
- Numbers and dates MUST appear in at least 4 of the 6 key_points (precision beats generality).

Return ONLY a JSON object, no markdown, no explanation:
{
  "title": "Concise title matching the topic",
  "url": "URL of the primary source",
  "summary": "2-3 sentence overview with specific numbers and names",
  "key_points": [
    "WHAT — ...",
    "WHERE — ...",
    "WHEN — ...",
    "WHO — ...",
    "HOW — ...",
    "SUMMARY — ..."
  ],
  "facts": [
    {"label": "short label", "value": "number or stat", "unit": "unit if any"}
  ]
}"""


# ---------------------------------------------------------------------------
# Fact extractor — pull numbers / entities from raw text for AI context
# ---------------------------------------------------------------------------

_FACT_RE = re.compile(
    r'(?:'
    r'\$[\d,\.]+(?:\s*(?:billion|million|trillion|tỷ|triệu|nghìn))?'
    r'|[\d,\.]+\s*(?:tỷ|triệu|nghìn|billion|million|trillion|%|USD|VND|đô|lần|x)'
    r'|(?:tháng\s+\d+|năm\s+\d{4}|\d{1,2}/\d{4})'
    r')',
    re.I
)


def _extract_facts_from_text(text: str) -> list[str]:
    """Pull raw number/stat strings from article text (up to 20 matches)."""
    matches = _FACT_RE.findall(text)
    seen: set[str] = set()
    unique = []
    for m in matches:
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            unique.append(m)
        if len(unique) >= 20:
            break
    return unique


def _pick_top_urls(results: list[dict], n: int = 3) -> list[str]:
    """Pick up to n results from distinct domains."""
    seen_domains: set[str] = set()
    urls = []
    for r in results:
        url = r.get("href", "")
        if not url.startswith("http"):
            continue
        try:
            domain = url.split("/")[2]
        except IndexError:
            continue
        if domain not in seen_domains:
            seen_domains.add(domain)
            urls.append(url)
        if len(urls) >= n:
            break
    return urls


async def research_topic(topic: str, on_progress=None) -> list[dict]:
    """
    Search the web, scrape top-3 distinct-domain articles, extract facts, synthesize with AI.
    Returns a list with 1 item (merged) for pipeline compatibility.
    """
    if on_progress:
        await on_progress("Searching the web...", 5)

    from ddgs import DDGS

    has_viet = any(ord(c) > 127 for c in topic)
    region = "vn-vi" if has_viet else "wt-wt"

    # Build 2-3 query variants for broader coverage
    queries = [topic]
    if has_viet:
        queries.append(f"{topic} số liệu thống kê")
    else:
        queries.append(f"{topic} statistics data")

    all_results: list[dict] = []

    def do_search(q: str) -> list[dict]:
        with DDGS() as ddgs:
            r = list(ddgs.text(q, max_results=15, region=region))
            if not r:
                r = list(ddgs.news(q, max_results=10, region=region))
            if len(r) < 5:
                r += list(ddgs.text(q, max_results=10, region="wt-wt"))
            return r

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [loop.run_in_executor(pool, do_search, q) for q in queries]
            batches = await asyncio.gather(*tasks, return_exceptions=True)
        seen_urls: set[str] = set()
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                url = item.get("href", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
    except Exception as e:
        print(f"Search error: {e}")
        all_results = []

    if not all_results:
        return []

    if on_progress:
        await on_progress(f"🔍 Found {len(all_results)} results across {len(queries)} queries", 15)
        for i, r in enumerate(all_results[:6]):
            title = r.get("title", "")[:55]
            url = r.get("href", "")
            domain = url.split("/")[2] if url.startswith("http") else url
            await on_progress(f"  [{i+1}] {title} — {domain}", 15)

    # Scrape top-3 distinct-domain articles in parallel
    top_urls = _pick_top_urls(all_results, n=3)
    if on_progress:
        await on_progress(f"📰 Scraping {len(top_urls)} articles...", 20)

    async def _scrape_safe(url: str) -> tuple[str, str]:
        """Returns (url, text_or_empty)."""
        try:
            text = await asyncio.wait_for(_scrape_url(url), timeout=15)
            return url, text
        except Exception as e:
            print(f"[research] scrape failed {url[:60]}: {e}")
            return url, ""

    scraped = await asyncio.gather(*[_scrape_safe(u) for u in top_urls])

    # Build rich context: scraped text + extracted facts + snippets
    source_blocks: list[str] = []
    primary_url = top_urls[0] if top_urls else ""

    for i, (url, text) in enumerate(scraped):
        if text:
            facts = _extract_facts_from_text(text)
            fact_line = ", ".join(facts[:12]) if facts else "—"
            source_blocks.append(
                f"=== SOURCE {i+1}: {url} ===\n"
                f"Key numbers found: {fact_line}\n\n"
                f"{text[:2500]}"
            )
            if on_progress:
                await on_progress(
                    f"  ✅ Scraped {len(text):,} chars, {len(facts)} numbers — {url.split('/')[2]}",
                    25 + i * 5,
                )
        else:
            # Fall back to search snippets for this domain
            domain_snippets = [
                r for r in all_results if url.split("/")[2] in r.get("href", "")
            ][:3]
            if domain_snippets:
                snippet_text = "\n".join(
                    f"- {r.get('title','')} | {r.get('body','')[:200]}"
                    for r in domain_snippets
                )
                source_blocks.append(f"=== SOURCE {i+1}: {url} (snippet only) ===\n{snippet_text}")

    # Also include top-10 search snippets as a quick reference layer
    snippets_text = "\n\n".join([
        f"[{i+1}] {r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')[:250]}"
        for i, r in enumerate(all_results[:10])
    ])
    source_blocks.append(f"=== SEARCH SNIPPETS (top-10) ===\n{snippets_text}")

    combined_sources = "\n\n".join(source_blocks)

    if on_progress:
        await on_progress("🤖 AI synthesizing 3 sources...", 40)

    prompt = f"""Topic: {topic}

{combined_sources}

Synthesize all sources above into 6 key points for a short video.
Embed REAL numbers, names, and dates you found — do not use placeholders.
If sources conflict, prefer the most specific / most-cited figure."""

    from worker.ai_utils import call_ai_stream
    _last_emit = [0.0]

    async def on_token(accumulated: str):
        import time
        now = time.monotonic()
        if on_progress and now - _last_emit[0] > 1.5:
            _last_emit[0] = now
            snippet = accumulated.replace("\n", " ").strip()[-100:]
            await on_progress(f"🤖 AI: ...{snippet}", 55)

    try:
        raw_text = await call_ai_stream(prompt, RESEARCH_SYSTEM_PROMPT, on_chunk=on_token)
    except Exception as e:
        print(f"AI analysis failed: {e}")
        if on_progress:
            await on_progress(f"AI unavailable ({type(e).__name__}), using raw data...", 60)
        best = all_results[0]
        return [{
            "title": best.get("title", ""),
            "url": best.get("href", ""),
            "summary": best.get("body", "")[:300],
            "key_points": [],
        }]

    if on_progress:
        await on_progress("Curating research results...", 70)

    try:
        raw_text = raw_text.strip()
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        parsed = json.loads(raw_text.strip())
        article = parsed[0] if isinstance(parsed, list) else parsed
        if not article.get("url"):
            article["url"] = primary_url
    except Exception:
        best = all_results[0]
        article = {
            "title": best.get("title", ""),
            "url": best.get("href", ""),
            "summary": best.get("body", "")[:300],
            "key_points": [],
        }

    if on_progress:
        await on_progress("✅ Research complete (3 sources synthesized)", 100)

    return [article]
