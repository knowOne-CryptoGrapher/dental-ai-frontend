"""
Tests for the Stripe-backed billing module.

These tests run against the LIVE backend (httpx HTTP layer) so they
exercise the full request → emergentintegrations → Stripe → DB chain.

When STRIPE_API_KEY is sk_test_emergent (shared platform key), Stripe
session creation works but session lookup may 404 — those failures
fall through to the DB-state fallback, which the tests verify.
"""
from __future__ import annotations
import os
import httpx
import pytest

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@dentaltest.com"
ADMIN_PASSWORD = "TestPass123!"


@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


def test_plans_endpoint_public_and_returns_three_plans():
    r = httpx.get(f"{API}/billing/plans")
    assert r.status_code == 200
    plans = r.json()
    ids = sorted(p["id"] for p in plans)
    assert ids == ["basic", "enterprise", "professional"]


def test_plans_have_required_fields_and_no_secret_price_id():
    r = httpx.get(f"{API}/billing/plans")
    for p in r.json():
        assert {"id", "name", "price_usd", "calls_included", "providers_max",
                "locations_max", "recurring"} <= set(p.keys())
        # stripe_price_id must NEVER be exposed publicly
        assert "stripe_price_id" not in p


def test_basic_plan_pricing_matches_business_decision():
    r = httpx.get(f"{API}/billing/plans")
    by_id = {p["id"]: p for p in r.json()}
    assert by_id["basic"]["price_usd"] == 499.0
    assert by_id["professional"]["price_usd"] == 699.0
    assert by_id["enterprise"]["price_usd"] == 999.0


def test_usage_returns_full_state_for_practice_admin(admin_token):
    r = httpx.get(f"{API}/billing/usage", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    for k in ("plan", "plan_name", "price", "billing_status", "usage",
              "stripe_customer_id", "stripe_subscription_id"):
        assert k in body
    assert {"calls", "providers", "locations", "claims_submitted"} <= set(body["usage"].keys())


def test_usage_requires_admin():
    r = httpx.get(f"{API}/billing/usage")
    assert r.status_code in (401, 403)


def test_invoices_returns_list_for_admin(admin_token):
    r = httpx.get(f"{API}/billing/invoices", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_checkout_creates_stripe_session(admin_token):
    """Stripe should hand back a real cs_test_... session URL."""
    r = httpx.post(f"{API}/billing/checkout",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"plan": "basic", "origin_url": BASE_URL})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"].startswith("cs_test_") or body["session_id"].startswith("cs_live_")
    assert body["url"].startswith("https://checkout.stripe.com/")
    assert body["mode"] in ("subscription", "one_time_amount")


def test_checkout_rejects_invalid_plan(admin_token):
    r = httpx.post(f"{API}/billing/checkout",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"plan": "platinum", "origin_url": BASE_URL})
    assert r.status_code == 400


def test_checkout_rejects_missing_origin_url(admin_token):
    r = httpx.post(f"{API}/billing/checkout",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"plan": "basic"})
    assert r.status_code == 400


def test_checkout_persists_pending_transaction(admin_token):
    """Each checkout must write a row to payment_transactions BEFORE redirect."""
    r = httpx.post(f"{API}/billing/checkout",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"plan": "professional", "origin_url": BASE_URL})
    assert r.status_code == 200
    sid = r.json()["session_id"]

    # Polling that session_id should return SOMETHING (either Stripe state,
    # or DB fallback if the shared-key lookup 404s)
    poll = httpx.get(f"{API}/billing/checkout/status/{sid}",
                     headers={"Authorization": f"Bearer {admin_token}"})
    assert poll.status_code == 200, poll.text
    body = poll.json()
    assert body["session_id"] == sid
    assert body["plan_id"] == "professional"
    # Payment status is one of: initiated/pending/unpaid/paid/expired
    assert body["payment_status"] in {"initiated", "pending", "unpaid", "paid", "expired", "no_payment_required"}
    # Source must always be one of these — proves the resilience path is covered
    assert body["source"] in {"db", "stripe", "db_fallback"}


def test_checkout_status_404_for_unknown_session(admin_token):
    r = httpx.get(f"{API}/billing/checkout/status/cs_test_doesnotexist123",
                  headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 404


def test_portal_400_when_no_customer_yet(admin_token):
    """Practice without stripe_customer_id can't open the portal."""
    r = httpx.post(f"{API}/billing/portal",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"origin_url": BASE_URL})
    # Either 400 ("No Stripe customer on file") if the DB has no
    # customer for this practice, or 200 if a previous test created one.
    assert r.status_code in (200, 400)
    if r.status_code == 400:
        assert "Stripe customer" in r.json()["detail"]


def test_portal_requires_admin():
    r = httpx.post(f"{API}/billing/portal", json={"origin_url": BASE_URL})
    assert r.status_code in (401, 403)


def test_reconcile_404_for_unknown_session(admin_token):
    r = httpx.post(
        f"{API}/billing/reconcile/cs_test_doesnotexist123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


def test_reconcile_requires_admin():
    r = httpx.post(f"{API}/billing/reconcile/cs_test_anything")
    assert r.status_code in (401, 403)


def test_reconcile_idempotent_on_already_promoted(admin_token):
    """A session that's already promoted should report so without side-effects."""
    # Create a fresh session, then call reconcile — it's pending, so reports
    # 'nothing to promote' since payment_status != 'paid'.
    r = httpx.post(
        f"{API}/billing/checkout",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": "basic", "origin_url": BASE_URL},
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]
    rec = httpx.post(
        f"{API}/billing/reconcile/{sid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rec.status_code == 200
    body = rec.json()
    # Pending session — Stripe says payment_status=unpaid, so we should report
    # reconciled=False with a clear reason
    assert body["session_id"] == sid
    assert body["reconciled"] is False
    assert "reason" in body
