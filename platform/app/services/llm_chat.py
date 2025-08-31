import os
import httpx
from fastapi import HTTPException, status

# --- Configuration ---
# Read sensitive data from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1:free")
HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://example.invalid")
X_TITLE = os.getenv("OPENROUTER_TITLE", "FIP")

async def send_llm_message(messages, model: str = DEFAULT_MODEL, temperature=0.7):
    """
    Sends messages to the OpenRouter LLM and returns the reply.
    """
    if not OPENROUTER_API_KEY:
        return "[OpenRouter API error] Missing OPENROUTER_API_KEY env var."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERER,
        "X-Title": X_TITLE,
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if "choices" in data and data["choices"] and "message" in data["choices"][0] and "content" in data["choices"][0]["message"]:
                return data["choices"][0]["message"]["content"]
            elif "error" in data:
                return f"[OpenRouter API error] {data['error'].get('message', 'Unknown error from OpenRouter API.')}"
            else:
                return "[OpenRouter API error] No valid response from OpenRouter API."
        except Exception as e:
            return f"[OpenRouter API error] {str(e)}"