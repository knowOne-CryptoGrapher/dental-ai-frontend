"""
E2E registration + onboarding flow test — Enterprise plan.

Verifies:
  - Self-serve signup for an Enterprise-plan practice is blocked (400),
    per the SELF_SERVE_TIERS_ENABLED lockdown (self-serve is basic-only).
  - An Enterprise-plan practice, created directly via DB (bypassing the
    now-blocked self-serve path — same conftest.create_practice/create_user
    pattern used elsewhere in this suite), can access enterprise-gated
    features: custom_voice, knowledge_base, custom_routing_rules.

Environment variables required:
  TEST_API_URL  — must be set explicitly; refuses to default to production
"""
import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from .conftest import create_practice, create_user, cleanup_practice

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
    """Self-serve signup (user account only, no practice) — unaffected by
    the self-serve tier lockdown. Used here only to exercise the blocked-
    upgrade path below."""
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
def enterprise_env():
    """A real Enterprise-plan practice + admin, created directly via DB.
    The self-serve HTTP path for this tier is deliberately blocked (see
    test_self_serve_enterprise_signup_blocked below), so plan-gate
    coverage is exercised against a DB-seeded practice instead."""
    practice = create_practice("plan-gate-enterprise", plan="enterprise")
    admin = create_user(practice, "admin")
    yield {"practice": practice, "admin": admin}
    cleanup_practice(practice["practice_id"])


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEnterpriseRegistrationFlow:

    def test_signup_returns_jwt(self, signup_result):
        assert signup_result["token"], "signup must return a non-empty JWT"
        assert signup_result["user"]["email"].startswith("enterprise-test-")

    def test_signup_no_practice_yet(self, signup_result):
        assert signup_result["user"]["practice_id"] is None

    def test_self_serve_enterprise_signup_blocked(self, client, signup_result):
        """POST /api/practices with plan=enterprise must be rejected —
        self-serve is currently limited to basic (SELF_SERVE_TIERS_ENABLED)."""
        r = client.post(
            "/api/practices",
            json={
                "name": "Should Not Be Created",
                "province": "BC",
                "timezone": "America/Vancouver",
                "plan": "enterprise",
                "accepted_terms_version": TERMS_VERSION,
                "accepted_privacy_version": PRIVACY_VERSION,
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            },
            headers=_headers(signup_result["token"]),
        )
        assert r.status_code == 400, (
            f"Expected 400 for self-serve enterprise signup, got {r.status_code}. {r.text}"
        )
        assert "Self-serve signup is currently limited to" in r.text

    def test_practice_created_with_enterprise_plan(self, enterprise_env):
        assert enterprise_env["practice"]["doc"]["subscription_plan"] == "enterprise"

    def test_admin_has_practice_context(self, client, enterprise_env):
        """DB-seeded admin's JWT/session correctly reflects the practice and role."""
        r = client.get("/api/auth/me", headers=_headers(enterprise_env["admin"]["token"]))
        data = _assert_ok(r, "auth/me")
        assert data["practice_id"] == enterprise_env["practice"]["practice_id"]
        assert data.get("role") == "admin"

    def test_enterprise_gate_voice(self, client, enterprise_env):
        """GET /api/settings/voice — gated on custom_voice (enterprise+)."""
        r = client.get("/api/settings/voice", headers=_headers(enterprise_env["admin"]["token"]))
        assert r.status_code == 200, (
            f"Enterprise voice endpoint returned {r.status_code} — "
            f"plan gate may not be active or plan was not set correctly. {r.text}"
        )

    def test_enterprise_gate_knowledge(self, client, enterprise_env):
        """GET /api/knowledge — gated on knowledge_base (enterprise+)."""
        r = client.get("/api/knowledge", headers=_headers(enterprise_env["admin"]["token"]))
        assert r.status_code == 200, (
            f"Enterprise knowledge endpoint returned {r.status_code}. {r.text}"
        )

    def test_enterprise_gate_routing_rules(self, client, enterprise_env):
        """GET /api/routing-rules — gated on custom_routing_rules (enterprise+)."""
        r = client.get("/api/routing-rules", headers=_headers(enterprise_env["admin"]["token"]))
        assert r.status_code == 200, (
            f"Enterprise routing-rules endpoint returned {r.status_code}. {r.text}"
        )

    def test_no_plan_gate_failures(self, client, enterprise_env):
        """None of the enterprise endpoints should return 402."""
        endpoints = ["/api/settings/voice", "/api/knowledge", "/api/routing-rules"]
        h = _headers(enterprise_env["admin"]["token"])
        for ep in endpoints:
            r = client.get(ep, headers=h)
            assert r.status_code != 402, (
                f"{ep} returned 402 Payment Required — enterprise plan gate is blocking. {r.text}"
            )

    def test_no_auth_failures(self, client, enterprise_env):
        """None of the enterprise endpoints should return 401 or 403."""
        endpoints = ["/api/settings/voice", "/api/knowledge", "/api/routing-rules"]
        h = _headers(enterprise_env["admin"]["token"])
        for ep in endpoints:
            r = client.get(ep, headers=h)
            assert r.status_code not in (401, 403), (
                f"{ep} returned {r.status_code} — JWT or RBAC issue. {r.text}"
            )
