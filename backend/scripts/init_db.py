"""
Idempotent database initializer for Dental AI.
Safe to run multiple times — uses upserts and create_if_not_exists patterns.
"""
import os
import sys
import uuid
from datetime import datetime, timezone, date
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, errors

# Load .env from the backend directory (works whether the script is run from
# backend/ or from the repo root).
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, "..", ".env"))

MONGO_URI = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
DB_NAME   = "dental_ai"

PRACTICE_ID = "practice-test-001"

if not MONGO_URI:
    print("ERROR: MONGODB_URI (or MONGO_URL) is not set.", file=sys.stderr)
    sys.exit(1)

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def uid() -> str:
    return str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
try:
    client.admin.command("ping")
    print("✅ Connected to MongoDB Atlas\n")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

db = client[DB_NAME]

# ---------------------------------------------------------------------------
# 1. providers
# ---------------------------------------------------------------------------

print("── providers ──────────────────────────────────")

working_hours_full = {
    "mon": [{"start": "08:00", "end": "17:00"}],
    "tue": [{"start": "08:00", "end": "17:00"}],
    "wed": [{"start": "08:00", "end": "17:00"}],
    "thu": [{"start": "08:00", "end": "17:00"}],
    "fri": [{"start": "08:00", "end": "15:00"}],
    "sat": [],
    "sun": [],
}

working_hours_hygienist = {
    "mon": [{"start": "09:00", "end": "17:00"}],
    "tue": [{"start": "09:00", "end": "17:00"}],
    "wed": [],
    "thu": [{"start": "09:00", "end": "17:00"}],
    "fri": [{"start": "09:00", "end": "14:00"}],
    "sat": [],
    "sun": [],
}

providers_seed = [
    {
        "id": "provider-sarah-lee-001",
        "practice_id": PRACTICE_ID,
        "name": "Dr. Sarah Lee",
        "role": "dentist",
        "specialties": ["General Dentistry", "Cosmetic Dentistry"],
        "phone": "+1-555-100-0001",
        "email": "sarah.lee@dentalai.test",
        "appointment_types": ["cleaning", "filling", "crown", "whitening", "exam", "emergency"],
        "working_hours": working_hours_full,
        "on_call": True,
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "provider-michael-chen-001",
        "practice_id": PRACTICE_ID,
        "name": "Dr. Michael Chen",
        "role": "dentist",
        "specialties": ["General Dentistry", "Oral Surgery", "Implants"],
        "phone": "+1-555-100-0002",
        "email": "michael.chen@dentalai.test",
        "appointment_types": ["extraction", "implant", "root_canal", "exam", "filling", "emergency"],
        "working_hours": {
            **working_hours_full,
            "mon": [{"start": "10:00", "end": "18:00"}],
            "tue": [{"start": "10:00", "end": "18:00"}],
        },
        "on_call": False,
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "provider-emily-rogers-001",
        "practice_id": PRACTICE_ID,
        "name": "Emily Rogers",
        "role": "hygienist",
        "specialties": ["Preventive Care", "Periodontal Therapy"],
        "phone": "+1-555-100-0003",
        "email": "emily.rogers@dentalai.test",
        "appointment_types": ["cleaning", "scaling", "polishing", "fluoride", "x-rays"],
        "working_hours": working_hours_hygienist,
        "on_call": False,
        "created_at": now(),
        "updated_at": now(),
    },
]

for p in providers_seed:
    result = db.providers.update_one(
        {"id": p["id"]},
        {"$setOnInsert": p},
        upsert=True,
    )
    status = "inserted" if result.upserted_id else "already exists"
    print(f"  {p['name']} → {status}")

# ---------------------------------------------------------------------------
# 2. patients
# ---------------------------------------------------------------------------

print("\n── patients ───────────────────────────────────")

patients_seed = [
    {
        "id": "patient-test-001",
        "practice_id": PRACTICE_ID,
        "first_name": "James",
        "last_name": "Harlow",
        "phone": "+1-555-200-0001",
        "email": "james.harlow@example.com",
        "date_of_birth": "1985-03-14",
        "insurance_provider": "Sun Life Financial",
        "insurance_id": "SL-00123456",
        "notes": "Prefers morning appointments. Mild anxiety — needs extra reassurance.",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "patient-test-002",
        "practice_id": PRACTICE_ID,
        "first_name": "Priya",
        "last_name": "Nair",
        "phone": "+1-555-200-0002",
        "email": "priya.nair@example.com",
        "date_of_birth": "1992-07-28",
        "insurance_provider": "Manulife",
        "insurance_id": "ML-00789012",
        "notes": "Orthodontic retainer — check fit at each visit.",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "patient-test-003",
        "practice_id": PRACTICE_ID,
        "first_name": "Carlos",
        "last_name": "Mendez",
        "phone": "+1-555-200-0003",
        "email": "carlos.mendez@example.com",
        "date_of_birth": "1978-11-05",
        "insurance_provider": "Great-West Life",
        "insurance_id": "GW-00345678",
        "notes": "History of gum disease. Requires 3-month recall schedule.",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "patient-test-004",
        "practice_id": PRACTICE_ID,
        "first_name": "Aisha",
        "last_name": "Thompson",
        "phone": "+1-555-200-0004",
        "email": "aisha.thompson@example.com",
        "date_of_birth": "2001-04-19",
        "insurance_provider": "Desjardins",
        "insurance_id": "DJ-00567890",
        "notes": "New patient. Referred by Dr. Chen.",
        "created_at": now(),
        "updated_at": now(),
    },
]

for p in patients_seed:
    result = db.patients.update_one(
        {"id": p["id"]},
        {"$setOnInsert": p},
        upsert=True,
    )
    status = "inserted" if result.upserted_id else "already exists"
    print(f"  {p['first_name']} {p['last_name']} → {status}")

# ---------------------------------------------------------------------------
# 3. appointments
# ---------------------------------------------------------------------------

print("\n── appointments ───────────────────────────────")

appointments_seed = [
    {
        "id": "appt-001",
        "practice_id": PRACTICE_ID,
        "patient_id": "patient-test-001",
        "provider_id": "provider-sarah-lee-001",
        "appointment_type": "exam",
        "start_time": "2026-06-02T09:00:00+00:00",
        "end_time":   "2026-06-02T09:30:00+00:00",
        "status": "scheduled",
        "notes": "Annual exam + X-rays",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "appt-002",
        "practice_id": PRACTICE_ID,
        "patient_id": "patient-test-002",
        "provider_id": "provider-emily-rogers-001",
        "appointment_type": "cleaning",
        "start_time": "2026-06-02T10:00:00+00:00",
        "end_time":   "2026-06-02T11:00:00+00:00",
        "status": "scheduled",
        "notes": "Regular 6-month cleaning",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "appt-003",
        "practice_id": PRACTICE_ID,
        "patient_id": "patient-test-003",
        "provider_id": "provider-michael-chen-001",
        "appointment_type": "extraction",
        "start_time": "2026-06-03T11:00:00+00:00",
        "end_time":   "2026-06-03T12:00:00+00:00",
        "status": "scheduled",
        "notes": "Lower left wisdom tooth extraction",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "appt-004",
        "practice_id": PRACTICE_ID,
        "patient_id": "patient-test-004",
        "provider_id": "provider-sarah-lee-001",
        "appointment_type": "filling",
        "start_time": "2026-06-04T14:00:00+00:00",
        "end_time":   "2026-06-04T14:45:00+00:00",
        "status": "scheduled",
        "notes": "Composite filling tooth #14",
        "created_at": now(),
        "updated_at": now(),
    },
    {
        "id": "appt-005",
        "practice_id": PRACTICE_ID,
        "patient_id": "patient-test-001",
        "provider_id": "provider-emily-rogers-001",
        "appointment_type": "scaling",
        "start_time": "2026-05-20T09:00:00+00:00",
        "end_time":   "2026-05-20T10:00:00+00:00",
        "status": "completed",
        "notes": "Full mouth scaling completed successfully",
        "created_at": now(),
        "updated_at": now(),
    },
]

for a in appointments_seed:
    result = db.appointments.update_one(
        {"id": a["id"]},
        {"$setOnInsert": a},
        upsert=True,
    )
    status = "inserted" if result.upserted_id else "already exists"
    print(f"  appt-{a['id'][-3:]} ({a['appointment_type']}) → {status}")

# ---------------------------------------------------------------------------
# 4. practice_settings
# ---------------------------------------------------------------------------

print("\n── practice_settings ──────────────────────────")

practice_settings_doc = {
    "id": "settings-test-001",
    "practice_id": PRACTICE_ID,
    "practice_name": "Dental AI Test Practice",
    "phone_number": "+1-555-000-1111",
    "timezone": "America/Vancouver",
    "retell_api_key": "<placeholder>",
    "retell_agent_id": "<placeholder>",
    "emergency_rules": {
        "allow_after_hours": True,
        "forward_to_provider": True,
        "fallback_number": "+1-555-000-2222",
    },
    "branding": {
        "primary_color": "#1a73e8",
        "logo_url": "",
    },
    "created_at": now(),
    "updated_at": now(),
}

result = db.practice_settings.update_one(
    {"practice_id": PRACTICE_ID},
    {"$setOnInsert": practice_settings_doc},
    upsert=True,
)
status = "inserted" if result.upserted_id else "already exists"
print(f"  Dental AI Test Practice → {status}")

# ---------------------------------------------------------------------------
# 5. audit_logs — collection only, no seed data
# ---------------------------------------------------------------------------

print("\n── audit_logs ─────────────────────────────────")

if "audit_logs" not in db.list_collection_names():
    db.create_collection("audit_logs")
    print("  Collection created (empty)")
else:
    print("  Collection already exists (empty is expected)")

# ---------------------------------------------------------------------------
# 6. system_settings
# ---------------------------------------------------------------------------

print("\n── system_settings ────────────────────────────")

system_settings_seed = [
    {"key": "version",        "value": "1.0.0"},
    {"key": "retell_enabled", "value": True},
]

for s in system_settings_seed:
    result = db.system_settings.update_one(
        {"key": s["key"]},
        {"$setOnInsert": {**s, "updated_at": now()}},
        upsert=True,
    )
    status = "inserted" if result.upserted_id else "already exists"
    print(f"  {s['key']} = {s['value']} → {status}")

# ---------------------------------------------------------------------------
# 7. Indexes
# ---------------------------------------------------------------------------

print("\n── indexes ────────────────────────────────────")

index_specs = [
    ("providers",    [("practice_id", ASCENDING)], {}),
    ("providers",    [("role", ASCENDING)],         {}),
    ("patients",     [("practice_id", ASCENDING)],  {}),
    ("patients",     [("phone", ASCENDING)],         {}),
    ("patients",     [("email", ASCENDING)],         {}),
    ("appointments", [("practice_id", ASCENDING)],  {}),
    ("appointments", [("provider_id", ASCENDING)],  {}),
    ("appointments", [("patient_id", ASCENDING)],   {}),
    ("appointments", [("start_time", ASCENDING)],   {}),
    ("audit_logs",   [("practice_id", ASCENDING)],  {}),
    ("audit_logs",   [("timestamp", ASCENDING)],    {}),
]

for coll_name, keys, opts in index_specs:
    try:
        name = db[coll_name].create_index(keys, **opts)
        print(f"  {coll_name}.{keys[0][0]} → ensured ({name})")
    except errors.OperationFailure as e:
        print(f"  {coll_name}.{keys[0][0]} → skipped ({e.details.get('codeName', e)})")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

collections = ["providers", "patients", "appointments", "practice_settings",
               "audit_logs", "system_settings"]

print("\n" + "═" * 52)
print("  SUMMARY")
print("═" * 52)
print(f"  Database : {DB_NAME}")
print(f"  Cluster  : dental-ai.nfsibx.mongodb.net")
print()

for cname in collections:
    count = db[cname].count_documents({})
    print(f"  {cname:<22} {count:>3} document(s)")

print()
for cname in collections:
    docs = list(db[cname].find({}, {"_id": 0}).limit(3))
    if not docs:
        continue
    print(f"── {cname} (first {len(docs)}) " + "─" * (36 - len(cname)))
    for d in docs:
        # print key fields only to keep output readable
        keys = ["id", "name", "first_name", "last_name", "key",
                "practice_name", "appointment_type", "action"]
        label = next((d[k] for k in keys if k in d), str(d)[:60])
        print(f"   {label}")
    print()

print("✅ Initialization complete.")
client.close()
