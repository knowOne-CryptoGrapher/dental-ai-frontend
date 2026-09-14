from fastapi import APIRouter, HTTPException, Depends, Request
import os
import uuid
from datetime import datetime, timezone, timedelta
import logging

from models import (
    UserRegister, UserLogin, UserInvite, PracticeCreate, SignupRequest,
    PasswordResetRequest, PasswordResetConfirm,
)
from auth import (
    get_db, hash_password, verify_password, create_access_token,
    get_current_user, require_role, log_audit_event, log_security_event,
)
from plans import enforce_plan_limit, SELF_SERVE_TIERS_ENABLED
from utils.rate_limiter import limiter
from services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_PASSWORD_RESET_EXPIRY_HOURS = 1
_FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "https://frontdeskdentalai.com")
_RESET_REQUESTED_RESPONSE = {
    "message": "If an account with that email exists, we've sent a password reset link."
}


def _user_response(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "practice_id": user.get("practice_id"),
        "practice_name": user.get("practice_name"),
        "role": user.get("role", "staff"),
        "provider_id": user.get("provider_id"),
        "is_active": user.get("is_active", True),
        "onboarding_completed": user.get("onboarding_completed", False),
        "phone_number": user.get("phone_number"),
        "created_at": user.get("created_at"),
        "impersonated_by": user.get("impersonated_by"),
        "impersonator_email": user.get("impersonator_email"),
    }


@router.post("/signup")
@limiter.limit("10/hour")
async def signup(request: Request, data: SignupRequest):
    """
    Create a new admin user account without a practice.
    The practice is created separately via POST /api/practices.
    Returns a JWT that can be used immediately to call POST /api/practices.
    """
    try:
        db = get_db()
        existing_user = await db.users.find_one({"email": data.email})
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please log in instead.",
            )

        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": data.email,
            "password_hash": hash_password(data.password),
            "full_name": data.full_name,
            "contact_phone": data.contact_phone,
            "practice_id": None,
            "role": "admin",
            "is_active": True,
            "onboarding_completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)

        token = create_access_token(data={
            "sub": user_id,
            "practice_id": None,
            "role": "admin",
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": _user_response(user_doc),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("signup_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Signup failed")


@router.post("/register")
@limiter.limit("10/hour")
async def register(request: Request, data: UserRegister):
    """Register a new practice admin (creates practice + admin user)"""
    try:
        if "basic" not in SELF_SERVE_TIERS_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Self-serve signup is currently unavailable. Contact sales to get started.",
            )
        db = get_db()
        if await db.users.find_one({"email": data.email}):
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create practice
        practice_id = str(uuid.uuid4())
        practice_doc = {
            "id": practice_id,
            "name": data.practice_name,
            "contact_email": data.email,
            "status": "active",
            "billing_status": "active",
            "subscription_plan": "basic",
            "default_timezone": "America/Toronto",
            "default_retention_years": 7,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.practices.insert_one(practice_doc)

        # Create default location
        location_id = str(uuid.uuid4())
        await db.locations.insert_one({
            "id": location_id,
            "practice_id": practice_id,
            "name": "Main Office",
            "timezone": "America/Toronto",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Create admin user
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": data.email,
            "password_hash": hash_password(data.password),
            "full_name": data.full_name,
            "practice_id": practice_id,
            "practice_name": data.practice_name,
            "role": "admin",
            "is_active": True,
            "onboarding_completed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)

        # Create mock billing customer
        await db.billing_customers.insert_one({
            "id": str(uuid.uuid4()),
            "practice_id": practice_id,
            "stripe_customer_id": f"cus_mock_{practice_id[:8]}",
            "plan": "basic",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        token = create_access_token(data={
            "sub": user_id,
            "practice_id": practice_id,
            "role": "admin",
        })
        return {"access_token": token, "token_type": "bearer", "user": _user_response(user_doc)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("register_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login")
@limiter.limit("5/15minutes")
async def login(request: Request, creds: UserLogin):
    try:
        db = get_db()
        ip = request.client.host if request.client else None
        user = await db.users.find_one({"email": creds.email}, {"_id": 0})

        if not user or not verify_password(creds.password, user["password_hash"]):
            await log_security_event(
                "login_failed",
                ip_address=ip,
                details={"email_domain": creds.email.split("@")[-1]},
            )
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.get("is_active", True):
            await log_security_event(
                "login_disabled_account",
                user_id=user["id"],
                practice_id=user.get("practice_id"),
                ip_address=ip,
            )
            raise HTTPException(status_code=403, detail="Account disabled")

        token = create_access_token(data={
            "sub": user["id"],
            "practice_id": user.get("practice_id"),
            "role": user.get("role", "staff"),
        })
        return {"access_token": token, "token_type": "bearer", "user": _user_response(user)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/request-password-reset")
@limiter.limit("5/15minutes")
async def request_password_reset(request: Request, body: PasswordResetRequest):
    db = get_db()
    ip = request.client.host if request.client else None
    email_lc = body.email.lower()

    user = await db.users.find_one({"email": email_lc}, {"_id": 0})
    if not user or not user.get("is_active", True):
        # Same response regardless of whether the account exists (or is
        # disabled) — prevents account enumeration via the reset flow, same
        # principle as /login's generic "Invalid email or password".
        return _RESET_REQUESTED_RESPONSE

    now = datetime.now(timezone.utc)
    token = str(uuid.uuid4())
    await db.password_reset_tokens.insert_one({
        "token": token,
        "user_id": user["id"],
        "email": email_lc,
        "practice_id": user.get("practice_id"),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=_PASSWORD_RESET_EXPIRY_HOURS)).isoformat(),
        "used": False,
        "used_at": None,
    })

    await log_security_event(
        "password_reset_requested",
        user_id=user["id"],
        practice_id=user.get("practice_id"),
        ip_address=ip,
    )

    reset_url = f"{_FRONTEND_BASE}/reset-password/{token}"

    # Send reset email — non-fatal, same pattern as invite emails in invite_router.py.
    try:
        practice = None
        if user.get("practice_id"):
            practice = await db.practices.find_one({"id": user["practice_id"]}, {"_id": 0})
        branding = (practice or {}).get("settings", {}).get("branding", {})
        await email_service.send(
            to_email=body.email,
            subject="Reset your Front Desk Dental AI password",
            template_name="password_reset",
            template_vars={
                "reset_url": reset_url,
                "expiry_hours": str(_PASSWORD_RESET_EXPIRY_HOURS),
                "practice_name": (practice or {}).get("name", "your practice"),
            },
            practice_id=user.get("practice_id"),
            practice_branding=branding,
            reply_to=branding.get("reply_to_email"),
        )
    except Exception as e:
        logger.error("request_password_reset: email error", extra={"error": str(e)})

    return _RESET_REQUESTED_RESPONSE


@router.get("/reset-password/{token}")
async def validate_password_reset_token(token: str):
    db = get_db()
    reset_doc = await db.password_reset_tokens.find_one({"token": token}, {"_id": 0})
    if not reset_doc:
        raise HTTPException(status_code=404, detail="Reset link not found")
    if reset_doc.get("used"):
        raise HTTPException(status_code=410, detail="This reset link has already been used")

    expires_at = datetime.fromisoformat(reset_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="This reset link has expired")

    return {"email": reset_doc["email"], "valid": True}


@router.post("/reset-password/{token}")
async def reset_password(token: str, body: PasswordResetConfirm, request: Request):
    db = get_db()
    ip = request.client.host if request.client else None

    reset_doc = await db.password_reset_tokens.find_one({"token": token}, {"_id": 0})
    if not reset_doc:
        raise HTTPException(status_code=404, detail="Reset link not found")
    if reset_doc.get("used"):
        raise HTTPException(status_code=410, detail="This reset link has already been used")

    expires_at = datetime.fromisoformat(reset_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="This reset link has expired")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = await db.users.find_one({"id": reset_doc["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"id": reset_doc["user_id"]},
        {"$set": {"password_hash": hash_password(body.new_password)}},
    )
    await db.password_reset_tokens.update_one(
        {"token": token},
        {"$set": {"used": True, "used_at": now.isoformat()}},
    )

    # No JWT revocation infrastructure exists yet (confirmed during scoping) —
    # any token issued before this reset remains valid until it naturally
    # expires. Logged here so a reset (or attacker-forced reset) is auditable;
    # full session invalidation is a tracked future item, not built here.
    await log_security_event(
        "password_reset_completed",
        user_id=user["id"],
        practice_id=user.get("practice_id"),
        ip_address=ip,
    )

    return {"message": "Password reset successful. Please sign in with your new password."}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return _user_response(current_user)

