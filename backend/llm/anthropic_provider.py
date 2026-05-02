"""Anthropic provider (Claude)."""
from __future__ import annotations
import logging
from typing import AsyncIterator

from anthropic import AsyncAnthropic
from .base import ChatMessage, LLMProvider, LLMResponse, ProviderConfig, StreamChunk

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """
    Anthropic uses a different message shape than OpenAI: a top-level `system`
    string, then alternating user/assistant messages. This adapter coalesces
    consecutive system messages into the system field.
    """
    name = "anthropic"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = AsyncAnthropic(
            api_key=config.api_key or "missing-key",
            base_url=config.base_url,
            timeout=config.timeout,
        )

    @staticmethod
    def _split(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
        sys_parts = []
        rest: list[dict] = []
        for m in messages:
            if m.role == "system":
                sys_parts.append(m.content)
            elif m.role in ("user", "assistant"):
                rest.append({"role": m.role, "content": m.content})
            # tool messages are ignored — Retell handles tool calls separately.
        return "\n\n".join(sys_parts), rest

    async def complete(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> LLMResponse:
        system, msgs = self._split(messages)
        resp = await self._client.messages.create(
            model=model,
            system=system or None,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens or 1024,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "text", None))
        return LLMResponse(
            content=text,
            model=model,
            provider=self.name,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            finish_reason=resp.stop_reason or "stop",
        )

    async def stream(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> AsyncIterator[StreamChunk]:
        system, msgs = self._split(messages)
        async with self._client.messages.stream(
            model=model,
            system=system or None,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens or 1024,
        ) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(delta=text)
            final = await stream.get_final_message()
            yield StreamChunk(
                delta="",
                finish_reason=final.stop_reason or "stop",
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )
