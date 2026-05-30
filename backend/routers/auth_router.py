from fastapi import APIRouter, HTTPException, Depends, Request
import uuid
from datetime import datetime, timezone
import logging

from models import UserRegister, UserLogin, UserInvite, PracticeCreate
from auth import (
    get_db, hash_password, verify_password, create_access_token,
    get_current_user, require_role, log_audit_event, log_security_event,
)
from plans import enforce_plan_limit
from utils.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


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


@router.post("/register")
async def register(data: UserRegister):
    """Register a new practice admin (creates practice + admin user)"""
    try:
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
            "subscription_plan": "starter",
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
            "plan": "starter",
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


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return _user_response(current_user)


@router.post("/invite")
async def invite_user(invite: UserInvite, current_user: dict = Depends(require_role("admin"))):
    """Admin invites a user to their practice"""
    db = get_db()
    if await db.users.find_one({"email": invite.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    if invite.role not in ["admin", "staff", "provider", "auditor"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    await enforce_plan_limit(db, current_user["practice_id"], "users")

    user_id = str(uuid.uuid4())
    # Default password for invited users (they should change it)
    default_pw = f"Welcome{uuid.uuid4().hex[:6]}!"
    user_doc = {
        "id": user_id,
        "email": invite.email,
        "password_hash": hash_password(default_pw),
        "full_name": invite.full_name,
        "practice_id": current_user["practice_id"],
        "practice_name": current_user.get("practice_name"),
        "provider_id": invite.provider_id,
        "role": invite.role,
        "is_active": True,
        "onboarding_completed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)

    await log_audit_event(
        user_id=current_user["id"], practice_id=current_user["practice_id"],
        action="user_invited", resource_type="user", resource_id=user_id,
        details={"email": invite.email, "role": invite.role}
    )

    return {
        "status": "success",
        "user": _user_response(user_doc),
        "temporary_password": default_pw,
        "message": f"User invited. Temporary password: {default_pw}"
    }
