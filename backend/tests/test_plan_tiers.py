"""
Plan tier tests.

Covers:
  • Plan registry (get_plan / list_plans / is_valid_plan_id)
  • Plan-aware LLM router (basic blocks escalation; pro/enterprise allow it)
  • Super-admin /plans + /practices/{id}/plan endpoints
  • /api/billing/features per-practice feature flags
  • Dashboard surfaces failed_payments + plan_distribution
"""
from __future__ import annotations
import os
import pytest
import httpx

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "owner@dentalai.com"
SUPER_PASSWORD = "OwnerPass123!"
ADMIN_EMAIL = "admin@dentaltest.com"
ADMIN_PASSWORD = "TestPass123!"


# ── Unit: plan registry ──────────────────────────────────────────────


def test_plan_registry_has_five_tiers():
    from plans import list_plans, PLANS
    ids = sorted(p.id for p in list_plans())
    assert ids == ["basic", "elite", "enterprise", "founding_clinic_basic", "professional"]
    assert PLANS["basic"].price_usd == 499.0
    assert PLANS["professional"].price_usd == 699.0
    assert PLANS["enterprise"].price_usd == 999.0
    assert PLANS["elite"].price_usd == 1499.0


def test_get_plan_falls_back_to_basic_on_unknown():
    """Defensive — old DBs may have legacy 'starter' or null plan_id."""
    from plans import get_plan
    assert get_plan("starter").id == "basic"
    assert get_plan(None).id == "basic"
    assert get_plan("").id == "basic"
    assert get_plan("definitely_not_a_plan").id == "basic"


def test_basic_plan_disables_escalation_features():
    from plans import get_plan
    basic = get_plan("basic")
    assert basic.llm.allow_escalation is False
    assert basic.features.analytics is False
    assert basic.features.insurance is False
    # audit_log is a deliberate exception, not an oversight — Basic gets
    # compliance logging regardless of tier, unrelated to LLM escalation
    # (which is what this test is actually about). It was False when this
    # test was first written; plans.py now explicitly sets it True for basic.
    assert basic.features.audit_log is True


def test_professional_plan_enables_escalation_and_features():
    from plans import get_plan
    pro = get_plan("professional")
    assert pro.llm.allow_escalation is True
    assert pro.features.analytics is True
    assert pro.features.insurance is True
    assert pro.features.audit_log is True
    assert pro.features.multi_location is True


def test_enterprise_unlocks_its_feature_set():
    from plans import get_plan
    ent = get_plan("enterprise")
    flags = ent.features.__dict__
    for f in ("analytics", "insurance", "audit_log", "multi_location",
              "custom_voice", "custom_routing_rules", "knowledge_base", "sip_telephony"):
        assert flags[f] is True, f"Enterprise should unlock {f}: {flags}"
    # These remain Elite-only — Enterprise must NOT have them
    for f in ("dedicated_support", "baa_available", "custom_model_selection"):
        assert flags[f] is False, f"Enterprise should NOT unlock {f} (Elite-only): {flags}"


def test_elite_unlocks_everything():
    from plans import get_plan
    elite = get_plan("elite")
    flags = elite.features.__dict__
    # insurance_preview is a founding_clinic_basic-only flag, not part of
    # Elite's (or any paid tier's) real feature set — excluded deliberately.
    checked = {k: v for k, v in flags.items() if k != "insurance_preview"}
    assert all(checked.values()), f"Elite should unlock everything except insurance_preview: {flags}"


def test_public_dict_never_leaks_stripe_price_id():
    from plans import list_plans
    for p in list_plans():
        d = p.public_dict()
        assert "stripe_price_id" not in d


# ── Unit: plan-aware LLM router ──────────────────────────────────────


def test_router_basic_plan_does_not_escalate_on_insurance():
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    from plans import get_plan
    r = LLMRouter()
    msgs = [ChatMessage(role="user", content="Does my insurance cover root canals?")]
    d = r.decide(msgs, plan=get_plan("basic"))
    assert d.escalated is False, "basic plan must not escalate"
    # The reason should mention plan disallowed
    assert "plan disallows" in d.reason.lower()
    # And it must use the plan's default model, not the global ESCALATION_MODEL
    basic = get_plan("basic")
    assert d.model == basic.llm.default_model


def test_router_professional_plan_escalates_on_insurance():
    from llm.router import LLMRouter
    from llm.base import ChatMessage
    from plans import get_plan
    r = LLMRouter()
    msgs = [ChatMessage(role="user", content="Does my insurance cover root canals?")]
    d = r.decide(msgs, plan=get_plan("professional"))
    assert d.escalated is True
    assert d.trigger == "insurance_question"


# ── HTTP integration ─────────────────────────────────────────────────


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


@pytest.fixture(scope="module")
def admin_practice_id(admin_token):
    r = httpx.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    return r.json()["practice_id"]


def test_superadmin_plans_endpoint(super_token):
    r = httpx.get(f"{API}/superadmin/plans", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    plans = r.json()
    assert len(plans) == 5
    for p in plans:
        assert "features" in p
        assert "stripe_price_id" not in p


def test_superadmin_plans_blocks_practice_admin(admin_token):
    r = httpx.get(f"{API}/superadmin/plans", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 403


def test_billing_features_returns_current_plan(admin_token, admin_practice_id, super_token):
    # First force the practice to professional
    httpx.post(
        f"{API}/superadmin/practices/{admin_practice_id}/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "professional", "reason": "test"},
    ).raise_for_status()
    r = httpx.get(f"{API}/billing/features", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["plan_id"] == "professional"
    assert body["features"]["analytics"] is True
    assert body["features"]["insurance"] is True


def test_set_plan_validates_plan_id(super_token, admin_practice_id):
    r = httpx.post(
        f"{API}/superadmin/practices/{admin_practice_id}/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "platinum"},
    )
    assert r.status_code == 400
    assert "Invalid plan" in r.json()["detail"]


def test_set_plan_404_for_unknown_practice(super_token):
    r = httpx.post(
        f"{API}/superadmin/practices/00000000-0000-0000-0000-000000000000/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "basic"},
    )
    assert r.status_code == 404


def test_set_plan_writes_audit_log(super_token, admin_practice_id):
    """Plan changes must be auditable for SOC 2."""
    httpx.post(
        f"{API}/superadmin/practices/{admin_practice_id}/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "enterprise", "reason": "audit test"},
    ).raise_for_status()
    # Audit log isn't directly query-able as super-admin via HTTP, so do a Mongo dip.
    import asyncio, os
    from motor.motor_asyncio import AsyncIOMotorClient
    async def _check():
        db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
            os.environ.get("DB_NAME", "dental_receptionist")]
        return await db.audit_logs.find_one(
            {"action": "practice_plan_changed", "practice_id": admin_practice_id},
            sort=[("timestamp", -1)],
        )
    log = asyncio.run(_check())
    assert log is not None
    assert log["details"]["new_plan"] == "enterprise"
    assert log["details"]["manual_override"] is True


def test_dashboard_includes_failed_payments_and_plan_distribution(super_token):
    r = httpx.get(f"{API}/superadmin/dashboard", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "failed_payments" in body
    assert isinstance(body["failed_payments"], list)
    assert "plan_distribution" in body
    assert isinstance(body["plan_distribution"], dict)
    assert "past_due" in body["practices"]
    assert "cancelled_subscriptions" in body["practices"]


def test_route_endpoint_respects_practice_plan(super_token, admin_practice_id):
    """When practice_id is sent and plan is basic, /route should NOT escalate
    even on a clear insurance question."""
    httpx.post(
        f"{API}/superadmin/practices/{admin_practice_id}/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "basic"},
    ).raise_for_status()
    r = httpx.post(f"{API}/llm/route", json={
        "messages": [{"role": "user", "content": "Does my Delta Dental cover crowns?"}],
        "practice_id": admin_practice_id,
    })
    assert r.status_code == 200
    decision = r.json()
    assert decision["escalated"] is False
    assert "plan disallows" in decision["reason"].lower()

    # Bump to professional → should escalate
    httpx.post(
        f"{API}/superadmin/practices/{admin_practice_id}/plan",
        headers={"Authorization": f"Bearer {super_token}"},
        json={"plan_id": "professional"},
    ).raise_for_status()
    r = httpx.post(f"{API}/llm/route", json={
        "messages": [{"role": "user", "content": "Does my Delta Dental cover crowns?"}],
        "practice_id": admin_practice_id,
    })
    assert r.json()["escalated"] is True
