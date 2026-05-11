"""
Research Engine — Uses DuckDuckGo to find the single most relevant article
for a topic, then extracts 6 key points to drive 6 video scenes.
"""
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import settings


RESEARCH_SYSTEM_PROMPT = """You are a research assistant for a short-video production studio.
Your job: given a topic and search results, produce exactly 6 scene briefs using the 4WH-1W framework.

FRAMEWORK (6 scenes in order):
  Scene 1 — WHAT   : What is happening / what is the core fact or event?
  Scene 2 — WHERE  : Where does this happen? Location, context, scope.
  Scene 3 — WHEN   : When / timeline — history, current moment, or forecast.
  Scene 4 — WHO    : Who is involved, affected, or driving this?
  Scene 5 — HOW    : How does it work, develop, or unfold? Mechanism or detail.
  Scene 6 — SUMMARY: Why it matters + one concrete takeaway or call-to-action for the viewer.

RULES:
- Stay strictly on the given topic. Do NOT drift to tangentially related subjects.
- If the search results are weak or off-topic, use them as a starting point but fill gaps with accurate general knowledge about the exact topic.
- Each key_point must be a single, self-contained fact or angle — vivid enough to fill a 10-second narrated video scene.
- Write key_points in the SAME LANGUAGE as the topic (Vietnamese topic → Vietnamese key_points).
- key_points must follow the WHAT / WHERE / WHEN / WHO / HOW / SUMMARY order exactly.

Return ONLY a JSON object, no markdown, no explanation:
{
  "title": "Concise title matching the topic",
  "url": "URL of the most relevant source, or empty string if none",
  "summary": "2-3 sentence overview of the topic in the topic's language",
  "key_points": [
    "WHAT — ...",
    "WHERE — ...",
    "WHEN — ...",
    "WHO — ...",
    "HOW — ...",
    "SUMMARY — ..."
  ]
}"""


async def research_topic(topic: str, on_progress=None) -> list[dict]:
    """
    Search the web, pick the single most relevant article, extract 6 key points.
    Returns a list with 1 item for pipeline compatibility.
    """
    if on_progress:
        await on_progress("Searching the web...", 10)

    from ddgs import DDGS

    results = []

    def do_search():
        with DDGS() as ddgs:
            # Use region hint based on language detection (simple heuristic)
            has_viet = any(ord(c) > 127 for c in topic)
            region = "vn-vi" if has_viet else "wt-wt"
            text_results = list(ddgs.text(topic, max_results=15, region=region))
            if not text_results:
                text_results = list(ddgs.news(topic, max_results=15, region=region))
            # Fallback: try worldwide if region search returned too few
            if len(text_results) < 5:
                text_results = list(ddgs.text(topic, max_results=15, region="wt-wt"))
            return text_results

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, do_search)
    except Exception as e:
        print(f"Search error: {e}")
        results = []

    if not results:
        return []

    # Show what was found after search
    if on_progress:
        await on_progress(f"🔍 Found {len(results)} results:", 20)
        for i, r in enumerate(results[:8]):
            title = r.get("title", "")[:60]
            url = r.get("href", "")
            domain = url.split("/")[2] if url.startswith("http") else url
            await on_progress(f"  [{i+1}] {title} — {domain}", 20)

    if on_progress:
        await on_progress("🤖 Analyzing results with AI...", 30)

    results_text = "\n\n".join([
        f"[{i+1}] Title: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')[:300]}"
        for i, r in enumerate(results[:15])
    ])

    prompt = f"""Topic: {topic}

Search Results:
{results_text}

Select the single most relevant article and extract 6 key points for a short video."""

    from worker.ai_utils import call_ai_stream
    raw_text = ""
    _last_emit = [0.0]

    async def on_token(accumulated: str):
        import time
        now = time.monotonic()
        # Throttle: emit at most every 1.5s to avoid flooding the WS
        if on_progress and now - _last_emit[0] > 1.5:
            _last_emit[0] = now
            # Show last 120 chars of AI output so user can see it thinking
            snippet = accumulated.replace("\n", " ").strip()[-120:]
            await on_progress(f"🤖 AI: ...{snippet}", 40)

    try:
        raw_text = await call_ai_stream(prompt, RESEARCH_SYSTEM_PROMPT, on_chunk=on_token)
    except Exception as e:
        print(f"AI analysis failed, using raw search results: {e}")
        if on_progress:
            await on_progress(f"AI unavailable ({type(e).__name__}), script engine will generate outline...", 60)
        best = results[0]
        return [{
            "title": best.get("title", ""),
            "url": best.get("href", ""),
            "summary": best.get("body", "")[:300],
            "key_points": [],  # Let script_engine call the outline AI instead of using raw titles
        }]

    if on_progress:
        await on_progress("Curating research results...", 60)

    # Parse JSON — expect a single object, not an array
    try:
        raw_text = raw_text.strip()
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        parsed = json.loads(raw_text.strip())
        # Normalise: handle both object and array responses
        if isinstance(parsed, list):
            article = parsed[0]
        else:
            article = parsed
    except Exception:
        # Fallback to top raw result
        best = results[0]
        article = {
            "title": best.get("title", ""),
            "url": best.get("href", ""),
            "summary": best.get("body", "")[:300],
            "key_points": [],  # Let script_engine call the outline AI instead of using raw titles
        }

    if on_progress:
        await on_progress("Research complete", 100)

    return [article]
