import os
import json
import httpx
from typing import Optional

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.1-70b-versatile")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini")


async def call_text_primary_fallback(prompt: str, system_message: Optional[str] = None) -> str:
    """
    Calls Groq first, then OpenAI if Groq fails. Returns plain text.
    """
    try:
        return await call_groq_text(prompt, system_message)
    except Exception:
        return await call_openai_text(prompt, system_message)


async def call_groq_text(prompt: str, system_message: Optional[str] = None) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [{"role": "user", "content": prompt}]
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})

    payload = {
        "model": GROQ_TEXT_MODEL,
        "messages": messages,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def call_openai_text(prompt: str, system_message: Optional[str] = None) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [{"role": "user", "content": prompt}]
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})

    payload = {
        "model": OPENAI_TEXT_MODEL,
        "messages": messages,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
