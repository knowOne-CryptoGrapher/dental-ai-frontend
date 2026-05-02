"""
Platform Console (Super-admin) — practice management & dashboard tests.

Covers new endpoints:
  POST   /api/superadmin/practices              (create practice + first admin)
  PATCH  /api/superadmin/practices/{id}         (update fields/status)
  POST   /api/superadmin/practices/{id}/suspend
  POST   /api/superadmin/practices/{id}/activate
  GET    /api/superadmin/dashboard              (platform metrics)

Also re-validates RBAC: practice admin token gets 403 on every superadmin
endpoint, and a suspended practice's admin cannot log in.
"""
import os
import time
import uuid
import httpx
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
API_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://tooth-reception.preview.emergentagent.com").rstrip("/")

MONGO = MongoClient(os.environ["MONGO_URL"])
DB = MONGO[os.environ["DB_NAME"]]


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def super_admin_headers():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": "owner@dentalai.com", "password": "OwnerPass123!"},
                   timeout=10.0)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def practice_admin_headers():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": "admin@dentaltest.com", "password": "TestPass123!"},
                   timeout=10.0)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def created_practice(super_admin_headers):
    """Create a fresh practice and tear it down after the module."""
    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    admin_email = f"restructure-{suffix}@test.com"
    payload = {
        "practice_name": f"TEST_Restructure {suffix}",
        "contact_email": f"contact-{suffix}@test.com",
        "contact_phone": "+15551112233",
        "timezone": "America/Toronto",
        "admin_email": admin_email,
        "admin_password": "TempAdm1n!Pass",
        "admin_full_name": "TEST Restructure Admin",
    }
    r = httpx.post(f"{API_URL}/api/superadmin/practices",
                   headers=super_admin_headers, json=payload, timeout=15.0)
    assert r.status_code == 201, r.text
    body = r.json()
    yield {"id": body["practice_id"], "admin_email": admin_email,
           "admin_password": payload["admin_password"], "name": payload["practice_name"]}
    # Cleanup
    DB.users.delete_many({"practice_id": body["practice_id"]})
    DB.practices.delete_many({"id": body["practice_id"]})
    DB.locations.delete_many({"practice_id": body["practice_id"]})


# ─── Dashboard ─────────────────────────────────────────────────────────

def test_dashboard_returns_full_shape(super_admin_headers):
    r = httpx.get(f"{API_URL}/api/superadmin/dashboard",
                  headers=super_admin_headers, timeout=10.0)
    assert r.status_code == 200, r.text
    d = r.json()
    # Status counts
    assert "practices" in d
    for k in ("total", "active", "onboarding", "suspended", "retell_provisioned"):
        assert k in d["practices"], f"missing practices.{k}"
        assert isinstance(d["practices"][k], int)
    assert d["practices"]["total"] >= 1
    # Platform metrics
    for k in ("total_patients", "total_appointments", "total_users", "calls_last_30_days"):
        assert k in d["platform"], f"missing platform.{k}"
        assert isinstance(d["platform"][k], int)
    # Recent practices list
    assert isinstance(d["recent_practices"], list)
    assert len(d["recent_practices"]) <= 5
    for p in d["recent_practices"]:
        assert {"id", "name", "status", "retell_provisioned"}.issubset(p.keys())
    assert isinstance(d["automation_available"], bool)


# ─── Create practice ───────────────────────────────────────────────────

def test_create_practice_persists_and_lists(super_admin_headers, created_practice):
    # GET /practices should now contain the created practice
    r = httpx.get(f"{API_URL}/api/superadmin/practices",
                  headers=super_admin_headers, timeout=10.0)
    assert r.status_code == 200
    practice_ids = [p["id"] for p in r.json()["practices"]]
    assert created_practice["id"] in practice_ids
    # And status is 'onboarding' as documented
    row = next(p for p in r.json()["practices"] if p["id"] == created_practice["id"])
    assert row["status"] == "onboarding"


def test_create_practice_duplicate_admin_email_returns_409(super_admin_headers, created_practice):
    # Try to create another practice using the SAME admin email.
    payload = {
        "practice_name": "TEST_Dup Practice",
        "contact_email": "dup-contact@test.com",
        "timezone": "America/Toronto",
        "admin_email": created_practice["admin_email"],
        "admin_password": "AnotherStrong!Pwd",
        "admin_full_name": "Dup Admin",
    }
    r = httpx.post(f"{API_URL}/api/superadmin/practices",
                   headers=super_admin_headers, json=payload, timeout=10.0)
    assert r.status_code == 409
    assert r.json().get("detail") == "Admin email already registered"


def test_new_admin_can_login(created_practice):
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": created_practice["admin_email"],
                         "password": created_practice["admin_password"]},
                   timeout=10.0)
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


# ─── Suspend / Activate ────────────────────────────────────────────────

def test_suspend_practice_disables_users_and_blocks_login(super_admin_headers, created_practice):
    pid = created_practice["id"]
    r = httpx.post(f"{API_URL}/api/superadmin/practices/{pid}/suspend",
                   headers=super_admin_headers, timeout=10.0)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "suspended"

    # DB-side: practice flagged suspended
    practice = DB.practices.find_one({"id": pid})
    assert practice["status"] == "suspended"
    # All users for this practice should be is_active=False
    user = DB.users.find_one({"email": created_practice["admin_email"]})
    assert user["is_active"] is False

    # Login should now be blocked (403 'Account disabled')
    login = httpx.post(f"{API_URL}/api/auth/login",
                       json={"email": created_practice["admin_email"],
                             "password": created_practice["admin_password"]},
                       timeout=10.0)
    assert login.status_code in (401, 403), f"suspended user logged in: {login.status_code}"


def test_activate_practice_reenables_users(super_admin_headers, created_practice):
    pid = created_practice["id"]
    r = httpx.post(f"{API_URL}/api/superadmin/practices/{pid}/activate",
                   headers=super_admin_headers, timeout=10.0)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    user = DB.users.find_one({"email": created_practice["admin_email"]})
    assert user["is_active"] is True

    login = httpx.post(f"{API_URL}/api/auth/login",
                       json={"email": created_practice["admin_email"],
                             "password": created_practice["admin_password"]},
                       timeout=10.0)
    assert login.status_code == 200


# ─── Patch endpoint sanity ─────────────────────────────────────────────

def test_patch_practice_updates_name(super_admin_headers, created_practice):
    pid = created_practice["id"]
    new_name = f"TEST_Renamed {uuid.uuid4().hex[:4]}"
    r = httpx.patch(f"{API_URL}/api/superadmin/practices/{pid}",
                    headers=super_admin_headers,
                    json={"name": new_name}, timeout=10.0)
    assert r.status_code == 200
    practice = DB.practices.find_one({"id": pid})
    assert practice["name"] == new_name


def test_patch_invalid_status_rejected(super_admin_headers, created_practice):
    r = httpx.patch(f"{API_URL}/api/superadmin/practices/{created_practice['id']}",
                    headers=super_admin_headers,
                    json={"status": "bogus"}, timeout=10.0)
    assert r.status_code == 400


def test_patch_unknown_practice_404(super_admin_headers):
    r = httpx.patch(f"{API_URL}/api/superadmin/practices/does-not-exist",
                    headers=super_admin_headers,
                    json={"name": "x"}, timeout=10.0)
    assert r.status_code == 404


# ─── RBAC: practice admin must be 403 on every super-admin endpoint ────

@pytest.mark.parametrize("method,path,body", [
    ("GET",   "/api/superadmin/dashboard", None),
    ("GET",   "/api/superadmin/practices", None),
    ("POST",  "/api/superadmin/practices",
     {"practice_name": "X", "contact_email": "x@x.com",
      "admin_email": "y@y.com", "admin_password": "Strong!123",
      "admin_full_name": "Y"}),
])
def test_practice_admin_forbidden_on_superadmin_routes(practice_admin_headers, method, path, body):
    r = httpx.request(method, f"{API_URL}{path}",
                      headers=practice_admin_headers, json=body, timeout=10.0)
    assert r.status_code == 403, f"{method} {path} returned {r.status_code}"


def test_practice_admin_forbidden_on_suspend_activate(practice_admin_headers, created_practice):
    pid = created_practice["id"]
    for action in ("suspend", "activate"):
        r = httpx.post(f"{API_URL}/api/superadmin/practices/{pid}/{action}",
                       headers=practice_admin_headers, timeout=10.0)
        assert r.status_code == 403, f"{action} returned {r.status_code}"


# ─── Unauth must be 401/403 ────────────────────────────────────────────

def test_unauth_dashboard_blocked():
    r = httpx.get(f"{API_URL}/api/superadmin/dashboard", timeout=5.0)
    assert r.status_code in (401, 403)
