import httpx
import json
from config import settings

async def call_ai(prompt: str, system_prompt: str, temperature: float = 0.7) -> str:
    """
    Centralized AI caller. Toggles between Local Ollama and Cloud OpenAI/compatible.
    """
    if settings.use_cloud_ai and settings.openai_api_key:
        # Cloud Mode (OpenAI / DeepSeek / etc)
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
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.openai_base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    else:
        # Local Mode (Ollama)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 1024,
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
