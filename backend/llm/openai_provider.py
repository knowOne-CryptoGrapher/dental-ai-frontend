"""OpenAI provider (also handles OpenAI-compatible local models via base_url)."""
from __future__ import annotations
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI
from .base import ChatMessage, LLMProvider, LLMResponse, ProviderConfig, StreamChunk

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key or "missing-key",
            base_url=config.base_url,  # None → use api.openai.com
            timeout=config.timeout,
        )

    @staticmethod
    def _to_openai_msgs(messages: list[ChatMessage]) -> list[dict]:
        return [
            {k: v for k, v in (("role", m.role), ("content", m.content), ("name", m.name)) if v is not None}
            for m in messages
        ]

    async def complete(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=model,
            messages=self._to_openai_msgs(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )

    async def stream(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> AsyncIterator[StreamChunk]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=self._to_openai_msgs(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for ev in stream:
            if not ev.choices:
                # Final usage event (when stream_options.include_usage)
                if getattr(ev, "usage", None):
                    yield StreamChunk(
                        delta="",
                        finish_reason="stop",
                        input_tokens=ev.usage.prompt_tokens,
                        output_tokens=ev.usage.completion_tokens,
                    )
                continue
            choice = ev.choices[0]
            delta = (choice.delta.content or "") if choice.delta else ""
            yield StreamChunk(delta=delta, finish_reason=choice.finish_reason)
