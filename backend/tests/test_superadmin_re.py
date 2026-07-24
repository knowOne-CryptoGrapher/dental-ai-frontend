"""
Phase 1.5 — Super-admin Retell access enforcement.

Verifies that:
  - Practice admins cannot read or write Retell config
  - Practice admins cannot fetch the rendered prompt
  - Super admins can list all practices and read/write any practice's Retell config
  - Provision / Re-sync return 501 with a clear message until RETELL_API_KEY is set
"""
import os
import time
import uuid
import httpx
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
API_URL = os.environ.get("TEST_API_URL", "https://dental-ai-backend-cszmxu7emq-uw.a.run.app").rstrip("/")

MONGO = MongoClient(os.environ["MONGO_URL"])
DB = MONGO[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def practice_admin():
    """Onboard a fresh practice and return its admin token."""
    email = f"adm-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    password = "Adm1n!"
    r = httpx.post(f"{API_URL}/api/onboarding/practice", json={
        "practice_name": "RBAC Test Clinic",
        "timezone": "America/Toronto",
        "admin_email": email, "admin_password": password,
        "admin_full_name": "RBAC Admin",
    }, timeout=10.0)
    assert r.status_code == 200
    data = r.json()
    yield {
        "email": email, "password": password,
        "practice_id": data["practice_id"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }
    DB.users.delete_many({"email": email})
    DB.practices.delete_many({"id": data["practice_id"]})
    DB.locations.delete_many({"practice_id": data["practice_id"]})


@pytest.fixture(scope="module")
def super_admin():
    """Use the seeded super_admin account."""
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": "owner@dentalai.com", "password": "OwnerPass123!"},
                   timeout=10.0)
    assert r.status_code == 200, r.text
    return {"headers": {"Authorization": f"Bearer {r.json()['access_token']}"}}


# ──────────────────────────────────────────────────────────────────────
# Practice admins are LOCKED OUT of Retell infrastructure
# ──────────────────────────────────────────────────────────────────────

def test_admin_cannot_read_prompt(practice_admin):
    r = httpx.get(f"{API_URL}/api/agent/{practice_admin['practice_id']}/prompt",
                  headers=practice_admin["headers"], timeout=5.0)
    assert r.status_code == 403, f"LEAK: admin got prompt (status={r.status_code})"


def test_admin_cannot_write_retell_config_via_general_endpoint(practice_admin):
    r = httpx.put(
        f"{API_URL}/api/practice/{practice_admin['practice_id']}/config",
        headers=practice_admin["headers"],
        json={"retell": {"agent_id": "hacked_agent", "phone_number": "+15550001111"}},
        timeout=5.0,
    )
    assert r.status_code == 403


def test_admin_cannot_list_all_practices(practice_admin):
    r = httpx.get(f"{API_URL}/api/superadmin/practices",
                  headers=practice_admin["headers"], timeout=5.0)
    assert r.status_code == 403


def test_admin_cannot_read_any_retell_config(practice_admin):
    r = httpx.get(
        f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell",
        headers=practice_admin["headers"], timeout=5.0,
    )
    assert r.status_code == 403


def test_admin_cannot_provision_or_resync(practice_admin):
    for path in ("provision", "resync"):
        r = httpx.post(
            f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell/{path}",
            headers=practice_admin["headers"], timeout=5.0,
        )
        assert r.status_code == 403, f"LEAK: admin called {path} (status={r.status_code})"


# ──────────────────────────────────────────────────────────────────────
# Practice admins CAN still update cosmetic branding/hours
# ──────────────────────────────────────────────────────────────────────

def test_admin_can_still_update_branding(practice_admin):
    r = httpx.put(
        f"{API_URL}/api/practice/{practice_admin['practice_id']}/branding",
        headers=practice_admin["headers"],
        json={"agent_name": "Sophie", "greeting": "Hi!", "closing": "Bye!", "voice_tone": "casual"},
        timeout=5.0,
    )
    assert r.status_code == 200


def test_admin_can_still_update_hours(practice_admin):
    r = httpx.put(
        f"{API_URL}/api/practice/{practice_admin['practice_id']}/hours",
        headers=practice_admin["headers"],
        json={
            "timezone": "America/Toronto",
            "weekly": {"mon": {"open": "09:00", "close": "18:00"},
                       "tue": None, "wed": None, "thu": None, "fri": None, "sat": None, "sun": None},
            "closed_dates": [],
        },
        timeout=5.0,
    )
    assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────────
# Super admin CAN do everything across every practice
# ──────────────────────────────────────────────────────────────────────

def test_super_admin_lists_practices(super_admin):
    r = httpx.get(f"{API_URL}/api/superadmin/practices",
                  headers=super_admin["headers"], timeout=10.0)
    assert r.status_code == 200
    d = r.json()
    assert "practices" in d
    assert d["count"] >= 1


def test_super_admin_reads_any_retell_config(super_admin, practice_admin):
    r = httpx.get(
        f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell",
        headers=super_admin["headers"], timeout=5.0,
    )
    assert r.status_code == 200
    d = r.json()
    assert "rendered_prompt" in d
    assert "function_urls" in d
    assert "webhook_url" in d
    assert "automation_available" in d


def test_super_admin_writes_retell_config(super_admin, practice_admin):
    r = httpx.put(
        f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell",
        headers=super_admin["headers"],
        json={"agent_id": "agent_test_xyz", "phone_number": "+15551112222"},
        timeout=5.0,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["agent_id"] == "agent_test_xyz"
    assert d["phone_number"] == "+15551112222"


def test_super_admin_can_read_prompt(super_admin, practice_admin):
    r = httpx.get(
        f"{API_URL}/api/agent/{practice_admin['practice_id']}/prompt",
        headers=super_admin["headers"], timeout=5.0,
    )
    assert r.status_code == 200
    assert "{{" not in r.json()["prompt"]


def test_provision_returns_501_until_api_key_set(super_admin, practice_admin):
    r = httpx.post(
        f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell/provision",
        headers=super_admin["headers"], timeout=5.0,
    )
    # 501 = Not Implemented — clear message that automation needs the key
    assert r.status_code == 501
    assert "RETELL_API_KEY" in r.json()["detail"] or "Phase 2" in r.json()["detail"]


def test_resync_returns_501_until_api_key_set(super_admin, practice_admin):
    r = httpx.post(
        f"{API_URL}/api/superadmin/practices/{practice_admin['practice_id']}/retell/resync",
        headers=super_admin["headers"], timeout=5.0,
    )
    assert r.status_code == 501
