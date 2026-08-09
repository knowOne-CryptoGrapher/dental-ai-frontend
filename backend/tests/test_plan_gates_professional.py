"""
E2E plan gate test — Professional plan.

Verifies:
  - Self-serve signup for a Professional-plan practice is blocked (400),
    per the SELF_SERVE_TIERS_ENABLED lockdown (self-serve is basic-only).
  - A Professional-plan practice, created directly via DB (bypassing the
    now-blocked self-serve path — same conftest.create_practice/create_user
    pattern used elsewhere in this suite), can access Professional+
    features (analytics, insurance) and is blocked from Enterprise+
    features (knowledge_base, routing_rules) and Elite features (baa).

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
    """Self-serve signup (user account only, no practice) — unaffected by
    the self-serve tier lockdown, still works normally for basic-eligible
    signups. Used here only to exercise the blocked-upgrade path below."""
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
def professional_env():
    """A real Professional-plan practice + admin, created directly via DB.
    The self-serve HTTP path for this tier is deliberately blocked (see
    test_self_serve_professional_signup_blocked below), so plan-gate
    coverage is exercised against a DB-seeded practice instead."""
    practice = create_practice("plan-gate-professional", plan="professional")
    admin = create_user(practice, "admin")
    yield {"practice": practice, "admin": admin}
    cleanup_practice(practice["practice_id"])


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestProfessionalPlanGates:

    def test_signup_returns_jwt(self, signup_result):
        assert signup_result["token"], "signup must return a non-empty JWT"
        assert signup_result["user"]["email"].startswith("professional-test-")

    def test_signup_no_practice_yet(self, signup_result):
        assert signup_result["user"]["practice_id"] is None

    def test_self_serve_professional_signup_blocked(self, client, signup_result):
        """POST /api/practices with plan=professional must be rejected —
        self-serve is currently limited to basic (SELF_SERVE_TIERS_ENABLED)."""
        r = client.post(
            "/api/practices",
            json={
                "name": "Should Not Be Created",
                "province": "BC",
                "timezone": "America/Vancouver",
                "plan": "professional",
                "accepted_terms_version": TERMS_VERSION,
                "accepted_privacy_version": PRIVACY_VERSION,
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            },
            headers=_headers(signup_result["token"]),
        )
        assert r.status_code == 400, (
            f"Expected 400 for self-serve professional signup, got {r.status_code}. {r.text}"
        )
        assert "Self-serve signup is currently limited to" in r.text

    def test_practice_created_with_professional_plan(self, professional_env):
        assert professional_env["practice"]["doc"]["subscription_plan"] == "professional"

    def test_admin_has_practice_context(self, client, professional_env):
        """DB-seeded admin's JWT/session correctly reflects the practice and role."""
        r = client.get("/api/auth/me", headers=_headers(professional_env["admin"]["token"]))
        data = _assert_ok(r, "auth/me")
        assert data["practice_id"] == professional_env["practice"]["practice_id"]
        assert data.get("role") == "admin"

    def test_professional_analytics_allowed(self, client, professional_env):
        """GET /api/analytics/dashboard — Professional+ feature, must return 200."""
        r = client.get("/api/analytics/dashboard", headers=_headers(professional_env["admin"]["token"]))
        assert r.status_code == 200, (
            f"Expected 200 for analytics on Professional plan, got {r.status_code} — "
            f"plan gate may be over-blocking. {r.text}"
        )

    def test_professional_insurance_allowed(self, client, professional_env):
        """GET /api/insurance/claims — Professional+ feature, must return 200."""
        r = client.get("/api/insurance/claims", headers=_headers(professional_env["admin"]["token"]))
        assert r.status_code == 200, (
            f"Expected 200 for insurance on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_knowledge_blocked(self, client, professional_env):
        """GET /api/knowledge — gated on knowledge_base (Enterprise+), must be 402."""
        r = client.get("/api/knowledge", headers=_headers(professional_env["admin"]["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for knowledge on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_routing_rules_blocked(self, client, professional_env):
        """GET /api/routing-rules — gated on custom_routing_rules (Enterprise+), must be 402."""
        r = client.get("/api/routing-rules", headers=_headers(professional_env["admin"]["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for routing-rules on Professional plan, got {r.status_code}. {r.text}"
        )

    def test_professional_gate_baa_blocked(self, client, professional_env):
        """GET /api/billing/baa — gated on baa_available (Elite only), must be 402."""
        r = client.get("/api/billing/baa", headers=_headers(professional_env["admin"]["token"]))
        assert r.status_code == 402, (
            f"Expected 402 for billing/baa on Professional plan, got {r.status_code}. {r.text}"
        )
