import httpx
import json
from config import settings


def _anthropic_key() -> str:
    return settings.anthropic_api_key or settings.cloud_ai_api_key


async def call_ai_stream(
    prompt: str,
    system_prompt: str,
    on_chunk=None,
    temperature: float = 0.7,
    timeout: float = 300.0,
) -> str:
    """
    Like call_ai but streams tokens. Calls on_chunk(accumulated_text) after each token.
    Returns full response when done.
    """
    full = ""
    _ak = _anthropic_key()

    if _ak:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=_ak)
        async with client.messages.stream(
            model=settings.claude_model,
            max_tokens=2048,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for token in stream.text_stream:
                full += token
                if on_chunk:
                    await on_chunk(full)
        return full

    if settings.use_cloud_ai and settings.openai_api_key:
        _base = settings.openai_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{_base}/chat/completions", headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        token = chunk["choices"][0]["delta"].get("content", "")
                        if token:
                            full += token
                            if on_chunk:
                                await on_chunk(full)
                    except Exception:
                        pass
    else:
        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": 512},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{settings.ollama_base_url}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            full += token
                            if on_chunk:
                                await on_chunk(full)
                        if chunk.get("done"):
                            break
                    except Exception:
                        pass

    return full


async def call_ai(prompt: str, system_prompt: str, temperature: float = 0.7, timeout: float = 300.0) -> str:
    """
    Centralized AI caller. Priority: Anthropic Claude → OpenAI-compatible → Ollama local.
    """
    _ak = _anthropic_key()
    if _ak:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=_ak)
        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    if settings.use_cloud_ai and settings.openai_api_key:
        _base = settings.openai_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{_base}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # Local Mode (Ollama)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 512,
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")
