# backend/routers/onboarding_router.py
"""Phase 1 Onboarding API — self-service practice provisioning."""
import logging
import uuid
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from models import OnboardingRequest, default_practice_settings
from auth import get_db, hash_password, create_access_token, log_audit_event
from agent.prompt_renderer import render_amanda_prompt
from regions.region_config import derive_region, DB_CLUSTER_LABELS
from config import TERMS_VERSION, PRIVACY_POLICY_VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Your new production domain (optional override)
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")


def _backend_base(request_url: str) -> str:
    """
    Derive https://host from the incoming request for the Retell URL strings.
    Fallback to BACKEND_PUBLIC_URL if set, otherwise use the request host.
    """
    from urllib.parse import urlparse

    # If user has set BACKEND_PUBLIC_URL in .env, always use that
    if BACKEND_PUBLIC_URL:
        return BACKEND_PUBLIC_URL

    # Otherwise derive from incoming request
    p = urlparse(request_url)
    if p.scheme and p.netloc:
        return f"{p.scheme}://{p.netloc}"

    # Last-resort fallback for local dev
    return "http://localhost:8000"


def _function_urls(base: str) -> dict:
    """Retell function endpoints for this practice."""
    return {
        "lookup_patient": f"{base}/api/retell/lookup-patient",
        "list_providers": f"{base}/api/retell/list-providers",
        "check_provider_availability": f"{base}/api/retell/check-provider-availability",
        "book_appointments": f"{base}/api/retell/book-appointment",
        "get_patient_appointments": f"{base}/api/retell/get-patient-appointments",
        "cancel_appointment": f"{base}/api/retell/cancel-appointment",
        "register_patient": f"{base}/api/retell/register-patient",
    }


@router.post("/practice")
async def onboard_practice(req: OnboardingRequest, request: Request):
    """
    Create a practice + admin user in one call.
    Seeds default hours, appointment types, emergency rules, branding.
    Returns a JWT + the rendered Retell setup payload.
    """
    db = get_db()

    # Reject duplicate admin email upfront
    existing_user = await db.users.find_one({"email": req.admin_email})
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate legal version match — reject stale acceptances
    if req.accepted_terms_version != TERMS_VERSION:
        await log_audit_event(
            user_id="system", practice_id=None,
            action="legal_version_mismatch", resource_type="registration",
            details={
                "field": "accepted_terms_version",
                "submitted": req.accepted_terms_version,
                "current": TERMS_VERSION,
            },
        )
        raise HTTPException(
            status_code=400,
            detail=f"Terms version mismatch. Expected {TERMS_VERSION}, got {req.accepted_terms_version}. Please refresh and try again.",
        )
    if req.accepted_privacy_version != PRIVACY_POLICY_VERSION:
        await log_audit_event(
            user_id="system", practice_id=None,
            action="legal_version_mismatch", resource_type="registration",
            details={
                "field": "accepted_privacy_version",
                "submitted": req.accepted_privacy_version,
                "current": PRIVACY_POLICY_VERSION,
            },
        )
        raise HTTPException(
            status_code=400,
            detail=f"Privacy policy version mismatch. Expected {PRIVACY_POLICY_VERSION}, got {req.accepted_privacy_version}. Please refresh and try again.",
        )

    # Extract accepted_ip server-side — never trust client-supplied IP
    accepted_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )

    # Derive data residency from province — raises 400 on invalid code
    try:
        home_region = derive_region(req.province)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    now_iso = datetime.now(timezone.utc).isoformat()
    practice_id = str(uuid.uuid4())

    # Default settings
    defaults = default_practice_settings()
    defaults["hours"]["timezone"] = req.timezone
    defaults["branding"]["greeting"] = (
        f"Thank you for calling {req.practice_name}! This is "
        f"{defaults['branding']['agent_name']}. How can I help today?"
    )

    # Create practice — region fields are set here and are immutable thereafter
    practice_doc = {
        "id": practice_id,
        "name": req.practice_name,
        "contact_email": req.contact_email,
        "contact_phone": req.contact_phone,
        "status": "onboarding",
        "billing_status": "active",
        "subscription_plan": "basic",
        "default_timezone": req.timezone,
        "default_retention_years": 7,
        "settings": defaults,
        "created_at": now_iso,
        # Data residency — immutable after creation
        "province":       req.province.strip().upper(),
        "home_region":    home_region.value,
        "db_cluster":     DB_CLUSTER_LABELS[home_region],
        "compute_region": os.getenv("COMPUTE_REGION", "northamerica-west2"),
        # Legal acceptance — immutable after creation
        "accepted_terms_version":   req.accepted_terms_version,
        "accepted_privacy_version": req.accepted_privacy_version,
        "accepted_at":              req.accepted_at.isoformat(),
        "accepted_ip":              accepted_ip,
    }
    await db.practices.insert_one(practice_doc)

    # Default location
    await db.locations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "practice_id": practice_id,
            "name": "Main Office",
            "timezone": req.timezone,
            "is_active": True,
            "created_at": now_iso,
        }
    )

    # Audit log — practice registration with legal acceptance record
    # Never log: practice name, contact info, or any PHI
    await log_audit_event(
        user_id="system",
        practice_id=practice_id,
        action="practice_registered",
        resource_type="practice",
        resource_id=practice_id,
        details={
            "accepted_terms_version":   req.accepted_terms_version,
            "accepted_privacy_version": req.accepted_privacy_version,
            "accepted_at":              req.accepted_at.isoformat(),
            "accepted_ip":              accepted_ip,
            "province":                 req.province.strip().upper(),
            "home_region":              practice_doc.get("home_region"),
        },
    )

    # Admin user
    admin_id = str(uuid.uuid4())
    await db.users.insert_one(
        {
            "id": admin_id,
            "practice_id": practice_id,
            "email": req.admin_email,
            "password_hash": hash_password(req.admin_password),
            "full_name": req.admin_full_name,
            "role": "admin",
            "created_at": now_iso,
        }
    )

    # Build auth token for immediate login
    token = create_access_token(
        {"sub": admin_id, "practice_id": practice_id, "role": "admin"}
    )

    # Render initial prompt (no providers yet)
    practice_for_render = dict(practice_doc)
    rendered_prompt = render_amanda_prompt(practice_for_render, providers=[])

    # Build URLs using your new domain
    base = _backend_base(str(request.url))
    urls = _function_urls(base)

    return {
        "practice_id": practice_id,
        "admin_user_id": admin_id,
        "access_token": token,
        "token_type": "bearer",
        "status": "onboarding",
        "next_steps": {
            "rendered_prompt": rendered_prompt,
            "function_urls": urls,
            "webhook_url": f"{base}/api/webhooks/retell/{practice_id}",
            "practice_id_to_hardcode": practice_id,
        },
    }


@router.post("/{practice_id}/complete")
async def complete_onboarding(practice_id: str):
    """
    Transition a practice from status='onboarding' to status='active'.
    Called by the wizard's final step once the operator has pasted their
    Retell agent_id + phone_number into config.
    """
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    await db.practices.update_one(
        {"id": practice_id}, {"$set": {"status": "active"}}
    )

    return {"practice_id": practice_id, "status": "active"}
