"""
Super-admin only platform management.

Owner-of-the-software endpoints for the Platform Console:
  - Manage practices (create, update, suspend, activate, delete)
  - Retell agent provisioning (create agent, upload prompt + functions,
    buy phone number; Phase 2 SDK integration pending)
  - Platform dashboard metrics (practice count, calls, etc.)

Practice admins/staff/providers cannot reach any of these routes (403).
"""
import os
import uuid
import logging
import hashlib
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field

from auth import get_db, require_role, hash_password, create_access_token, log_audit_event
from agent.prompt_renderer import render_amanda_prompt
from models import default_practice_settings
from plans import is_valid_plan_id, list_plans, get_plan, DEFAULT_PLAN_ID
from regions.region_config import derive_region, DB_CLUSTER_LABELS
from services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])

RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "")


def _function_urls(base: str) -> dict:
    return {
        "lookup_patient":              f"{base}/api/retell/lookup-patient",
        "list_providers":              f"{base}/api/retell/list-providers",
        "check_provider_availability": f"{base}/api/retell/check-provider-availability",
        "book_appointment":            f"{base}/api/retell/book-appointment",
        "get_patient_appointments":    f"{base}/api/retell/get-patient-appointments",
        "cancel_appointment":          f"{base}/api/retell/cancel-appointment",
        "register_patient":            f"{base}/api/retell/register-patient",
        "get_practice_context":        f"{base}/api/retell/practice-context",
        "query_knowledge_base":        f"{base}/api/knowledge/query",
        "ingest_call_summary":         f"{base}/api/retell/call-summary",
    }


def _backend_base() -> str:
    return os.environ.get(
        "PUBLIC_BACKEND_URL",
        "https://dental-ai-backend-cszmxu7emq-uw.a.run.app",
    )


# ──────────────────────────────────────────────────────────────────────
# List all practices (for the picker)
# ──────────────────────────────────────────────────────────────────────

@router.get("/practices")
async def list_all_practices(
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    practices = await db.practices.find({}, {"_id": 0}).to_list(1000)
    out = []
    for p in practices:
        retell = (p.get("settings") or {}).get("retell") or {}
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "status": p.get("status", "active"),
            "subscription_plan": p.get("subscription_plan") or DEFAULT_PLAN_ID,
            "billing_status": p.get("billing_status", "active"),
            "stripe_customer_id": p.get("stripe_customer_id"),
            "contact_email": p.get("contact_email"),
            "created_at": p.get("created_at"),
            "retell_provisioned": bool(retell.get("agent_id")),
            "retell_agent_id": retell.get("agent_id"),
            "retell_phone_number": retell.get("phone_number"),
        })
    out.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return {"count": len(out), "practices": out}


# ──────────────────────────────────────────────────────────────────────
# Read full Retell config for one practice
# ──────────────────────────────────────────────────────────────────────

@router.get("/practices/{practice_id}/retell")
async def get_retell_config(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    providers = await db.providers.find(
        {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]},
        {"_id": 0}
    ).to_list(100)
    rendered_prompt = render_amanda_prompt(practice, providers)
    prompt_hash = hashlib.sha256(rendered_prompt.encode()).hexdigest()[:12]

    retell = (practice.get("settings") or {}).get("retell") or {}
    base = _backend_base()
    return {
        "practice_id": practice_id,
        "practice_name": practice.get("name"),
        "status": practice.get("status"),
        "agent_id": retell.get("agent_id"),
        "phone_number": retell.get("phone_number"),
        "provisioned_at": retell.get("provisioned_at"),
        "rendered_prompt": rendered_prompt,
        "prompt_hash": prompt_hash,
        "function_urls": _function_urls(base),
        "webhook_url": f"{base}/api/webhooks/retell/{practice_id}",
        "automation_available": bool(RETELL_API_KEY),
    }


# ──────────────────────────────────────────────────────────────────────
# Manual save (for the rare case super-admin wants to edit by hand)
# ──────────────────────────────────────────────────────────────────────

@router.put("/practices/{practice_id}/retell")
async def update_retell_config(
    practice_id: str,
    body: dict,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0, "id": 1})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    retell_update = {
        "agent_id": body.get("agent_id"),
        "phone_number": body.get("phone_number"),
        "provisioned_at": body.get("provisioned_at") or datetime.now(timezone.utc).isoformat(),
    }
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.retell": retell_update}},
    )
    return retell_update


# ──────────────────────────────────────────────────────────────────────
# Automation — provision a brand new Retell agent for a practice
# ──────────────────────────────────────────────────────────────────────

@router.post("/practices/{practice_id}/retell/provision")
async def provision_retell_agent(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    """
    Full automation: create Retell agent, upload prompt, register all 7
    custom functions, set webhook URL, buy phone number, link it, and
    save agent_id + phone to practice settings.

    Phase 2: requires RETELL_API_KEY in backend env. Until then this
    endpoint returns a clear "not configured" response so the UI can
    fall back to manual setup.
    """
    if not RETELL_API_KEY:
        raise HTTPException(
            status_code=501,
            detail=(
                "Retell automation not configured. Set RETELL_API_KEY in "
                "backend/.env and restart the backend. Until then, use the "
                "manual setup flow shown on this page."
            ),
        )
    # Phase 2 implementation seam — see /app/docs/PHASE_1_PLAN.md
    raise HTTPException(
        status_code=501,
        detail="Retell SDK integration pending — Phase 2 implementation."
    )


@router.post("/practices/{practice_id}/retell/resync")
async def resync_retell_agent(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    """Push the latest rendered prompt + function URLs to an existing
    Retell agent. Used when practice config changes (new providers,
    updated hours, etc.). Phase 2 implementation seam."""
    if not RETELL_API_KEY:
        raise HTTPException(
            status_code=501,
            detail="Retell automation not configured. Set RETELL_API_KEY in backend/.env."
        )
    raise HTTPException(
        status_code=501,
        detail="Retell SDK integration pending — Phase 2 implementation."
    )


# ──────────────────────────────────────────────────────────────────────
# PLATFORM CONSOLE — Practice management (create / update / suspend)
# ──────────────────────────────────────────────────────────────────────


class PracticeCreatePayload(BaseModel):
    practice_name: str = Field(..., min_length=2, max_length=120)
    province: str = Field(..., min_length=2, max_length=2, description="Two-letter Canadian province code")
    contact_email: EmailStr
    contact_phone: str | None = None
    timezone: str = "America/Toronto"
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8)
    admin_full_name: str = Field(..., min_length=2, max_length=120)


_IMMUTABLE_PRACTICE_FIELDS = {
    "home_region", "db_cluster", "compute_region", "province",
    "accepted_terms_version", "accepted_privacy_version", "accepted_at", "accepted_ip",
}


class PracticeUpdatePayload(BaseModel):
    name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    status: str | None = None  # 'active' | 'suspended' | 'onboarding'
    subscription_plan: str | None = None


@router.post("/practices", status_code=201)
async def create_practice(
    payload: PracticeCreatePayload,
    current_user: dict = Depends(require_role("super_admin")),
):
    """Super-admin creates a brand-new practice + its first admin user.
    The practice starts in 'onboarding' status so the admin lands on the
    wizard at first login. Idempotent on admin_email (409 if taken)."""
    db = get_db()

    if await db.users.find_one({"email": payload.admin_email}):
        raise HTTPException(status_code=409, detail="Admin email already registered")

    now_iso = datetime.now(timezone.utc).isoformat()
    practice_id = str(uuid.uuid4())

    defaults = default_practice_settings()
    defaults["hours"]["timezone"] = payload.timezone
    defaults["branding"]["greeting"] = (
        f"Thank you for calling {payload.practice_name}! This is "
        f"{defaults['branding']['agent_name']}. How can I help today?"
    )

    # Derive data residency from province
    try:
        home_region = derive_region(payload.province)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    practice_doc = {
        "id": practice_id,
        "name": payload.practice_name,
        "contact_email": payload.contact_email,
        "contact_phone": payload.contact_phone,
        "status": "onboarding",
        "billing_status": "active",
        "subscription_plan": DEFAULT_PLAN_ID,
        "default_timezone": payload.timezone,
        "default_retention_years": 7,
        "settings": defaults,
        "created_at": now_iso,
        "created_by_super_admin": current_user.get("id"),
        # Data residency — immutable after creation
        "province":       payload.province.strip().upper(),
        "home_region":    home_region.value,
        "db_cluster":     DB_CLUSTER_LABELS[home_region],
        "compute_region": os.getenv("COMPUTE_REGION", "northamerica-west2"),
    }
    await db.practices.insert_one(practice_doc)

    await db.locations.insert_one({
        "id": str(uuid.uuid4()),
        "practice_id": practice_id,
        "name": "Main Office",
        "timezone": payload.timezone,
        "is_active": True,
        "created_at": now_iso,
    })

    admin_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": admin_id,
        "practice_id": practice_id,
        "practice_name": payload.practice_name,
        "email": payload.admin_email,
        "password_hash": hash_password(payload.admin_password),
        "full_name": payload.admin_full_name,
        "role": "admin",
        "is_active": True,
        "onboarding_completed": False,
        "created_at": now_iso,
    })

    return {
        "practice_id": practice_id,
        "name": payload.practice_name,
        "status": "onboarding",
        "admin_email": payload.admin_email,
        "admin_user_id": admin_id,
    }


@router.patch("/practices/{practice_id}")
async def update_practice(
    practice_id: str,
    payload: PracticeUpdatePayload,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0, "id": 1})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Region fields are immutable after practice creation
    attempted_immutable = set(update.keys()) & _IMMUTABLE_PRACTICE_FIELDS
    if attempted_immutable:
        raise HTTPException(
            status_code=400,
            detail=f"Fields are immutable after practice creation: {sorted(attempted_immutable)}",
        )

    if "status" in update and update["status"] not in {"active", "suspended", "onboarding"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    if "subscription_plan" in update and not is_valid_plan_id(update["subscription_plan"]):
        valid = ", ".join(p.id for p in list_plans())
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {valid}")

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.practices.update_one({"id": practice_id}, {"$set": update})

    # If suspending, also disable all users so they can't log in
    if update.get("status") == "suspended":
        await db.users.update_many(
            {"practice_id": practice_id},
            {"$set": {"is_active": False}},
        )
    elif update.get("status") == "active":
        await db.users.update_many(
            {"practice_id": practice_id},
            {"$set": {"is_active": True}},
        )

    return {"practice_id": practice_id, **update}


# ──────────────────────────────────────────────────────────────────────
# Sales lead approval queue
# ──────────────────────────────────────────────────────────────────────

@router.get("/leads")
async def list_leads(
    status: Optional[str] = None,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    leads = await db.sales_leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"count": len(leads), "leads": leads}


@router.post("/leads/{lead_id}/approve")
async def approve_lead(
    lead_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    lead = await db.sales_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.get("status") != "new":
        raise HTTPException(status_code=400, detail=f"Lead is already {lead.get('status')}")

    # Derive data residency. lead.province is free text from the contact form
    # (not validated against Canadian codes) — falls back to BC/ca-west for
    # unrecognised or non-Canadian input. No US/other-region support exists
    # elsewhere in this codebase today.
    try:
        home_region = derive_region(lead.get("province") or "BC")
    except ValueError:
        home_region = derive_region("BC")

    practice_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    practice_doc = {
        "id": practice_id,
        "name": lead.get("name") + " Dental",
        "contact_email": lead.get("email"),
        "contact_phone": lead.get("phone"),
        "status": "onboarding",
        "billing_status": "active",
        "subscription_plan": lead.get("requested_plan", "professional"),
        "default_timezone": "America/Toronto",
        "default_retention_years": 7,
        "settings": default_practice_settings(),
        "created_at": now,
        "created_by_super_admin": current_user.get("id"),
        # Data residency — immutable after creation (mirrors create_practice above)
        "province":       (lead.get("province") or "BC").strip().upper(),
        "country":        lead.get("country") or "CA",
        "home_region":    home_region.value,
        "db_cluster":     DB_CLUSTER_LABELS[home_region],
        "compute_region": os.getenv("COMPUTE_REGION", "northamerica-west2"),
    }
    await db.practices.insert_one(practice_doc)

    await db.locations.insert_one({
        "id": str(uuid.uuid4()),
        "practice_id": practice_id,
        "name": "Main Office",
        "timezone": "America/Toronto",
        "is_active": True,
        "created_at": now,
    })

    # Send invite email to lead so they set their own password
    try:
        invite_token = str(uuid.uuid4())
        expire_at = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
        await db.invite_tokens.insert_one({
            "token": invite_token,
            "practice_id": practice_id,
            "email": lead.get("email"),
            "role": "admin",
            "created_at": now,
            "expires_at": expire_at,
            "used": False,
            "used_at": None,
            "created_by": current_user.get("id"),
        })
        frontend_base = os.getenv("FRONTEND_BASE_URL", "https://frontdeskdentalai.com")
        invite_url = f"{frontend_base}/invite/{invite_token}"
        # send_internal_notification is documented as internal-team-only (skips
        # the suppression list) — used here because send() requires a
        # practice-scoped template and none exists yet for lead approval.
        await email_service.send_internal_notification(
            to_email=lead.get("email"),
            subject="You're approved — set up your Dental AI account",
            body_text=(
                f"Hi {lead.get('name')},\n\n"
                f"Your Dental AI account has been approved.\n\n"
                f"Click the link below to set your password and access your dashboard:\n\n"
                f"{invite_url}\n\n"
                f"This link expires in 72 hours.\n\n"
                f"Welcome aboard,\nThe Dental AI Team"
            ),
        )
    except Exception as e:
        logger.error("approve_lead_invite_error", extra={"lead_id": lead_id, "error": str(e)})

    await db.sales_leads.update_one(
        {"id": lead_id},
        {"$set": {
            "status": "approved",
            "practice_id": practice_id,
            "approved_at": now,
            "approved_by": current_user.get("id"),
        }},
    )
    return {"success": True, "practice_id": practice_id, "invite_sent_to": lead.get("email")}


@router.post("/leads/{lead_id}/deny")
async def deny_lead(
    lead_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    db = get_db()
    lead = await db.sales_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.get("status") != "new":
        raise HTTPException(status_code=400, detail=f"Lead is already {lead.get('status')}")

    try:
        # See note above on send_internal_notification's suppression-list caveat.
        await email_service.send_internal_notification(
            to_email=lead.get("email"),
            subject="Your Dental AI application",
            body_text=(
                f"Hi {lead.get('name')},\n\n"
                f"Thank you for your interest in Dental AI.\n\n"
                f"After reviewing your application, we're unable to move forward at this time. "
                f"We appreciate you reaching out and encourage you to apply again in the future.\n\n"
                f"Best regards,\nThe Dental AI Team"
            ),
        )
    except Exception as e:
        logger.error("deny_lead_email_error", extra={"lead_id": lead_id, "error": str(e)})

    now = datetime.now(timezone.utc).isoformat()
    await db.sales_leads.update_one(
        {"id": lead_id},
        {"$set": {"status": "denied", "denied_at": now, "denied_by": current_user.get("id")}}
    )
    return {"success": True, "denied": lead_id}


@router.post("/practices/{practice_id}/suspend")
async def suspend_practice(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    return await update_practice(
        practice_id, PracticeUpdatePayload(status="suspended"), current_user
    )


@router.post("/practices/{practice_id}/activate")
async def activate_practice(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    return await update_practice(
        practice_id, PracticeUpdatePayload(status="active"), current_user
    )


# ──────────────────────────────────────────────────────────────────────
# PLATFORM CONSOLE — Dashboard metrics
# ──────────────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def platform_dashboard(
    current_user: dict = Depends(require_role("super_admin")),
):
    """Top-line platform metrics for the super-admin dashboard."""
    db = get_db()

    total_practices = await db.practices.count_documents({})
    active_practices = await db.practices.count_documents({"status": "active"})
    onboarding_practices = await db.practices.count_documents({"status": "onboarding"})
    suspended_practices = await db.practices.count_documents({"status": "suspended"})

    provisioned = await db.practices.count_documents({"settings.retell.agent_id": {"$ne": None, "$exists": True}})

    # Failed-payments widget: practices currently in past_due or cancelled
    past_due = await db.practices.find(
        {"billing_status": {"$in": ["past_due", "cancelled"]}},
        {"_id": 0, "id": 1, "name": 1, "billing_status": 1, "subscription_plan": 1,
         "stripe_customer_id": 1, "billing_status_updated_at": 1, "last_payment_at": 1,
         "contact_email": 1},
    ).sort("billing_status_updated_at", -1).limit(20).to_list(20)

    past_due_count = await db.practices.count_documents({"billing_status": "past_due"})
    cancelled_count = await db.practices.count_documents({"billing_status": "cancelled"})

    # Plan distribution
    plan_pipeline = [
        {"$match": {"status": {"$ne": "onboarding"}}},
        {"$group": {"_id": {"$ifNull": ["$subscription_plan", "basic"]}, "n": {"$sum": 1}}},
    ]
    plan_rows = await db.practices.aggregate(plan_pipeline).to_list(20)
    plan_distribution = {r["_id"] or "basic": r["n"] for r in plan_rows}

    total_patients = await db.patients.count_documents({})
    total_appointments = await db.appointments.count_documents({})
    total_users = await db.users.count_documents({})

    # Calls in past 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    calls_30d = await db.call_logs.count_documents({"created_at": {"$gte": cutoff}})

    # Recent practices (5 most recent)
    recent = await db.practices.find({}, {"_id": 0, "id": 1, "name": 1, "status": 1, "created_at": 1, "settings.retell.agent_id": 1}).sort("created_at", -1).limit(5).to_list(5)
    recent_out = []
    for p in recent:
        retell = (p.get("settings") or {}).get("retell") or {}
        recent_out.append({
            "id": p["id"],
            "name": p.get("name"),
            "status": p.get("status"),
            "created_at": p.get("created_at"),
            "retell_provisioned": bool(retell.get("agent_id")),
        })

    return {
        "practices": {
            "total": total_practices,
            "active": active_practices,
            "onboarding": onboarding_practices,
            "suspended": suspended_practices,
            "retell_provisioned": provisioned,
            "past_due": past_due_count,
            "cancelled_subscriptions": cancelled_count,
        },
        "plan_distribution": plan_distribution,
        "platform": {
            "total_patients": total_patients,
            "total_appointments": total_appointments,
            "total_users": total_users,
            "calls_last_30_days": calls_30d,
        },
        "recent_practices": recent_out,
        "failed_payments": past_due,
        "automation_available": bool(RETELL_API_KEY),
    }


# ──────────────────────────────────────────────────────────────────────
# PLATFORM CONSOLE — Impersonate a practice (support / debugging)
# ──────────────────────────────────────────────────────────────────────


@router.post("/practices/{practice_id}/impersonate")
async def impersonate_practice(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    """Issue a short-lived JWT for the practice's first admin user so
    the super-admin can drop into that clinic's UI for support /
    debugging. The JWT carries an `impersonated_by` claim so the UI
    can render a persistent banner + Exit button. Audit-logged."""
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    if practice.get("status") == "suspended":
        raise HTTPException(status_code=400, detail="Cannot impersonate a suspended practice. Activate it first.")

    target = await db.users.find_one(
        {"practice_id": practice_id, "role": "admin"},
        {"_id": 0, "password_hash": 0},
        sort=[("created_at", 1)],
    )
    if not target:
        raise HTTPException(status_code=404, detail="Practice has no admin user to impersonate")

    token = create_access_token(
        data={
            "sub": target["id"],
            "practice_id": practice_id,
            "role": target.get("role", "admin"),
            "impersonated_by": current_user.get("id"),
            "impersonator_email": current_user.get("email"),
        },
        expires_delta=timedelta(hours=1),
    )

    await log_audit_event(
        user_id=current_user.get("id"),
        practice_id=practice_id,
        action="practice_impersonated",
        resource_type="practice",
        resource_id=practice_id,
        details={
            "impersonator_email": current_user.get("email"),
            "target_user_id": target["id"],
            "target_user_email": target.get("email"),
        },
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_seconds": 3600,
        "target_practice": {
            "id": practice_id,
            "name": practice.get("name"),
        },
        "target_user": {
            "id": target["id"],
            "email": target.get("email"),
            "full_name": target.get("full_name"),
            "role": target.get("role"),
        },
    }



# ──────────────────────────────────────────────────────────────────────
# PLATFORM CONSOLE — Plans & manual plan override
# ──────────────────────────────────────────────────────────────────────


@router.get("/plans")
async def superadmin_list_plans(current_user: dict = Depends(require_role("super_admin"))):
    """List all plan tiers w/ features for the plan selector UI."""
    return [p.public_dict() for p in list_plans()]


@router.post("/practices/{practice_id}/plan")
async def set_practice_plan(
    practice_id: str,
    body: dict,
    current_user: dict = Depends(require_role("super_admin")),
):
    """Manually set a practice's plan (super-admin override).
    Stripe is the source of truth in normal operation, but this allows
    the platform owner to grant comp accounts, downgrade for non-payment,
    or fix data while a Stripe webhook is pending."""
    db = get_db()
    plan_id = (body.get("plan_id") or "").lower()
    if not is_valid_plan_id(plan_id):
        valid = ", ".join(p.id for p in list_plans())
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {valid}")

    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0, "subscription_plan": 1})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    old_plan = practice.get("subscription_plan", DEFAULT_PLAN_ID)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {
            "subscription_plan": plan_id,
            "plan_updated_at": now_iso,
            "plan_updated_by": current_user.get("email"),
        }},
    )
    await log_audit_event(
        user_id=current_user.get("id"),
        practice_id=practice_id,
        action="practice_plan_changed",
        resource_type="practice",
        resource_id=practice_id,
        details={
            "old_plan": old_plan,
            "new_plan": plan_id,
            "manual_override": True,
            "by_super_admin": current_user.get("email"),
            "reason": body.get("reason"),
        },
    )
    plan = get_plan(plan_id)
    return {
        "practice_id": practice_id,
        "old_plan": old_plan,
        "new_plan": plan_id,
        "plan_name": plan.name,
        "updated_at": now_iso,
    }
