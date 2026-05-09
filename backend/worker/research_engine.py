"""
Research Engine — Uses Ollama + DuckDuckGo to research a topic
and return 5 relevant articles with summaries.
"""
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import settings


RESEARCH_SYSTEM_PROMPT = """You are a research assistant. Given a topic and a list of search results,
select the 5 most relevant and interesting articles. For each article, return a JSON array with this structure:

[
  {
    "title": "Article title",
    "url": "https://...",
    "summary": "2-3 sentence summary of what the article is about",
    "why_relevant": "Why this is interesting for the given topic"
  }
]

Return ONLY the JSON array. No markdown, no explanation."""


async def research_topic(topic: str, on_progress=None) -> list[dict]:
    """
    Research a topic using DuckDuckGo + Ollama to curate 5 relevant results.
    """
    if on_progress:
        await on_progress("Searching the web...", 10)

    # Step 1: Web search (Run sync DDGS in thread to avoid blocking)
    from ddgs import DDGS

    results = []
    def do_search():
        with DDGS() as ddgs:
            search_results = list(ddgs.text(topic, max_results=10))
            if not search_results:
                search_results = list(ddgs.news(topic, max_results=10))
            return search_results

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, do_search)
    except Exception as e:
        print(f"Search error: {e}")
        results = []

    if not results:
        return []

    if on_progress:
        await on_progress("Analyzing results with AI...", 30)

    # Step 2: Let Ollama curate and summarize
    results_text = "\n\n".join([
        f"Title: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')[:200]}"
        for r in results[:10]
    ])

    prompt = f"""Topic: {topic}

Search Results:
{results_text}

Please select and summarize the 5 most relevant articles."""

    from worker.ai_utils import call_ai
    raw_text = await call_ai(prompt, RESEARCH_SYSTEM_PROMPT)

    if on_progress:
        await on_progress("Curating research results...", 60)

    # Parse JSON response
    try:
        raw_text = raw_text.strip()
        if "```" in raw_text:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        articles = json.loads(raw_text.strip())
    except Exception:
        # Fallback: use raw search results directly
        articles = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "summary": r.get("body", "")[:200],
                "why_relevant": "Top search result"
            }
            for r in results[:5]
        ]

    if on_progress:
        await on_progress("Research complete", 100)

    return articles[:5]
