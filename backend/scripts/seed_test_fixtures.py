"""
Seeds the two shared login fixture accounts the backend test suite expects:
  - owner@dentalai.com   (super_admin, no practice)
  - admin@dentaltest.com (practice admin, linked to a dedicated fixture practice)

Referenced by: test_superadmin_re.py, test_platform_console.py, test_plan_tiers.py,
test_billing.py, test_impersonation.py, test_phase1_multi_tenant.py,
test_enterprise_api.py, test_provider_scheduling.py, test_llm_router.py,
test_cancel_appointment.py.

Idempotent — safe to run repeatedly; skips anything that already exists.

Usage (run once, from the backend directory):
    python scripts/seed_test_fixtures.py

Requires MONGODB_URI (or MONGO_URL) and optionally DATABASE_NAME (default: dental_ai)
in the environment or in backend/.env — the SAME database the test suite itself
connects to (see tests/conftest.py). There is currently no separate test database:
this seeds directly into whatever MONGODB_URI points at, which today is the same
Atlas cluster used by local dev and production (see HANDOFF.md).
"""
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, ".."))  # so `import models` resolves
load_dotenv(os.path.join(_here, "..", ".env"))

from models import default_practice_settings  # noqa: E402

MONGO_URI = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DATABASE_NAME") or os.environ.get("DB_NAME") or "dental_ai"

if not MONGO_URI:
    print("ERROR: MONGODB_URI (or MONGO_URL) is not set.", file=sys.stderr)
    sys.exit(1)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
db = client[DB_NAME]

FIXTURE_PRACTICE_ID = "practice-fixture-admin-001"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ── 1. Fixture practice for admin@dentaltest.com ───────────────────────────
if db.practices.find_one({"id": FIXTURE_PRACTICE_ID}):
    print(f"Practice already exists: {FIXTURE_PRACTICE_ID}")
else:
    db.practices.insert_one({
        "id": FIXTURE_PRACTICE_ID,
        "name": "Dental AI Fixture Practice",
        "contact_email": "admin@dentaltest.com",
        "contact_phone": "+15550001234",
        "status": "active",
        "billing_status": "active",
        "subscription_plan": "basic",
        "default_timezone": "America/Toronto",
        "default_retention_years": 7,
        "settings": default_practice_settings(),
        "created_at": now(),
        "created_by_super_admin": "seed_test_fixtures.py",
        # Data residency — same shape as real provisioning (approve_lead / approve_founding_clinic)
        "province": "BC",
        "country": "CA",
        "home_region": "ca-west",
        "db_cluster": "atlas-ca-west",
        "compute_region": "northamerica-west2",
    })
    print(f"Practice created: {FIXTURE_PRACTICE_ID}")

    db.locations.insert_one({
        "id": str(uuid.uuid4()),
        "practice_id": FIXTURE_PRACTICE_ID,
        "name": "Main Office",
        "timezone": "America/Toronto",
        "is_active": True,
        "created_at": now(),
    })
    print("Location created: Main Office")

# ── 2. owner@dentalai.com (super_admin) ─────────────────────────────────────
SUPER_EMAIL = "owner@dentalai.com"
SUPER_PASSWORD = "OwnerPass123!"

if db.users.find_one({"email": SUPER_EMAIL}):
    print(f"User already exists: {SUPER_EMAIL}")
else:
    db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": SUPER_EMAIL,
        "password_hash": hash_password(SUPER_PASSWORD),
        "full_name": "Test Super Admin",
        "practice_id": None,
        "role": "super_admin",
        "is_active": True,
        "onboarding_completed": True,
        "created_at": now(),
    })
    print(f"User created: {SUPER_EMAIL} (super_admin)")

# ── 3. admin@dentaltest.com (practice admin) ────────────────────────────────
ADMIN_EMAIL = "admin@dentaltest.com"
ADMIN_PASSWORD = "TestPass123!"

if db.users.find_one({"email": ADMIN_EMAIL}):
    print(f"User already exists: {ADMIN_EMAIL}")
else:
    db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": ADMIN_EMAIL,
        "password_hash": hash_password(ADMIN_PASSWORD),
        "full_name": "Test Practice Admin",
        "practice_id": FIXTURE_PRACTICE_ID,
        "practice_name": "Dental AI Fixture Practice",
        "role": "admin",
        "is_active": True,
        "onboarding_completed": True,
        "created_at": now(),
    })
    print(f"User created: {ADMIN_EMAIL} (admin, practice {FIXTURE_PRACTICE_ID})")

client.close()
print("\nDone.")
