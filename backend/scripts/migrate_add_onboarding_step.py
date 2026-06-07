"""
One-time migration: add onboarding_step and onboarding_completed_at to all
practice documents that pre-date these fields.

Operations (in order):
  1. Set onboarding_step = 0 on every practice that lacks the field.
  2. Set onboarding_step = 999 on practices that are already "active" and
     still have onboarding_step = 0 — they completed onboarding before this
     field existed, so 0 is misleading.
  3. Set onboarding_completed_at = None on active practices that lack the
     field entirely (backfill so the document shape is consistent).

Usage (run once, from the backend directory):
    python scripts/migrate_add_onboarding_step.py

Requires MONGODB_URI (or MONGO_URL) and optionally DATABASE_NAME (default: dental_ai)
in the environment or in backend/.env.
"""
import os
import sys

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

# 1. Backfill onboarding_step = 0 for practices that don't have the field yet.
r1 = db.practices.update_many(
    {"onboarding_step": {"$exists": False}},
    {"$set": {"onboarding_step": 0}},
)
print(f"[1] onboarding_step backfill  — matched: {r1.matched_count}, modified: {r1.modified_count}")

# 2. Mark already-active practices as fully complete (step 999).
#    These practices finished onboarding before this field existed.
r2 = db.practices.update_many(
    {"status": "active", "onboarding_step": 0},
    {"$set": {"onboarding_step": 999}},
)
print(f"[2] active → step 999         — matched: {r2.matched_count}, modified: {r2.modified_count}")

# 3. Backfill onboarding_completed_at = None on active practices that lack it.
r3 = db.practices.update_many(
    {"onboarding_completed_at": {"$exists": False}, "status": "active"},
    {"$set": {"onboarding_completed_at": None}},
)
print(f"[3] completed_at backfill     — matched: {r3.matched_count}, modified: {r3.modified_count}")

client.close()
