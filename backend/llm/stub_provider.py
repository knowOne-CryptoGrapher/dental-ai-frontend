"""
Stub provider for tests + dev when no real API keys are configured.
Deterministic, fast, and free. Echoes back a canned response that
includes the provider/model identity so logs/tests are clear.
"""
from __future__ import annotations
import asyncio
from typing import AsyncIterator

from .base import ChatMessage, LLMProvider, LLMResponse, StreamChunk


class StubProvider(LLMProvider):
    name = "stub"

    def is_configured(self) -> bool:  # always true — no keys required
        return True

    @staticmethod
    def _make_reply(messages: list[ChatMessage], model: str) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[stub:{model}] echo: {last_user[:80]}"

    async def complete(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> LLMResponse:
        text = self._make_reply(messages, model)
        return LLMResponse(
            content=text,
            model=model,
            provider=self.name,
            input_tokens=sum(len(m.content) for m in messages) // 4,
            output_tokens=len(text) // 4,
            finish_reason="stop",
        )

    async def stream(self, messages, model, *, temperature=0.7, max_tokens=None, **kwargs) -> AsyncIterator[StreamChunk]:
        text = self._make_reply(messages, model)
        # Emit word-by-word so streaming wiring is exercised in tests.
        for word in text.split():
            yield StreamChunk(delta=word + " ")
            await asyncio.sleep(0)
        yield StreamChunk(
            delta="",
            finish_reason="stop",
            input_tokens=sum(len(m.content) for m in messages) // 4,
            output_tokens=len(text) // 4,
        )
