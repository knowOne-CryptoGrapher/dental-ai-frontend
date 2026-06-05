"""
Multi-tenant staff invite system.

Endpoints
---------
POST /api/practices/{practice_id}/staff/invite  — admin only, creates a token
GET  /api/practices/{practice_id}/staff/invites — admin only, lists pending invites
GET  /api/invite/{token}                        — public, validates invite
POST /api/invite/{token}/complete               — public, completes signup
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request

from models import InviteCreate, InviteComplete
from auth import get_db, require_role, log_audit_event, hash_password, create_access_token
from config import TERMS_VERSION, PRIVACY_POLICY_VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["invites"])

_ALLOWED_ROLES = {"staff", "provider", "auditor"}
_INVITE_EXPIRY_HOURS = 24
_FRONTEND_BASE = os.getenv("FRONTEND_BASE_URL", "https://app.frontdeskdentalai.com")


def _ensure_practice_access(current_user: dict, practice_id: str) -> None:
    if current_user.get("role") == "super_admin":
        return
    if current_user.get("practice_id") != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")


async def _get_practice_or_404(db, practice_id: str) -> dict:
    doc = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Practice not found")
    return doc


# ── Admin: create invite ─────────────────────────────────────────────────────

@router.post("/practices/{practice_id}/staff/invite")
async def create_invite(
    practice_id: str,
    body: InviteCreate,
    request: Request,
    current_user: dict = Depends(require_role("admin", "super_admin")),
):
    _ensure_practice_access(current_user, practice_id)

    if body.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(sorted(_ALLOWED_ROLES))}",
        )

    db = get_db()
    practice = await _get_practice_or_404(db, practice_id)

    email_lc = body.email.lower()
    existing = await db.users.find_one(
        {"email": email_lc, "practice_id": practice_id, "is_active": True},
        {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="An active user with this email already exists in this practice"
        )

    now = datetime.now(timezone.utc)
    token = str(uuid.uuid4())
    invite_doc = {
        "token": token,
        "practice_id": practice_id,
        "email": email_lc,
        "role": body.role,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=_INVITE_EXPIRY_HOURS)).isoformat(),
        "used": False,
        "used_at": None,
        "created_by": current_user["id"],
    }
    await db.invite_tokens.insert_one(invite_doc)

    await db.ai_safety_logs.insert_one({
        "event_type": "staff_invite_created",
        "actor_id": current_user["id"],
        "target_email": email_lc,
        "practice_id": practice_id,
        "role": body.role,
        "token": token,
        "created_at": now.isoformat(),
    })

    await log_audit_event(
        current_user["id"], practice_id, "staff_invite_created",
        "invite_token", token,
        {"target_email": email_lc, "role": body.role},
        request.client.host if request.client else None,
    )

    invite_url = f"{_FRONTEND_BASE}/invite/{token}"
    return {
        "invite_url": invite_url,
        "token": token,
        "expires_in_hours": _INVITE_EXPIRY_HOURS,
        "practice_name": practice.get("name"),
    }


# ── Admin: list pending invites ───────────────────────────────────────────────

@router.get("/practices/{practice_id}/staff/invites")
async def list_invites(
    practice_id: str,
    current_user: dict = Depends(require_role("admin", "super_admin")),
):
    _ensure_practice_access(current_user, practice_id)
    db = get_db()
    await _get_practice_or_404(db, practice_id)

    now_iso = datetime.now(timezone.utc).isoformat()
    invites = await db.invite_tokens.find(
        {
            "practice_id": practice_id,
            "used": False,
            "expires_at": {"$gt": now_iso},
        },
        {"_id": 0, "token": 1, "email": 1, "role": 1, "created_at": 1, "expires_at": 1},
    ).sort("created_at", -1).to_list(100)

    return invites


# ── Public: validate invite ───────────────────────────────────────────────────

@router.get("/invite/{token}")
async def validate_invite(token: str):
    db = get_db()
    invite = await db.invite_tokens.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.get("used"):
        raise HTTPException(status_code=410, detail="This invite link has already been used")

    expires_at = datetime.fromisoformat(invite["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="This invite link has expired")

    practice = await db.practices.find_one(
        {"id": invite["practice_id"]}, {"_id": 0, "name": 1, "status": 1}
    )
    if not practice or practice.get("status") == "cancelled":
        raise HTTPException(status_code=404, detail="Practice not found")

    return {
        "email": invite["email"],
        "role": invite["role"],
        "practice_name": practice["name"],
        "valid": True,
    }


# ── Public: complete signup ───────────────────────────────────────────────────

@router.post("/invite/{token}/complete")
async def complete_invite(token: str, body: InviteComplete, request: Request):
    db = get_db()
    invite = await db.invite_tokens.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.get("used"):
        raise HTTPException(status_code=410, detail="This invite link has already been used")

    expires_at = datetime.fromisoformat(invite["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="This invite link has expired")

    if body.accepted_terms_version != TERMS_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Must accept current Terms of Service version {TERMS_VERSION}",
        )
    if body.accepted_privacy_version != PRIVACY_POLICY_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Must accept current Privacy Policy version {PRIVACY_POLICY_VERSION}",
        )

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if not body.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")

    practice = await _get_practice_or_404(db, invite["practice_id"])

    existing = await db.users.find_one(
        {"email": invite["email"], "practice_id": invite["practice_id"]},
        {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())
    new_user = {
        "id": user_id,
        "email": invite["email"],
        "full_name": body.full_name.strip(),
        "password_hash": hash_password(body.password),
        "role": invite["role"],
        "practice_id": invite["practice_id"],
        "practice_name": practice.get("name"),
        "is_active": True,
        "onboarding_completed": True,
        # Residency — inherited from practice, immutable after creation
        "province": practice.get("province"),
        "home_region": practice.get("home_region"),
        "db_cluster": practice.get("db_cluster"),
        # Legal acceptance
        "accepted_terms_version": body.accepted_terms_version,
        "accepted_privacy_version": body.accepted_privacy_version,
        "accepted_at": now.isoformat(),
        "created_at": now.isoformat(),
        "invite_token": token,
    }
    await db.users.insert_one(new_user)

    await db.invite_tokens.update_one(
        {"token": token},
        {"$set": {"used": True, "used_at": now.isoformat()}},
    )

    await db.ai_safety_logs.insert_one({
        "event_type": "staff_invite_completed",
        "user_id": user_id,
        "practice_id": invite["practice_id"],
        "role": invite["role"],
        "created_at": now.isoformat(),
    })

    await log_audit_event(
        user_id, invite["practice_id"], "staff_invite_completed",
        "user", user_id,
        {"role": invite["role"]},
        request.client.host if request.client else None,
    )

    access_token = create_access_token({
        "sub": user_id,
        "practice_id": invite["practice_id"],
        "role": invite["role"],
    })

    user_response = {
        k: v for k, v in new_user.items()
        if k not in ("password_hash", "_id", "invite_token")
    }
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response,
    }
