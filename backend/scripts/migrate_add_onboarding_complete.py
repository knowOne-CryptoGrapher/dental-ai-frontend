"""
One-time migration: backfill onboarding_complete on all existing practice
documents that pre-date this field.

Operations (in order):
  1. Set onboarding_complete = True on active practices that lack the field.
     These completed onboarding before the field existed.
  2. Set onboarding_complete = False on onboarding practices that lack the field.
     These are in-progress or orphaned and have not yet finished.

Usage (run once, from the backend directory):
    python scripts/migrate_add_onboarding_complete.py

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

# 1. Backfill onboarding_complete = True for active practices that lack the field.
r1 = db.practices.update_many(
    {"status": "active", "onboarding_complete": {"$exists": False}},
    {"$set": {"onboarding_complete": True}},
)
print(f"[1] active → onboarding_complete=True   — matched: {r1.matched_count}, modified: {r1.modified_count}")

# 2. Backfill onboarding_complete = False for onboarding practices that lack the field.
r2 = db.practices.update_many(
    {"status": "onboarding", "onboarding_complete": {"$exists": False}},
    {"$set": {"onboarding_complete": False}},
)
print(f"[2] onboarding → onboarding_complete=False — matched: {r2.matched_count}, modified: {r2.modified_count}")

client.close()
