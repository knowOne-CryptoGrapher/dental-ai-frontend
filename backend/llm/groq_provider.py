# backend/llm/groq_provider.py

import os
from groq import AsyncGroq
from llm.base import (
    LLMProvider,
    ProviderConfig,
    ChatMessage,
    LLMResponse,
    StreamChunk,
)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = AsyncGroq(api_key=config.api_key)
        self.default_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:

        groq_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=groq_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content,
            model=model or self.default_model,
            provider="groq",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            finish_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ):
        groq_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        stream = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=groq_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            finish = chunk.choices[0].finish_reason

            yield StreamChunk(
                delta=delta,
                finish_reason=finish,
                input_tokens=chunk.usage.prompt_tokens if chunk.usage else 0,
                output_tokens=chunk.usage.completion_tokens if chunk.usage else 0,
            )
