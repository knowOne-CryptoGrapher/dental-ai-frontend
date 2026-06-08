"""
One-time migration: unstick practices that are in "onboarding" status but
should be considered complete or safe to skip to the dashboard.

This fixes the login → /onboarding redirect loop caused by practices that
have status="onboarding" but were never properly completed.

Operations (in order):
  1. Practices with status="onboarding" AND onboarding_step >= 8 are far
     enough through the wizard to be treated as complete. Set them active.
  2. Practices with status="onboarding" AND onboarding_step == 0 (or missing)
     never started the wizard and are orphaned. Set them active so users can
     reach the dashboard and configure via Settings instead.

Usage (run once, from the backend directory):
    python scripts/migrate_fix_onboarding_status.py

Requires MONGODB_URI (or MONGO_URL) and optionally DATABASE_NAME (default: dental_ai)
in the environment or in backend/.env.
"""
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, "..", ".env"))

MONGO_URI = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DATABASE_NAME") or os.environ.get("DB_NAME") or "dental_ai"

if not MONGO_URI:
    print("ERROR: MONGODB_URI (or MONGO_URL) is not set.", file=sys.stderr)
    sys.exit(1)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
db = client[DB_NAME]

now_iso = datetime.now(timezone.utc).isoformat()

# 1. Practices that reached step 8 (Test & Finish) or beyond but never called
#    complete-onboarding. They completed the wizard content; mark them active.
r1 = db.practices.update_many(
    {"status": "onboarding", "onboarding_step": {"$gte": 8}},
    {"$set": {
        "status":                  "active",
        "onboarding_step":         999,
        "onboarding_completed_at": now_iso,
    }},
)
print(f"[1] step>=8 onboarding -> active  — matched: {r1.matched_count}, modified: {r1.modified_count}")

# 2. Practices with status="onboarding" but step=0 or missing step — orphaned,
#    never progressed. Send them to the dashboard; they can configure via Settings.
r2 = db.practices.update_many(
    {"status": "onboarding", "$or": [
        {"onboarding_step": {"$exists": False}},
        {"onboarding_step": 0},
    ]},
    {"$set": {
        "status":                  "active",
        "onboarding_step":         999,
        "onboarding_completed_at": now_iso,
    }},
)
print(f"[2] step=0 orphaned -> active     — matched: {r2.matched_count}, modified: {r2.modified_count}")

client.close()
