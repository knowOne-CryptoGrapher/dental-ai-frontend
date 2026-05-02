"""
External LLM Routing Layer
==========================

Backend-owned, provider-agnostic LLM router. Retell calls our
`/api/llm/chat/completions` endpoint as its Custom LLM; we route each
turn to the cheapest acceptable model and only escalate when the
conversation calls for it.

Architecture (designed to be portable away from this codebase):
    routers/llm_router.py    →  HTTP layer (Retell Custom LLM contract)
    llm/router.py            →  Intent detection + model selection rules
    llm/registry.py          →  Provider lookup (("openai","gpt-4o-mini") → instance)
    llm/base.py              →  LLMProvider abstract base + ChatMessage dataclass
    llm/openai_provider.py   →  OpenAI (and OpenAI-compatible local models)
    llm/anthropic_provider.py
    llm/google_provider.py
    llm/cache.py             →  Per-call cache (TTL'd, keyed by call_id)
    llm/logging.py           →  MongoDB audit of every routing decision

API keys come from env (OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY).
No emergentintegrations dependency — fully portable.
"""
from .registry import get_provider, list_providers, ProviderRegistry
from .router import LLMRouter, RoutingDecision, RoutingRule
from .base import LLMProvider, ChatMessage, LLMResponse
from .cache import CallCache, get_call_cache

__all__ = [
    "get_provider", "list_providers", "ProviderRegistry",
    "LLMRouter", "RoutingDecision", "RoutingRule",
    "LLMProvider", "ChatMessage", "LLMResponse",
    "CallCache", "get_call_cache",
]
