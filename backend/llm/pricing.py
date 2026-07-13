"""
LLM pricing table — used by the cost-savings ROI widget.

Prices are USD per **1 million tokens** (input, output). Numbers below are
Feb 2026 list prices and are easy to override per deployment via a JSON
file at LLM_PRICING_PATH.

Lookup is keyed by (provider, model). Unknown models fall back to a
neutral $0 entry — they don't poison the dashboard, they just don't
contribute to savings totals until the operator adds a price.
"""
from __future__ import annotations
import os
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float   # USD per 1M input tokens
    output_per_million: float  # USD per 1M output tokens

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * self.input_per_million
            + (output_tokens / 1_000_000) * self.output_per_million
        )


# Default list prices (USD per 1M tokens). Update via LLM_PRICING_PATH.
DEFAULT_PRICES: dict[tuple[str, str], ModelPrice] = {
    # OpenAI
    ("openai", "gpt-4o-mini"):       ModelPrice(0.15, 0.60),
    ("openai", "gpt-4o"):            ModelPrice(2.50, 10.00),
    ("openai", "gpt-4.1-mini"):      ModelPrice(0.40, 1.60),
    ("openai", "gpt-4.1"):           ModelPrice(2.00, 8.00),
    ("openai", "o4-mini"):           ModelPrice(1.10, 4.40),
    # Anthropic
    ("anthropic", "claude-3-5-sonnet-20241022"): ModelPrice(3.00, 15.00),
    ("anthropic", "claude-3-5-sonnet-20240620"): ModelPrice(3.00, 15.00),
    ("anthropic", "claude-3-5-haiku-20241022"):  ModelPrice(0.80, 4.00),
    ("anthropic", "claude-3-opus-20240229"):     ModelPrice(15.00, 75.00),
    ("anthropic", "claude-3-haiku-20240307"):    ModelPrice(0.25, 1.25),
    # Google
    ("google", "gemini-1.5-flash"):  ModelPrice(0.075, 0.30),
    ("google", "gemini-1.5-flash-8b"): ModelPrice(0.0375, 0.15),
    ("google", "gemini-1.5-pro"):    ModelPrice(1.25, 5.00),
    ("google", "gemini-2.0-flash"):  ModelPrice(0.10, 0.40),
    # Groq
    ("groq", "llama-3.3-70b-versatile"): ModelPrice(0.59, 0.79),
    # Anthropic (current generation)
    ("anthropic", "claude-haiku-4-5-20251001"): ModelPrice(0.80, 4.00),
    # Local / stub → free
    ("local", "*"):                  ModelPrice(0.0, 0.0),
    ("stub", "*"):                   ModelPrice(0.0, 0.0),
}


_loaded: dict[tuple[str, str], ModelPrice] | None = None


def _load_overrides() -> dict[tuple[str, str], ModelPrice]:
    """Optional override file — JSON list of {provider, model, input_per_million, output_per_million}."""
    path = os.environ.get("LLM_PRICING_PATH")
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            rows = json.load(f)
        return {
            (r["provider"], r["model"]): ModelPrice(float(r["input_per_million"]), float(r["output_per_million"]))
            for r in rows
        }
    except Exception as e:
        logger.warning(f"LLM pricing override load failed: {e}")
        return {}


def _table() -> dict[tuple[str, str], ModelPrice]:
    global _loaded
    if _loaded is None:
        _loaded = {**DEFAULT_PRICES, **_load_overrides()}
    return _loaded


def get_price(provider: str, model: str) -> ModelPrice:
    table = _table()
    p = table.get((provider, model))
    if p is not None:
        return p
    # Wildcard fallback: ("provider", "*") — used for stub/local.
    p = table.get((provider, "*"))
    if p is not None:
        # If wildcard says free (e.g., stub), but the model has a real
        # price registered under a different provider, prefer that real
        # price. This way the cost-savings dashboard shows meaningful
        # baseline numbers even while the operator is still on stub.
        if p.input_per_million == 0.0 and p.output_per_million == 0.0:
            real = next(
                (price for (prov, mdl), price in table.items()
                 if mdl == model and (price.input_per_million > 0 or price.output_per_million > 0)),
                None,
            )
            if real is not None:
                return real
        return p
    # Unknown — try matching by model name across any provider.
    real = next(
        (price for (prov, mdl), price in table.items()
         if mdl == model and (price.input_per_million > 0 or price.output_per_million > 0)),
        None,
    )
    if real is not None:
        return real
    return ModelPrice(0.0, 0.0)


def reset_for_tests() -> None:
    global _loaded
    _loaded = None
