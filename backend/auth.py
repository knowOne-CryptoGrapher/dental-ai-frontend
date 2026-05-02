import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import bcrypt

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dental-ai-enterprise-secret-2025")
ALGORITHM = "HS256"
security = HTTPBearer()

# ==== PASSWORD HELPERS ====

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ==== DB REFERENCE (set from server.py) ====
_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    return _db

# ==== CURRENT USER DEPENDENCY ====

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        db = get_db()
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        # Carry impersonation context from the JWT into the user dict so
        # downstream code (and /auth/me) can surface it to the UI.
        if payload.get("impersonated_by"):
            user["impersonated_by"] = payload.get("impersonated_by")
            user["impersonator_email"] = payload.get("impersonator_email")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==== RBAC DEPENDENCIES ====

ROLE_HIERARCHY = {
    "super_admin": 100,
    "admin": 80,
    "staff": 60,
    "provider": 50,
    "auditor": 40,
}

def require_role(*allowed_roles):
    """Dependency factory: require user to have one of the allowed roles"""
    async def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role", "staff")
        if user_role not in allowed_roles and user_role != "super_admin":
            raise HTTPException(status_code=403, detail=f"Role '{user_role}' not authorized. Required: {allowed_roles}")
        return current_user
    return role_checker

def require_practice_access(current_user: dict, practice_id: str):
    """Verify user has access to the given practice"""
    if current_user.get("role") == "super_admin":
        return True
    if current_user.get("practice_id") != practice_id:
        raise HTTPException(status_code=403, detail="Access denied to this practice")
    return True

# ==== AUDIT HELPER ====

async def log_audit_event(user_id: str, practice_id: str, action: str, resource_type: str, resource_id: str = None, details: dict = None, ip_address: str = None):
    try:
        db = get_db()
        entry = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "practice_id": practice_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": ip_address
        }
        await db.audit_logs.insert_one(entry)
    except Exception as e:
        logger.error(f"Audit log error: {e}")

async def log_analytics_event(practice_id: str, event_type: str, event_data: dict = None):
    try:
        db = get_db()
        event = {
            "id": str(uuid.uuid4()),
            "practice_id": practice_id,
            "event_type": event_type,
            "event_data": event_data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date_key": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }
        await db.analytics_events.insert_one(event)
    except Exception as e:
        logger.error(f"Analytics event error: {e}")

# ==== EMERGENCY DETECTION ====

EMERGENCY_KEYWORDS = [
    "emergency", "urgent", "pain", "severe", "bleeding", "swelling", "broken",
    "knocked out", "tooth fell out", "accident", "injury", "trauma", "fever",
    "infection", "abscess", "can't eat", "can't sleep", "unbearable"
]

async def detect_emergency(text: str) -> bool:
    if not text:
        return False
    return any(kw in text.lower() for kw in EMERGENCY_KEYWORDS)

# ==== FILE NUMBER GENERATOR ====

async def generate_file_number(practice_id: str) -> str:
    db = get_db()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    patients = await db.patients.find(
        {"practice_id": practice_id, "file_number": {"$regex": f"^DP-{today}-"}},
        {"file_number": 1}
    ).sort("file_number", -1).limit(1).to_list(1)
    next_num = int(patients[0]["file_number"].split("-")[-1]) + 1 if patients else 1
    return f"DP-{today}-{next_num:04d}"
