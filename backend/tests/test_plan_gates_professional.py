"""
E2E plan gate test — Professional plan.

Verifies that a Professional-plan practice:
  - Can access Professional+ features (analytics, insurance)
  - Is blocked from Enterprise+ features (knowledge_base, routing_rules)
  - Is blocked from Elite features (baa)

Environment variables required:
  TEST_API_URL  — must be set explicitly; refuses to default to production
"""
import os
import uuid
from datetime import datetime, timezone

import httpx
import pymongo
import pytest

_mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL") or ""
_db_name = os.environ.get("DATABASE_NAME") or os.environ.get("DB_NAME") or "dental_ai"

_CLEANUP_COLLECTIONS = (
    "users", "providers", "patients", "appointments",
    "invite_tokens", "ai_safety_logs", "audit_logs",
)


def _cleanup_practice(practice_id: str) -> None:
    if not _mongo_uri:
        return
    mc = pymongo.MongoClient(_mongo_uri, serverSelectionTimeoutMS=5_000)
    db = mc[_db_name]
    for coll in _CLEANUP_COLLECTIONS:
        db[coll].delete_many({"practice_id": practice_id})
    db.practices.delete_one({"id": practice_id})
    mc.close()


_raw_api_url = os.environ.get("TEST_API_URL", "").strip()
if not _raw_api_url:
    pytest.skip(
        "TEST_API_URL not set — refusing to default to production API",
        allow_module_level=True,
    )
API_URL: str = _raw_api_url.rstrip("/")

TERMS_VERSION = "1.2"
PRIVACY_VERSION = "1.1"
PASSWORD = "TestAdmin2026!"


def _random_email(prefix: str = "professional-test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _assert_ok(r: httpx.Response, label: str) -> dict:
    assert r.status_code == 200, f"{label}: expected 200, got {r.status_code} — {r.text}"
    return r.json()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
def signup_result(client):
    """Step 1 — create admin user account (no practice yet)."""
    email = _random_email()
    r = client.post("/api/auth/signup", json={
        "email": email,
        "password": PASSWORD,
        "full_name": "Test Professional",
    })
    _assert_ok(r, "signup")
    data = r.json()
    assert "access_token" in data, f"signup: no access_token in {data}"
    assert data["user"]["practice_id"] is None, "signup: expected no practice_id yet"
    assert data["user"]["onboarding_completed"] is False
    return {"email": email, "token": data["access_token"], "user": data["user"]}


@pytest.fixture(scope="module")
def practice_result(client, signup_result):
    """Step 2 — create Professional practice, get new JWT with practice_id."""
    r = client.post(
        "/api/practices",
        json={
            "name": "Professional Test Clinic",
            "province": "BC",
            "timezone": "America/Vancouver",
            "plan": "professional",
            "accepted_terms_version": TERMS_VERSION,
            "accepted_privacy_version": PRIVACY_VERSION,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=_headers(signup_result["token"]),
    )
    _assert_ok(r, "create-practice")
    data = r.json()
    assert "access_token" in data, f"create-practice: no access_token in {data}"
    practice = data["practice"]
    assert practice["subscription_plan"] == "professional"
    assert practice["status"] == "onboarding"
    assert "id" in practice
    result = {
        "token": data["access_token"],
        "practice_id": practice["id"],
        "practice": practice,
    }
    yield result
    _cleanup_practice(result["practice_id"])


@pytest.fixture(scope="module")
def completed_result(client, practice_result):
    """Step 3 — complete onboarding."""
    practice_id = practice_result["practice_id"]
    r = client.post(
        f"/api/practices/{practice_id}/complete-onboarding",
        headers=_headers(practice_result["token"]),
    )
    _assert_ok(r, "complete-onboarding")
    data = r.json()
    assert data.get("success") is True, f"complete-onboarding: expected success=true, got {data}"
    return data


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestProfessionalPlanGates:

    def test_signup_returns_jwt(self, signup_result):
        assert signup_result["token"], "signup must return a non-empty JWT"
        assert signup_result["user"]["email"].startswith("professional-test-")

    def test_signup_no_practice_yet(self, signup_result):
        assert signup_result["user"]["practice_id"] is None

    def test_practice_created_with_professional_plan(self, practice_result):
        assert practice_result["practice"]["subscription_plan"] == "professional"

    def test_practice_id_in_new_token(self, client, practice_result):
        """New JWT from POST /api/practices must encode practice_id."""
        r = client.get("/api/auth/me", headers=_headers(practice_result["token"]))
        data = _assert_ok(r, "auth/me after create-practice")
        assert data["practice_id"] == practice_result["practice_id"]

    def test_onboarding_complete(self, completed_result):
        assert completed_result["success"] is True
        assert "onboarding_completed_at" in completed_result

    def test_auth_me_after_complete(self, client, practice_result, completed_result):
        r = client.get("/api/auth/me", headers=_headers(practice_result["token"]))
        data = _assert_ok(r, "auth/me after onboarding complete")
        assert data["practice_id"] == practice_result["practice_id"]
        assert data.get("role") == "admin"

    def test_professional_analytics_allowed(self, client, practice_result, completed_result):
        """GET /api/analytics/dashboard — Professional+ feature, must return 200."""
        r = client.get("/api/analytics/dashboard", headers=_headers(practice_result["token"]))
        assert r.status_code == 200, (
            f"Expected 200 for analytics on Professional plan, got {r.status_code} — "
            f"plan gate may be over-blocking. {r.text}"
        )

    def test_professional_insurance_allowed(self, client, practice_result, completed_result):
        """GET /api/insurance/claims — Professional+ feature, must return 200."""
        r = client.get("/api/insurance/claims", headers=_headers(practice_result["token"]))
        assert r.status_code == 200, (
            f"Expected 200 for insurance on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_knowledge_blocked(self, client, practice_result, completed_result):
        """GET /api/knowledge — gated on knowledge_base (Enterprise+), must be 403."""
        r = client.get("/api/knowledge", headers=_headers(practice_result["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for knowledge on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_routing_rules_blocked(self, client, practice_result, completed_result):
        """GET /api/routing-rules — gated on custom_routing_rules (Enterprise+), must be 403."""
        r = client.get("/api/routing-rules", headers=_headers(practice_result["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for routing-rules on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_baa_blocked(self, client, practice_result, completed_result):
        """GET /api/billing/baa — gated on baa_available (Elite only), must be 403."""
        r = client.get("/api/billing/baa", headers=_headers(practice_result["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for billing/baa on Professional plan, got {r.status_code}. {r.text}"
        )
