"""
Shared factories and fixtures for the dental-ai backend test suite.

Required environment variables:
    MONGODB_URI   — MongoDB connection string (or MONGO_URL as fallback)
    DATABASE_NAME — Database name (or DB_NAME as fallback; default "dental_ai")
    TEST_API_URL  — API base URL (default https://api.frontdeskdentalai.com)

All factory functions insert data directly into MongoDB so that tests are
hermetic and never rely on a running registration flow to create fixtures.
Bcrypt is used directly for password hashing, matching the server's hash_password().

Cleanup convention: every module-scoped fixture yields, then deletes every
document it inserted (keyed by practice_id). Orphaned test data is identifiable
by the "testpractice-" name prefix.
"""
import json
import os
import time
import uuid
import bcrypt
import httpx
import pytest
from pymongo import MongoClient
from retell.lib.webhook_auth import symmetric as _retell_symmetric

# ── Config ─────────────────────────────────────────────────────────────

API_URL: str = os.environ.get(
    "TEST_API_URL", "https://api.frontdeskdentalai.com"
)

_mongo_uri = (
    os.environ.get("MONGODB_URI")
    or os.environ.get("MONGO_URL")
    or ""
)
_db_name = (
    os.environ.get("DATABASE_NAME")
    or os.environ.get("DB_NAME")
    or "dental_ai"
)
if not _mongo_uri:
    raise EnvironmentError(
        "Set MONGODB_URI (or MONGO_URL) before running the test suite."
    )

RETELL_API_KEY = os.environ["RETELL_API_KEY"]

_mongo_client = MongoClient(_mongo_uri, serverSelectionTimeoutMS=5_000)
DB = _mongo_client[_db_name]

# Keep in sync with backend/config.py — bump when legal docs change.
TERMS_VERSION = "1.1"
PRIVACY_POLICY_VERSION = "1.0"

COLLECTIONS_TO_CLEAN = (
    "users", "providers", "patients", "appointments",
    "invite_tokens", "ai_safety_logs", "audit_logs",
)


# ── Low-level helpers ───────────────────────────────────────────────────

def sign_retell_body(body_bytes: bytes) -> str:
    """Real X-Retell-Signature header value for the given raw request body,
    same construction (retell.lib.webhook_auth.symmetric['sign']) that
    utils/retell_security.py verifies against. Works on any byte string,
    valid JSON or not — HMAC doesn't care about content."""
    return _retell_symmetric["sign"](body_bytes.decode("utf-8"), RETELL_API_KEY)


def signed_retell_post(url: str, body: dict, timeout: float = 10.0) -> httpx.Response:
    """POST a JSON body to a signature-protected /api/retell/* endpoint with
    a real, valid X-Retell-Signature. Serializes once and signs those exact
    bytes so the signature always matches what's actually transmitted."""
    body_bytes = json.dumps(body).encode("utf-8")
    return httpx.post(
        url,
        content=body_bytes,
        headers={"Content-Type": "application/json", "X-Retell-Signature": sign_retell_body(body_bytes)},
        timeout=timeout,
    )


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _login(email: str, password: str) -> dict:
    """Log in via the API and return {token, headers}."""
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15.0,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    token = r.json()["access_token"]
    return {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ── Practice factory ────────────────────────────────────────────────────

def create_practice(slug: str | None = None) -> dict:
    """Insert a practice document and return a context dict."""
    slug = slug or _uid("testpractice-")
    practice_id = str(uuid.uuid4())
    doc = {
        "id": practice_id,
        "name": f"Test Clinic [{slug}]",
        "contact_email": f"admin@{slug}.local",
        "status": "active",
        "billing_status": "active",
        "subscription_plan": "basic",
        "default_timezone": "America/Toronto",
        "default_retention_years": 7,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # Data residency — Canadian practice in Ontario
        "province": "ON",
        "home_region": "ca-east",
        "db_cluster": "atlas-ca-east",
        "compute_region": "northamerica-northeast1",
        "settings": {
            "branding": {
                "agent_name": "Amanda",
                "greeting": "Thank you for calling!",
                "closing": "Have a great day!",
                "voice_tone": "warm_professional",
            },
            "hours": {
                "timezone": "America/Toronto",
                "weekly": {
                    "mon": {"open": "08:00", "close": "17:00"},
                    "tue": {"open": "08:00", "close": "17:00"},
                    "wed": {"open": "08:00", "close": "17:00"},
                    "thu": {"open": "08:00", "close": "17:00"},
                    "fri": {"open": "08:00", "close": "15:00"},
                    "sat": None,
                    "sun": None,
                },
                "closed_dates": [],
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
            "insurance": {
                "accepted_carriers": [], "itrans_enabled": False, "cdanet_enabled": False
            },
            "retell": {
                "agent_id": None, "phone_number": None, "provisioned_at": None
            },
        },
    }
    DB.practices.insert_one(doc)
    return {"practice_id": practice_id, "name": doc["name"], "slug": slug, "doc": doc}


# ── User factory ────────────────────────────────────────────────────────

def create_user(practice: dict, role: str, slug: str | None = None) -> dict:
    """Insert a user with any role directly into MongoDB, then log in."""
    slug = slug or _uid(f"{role}-")
    email = f"{role}-{slug}@testclinic.local"
    password = f"TestPass-{slug[:6].upper()}!1"
    user_id = str(uuid.uuid4())

    DB.users.insert_one({
        "id": user_id,
        "email": email,
        "full_name": f"Test {role.title()} {slug}",
        "password_hash": _hash(password),
        "role": role,
        "practice_id": practice["practice_id"],
        "practice_name": practice["name"],
        "is_active": True,
        "onboarding_completed": True,
        # Inherit residency from practice
        "province": practice["doc"].get("province", "ON"),
        "home_region": practice["doc"].get("home_region", "ca-east"),
        "db_cluster": practice["doc"].get("db_cluster", "atlas-ca-east"),
        "accepted_terms_version": TERMS_VERSION,
        "accepted_privacy_version": PRIVACY_POLICY_VERSION,
        "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    ctx = _login(email, password)
    return {
        "id": user_id,
        "email": email,
        "password": password,
        "role": role,
        "practice_id": practice["practice_id"],
        **ctx,
    }


# ── Invite factory ──────────────────────────────────────────────────────

def create_invite_token(
    practice: dict,
    role: str = "staff",
    email: str | None = None,
    *,
    expired: bool = False,
    used: bool = False,
) -> str:
    """Insert an invite token directly into MongoDB and return the token string."""
    token = str(uuid.uuid4())
    now = time.time()
    DB.invite_tokens.insert_one({
        "token": token,
        "practice_id": practice["practice_id"],
        "email": email or f"invite-{_uid()}@testclinic.local",
        "role": role,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "expires_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(now + (-3600 if expired else 86400)),  # −1 h or +24 h
        ),
        "used": used,
        "used_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)) if used else None,
        "created_by": "test-fixture",
    })
    return token


# ── Appointment factory ─────────────────────────────────────────────────

def create_appointment(practice: dict, patient_name: str | None = None) -> dict:
    """Insert an appointment into MongoDB and return a context dict."""
    apt_id = str(uuid.uuid4())
    DB.appointments.insert_one({
        "id": apt_id,
        "practice_id": practice["practice_id"],
        "patient_id": str(uuid.uuid4()),
        "patient_name": patient_name or f"Test Patient {_uid()}",
        "patient_phone": "+15550000000",
        "appointment_date": "2027-06-01",
        "appointment_time": "10:00",
        "service_type": "Cleaning",
        "duration_minutes": 60,
        "status": "pending_verification",
        "is_emergency": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return {"appointment_id": apt_id, "practice_id": practice["practice_id"]}


# ── Cleanup ─────────────────────────────────────────────────────────────

def cleanup_practice(practice_id: str) -> None:
    """Delete all test data for a practice. Called in fixture teardown."""
    for coll in COLLECTIONS_TO_CLEAN:
        DB[coll].delete_many({"practice_id": practice_id})
    DB.practices.delete_one({"id": practice_id})
