"""
Migration: Add unique sparse index on appointments.booking_key
==============================================================

What this does
--------------
1. Backfills a `booking_key` field on every existing active appointment that
   has a provider_id.  Format: "{practice_id}|{provider_id}|{date}|{time}"

2. Creates a UNIQUE SPARSE index on `booking_key`.
   - Sparse: documents without the field (cancelled / no provider) are excluded.
   - Unique: two concurrent inserts with the same key cannot both succeed;
     the second raises DuplicateKeyError, which the API maps to HTTP 409.

Why this fixes the double-booking race
---------------------------------------
The previous flow was:
  find_one  (no conflict found)        ← both concurrent requests see null
  ...                                  ← interleaving window
  insert_one (appointment A inserted)
  insert_one (appointment B inserted)  ← duplicate slot, no error raised

With the index, the second insert raises DuplicateKeyError atomically at the
WiredTiger storage layer — no application-level transaction required.

Idempotent
----------
Safe to re-run.  The index creation uses create_index (no-op if already
exists), and backfill uses $setOnInsert-style upsert logic (only sets the
field if absent).

Pre-flight check
----------------
If existing double-bookings are detected, the script prints them and prompts
before attempting index creation (which would fail on a non-unique set).
The easiest fix is to cancel the duplicate appointments first.

Usage
-----
  python backend/scripts/add_booking_key_index.py
  python backend/scripts/add_booking_key_index.py --dry-run
"""

import sys
import os
import argparse
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

MONGO_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://dental-ai:Please12@dental-ai.nfsibx.mongodb.net/?appName=dental-ai",
)
DB_NAME = os.getenv("DATABASE_NAME", "dental_ai")

CANCELLED_STATUSES = {"cancelled", "no_show"}


def booking_key(practice_id: str, provider_id: str, date: str, time: str) -> str:
    return f"{practice_id}|{provider_id}|{date}|{time}"


def run(dry_run: bool = False) -> int:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        print("Connected to MongoDB Atlas")
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1

    db = client[DB_NAME]
    appts = db.appointments

    # ── Step 1: detect existing double-bookings ───────────────────────────────
    print("\n-- Checking for existing double-bookings --")

    pipeline = [
        {"$match": {
            "provider_id": {"$exists": True, "$ne": None},
            "status":      {"$nin": list(CANCELLED_STATUSES)},
        }},
        {"$group": {
            "_id": {
                "practice_id":    "$practice_id",
                "provider_id":    "$provider_id",
                "appointment_date": "$appointment_date",
                "appointment_time": "$appointment_time",
            },
            "count": {"$sum": 1},
            "ids":   {"$push": "$id"},
        }},
        # Only flag groups where both date and time are non-null.
        # Seed appointments created by init_db.py use a different schema
        # (start_time instead of appointment_date + appointment_time), so
        # they group under null keys and are not real double-bookings.
        {"$match": {
            "count": {"$gt": 1},
            "_id.appointment_date": {"$ne": None},
            "_id.appointment_time": {"$ne": None},
        }},
    ]

    duplicates = list(appts.aggregate(pipeline))
    if duplicates:
        print(f"  WARNING: {len(duplicates)} double-booked slot(s) found:")
        for d in duplicates:
            k = d["_id"]
            print(f"    provider={k.get('provider_id')}  "
                  f"{k.get('appointment_date')} {k.get('appointment_time')}"
                  f"  ({d['count']} active)  ids={d['ids']}")
        print()
        print("  The unique index CANNOT be created until these are resolved.")
        print("  Cancel the duplicate appointments first, then re-run this script.")
        if not dry_run:
            ans = input("  Continue anyway and attempt index creation? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                return 1
    else:
        print("  No double-bookings detected. Safe to proceed.")

    # ── Step 2: backfill booking_key on active appointments ───────────────────
    print("\n-- Backfilling booking_key on active appointments --")

    query = {
        "provider_id":  {"$exists": True, "$ne": None},
        "practice_id":  {"$exists": True, "$ne": None},
        "status":       {"$nin": list(CANCELLED_STATUSES)},
        "booking_key":  {"$exists": False},   # only touch docs that lack the field
    }

    candidates = list(appts.find(query, {
        "_id": 1, "id": 1, "practice_id": 1, "provider_id": 1,
        "appointment_date": 1, "appointment_time": 1,
    }))

    print(f"  {len(candidates)} appointment(s) need backfilling")

    if not dry_run:
        updated = 0
        skipped = 0
        for doc in candidates:
            pid  = doc.get("practice_id")
            pvid = doc.get("provider_id")
            dt   = doc.get("appointment_date")
            tm   = doc.get("appointment_time")

            if not all([pid, pvid, dt, tm]):
                skipped += 1
                continue

            key = booking_key(pid, pvid, dt, tm)
            appts.update_one(
                {"_id": doc["_id"], "booking_key": {"$exists": False}},
                {"$set": {"booking_key": key}},
            )
            updated += 1

        print(f"  Backfilled: {updated}  skipped (incomplete data): {skipped}")
    else:
        print("  [dry-run] No writes performed")

    # ── Step 3: create the unique sparse index ────────────────────────────────
    print("\n-- Creating unique sparse index on booking_key --")

    index_name = "booking_key_unique"

    # Check if index already exists
    existing_indexes = {idx["name"]: idx for idx in appts.list_indexes()}
    if index_name in existing_indexes:
        print(f"  Index '{index_name}' already exists — skipping creation")
    elif dry_run:
        print(f"  [dry-run] Would create index '{index_name}'")
    else:
        try:
            created = appts.create_index(
                [("booking_key", ASCENDING)],
                unique=True,
                sparse=True,
                name=index_name,
            )
            print(f"  Created index: {created}")
        except OperationFailure as e:
            print(f"  ERROR: index creation failed: {e}", file=sys.stderr)
            print("  This usually means duplicate booking_key values exist.", file=sys.stderr)
            print("  Re-run with --dry-run to inspect, or cancel the duplicates first.", file=sys.stderr)
            return 1

    # ── Summary ───────────────────────────────────────────────────────────────
    total_with_key = appts.count_documents({"booking_key": {"$exists": True}})
    total_active   = appts.count_documents({
        "provider_id": {"$exists": True, "$ne": None},
        "status":      {"$nin": list(CANCELLED_STATUSES)},
    })

    print(f"\n-- Summary --")
    print(f"  Active appointments with provider_id : {total_active}")
    print(f"  Appointments with booking_key field  : {total_with_key}")
    if total_active != total_with_key and not dry_run:
        diff = total_active - total_with_key
        print(f"  WARNING: {diff} active appointment(s) still missing booking_key")
        print("  These may have incomplete data (missing practice_id / provider_id).")

    client.close()
    print("\nDone." if not dry_run else "\nDry-run complete — no changes made.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be done without writing anything")
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))
