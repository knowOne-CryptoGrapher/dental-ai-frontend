"""
Tests for the External LLM Routing Layer.

Covers:
  • Routing rules (default + 4 escalation triggers)
  • Provider registry (stub always available; real providers gated by env)
  • Per-call cache (set/get/expire/end-call)
  • /api/llm/route endpoint (no auth)
  • /api/llm/providers endpoint
  • /api/llm/chat/completions (streaming, stub provider)
  • /api/llm/stats RBAC (super_admin only)
"""
from __future__ import annotations
import os
import time
import pytest
import httpx

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "owner@dentalai.com"
SUPER_PASSWORD = "OwnerPass123!"
ADMIN_EMAIL = "admin@dentaltest.com"
ADMIN_PASSWORD = "TestPass123!"


# ── Unit-level (no HTTP) ──────────────────────────────────────────────


def test_router_default_no_escalation():
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    r = LLMRouter()
    decision = r.decide([ChatMessage(role="user", content="hi can I book a cleaning?")])
    assert decision.escalated is False
    assert decision.trigger is None
    assert decision.model == r.default_model


@pytest.mark.parametrize("text,expected_trigger", [
    ("does my insurance cover this?", "insurance_question"),
    ("What's my deductible for this year?", "insurance_question"),
    ("how much is a root canal?", "treatment_plan"),
    ("I need a treatment plan", "treatment_plan"),
])
def test_router_keyword_triggers(text, expected_trigger):
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    r = LLMRouter()
    d = r.decide([ChatMessage(role="user", content=text)])
    assert d.escalated, f"{text!r} should escalate"
    assert d.trigger == expected_trigger


def test_router_uncertainty_regex():
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    r = LLMRouter()
    msgs = [
        ChatMessage(role="user", content="book me an appointment"),
        ChatMessage(role="assistant", content="I'm not sure I caught that"),
        ChatMessage(role="user", content="ok"),
    ]
    d = r.decide(msgs)
    assert d.escalated and d.trigger == "uncertainty"


def test_router_complex_scheduling_requires_min_turns():
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    r = LLMRouter()
    # Below threshold: 2 user turns, contains "earliest" — should NOT escalate
    msgs = [
        ChatMessage(role="user", content="hi"),
        ChatMessage(role="assistant", content="hello"),
        ChatMessage(role="user", content="what's the earliest available?"),
    ]
    d = r.decide(msgs)
    assert d.trigger != "complex_scheduling"
    # Above threshold: 4 user turns
    msgs = [
        ChatMessage(role="user", content="hi"),
        ChatMessage(role="assistant", content="hello"),
        ChatMessage(role="user", content="i need an appt"),
        ChatMessage(role="assistant", content="ok when"),
        ChatMessage(role="user", content="this week"),
        ChatMessage(role="assistant", content="any specific day"),
        ChatMessage(role="user", content="show me the earliest available time"),
    ]
    d = r.decide(msgs)
    assert d.escalated and d.trigger == "complex_scheduling"


def test_call_cache_set_get_expire():
    from llm.cache import CallCache
    c = CallCache(default_ttl_seconds=1)
    c.set("call_a", "patient", {"name": "Joe"})
    hit, val = c.get("call_a", "patient")
    assert hit is True and val == {"name": "Joe"}
    # Different call, same key → miss
    hit, val = c.get("call_b", "patient")
    assert hit is False
    # Expire
    time.sleep(1.1)
    hit, val = c.get("call_a", "patient")
    assert hit is False


def test_call_cache_get_or_set_executes_factory_once():
    from llm.cache import CallCache
    c = CallCache()
    n = {"calls": 0}

    def factory():
        n["calls"] += 1
        return "value"

    assert c.get_or_set("c", "k", factory) == "value"
    assert c.get_or_set("c", "k", factory) == "value"
    assert n["calls"] == 1


def test_call_cache_end_call_clears_bucket():
    from llm.cache import CallCache
    c = CallCache()
    c.set("xyz", "k1", 1); c.set("xyz", "k2", 2)
    c.end_call("xyz")
    assert c.get("xyz", "k1") == (False, None)


def test_pricing_known_models():
    from llm.pricing import get_price
    p = get_price("openai", "gpt-4o-mini")
    assert p.input_per_million == 0.15
    assert p.output_per_million == 0.60
    # 1M input + 1M output = $0.15 + $0.60 = $0.75
    assert round(p.cost(1_000_000, 1_000_000), 4) == 0.75


def test_pricing_stub_is_free():
    from llm.pricing import get_price
    # An unknown model on stub still costs $0 (no real price exists anywhere).
    p = get_price("stub", "totally-made-up-model-xyz")
    assert p.input_per_million == 0.0
    assert p.cost(1_000_000, 1_000_000) == 0.0


def test_pricing_stub_falls_back_to_market_price_for_known_model():
    """When stub serves a known model, cost should reflect the *real* market
    price. Otherwise the savings widget shows $0 forever in pre-launch."""
    from llm.pricing import get_price
    p = get_price("stub", "gpt-4o-mini")
    assert p.input_per_million == 0.15
    assert p.output_per_million == 0.60


def test_pricing_unknown_falls_back_to_zero():
    from llm.pricing import get_price
    p = get_price("openai", "nonexistent-future-model")
    assert p.input_per_million == 0.0


def test_stats_cost_block_present(super_token):
    r = httpx.get(f"{API}/llm/stats?days=7", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "cost" in body
    cost = body["cost"]
    for k in ("actual_usd", "if_all_escalated_usd", "savings_usd", "savings_pct",
              "baseline_provider", "baseline_model"):
        assert k in cost
    # Savings can never go negative — actual <= baseline by construction
    assert cost["savings_usd"] >= 0


def test_registry_always_includes_stub():
    from llm.registry import reset_registry_for_tests, list_providers
    reset_registry_for_tests()
    assert "stub" in list_providers()


# ── HTTP integration ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def super_token():
    r = httpx.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


def test_http_list_providers_public():
    r = httpx.get(f"{API}/llm/providers")
    assert r.status_code == 200
    assert "stub" in r.json()["providers"]


def test_http_route_endpoint_returns_decision():
    r = httpx.post(f"{API}/llm/route", json={
        "messages": [{"role": "user", "content": "what's my insurance deductible?"}]
    })
    assert r.status_code == 200
    body = r.json()
    assert body["escalated"] is True
    assert body["trigger"] == "insurance_question"


def test_http_chat_completions_streams_stub():
    with httpx.stream("POST", f"{API}/llm/chat/completions",
                     json={"messages": [{"role": "user", "content": "hello"}],
                           "stream": True, "call_id": "test_smoke"}) as r:
        assert r.status_code == 200
        # Headers expose routing decision
        assert r.headers.get("x-llm-provider") == "stub"
        assert r.headers.get("x-llm-escalated") == "0"
        chunks = [line for line in r.iter_lines() if line.startswith("data:")]
        assert any("[DONE]" in c for c in chunks)
        assert any("[stub:" in c for c in chunks)


def test_http_chat_completions_escalation_header():
    with httpx.stream("POST", f"{API}/llm/chat/completions",
                     json={"messages": [{"role": "user", "content": "does my insurance cover crowns?"}],
                           "stream": True, "call_id": "test_smoke_esc"}) as r:
        assert r.status_code == 200
        assert r.headers.get("x-llm-escalated") == "1"
        assert r.headers.get("x-llm-trigger") == "insurance_question"
        # drain
        for _ in r.iter_lines():
            pass


def test_http_stats_requires_super_admin(super_token, admin_token):
    r = httpx.get(f"{API}/llm/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 403
    r = httpx.get(f"{API}/llm/stats", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "totals" in body and "by_model" in body


def test_http_logs_requires_super_admin(super_token, admin_token):
    r = httpx.get(f"{API}/llm/logs?limit=5", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 403
    r = httpx.get(f"{API}/llm/logs?limit=5", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    assert "logs" in r.json()


def test_http_end_call_clears_cache():
    r = httpx.post(f"{API}/llm/calls/test_call_xyz/end")
    assert r.status_code == 200
    assert r.json()["call_id"] == "test_call_xyz"
