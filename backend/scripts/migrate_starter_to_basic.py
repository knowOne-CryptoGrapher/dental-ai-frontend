"""
One-time migration: rename the legacy "starter" subscription_plan value to "basic".

All registration paths previously wrote `subscription_plan: "starter"` to the DB.
plans.py only defines "basic", "professional", "enterprise", "elite".  get_plan()
silently falls back on unknown IDs, so the mismatch was hidden — but the stored
value was wrong.  This script corrects every affected practice document.

Usage (run once, from the backend directory):
    python scripts/migrate_starter_to_basic.py

Requires MONGODB_URI (or MONGO_URL) and optionally DATABASE_NAME (default: dental_ai)
in the environment or in backend/.env.
"""
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env from the backend directory (works whether the script is run from
# backend/ or from the repo root).
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, "..", ".env"))

MONGO_URI = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME   = os.environ.get("DATABASE_NAME") or os.environ.get("DB_NAME") or "dental_ai"

if not MONGO_URI:
    print("ERROR: MONGODB_URI (or MONGO_URL) is not set.", file=sys.stderr)
    sys.exit(1)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
db = client[DB_NAME]

result = db.practices.update_many(
    {"subscription_plan": "starter"},
    {"$set": {"subscription_plan": "basic"}},
)

print(f"practices matched : {result.matched_count}")
print(f"practices modified: {result.modified_count}")

client.close()
