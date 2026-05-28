"""
Creates the initial admin user for the Dental AI test practice.
Idempotent — skips insert if email already exists.
"""
import sys
import uuid
import bcrypt
from datetime import datetime, timezone
from pymongo import MongoClient

MONGO_URI   = "mongodb+srv://dental-ai:Please12@dental-ai.nfsibx.mongodb.net/?appName=dental-ai"
DB_NAME     = "dental_ai"
PRACTICE_ID = "practice-test-001"

EMAIL       = "admin@dentalai.test"
PASSWORD    = "DentalAI2026!"
FULL_NAME   = "Practice Admin"
ROLE        = "admin"

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
try:
    client.admin.command("ping")
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

db = client[DB_NAME]

if db.users.find_one({"email": EMAIL}):
    print(f"User already exists: {EMAIL}")
    client.close()
    sys.exit(0)

password_hash = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

user_doc = {
    "id":                   str(uuid.uuid4()),
    "email":                EMAIL,
    "password_hash":        password_hash,
    "full_name":            FULL_NAME,
    "practice_id":          PRACTICE_ID,
    "practice_name":        "Dental AI Test Practice",
    "role":                 ROLE,
    "is_active":            True,
    "onboarding_completed": True,
    "created_at":           datetime.now(timezone.utc).isoformat(),
}

db.users.insert_one(user_doc)

print("Admin user created")
print(f"  Email    : {EMAIL}")
print(f"  Password : {PASSWORD}")
print(f"  Role     : {ROLE}")
print(f"  Practice : Dental AI Test Practice ({PRACTICE_ID})")

client.close()
