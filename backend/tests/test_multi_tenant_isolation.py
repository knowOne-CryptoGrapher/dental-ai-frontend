"""
Multi-tenant isolation regression tests.

Spins up TWO practices with separate users, providers, patients, and
appointments, then exhaustively verifies that no endpoint leaks data
from Practice A into Practice B's session (or vice versa).

Run:
    cd /app/backend && python -m pytest tests/test_multi_tenant_isolation.py -v
"""
import os
import time
import uuid
import asyncio
import httpx
import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

API_URL = "https://tooth-reception.preview.emergentagent.com"

MONGO = MongoClient(os.environ["MONGO_URL"])
DB = MONGO[os.environ["DB_NAME"]]


# ──────────────────────────────────────────────────────────────────────
# Fixtures: build two independent practices
# ──────────────────────────────────────────────────────────────────────

def _create_practice_and_admin(slug: str) -> dict:
    """Create a practice + admin user directly in Mongo, then log in via API."""
    practice_id = str(uuid.uuid4())
    DB.practices.insert_one({
        "id": practice_id,
        "name": f"Test Clinic {slug}",
        "contact_email": f"admin-{slug}@example.com",
        "status": "active",
        "billing_status": "active",
        "subscription_plan": "starter",
        "default_timezone": "America/Toronto",
        "default_retention_years": 7,
        "created_at": time.time(),
    })

    # Use registration API so we get a properly hashed password + consistent schema
    email = f"iso-{slug}-{int(time.time())}@example.com"
    password = f"TestPass-{slug}-1!"
    reg = httpx.post(f"{API_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "full_name": f"Iso Admin {slug}",
        "practice_name": f"Test Clinic {slug} AUTO",  # will be ignored; we'll re-attach
    }, timeout=10.0)
    assert reg.status_code in (200, 201), f"reg failed: {reg.status_code} {reg.text}"

    # Re-attach user to our specific practice_id so both admins share the known pid
    DB.users.update_one({"email": email}, {"$set": {"practice_id": practice_id, "role": "admin"}})

    # Log in to get JWT
    login = httpx.post(f"{API_URL}/api/auth/login",
                       json={"email": email, "password": password}, timeout=10.0)
    assert login.status_code == 200, f"login failed: {login.text}"
    token = login.json()["access_token"]

    return {
        "practice_id": practice_id,
        "email": email,
        "password": password,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "slug": slug,
    }


@pytest.fixture(scope="module")
def two_practices():
    """Spin up two fully isolated practices, yield, then nuke them."""
    a = _create_practice_and_admin("alpha")
    b = _create_practice_and_admin("beta")

    # Seed a provider in each
    for p in (a, b):
        provider_id = str(uuid.uuid4())
        DB.providers.insert_one({
            "id": provider_id,
            "practice_id": p["practice_id"],
            "name": f"Dr. {p['slug'].title()}Provider",
            "role": "Dentist",
            "is_active": True, "active": True,
            "appointment_types": ["Cleaning"],
            "working_hours": {},
            "on_call": False,
        })
        p["provider_id"] = provider_id

    # Seed a patient in each (same phone number in both — classic leakage trap)
    shared_phone = f"+155501{int(time.time()) % 100000:05d}"
    for p in (a, b):
        patient_id = str(uuid.uuid4())
        DB.patients.insert_one({
            "id": patient_id,
            "practice_id": p["practice_id"],
            "name": f"{p['slug'].title()} Patient",
            "phone": shared_phone,   # INTENTIONAL collision
            "email": f"pt-{p['slug']}@iso.local",
            "consent_given": True,
            "created_at": time.time(),
        })
        p["patient_id"] = patient_id
    a["shared_phone"] = shared_phone
    b["shared_phone"] = shared_phone

    # Seed an appointment in each
    for p in (a, b):
        apt_id = str(uuid.uuid4())
        DB.appointments.insert_one({
            "id": apt_id,
            "practice_id": p["practice_id"],
            "patient_id": p["patient_id"],
            "patient_name": f"{p['slug'].title()} Patient",
            "provider_id": p["provider_id"],
            "provider_name": f"Dr. {p['slug'].title()}Provider",
            "appointment_date": "2027-01-15",
            "appointment_time": "10:00",
            "status": "scheduled",
            "reason": "Cleaning",
            "is_emergency": False,
            "created_at": time.time(),
        })
        p["appointment_id"] = apt_id

    yield a, b

    # Teardown
    for p in (a, b):
        DB.patients.delete_many({"practice_id": p["practice_id"]})
        DB.providers.delete_many({"practice_id": p["practice_id"]})
        DB.appointments.delete_many({"practice_id": p["practice_id"]})
        DB.call_logs.delete_many({"practice_id": p["practice_id"]})
        DB.users.delete_one({"email": p["email"]})
        DB.practices.delete_one({"id": p["practice_id"]})


# ──────────────────────────────────────────────────────────────────────
# Admin-API isolation tests (JWT-based)
# ──────────────────────────────────────────────────────────────────────

def test_patients_list_scoped_to_practice(two_practices):
    a, b = two_practices
    pa = httpx.get(f"{API_URL}/api/patients", headers=a["headers"], timeout=10.0).json()
    pb = httpx.get(f"{API_URL}/api/patients", headers=b["headers"], timeout=10.0).json()
    # Each admin sees only their own patient
    a_ids = {x["id"] for x in pa}
    b_ids = {x["id"] for x in pb}
    assert a["patient_id"] in a_ids
    assert b["patient_id"] not in a_ids, "LEAK: B's patient visible to A"
    assert b["patient_id"] in b_ids
    assert a["patient_id"] not in b_ids, "LEAK: A's patient visible to B"


def test_appointments_list_scoped_to_practice(two_practices):
    a, b = two_practices
    aa = httpx.get(f"{API_URL}/api/appointments", headers=a["headers"], timeout=10.0).json()
    bb = httpx.get(f"{API_URL}/api/appointments", headers=b["headers"], timeout=10.0).json()
    assert a["appointment_id"] in {x["id"] for x in aa}
    assert b["appointment_id"] not in {x["id"] for x in aa}, "LEAK: B's appointment visible to A"


def test_providers_list_scoped_to_practice(two_practices):
    a, b = two_practices
    pa = httpx.get(f"{API_URL}/api/providers", headers=a["headers"], timeout=10.0).json()
    pb = httpx.get(f"{API_URL}/api/providers", headers=b["headers"], timeout=10.0).json()
    assert a["provider_id"] in {x["id"] for x in pa}
    assert b["provider_id"] not in {x["id"] for x in pa}, "LEAK: B's provider visible to A"


def test_direct_patient_fetch_cross_tenant_blocked(two_practices):
    """A tries to GET B's patient by guessing the UUID."""
    a, b = two_practices
    r = httpx.get(f"{API_URL}/api/patients/{b['patient_id']}",
                  headers=a["headers"], timeout=10.0)
    assert r.status_code == 404, f"LEAK: A got B's patient (status={r.status_code})"


def test_direct_appointment_fetch_cross_tenant_blocked(two_practices):
    a, b = two_practices
    # GET by direct id (appointments have no direct GET single — test update instead)
    r = httpx.put(f"{API_URL}/api/appointments/{b['appointment_id']}",
                  headers=a["headers"], json={"status": "cancelled"}, timeout=10.0)
    assert r.status_code == 404, f"LEAK: A mutated B's appointment (status={r.status_code})"

    # Verify B's appointment is still scheduled
    bb = httpx.get(f"{API_URL}/api/appointments", headers=b["headers"], timeout=10.0).json()
    b_apt = next(x for x in bb if x["id"] == b["appointment_id"])
    assert b_apt["status"] == "scheduled", "LEAK: A altered B's appointment state"


def test_direct_patient_delete_cross_tenant_blocked(two_practices):
    a, b = two_practices
    r = httpx.delete(f"{API_URL}/api/patients/{b['patient_id']}",
                     headers=a["headers"], timeout=10.0)
    assert r.status_code == 404, f"LEAK: A deleted B's patient (status={r.status_code})"

    # Verify B's patient still exists
    pb = httpx.get(f"{API_URL}/api/patients/{b['patient_id']}",
                   headers=b["headers"], timeout=10.0)
    assert pb.status_code == 200


def test_stats_isolated(two_practices):
    a, b = two_practices
    sa = httpx.get(f"{API_URL}/api/stats", headers=a["headers"], timeout=10.0).json()
    sb = httpx.get(f"{API_URL}/api/stats", headers=b["headers"], timeout=10.0).json()
    # Each practice sees its own count of 1 patient, 1 provider, 1 appointment
    assert sa["total_patients"] == 1
    assert sb["total_patients"] == 1
    assert sa["providers"] == 1
    assert sb["providers"] == 1


def test_call_logs_isolated(two_practices):
    a, b = two_practices
    # Seed a call log in B
    DB.call_logs.insert_one({
        "practice_id": b["practice_id"],
        "call_id": f"b-only-{uuid.uuid4()}",
        "event_type": "call_ended",
        "from_number": "+15550000000",
        "created_at": time.time(),
    })
    # A should see zero call logs
    la = httpx.get(f"{API_URL}/api/call-logs", headers=a["headers"], timeout=10.0).json()
    assert all(c["practice_id"] == a["practice_id"] for c in la), \
        "LEAK: A saw B's call logs"


# ──────────────────────────────────────────────────────────────────────
# PUBLIC Retell-endpoint isolation tests (no JWT — by practice_id in body)
# ──────────────────────────────────────────────────────────────────────

def test_retell_lookup_patient_scopes_by_practice_id(two_practices):
    """
    Same phone number exists in BOTH practices. Retell lookup MUST return
    the patient belonging to the practice_id in the request body — NEVER
    the other one.
    """
    a, b = two_practices
    shared = a["shared_phone"]

    for p in (a, b):
        r = httpx.post(
            f"{API_URL}/api/retell/lookup-patient",
            json={
                "call": {"from_number": shared},
                "args": {"practice_id": p["practice_id"], "phone_number": ""},
            },
            timeout=10.0,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["found"] is True
        # CRITICAL: must return the patient belonging to this practice
        assert d["patient"]["id"] == p["patient_id"], (
            f"LEAK: lookup for practice {p['slug']} returned wrong patient "
            f"(got {d['patient']['id']}, expected {p['patient_id']})"
        )


def test_retell_list_providers_scopes_by_practice_id(two_practices):
    a, b = two_practices
    for p in (a, b):
        r = httpx.post(
            f"{API_URL}/api/retell/list-providers",
            json={"args": {"practice_id": p["practice_id"]}},
            timeout=10.0,
        )
        assert r.status_code == 200
        ids = {prov["id"] for prov in r.json()["providers"]}
        assert p["provider_id"] in ids
        # The OTHER practice's provider must NOT appear
        other = b if p is a else a
        assert other["provider_id"] not in ids, (
            f"LEAK: list_providers for {p['slug']} included {other['slug']}'s provider"
        )


def test_retell_check_availability_scopes_by_practice_id(two_practices):
    a, b = two_practices
    # Ask A's backend about B's provider by name → should NOT find it
    b_provider_name = f"{b['slug'].title()}Provider"
    r = httpx.post(
        f"{API_URL}/api/retell/check-provider-availability",
        json={
            "args": {
                "practice_id": a["practice_id"],
                "provider_name": b_provider_name,
                "date": "2027-01-15",
            }
        },
        timeout=10.0,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is False, (
        f"LEAK: A's backend confirmed availability for B's provider "
        f"{b_provider_name}: {d}"
    )


def test_retell_book_appointment_respects_practice_id(two_practices):
    """
    A book call carrying Practice A's id but from Practice B's caller phone
    must create the appointment under Practice A — NEVER under B's tenant.
    """
    a, b = two_practices
    caller = f"+1555333{int(time.time()) % 10000:04d}"
    r = httpx.post(
        f"{API_URL}/api/retell/book-appointment",
        json={
            "call": {"from_number": caller},
            "args": {
                "practice_id": a["practice_id"],
                "patient_phone": "",
                "patient_name": "Cross-tenant Book",
                "date": "2027-02-01",
                "time": "10:00",
                "reason": "Test",
            },
        },
        timeout=10.0,
    )
    assert r.status_code == 200
    apt_id = r.json()["appointment_id"]

    # Verify the appointment landed under A, not B
    apt = DB.appointments.find_one({"id": apt_id}, {"_id": 0})
    assert apt["practice_id"] == a["practice_id"], (
        f"LEAK: appointment landed in wrong tenant (got {apt['practice_id']})"
    )

    # Cleanup
    DB.appointments.delete_one({"id": apt_id})
    DB.patients.delete_many({"phone": caller})


def test_retell_get_patient_appointments_scoped(two_practices):
    """
    Same phone exists in both practices. Each practice's lookup must return
    only that practice's appointments.
    """
    a, b = two_practices
    shared = a["shared_phone"]
    for p in (a, b):
        r = httpx.post(
            f"{API_URL}/api/retell/get-patient-appointments",
            json={
                "call": {"from_number": shared},
                "args": {"practice_id": p["practice_id"], "phone_number": ""},
            },
            timeout=10.0,
        )
        assert r.status_code == 200
        d = r.json()
        if d.get("upcoming_appointments"):
            for apt in d["upcoming_appointments"]:
                # sanity: appointment id should be THIS practice's
                assert apt["id"] == p["appointment_id"], (
                    f"LEAK: practice {p['slug']} got appointment {apt['id']!r} "
                    f"expected {p['appointment_id']!r}"
                )


def test_retell_cancel_cross_tenant_blocked(two_practices):
    """
    Attempt to cancel B's appointment by passing A's practice_id.
    Must NOT succeed (either 404 or success:false, but must not touch B's data).
    """
    a, b = two_practices
    r = httpx.post(
        f"{API_URL}/api/retell/cancel-appointment",
        json={
            "call": {"from_number": b["shared_phone"]},
            "args": {
                "practice_id": a["practice_id"],      # wrong tenant
                "appointment_id": b["appointment_id"],  # B's appointment
                "phone_number": "",
            },
        },
        timeout=10.0,
    )
    # Must not return success with B's appointment cancelled
    if r.status_code == 200:
        d = r.json()
        assert not d.get("success", False), (
            "LEAK: cross-tenant cancel succeeded"
        )
    # Verify B's appointment still exists and is scheduled
    still = DB.appointments.find_one({"id": b["appointment_id"]}, {"_id": 0, "status": 1})
    assert still and still["status"] == "scheduled", (
        f"LEAK: B's appointment was modified from another tenant: {still}"
    )


# ──────────────────────────────────────────────────────────────────────
# Auth / JWT isolation
# ──────────────────────────────────────────────────────────────────────

def test_no_token_returns_401():
    r = httpx.get(f"{API_URL}/api/patients", timeout=5.0)
    assert r.status_code in (401, 403)


def test_bad_token_returns_401():
    r = httpx.get(f"{API_URL}/api/patients",
                  headers={"Authorization": "Bearer not-a-real-token"},
                  timeout=5.0)
    assert r.status_code in (401, 403)


def test_jwt_locks_user_to_practice(two_practices):
    """Attempt to use A's JWT against B-scoped routes (not possible by design,
    but the test proves the JWT carries practice_id, not user-selectable)."""
    a, _ = two_practices
    r = httpx.get(f"{API_URL}/api/auth/me", headers=a["headers"], timeout=5.0)
    assert r.status_code == 200
    me = r.json()
    assert me["practice_id"] == a["practice_id"]
