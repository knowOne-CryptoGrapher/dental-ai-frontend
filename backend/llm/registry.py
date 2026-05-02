"""
Provider registry: maps provider names → singleton provider instances.

Reads env at module import time. Add a provider by:

    from .registry import register_provider
    from .my_provider import MyProvider
    register_provider("my-llm", MyProvider(ProviderConfig(name="my-llm", api_key=...)))
"""
from __future__ import annotations
import os
import logging

from .base import LLMProvider, ProviderConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .stub_provider import StubProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not registered. Available: {list(self._providers)}")
        return self._providers[name]

    def has(self, name: str) -> bool:
        return name in self._providers

    def all(self) -> dict[str, LLMProvider]:
        return dict(self._providers)


_registry: ProviderRegistry | None = None


def _build_default_registry() -> ProviderRegistry:
    reg = ProviderRegistry()

    # OpenAI (real or local OpenAI-compat via base_url)
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    openai_base = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    if openai_key or openai_base:
        reg.register("openai", OpenAIProvider(ProviderConfig(
            name="openai", api_key=openai_key, base_url=openai_base,
        )))
        logger.info(f"LLM: OpenAI provider registered (base_url={openai_base or 'default'})")

    # Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        reg.register("anthropic", AnthropicProvider(ProviderConfig(
            name="anthropic", api_key=anthropic_key,
        )))
        logger.info("LLM: Anthropic provider registered")

    # Google
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if google_key:
        reg.register("google", GoogleProvider(ProviderConfig(
            name="google", api_key=google_key,
        )))
        logger.info("LLM: Google provider registered")

    # Local OpenAI-compat (e.g., Ollama, vLLM, LM Studio).
    # Configured separately so it doesn't shadow the real OpenAI provider.
    local_base = os.environ.get("LOCAL_LLM_BASE_URL", "").strip()
    if local_base:
        reg.register("local", OpenAIProvider(ProviderConfig(
            name="local", api_key=os.environ.get("LOCAL_LLM_API_KEY", "ollama") or "ollama",
            base_url=local_base,
        )))
        logger.info(f"LLM: local OpenAI-compat provider registered at {local_base}")

    # Stub — always available so dev/tests work without keys
    reg.register("stub", StubProvider(ProviderConfig(name="stub")))

    if len(reg.all()) == 1:
        # Only stub registered → no real keys. Loud warning so it's obvious.
        logger.warning(
            "LLM: NO real provider keys configured. Only stub provider is active. "
            "Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY in backend/.env "
            "to enable real LLM routing."
        )
    return reg


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = _build_default_registry()
    return _registry


def get_provider(name: str) -> LLMProvider:
    return get_registry().get(name)


def list_providers() -> list[str]:
    return list(get_registry().all().keys())


def reset_registry_for_tests() -> None:
    """Force the registry to rebuild from current env (test hook only)."""
    global _registry
    _registry = None
