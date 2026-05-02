"""
LLMProvider abstract base + shared types.

Every provider (OpenAI, Anthropic, Google, local OpenAI-compat) implements
this interface. The router only ever sees this interface — provider details
are encapsulated.
"""
from __future__ import annotations
import abc
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    role: Role
    content: str
    name: str | None = None


@dataclass
class LLMResponse:
    """Non-streaming response shape — useful for tests + logs."""
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"


@dataclass
class StreamChunk:
    """One chunk in a streaming response."""
    delta: str = ""
    finish_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderConfig:
    name: str  # 'openai' | 'anthropic' | 'google' | custom
    api_key: str | None = None
    base_url: str | None = None  # for OpenAI-compatible endpoints (Ollama, vLLM, etc.)
    timeout: float = 30.0
    extra: dict = field(default_factory=dict)


class LLMProvider(abc.ABC):
    """Provider abstraction. Subclasses translate the model-agnostic ChatMessage
    list into the provider's native request format and stream responses back."""

    name: str = "base"

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Single-shot non-streaming completion."""
        raise NotImplementedError

    @abc.abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """Streaming completion. Yields StreamChunk pieces in order."""
        raise NotImplementedError
        yield  # pragma: no cover  (makes it a generator)

    def is_configured(self) -> bool:
        """Returns True iff the provider has the credentials it needs to run."""
        return bool(self.config.api_key) or bool(self.config.base_url)
