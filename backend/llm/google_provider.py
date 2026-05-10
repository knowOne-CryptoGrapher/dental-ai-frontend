"""Google Gemini provider (Gemini 1.5 SDK)."""
from __future__ import annotations
import asyncio
import logging
from typing import AsyncIterator

import google.generativeai as genai

from .base import ChatMessage, LLMProvider, LLMResponse, ProviderConfig, StreamChunk

logger = logging.getLogger(__name__)


class GoogleProvider(LLMProvider):
    """
    Google Gemini provider using the new google-generativeai SDK.
    The SDK is sync-only, so we run sync calls in a worker thread
    to keep the API surface async-consistent with siblings.
    """
    name = "google"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        if config.api_key:
            genai.configure(api_key=config.api_key)

    @staticmethod
    def _to_history(messages: list[ChatMessage]) -> tuple[str | None, list[dict], str]:
        system_parts: list[str] = []
        history: list[dict] = []
        latest_user = ""

        normalized = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                role = "model" if m.role == "assistant" else "user"
                normalized.append({"role": role, "parts": [m.content]})

        if normalized and normalized[-1]["role"] == "user":
            latest_user = normalized[-1]["parts"][0]
            history = normalized[:-1]
        else:
            history = normalized

        system = "\n\n".join(system_parts) or None
        return system, history, latest_user

    def _model(self, model: str, system: str | None):
        return genai.GenerativeModel(
            model_name=model,
            system_instruction=system
        )

    async def complete(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> LLMResponse:
        system, history, prompt = self._to_history(messages)

        def _run():
            mdl = self._model(model, system)
            resp = mdl.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens or 1024,
                },
                safety_settings=None,
                # history is not directly supported in the same way as PaLM;
                # prepend manually if needed
            )
            return resp

        resp = await asyncio.to_thread(_run)

        usage = getattr(resp, "usage_metadata", None)

        return LLMResponse(
            content=resp.text or "",
            model=model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) if usage else 0,
            finish_reason="stop",
        )

    async def stream(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> AsyncIterator[StreamChunk]:
        system, history, prompt = self._to_history(messages)

        def _start():
            mdl = self._model(model, system)
            return mdl.generate_content(
                prompt,
                stream=True,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens or 1024,
                },
                safety_settings=None,
            )

        gen = await asyncio.to_thread(_start)

        loop = asyncio.get_running_loop()
        it = iter(gen)
        last_usage = None

        while True:
            try:
                chunk = await loop.run_in_executor(None, lambda: next(it, None))
            except Exception as e:
                logger.warning(f"Gemini stream error: {e}")
                break

            if chunk is None:
                break

            text = getattr(chunk, "text", "") or ""
            last_usage = getattr(chunk, "usage_metadata", last_usage)

            yield StreamChunk(delta=text)

        yield StreamChunk(
            delta="",
            finish_reason="stop",
            input_tokens=getattr(last_usage, "prompt_token_count", 0) if last_usage else 0,
            output_tokens=getattr(last_usage, "candidates_token_count", 0) if last_usage else 0,
        )
