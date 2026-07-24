"""
Phase 1 tests: per-practice config endpoints, prompt renderer, onboarding,
and the new scoped Retell webhook.

Run:
    cd /app/backend && python -m pytest tests/test_phase1_multi_tenant.py -v
"""
import os
import time
import uuid
import httpx
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

from agent.prompt_renderer import render_amanda_prompt

load_dotenv("/app/backend/.env")

API_URL = os.environ.get("TEST_API_URL", "https://dental-ai-backend-cszmxu7emq-uw.a.run.app").rstrip("/")

MONGO = MongoClient(os.environ["MONGO_URL"])
DB = MONGO[os.environ["DB_NAME"]]


# ──────────────────────────────────────────────────────────────────────
# Prompt renderer — pure unit tests, no HTTP
# ──────────────────────────────────────────────────────────────────────

def _sample_practice():
    return {
        "id": "test-pid-123",
        "name": "Empire Dental",
        "settings": {
            "branding": {
                "agent_name": "Amanda",
                "greeting": "Thank you for calling Empire Dental!",
                "closing": "Have a great day!",
                "voice_tone": "warm_professional",
            },
            "hours": {
                "timezone": "America/Toronto",
                "weekly": {
                    "mon": {"open": "08:00", "close": "17:00"},
                    "tue": {"open": "08:00", "close": "17:00"},
                    "wed": {"open": "08:00", "close": "17:00"},
                    "thu": {"open": "08:00", "close": "19:00"},
                    "fri": {"open": "08:00", "close": "15:00"},
                    "sat": None,
                    "sun": None,
                },
                "closed_dates": ["2026-12-25"],
            },
            "emergency": {
                "triggers": ["severe pain", "bleeding"],
                "response_policy": "earliest_available",
                "after_hours_handoff_phone": None,
            },
            "appointment_types": [
                {"id": "cleaning", "name": "Cleaning", "duration_min": 60},
                {"id": "emergency", "name": "Emergency", "duration_min": 45},
            ],
        },
    }


def test_prompt_all_placeholders_replaced():
    prompt = render_amanda_prompt(
        _sample_practice(),
        [{"name": "Dr. John Smith", "role": "Dentist", "on_call": True}],
    )
    assert "{{" not in prompt
    assert "}}" not in prompt


def test_prompt_contains_practice_data():
    prompt = render_amanda_prompt(
        _sample_practice(),
        [{"name": "Dr. John Smith", "role": "Dentist"}],
    )
    assert "Empire Dental" in prompt
    assert "test-pid-123" in prompt
    assert "Dr. John Smith" in prompt
    assert "Monday: 08:00" in prompt
    assert "Sunday: Closed" in prompt
    assert "2026-12-25" in prompt  # closed date surfaces
    assert "Cleaning" in prompt


def test_prompt_empty_providers_graceful():
    prompt = render_amanda_prompt(_sample_practice(), [])
    assert "{{" not in prompt
    assert "No active providers" in prompt


def test_prompt_tone_variants():
    practice = _sample_practice()
    for tone in ("warm_professional", "casual", "formal"):
        practice["settings"]["branding"]["voice_tone"] = tone
        prompt = render_amanda_prompt(practice, [])
        assert "{{" not in prompt


# ──────────────────────────────────────────────────────────────────────
# HTTP helper — one-off admin
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def admin():
    """Create a fresh practice + admin via the onboarding API, tear down after."""
    email = f"phase1-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    password = "Phase1Pass!"
    r = httpx.post(f"{API_URL}/api/onboarding/practice", json={
        "practice_name": "Phase1 Test Clinic",
        "timezone": "America/Toronto",
        "admin_email": email,
        "admin_password": password,
        "admin_full_name": "Phase1 Admin",
    }, timeout=10.0)
    assert r.status_code == 200, f"onboarding failed: {r.status_code} {r.text}"
    data = r.json()
    ctx = {
        "practice_id": data["practice_id"],
        "token": data["access_token"],
        "email": email,
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "next_steps": data["next_steps"],
    }
    yield ctx
    # Teardown
    DB.users.delete_many({"email": email})
    DB.practices.delete_many({"id": ctx["practice_id"]})
    DB.locations.delete_many({"practice_id": ctx["practice_id"]})


# ──────────────────────────────────────────────────────────────────────
# Onboarding API
# ──────────────────────────────────────────────────────────────────────

def test_onboarding_creates_practice_with_defaults(admin):
    p = DB.practices.find_one({"id": admin["practice_id"]}, {"_id": 0})
    assert p["status"] == "onboarding"
    s = p["settings"]
    assert s["branding"]["agent_name"] == "Amanda"
    assert "Phase1 Test Clinic" in s["branding"]["greeting"]
    assert s["hours"]["timezone"] == "America/Toronto"
    assert len(s["appointment_types"]) >= 3
    assert s["emergency"]["triggers"]


def test_onboarding_returns_usable_jwt(admin):
    r = httpx.get(f"{API_URL}/api/auth/me", headers=admin["headers"], timeout=5.0)
    assert r.status_code == 200
    me = r.json()
    assert me["practice_id"] == admin["practice_id"]
    assert me["role"] == "admin"


def test_onboarding_next_steps_complete(admin):
    ns = admin["next_steps"]
    assert "rendered_prompt" in ns
    assert "{{" not in ns["rendered_prompt"]
    assert "Phase1 Test Clinic" in ns["rendered_prompt"]
    assert admin["practice_id"] in ns["rendered_prompt"]
    assert "function_urls" in ns
    for key in ("lookup_patient", "list_providers", "check_provider_availability",
                "book_appointments", "register_patient"):
        assert key in ns["function_urls"]
    assert ns["webhook_url"].endswith(f"/{admin['practice_id']}")


def test_onboarding_duplicate_email_rejected(admin):
    r = httpx.post(f"{API_URL}/api/onboarding/practice", json={
        "practice_name": "Dupe Clinic",
        "timezone": "America/Toronto",
        "admin_email": admin["email"],  # same email
        "admin_password": "whatever!",
        "admin_full_name": "Dupe Admin",
    }, timeout=10.0)
    assert r.status_code == 409


# ──────────────────────────────────────────────────────────────────────
# Practice config endpoints
# ──────────────────────────────────────────────────────────────────────

def test_config_get_round_trip(admin):
    r = httpx.get(f"{API_URL}/api/practice/{admin['practice_id']}/config",
                  headers=admin["headers"], timeout=5.0)
    assert r.status_code == 200
    d = r.json()
    assert d["practice_id"] == admin["practice_id"]
    assert "settings" in d
    assert "branding" in d["settings"]


def test_branding_update(admin):
    new = {
        "agent_name": "Sam",
        "greeting": "Welcome to Phase1 Clinic, this is Sam!",
        "closing": "Take care!",
        "voice_tone": "casual",
    }
    r = httpx.put(f"{API_URL}/api/practice/{admin['practice_id']}/branding",
                  headers=admin["headers"], json=new, timeout=5.0)
    assert r.status_code == 200
    # Re-fetch
    r2 = httpx.get(f"{API_URL}/api/practice/{admin['practice_id']}/branding",
                   headers=admin["headers"], timeout=5.0)
    assert r2.json()["agent_name"] == "Sam"
    assert r2.json()["voice_tone"] == "casual"


def test_hours_update(admin):
    new = {
        "timezone": "America/Vancouver",
        "weekly": {
            "mon": {"open": "09:00", "close": "16:00"},
            "tue": None,
            "wed": {"open": "09:00", "close": "16:00"},
            "thu": None,
            "fri": {"open": "09:00", "close": "14:00"},
            "sat": None,
            "sun": None,
        },
        "closed_dates": ["2027-07-01"],
    }
    r = httpx.put(f"{API_URL}/api/practice/{admin['practice_id']}/hours",
                  headers=admin["headers"], json=new, timeout=5.0)
    assert r.status_code == 200
    r2 = httpx.get(f"{API_URL}/api/practice/{admin['practice_id']}/hours",
                   headers=admin["headers"], timeout=5.0)
    d = r2.json()
    assert d["timezone"] == "America/Vancouver"
    assert d["weekly"]["tue"] is None
    assert "2027-07-01" in d["closed_dates"]


def test_appointment_type_add_and_delete(admin):
    new = {"id": "whitening", "name": "Teeth Whitening", "duration_min": 90}
    r = httpx.post(f"{API_URL}/api/practice/{admin['practice_id']}/appointment-types",
                   headers=admin["headers"], json=new, timeout=5.0)
    assert r.status_code == 200
    assert any(t["id"] == "whitening" for t in r.json())

    # Duplicate rejected
    r2 = httpx.post(f"{API_URL}/api/practice/{admin['practice_id']}/appointment-types",
                    headers=admin["headers"], json=new, timeout=5.0)
    assert r2.status_code == 409

    # Delete
    r3 = httpx.delete(f"{API_URL}/api/practice/{admin['practice_id']}/appointment-types/whitening",
                      headers=admin["headers"], timeout=5.0)
    assert r3.status_code == 200
    assert not any(t["id"] == "whitening" for t in r3.json())


def test_config_cross_tenant_blocked(admin):
    """Admin of Practice A cannot access Practice B's config."""
    # Create a second practice
    email2 = f"phase1b-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    r = httpx.post(f"{API_URL}/api/onboarding/practice", json={
        "practice_name": "Other Clinic",
        "timezone": "America/Toronto",
        "admin_email": email2,
        "admin_password": "Other1!",
        "admin_full_name": "Other Admin",
    }, timeout=10.0)
    other_pid = r.json()["practice_id"]

    try:
        # Admin A tries to read B's config
        r = httpx.get(f"{API_URL}/api/practice/{other_pid}/config",
                      headers=admin["headers"], timeout=5.0)
        assert r.status_code == 404, f"LEAK: A read B's config (status={r.status_code})"

        # Admin A tries to update B's branding
        r2 = httpx.put(f"{API_URL}/api/practice/{other_pid}/branding",
                       headers=admin["headers"],
                       json={"agent_name": "Hacked", "greeting": "g", "closing": "c", "voice_tone": "casual"},
                       timeout=5.0)
        assert r2.status_code == 404, f"LEAK: A mutated B's branding (status={r2.status_code})"
    finally:
        DB.users.delete_many({"email": email2})
        DB.practices.delete_many({"id": other_pid})
        DB.locations.delete_many({"practice_id": other_pid})


# ──────────────────────────────────────────────────────────────────────
# Agent prompt endpoint — now SUPER_ADMIN ONLY (Phase 1.5)
# ──────────────────────────────────────────────────────────────────────

def test_agent_prompt_endpoint_blocked_for_practice_admin(admin):
    """Practice admins are LOCKED OUT of /api/agent/{id}/prompt."""
    r = httpx.get(f"{API_URL}/api/agent/{admin['practice_id']}/prompt",
                  headers=admin["headers"], timeout=5.0)
    assert r.status_code == 403


def test_agent_prompt_endpoint_works_for_super_admin(admin):
    """Super admin can read any practice's prompt."""
    sa_login = httpx.post(f"{API_URL}/api/auth/login",
                          json={"email": "owner@dentalai.com", "password": "OwnerPass123!"},
                          timeout=10.0)
    sa_headers = {"Authorization": f"Bearer {sa_login.json()['access_token']}"}
    r = httpx.get(f"{API_URL}/api/agent/{admin['practice_id']}/prompt",
                  headers=sa_headers, timeout=5.0)
    assert r.status_code == 200
    d = r.json()
    assert d["practice_id"] == admin["practice_id"]
    assert "{{" not in d["prompt"]


def test_agent_prompt_unknown_practice_returns_404(admin):
    """Even super admin gets 404 for non-existent practice."""
    sa_login = httpx.post(f"{API_URL}/api/auth/login",
                          json={"email": "owner@dentalai.com", "password": "OwnerPass123!"},
                          timeout=10.0)
    sa_headers = {"Authorization": f"Bearer {sa_login.json()['access_token']}"}
    fake = str(uuid.uuid4())
    r = httpx.get(f"{API_URL}/api/agent/{fake}/prompt", headers=sa_headers, timeout=5.0)
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# Scoped Retell webhook
# ──────────────────────────────────────────────────────────────────────

def test_scoped_webhook_known_practice(admin):
    r = httpx.post(
        f"{API_URL}/api/webhooks/retell/{admin['practice_id']}",
        json={
            "event": "call_started",
            "call": {
                "call_id": f"test-scoped-{uuid.uuid4().hex[:8]}",
                "from_number": "+15551234567",
                "to_number": "+15559876543",
                "direction": "inbound",
                "start_timestamp": int(time.time() * 1000),
            },
        },
        timeout=5.0,
    )
    assert r.status_code == 204


def test_scoped_webhook_unknown_practice_404():
    fake = str(uuid.uuid4())
    r = httpx.post(
        f"{API_URL}/api/webhooks/retell/{fake}",
        json={"event": "call_started", "call": {"call_id": "x"}},
        timeout=5.0,
    )
    assert r.status_code == 404


def test_legacy_webhook_still_accepts_200_family():
    r = httpx.post(
        f"{API_URL}/api/webhooks/retell",
        json={"event": "call_started",
              "call": {"call_id": f"legacy-{uuid.uuid4().hex[:6]}"}},
        timeout=5.0,
    )
    assert r.status_code == 204
