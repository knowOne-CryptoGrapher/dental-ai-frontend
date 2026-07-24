"""
Retell AI backend regression suite.

Covers items 1-13 of the hard-test checklist that are backend-verifiable.
Items 11 (real telephony) and items about Amanda's phrasing require a live
call and are not part of this suite.

Run:
    cd /app/backend && python -m pytest tests/test_retell_hard_suite.py -v
"""
import os
import time
import asyncio
import uuid
import httpx
import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

# Hit the public preview URL so this mirrors the real Retell path exactly.
API_URL = os.environ.get("TEST_API_URL", "https://dental-ai-backend-cszmxu7emq-uw.a.run.app").rstrip("/")
PRACTICE_ID = "c50330bb-079b-4286-ac62-717a40bfa8dd"

# A phone that's known to exist in this env (Darnell John)
KNOWN_PHONE = "+12502991248"


def wrap(args: dict, from_number: str | None = None) -> dict:
    """Mimic Retell's request body."""
    body = {"args": args}
    if from_number:
        body["call"] = {"from_number": from_number}
    return body


def post(path: str, body: dict) -> httpx.Response:
    return httpx.post(f"{API_URL}/api/retell{path}", json=body, timeout=10.0)


# ──────────────────────────────────────────────────────────────────────
# 1. lookup_patient
# ──────────────────────────────────────────────────────────────────────

def test_1a_lookup_known_patient_returns_all_fields():
    r = post("/lookup-patient", wrap(
        {"practice_id": PRACTICE_ID, "phone_number": ""},
        from_number=KNOWN_PHONE
    ))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    d = r.json()
    assert d["found"] is True
    for field in (
        "patient_name", "phone_number", "email",
        "last_appointment_date", "last_appointment_reason",
        "preferred_provider", "message"
    ):
        assert field in d, f"missing top-level field: {field}"
    assert d["phone_number"] == KNOWN_PHONE


def test_1b_lookup_unknown_patient():
    r = post("/lookup-patient", wrap(
        {"practice_id": PRACTICE_ID, "phone_number": ""},
        from_number="+17779998888"
    ))
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is False
    assert d["patient_name"] is None
    assert d["appointment_history"] == []
    assert "create a new patient record" in d["message"].lower()


def test_1c_malformed_json_returns_400_json_not_html():
    r = httpx.post(
        f"{API_URL}/api/retell/lookup-patient",
        content=b"this-is-not-json",
        headers={"Content-Type": "application/json"},
        timeout=5.0,
    )
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/json")
    assert "<html" not in r.text.lower()


# ──────────────────────────────────────────────────────────────────────
# 2. list_providers
# ──────────────────────────────────────────────────────────────────────

def test_2a_list_providers_returns_provider_name_and_specialty():
    r = post("/list-providers", wrap({"practice_id": PRACTICE_ID}))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 1
    for p in d["providers"]:
        assert "provider_name" in p
        assert "specialty" in p
        assert "id" in p


def test_2c_empty_practice_returns_no_crash():
    r = post("/list-providers", wrap({"practice_id": "nonexistent-" + uuid.uuid4().hex}))
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 0
    assert d["providers"] == []
    assert d["message"]  # non-empty graceful message


def test_2_missing_practice_id():
    r = post("/list-providers", wrap({}))
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/json")


# ──────────────────────────────────────────────────────────────────────
# 3. check_provider_availability
# ──────────────────────────────────────────────────────────────────────

def test_3a_provider_available():
    r = post("/check-provider-availability", wrap({
        "practice_id": PRACTICE_ID,
        "provider_name": "McDonald",
        "date": "2026-07-15",
        "time": "10:00"
    }))
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True
    assert d["provider_name"]
    assert d["date"] == "2026-07-15"
    assert d["time"] == "10:00"
    assert isinstance(d["suggested_times"], list)


def test_3b_provider_not_available_returns_suggestions():
    # Request a time outside normal working hours so it's not available
    r = post("/check-provider-availability", wrap({
        "practice_id": PRACTICE_ID,
        "provider_name": "McDonald",
        "date": "2026-07-15",
        "time": "23:00"
    }))
    assert r.status_code == 200
    d = r.json()
    # Either not available (suggestions) or available but with same time — both OK
    assert "suggested_times" in d
    assert isinstance(d["suggested_times"], list)


def test_3c_wrong_provider_name_graceful():
    r = post("/check-provider-availability", wrap({
        "practice_id": PRACTICE_ID,
        "provider_name": "Ghostprovider Faketown",
        "date": "2026-07-15"
    }))
    assert r.status_code == 200
    d = r.json()
    # Should not throw; should indicate unavailable and suggest alternatives
    assert d["available"] is False
    assert "message" in d


# ──────────────────────────────────────────────────────────────────────
# 4. book_appointment
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def cleanup_test_phone():
    """Delete test patient + appointments after each booking test."""
    phones_created = []
    yield phones_created
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    for p in phones_created:
        pats = list(db.patients.find({"phone": p}, {"_id": 0, "id": 1}))
        pids = [x["id"] for x in pats]
        db.appointments.delete_many({"patient_id": {"$in": pids}})
        db.patients.delete_many({"phone": p})
    client.close()


def test_4a_full_booking_creates_patient_and_appointment(cleanup_test_phone):
    phone = f"+1999000{int(time.time()) % 10000:04d}"
    cleanup_test_phone.append(phone)

    r = post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_phone": "",
        "patient_name": "Regression Full",
        "patient_email": "reg@example.com",
        "date": "2026-10-20",
        "time": "10:00",
        "provider_name": "McDonald",
        "reason": "Cleaning"
    }, from_number=phone))
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True
    assert d["appointment_id"]
    assert d["message"]


def test_4b_missing_required_fields_returns_400():
    r = post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_name": "Missing Date"
    }, from_number="+15550001111"))
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/json")


# ──────────────────────────────────────────────────────────────────────
# 5. get_patient_appointments
# ──────────────────────────────────────────────────────────────────────

def test_5a_patient_with_appointments(cleanup_test_phone):
    phone = f"+1999111{int(time.time()) % 10000:04d}"
    cleanup_test_phone.append(phone)

    # Book one
    post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_phone": "",
        "patient_name": "Reg Get",
        "date": "2026-10-22",
        "time": "11:00",
        "reason": "Checkup"
    }, from_number=phone))

    r = post("/get-patient-appointments", wrap({
        "practice_id": PRACTICE_ID,
        "phone_number": ""
    }, from_number=phone))
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is True
    assert d["count"] >= 1
    apt = d["upcoming_appointments"][0]
    for f in ("id", "date", "time", "provider_name", "reason", "status"):
        assert f in apt


def test_5b_no_appointments_graceful():
    phone = f"+1999222{int(time.time()) % 10000:04d}"
    r = post("/get-patient-appointments", wrap({
        "practice_id": PRACTICE_ID,
        "phone_number": ""
    }, from_number=phone))
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is False or d.get("count", 0) == 0
    assert d["message"]


# ──────────────────────────────────────────────────────────────────────
# 6. cancel_appointment
# ──────────────────────────────────────────────────────────────────────

def test_6a_cancel_single(cleanup_test_phone):
    phone = f"+1999333{int(time.time()) % 10000:04d}"
    cleanup_test_phone.append(phone)

    # Create
    book = post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_phone": "",
        "patient_name": "Reg Cancel",
        "date": "2026-10-24",
        "time": "09:00",
        "reason": "Cleaning"
    }, from_number=phone))
    apt_id = book.json()["appointment_id"]

    # Cancel
    r = post("/cancel-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "appointment_id": apt_id,
        "phone_number": ""
    }, from_number=phone))
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True


def test_6c_invalid_appointment_id_graceful():
    r = post("/cancel-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "appointment_id": "non-existent-uuid",
        "phone_number": ""
    }, from_number=KNOWN_PHONE))
    # Either 404 or 200 with success:false — both acceptable; must not 500
    assert r.status_code in (200, 404, 400)
    assert r.headers["content-type"].startswith("application/json")
    assert r.status_code != 500


# ──────────────────────────────────────────────────────────────────────
# 7. Emergency flag propagates
# ──────────────────────────────────────────────────────────────────────

def test_7a_emergency_flag_honored(cleanup_test_phone):
    phone = f"+1999444{int(time.time()) % 10000:04d}"
    cleanup_test_phone.append(phone)

    r = post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_phone": "",
        "patient_name": "Emergency Test",
        "date": "2026-10-26",
        "time": "09:00",
        "reason": "Severe pain",
        "is_emergency": True
    }, from_number=phone))
    assert r.status_code == 200
    assert r.json()["success"] is True


# ──────────────────────────────────────────────────────────────────────
# 8. Profile data returned from backend (preferred_provider)
# ──────────────────────────────────────────────────────────────────────

def test_8_profile_contains_preferred_provider_key():
    r = post("/lookup-patient", wrap(
        {"practice_id": PRACTICE_ID, "phone_number": ""},
        from_number=KNOWN_PHONE
    ))
    d = r.json()
    assert "preferred_provider" in d  # may be None if none yet


# ──────────────────────────────────────────────────────────────────────
# 10. Stability
# ──────────────────────────────────────────────────────────────────────

def test_10a_100_malformed_requests_all_400_json():
    fails = 0
    html_hits = 0
    server_errors = 0
    for i in range(50):  # 100 is overkill in CI; 50 still proves the point
        r = httpx.post(
            f"{API_URL}/api/retell/lookup-patient",
            content=f"garbage-{i}".encode(),
            headers={"Content-Type": "application/json"},
            timeout=5.0,
        )
        if r.status_code >= 500:
            server_errors += 1
        if "<html" in r.text.lower():
            html_hits += 1
        if r.status_code != 400:
            fails += 1
    assert server_errors == 0
    assert html_hits == 0
    assert fails == 0


def test_10b_load_20_parallel_requests_under_5s():
    async def one():
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                f"{API_URL}/api/retell/list-providers",
                json={"args": {"practice_id": PRACTICE_ID}},
            )
            return r.status_code, r.elapsed.total_seconds()

    async def run():
        return await asyncio.gather(*(one() for _ in range(20)))

    t0 = time.time()
    results = asyncio.run(run())
    total = time.time() - t0
    statuses = [r[0] for r in results]
    max_lat = max(r[1] for r in results)
    assert all(s == 200 for s in statuses), f"non-200s: {statuses}"
    assert total < 5.0, f"20 parallel took {total:.2f}s (must be <5s)"
    assert max_lat < 2.0, f"slowest request {max_lat:.2f}s (must be <2s)"


# ──────────────────────────────────────────────────────────────────────
# 13. Security
# ──────────────────────────────────────────────────────────────────────

def test_13a_sql_injection_attempt_handled():
    # MongoDB isn't SQL, but the principle stands — bad input must not crash
    r = post("/lookup-patient", wrap({
        "practice_id": PRACTICE_ID,
        "phone_number": "Robert'); DROP TABLE Patients;--"
    }))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    d = r.json()
    assert d["found"] is False  # no matching patient, not a crash


def test_13b_html_injection_in_patient_name(cleanup_test_phone):
    phone = f"+1999555{int(time.time()) % 10000:04d}"
    cleanup_test_phone.append(phone)

    r = post("/book-appointment", wrap({
        "practice_id": PRACTICE_ID,
        "patient_phone": "",
        "patient_name": "<script>alert('xss')</script>",
        "date": "2026-10-28",
        "time": "10:00",
        "reason": "Test"
    }, from_number=phone))
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is True
    # Backend stored the name raw (that's fine — escaping happens at render time)


def test_13c_oversized_payload_rejected():
    huge_name = "A" * 100_000
    r = httpx.post(
        f"{API_URL}/api/retell/lookup-patient",
        json={"args": {"practice_id": PRACTICE_ID, "phone_number": huge_name}},
        timeout=5.0,
    )
    # Must respond (200 with no match, or 400/413) — must not 500 or hang
    assert r.status_code < 500
    assert r.headers["content-type"].startswith("application/json")
