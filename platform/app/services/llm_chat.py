import os
import httpx
from fastapi import HTTPException, status

# --- Configuration ---
# Moved configuration to the top for better readability and management.
OPENROUTER_API_KEY = "REDACTED"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-r1-0528:free"

async def send_llm_message(messages, model: str = DEFAULT_MODEL, temperature=0.7):
    """
    Sends messages to the OpenRouter LLM and returns the reply.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "BetSite"
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