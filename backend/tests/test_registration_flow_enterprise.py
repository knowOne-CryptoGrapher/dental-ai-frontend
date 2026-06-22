"""
E2E registration + onboarding flow test — Enterprise plan.

Uses the REAL onboarding API (not the deprecated wizard shims):
  1. POST /api/auth/signup          — create admin user (no practice yet)
  2. POST /api/practices            — create practice, select enterprise plan, get new JWT
  3. POST /api/practices/{id}/complete-onboarding — mark onboarding done
  4. GET  /api/auth/me              — confirm user has practice_id
  5. GET  /api/settings/voice       — enterprise gate: custom_voice
  6. GET  /api/knowledge            — enterprise gate: knowledge_base
  7. GET  /api/routing-rules        — enterprise gate: custom_routing_rules

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

TERMS_VERSION = "1.1"
PRIVACY_VERSION = "1.0"
PASSWORD = "TestAdmin2026!"


def _random_email(prefix: str = "enterprise-test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


# ── Helpers ───────────────────────────────────────────────────────────────────

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
        "full_name": "Test Enterprise",
    })
    _assert_ok(r, "signup")
    data = r.json()
    assert "access_token" in data, f"signup: no access_token in {data}"
    assert data["user"]["practice_id"] is None, "signup: expected no practice_id yet"
    assert data["user"]["onboarding_completed"] is False
    return {"email": email, "token": data["access_token"], "user": data["user"]}


@pytest.fixture(scope="module")
def practice_result(client, signup_result):
    """Step 2 — create Enterprise practice, get new JWT with practice_id."""
    r = client.post(
        "/api/practices",
        json={
            "name": "Enterprise Test Clinic",
            "province": "BC",
            "timezone": "America/Vancouver",
            "plan": "enterprise",
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
    assert practice["subscription_plan"] == "enterprise"
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
    """Step 3 — complete onboarding, returns success + timestamp."""
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

class TestEnterpriseRegistrationFlow:

    def test_signup_returns_jwt(self, signup_result):
        assert signup_result["token"], "signup must return a non-empty JWT"
        assert signup_result["user"]["email"].startswith("enterprise-test-")

    def test_signup_no_practice_yet(self, signup_result):
        assert signup_result["user"]["practice_id"] is None

    def test_practice_created_with_enterprise_plan(self, practice_result):
        assert practice_result["practice"]["subscription_plan"] == "enterprise"

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

    def test_enterprise_gate_voice(self, client, practice_result):
        """GET /api/settings/voice — gated on custom_voice (enterprise+)."""
        r = client.get("/api/settings/voice", headers=_headers(practice_result["token"]))
        assert r.status_code == 200, (
            f"Enterprise voice endpoint returned {r.status_code} — "
            f"plan gate may not be active or plan was not set correctly. {r.text}"
        )

    def test_enterprise_gate_knowledge(self, client, practice_result):
        """GET /api/knowledge — gated on knowledge_base (enterprise+)."""
        r = client.get("/api/knowledge", headers=_headers(practice_result["token"]))
        assert r.status_code == 200, (
            f"Enterprise knowledge endpoint returned {r.status_code}. {r.text}"
        )

    def test_enterprise_gate_routing_rules(self, client, practice_result):
        """GET /api/routing-rules — gated on custom_routing_rules (enterprise+)."""
        r = client.get("/api/routing-rules", headers=_headers(practice_result["token"]))
        assert r.status_code == 200, (
            f"Enterprise routing-rules endpoint returned {r.status_code}. {r.text}"
        )

    def test_no_plan_gate_failures(self, client, practice_result):
        """None of the enterprise endpoints should return 402."""
        endpoints = ["/api/settings/voice", "/api/knowledge", "/api/routing-rules"]
        h = _headers(practice_result["token"])
        for ep in endpoints:
            r = client.get(ep, headers=h)
            assert r.status_code != 402, (
                f"{ep} returned 402 Payment Required — enterprise plan gate is blocking. {r.text}"
            )

    def test_no_auth_failures(self, client, practice_result):
        """None of the enterprise endpoints should return 401 or 403."""
        endpoints = ["/api/settings/voice", "/api/knowledge", "/api/routing-rules"]
        h = _headers(practice_result["token"])
        for ep in endpoints:
            r = client.get(ep, headers=h)
            assert r.status_code not in (401, 403), (
                f"{ep} returned {r.status_code} — JWT or RBAC issue. {r.text}"
            )
