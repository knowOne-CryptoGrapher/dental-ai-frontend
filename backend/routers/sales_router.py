"""
POST /api/sales/contact — public top-of-funnel lead capture.

No authentication required: this is a pre-signup endpoint.
Inserts into sales_leads collection and fires an internal notification email.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from auth import get_db
from models import SalesContactRequest
from services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sales", tags=["sales"])

SALES_NOTIFY_EMAIL = os.getenv("SALES_NOTIFY_EMAIL", "sales@dentalai.ca")


class FoundingClinicRequest(BaseModel):
    name: str
    clinic_name: str
    email: EmailStr
    phone: str
    province: str = "BC"


@router.post("/contact")
async def sales_contact(body: SalesContactRequest, request: Request):
    """
    Accept an inbound sales lead from the Contact Sales form.
    Public endpoint — no JWT required.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    lead_id = str(uuid.uuid4())

    lead_doc = {
        "id":             lead_id,
        "name":           body.name,
        "email":          body.email,
        "phone":          body.phone,
        "province":       body.province,
        "country":        body.country,
        "clinic_size":    body.clinic_size,
        "message":        body.message,
        "requested_plan": body.requested_plan,
        "created_at":     now.isoformat(),
        "status":         "new",
        "source_ip": (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        ),
    }

    try:
        await db.sales_leads.insert_one(lead_doc)
    except Exception as exc:
        logger.error("sales_lead_insert_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to save lead")

    subject = (
        f"[New Lead] {body.requested_plan.title()} — "
        f"{body.name} ({body.clinic_size} locations)"
    )
    body_text = (
        f"New Contact Sales lead\n"
        f"{'─' * 40}\n"
        f"Name:          {body.name}\n"
        f"Email:         {body.email}\n"
        f"Phone:         {body.phone or 'not provided'}\n"
        f"Clinic size:   {body.clinic_size}\n"
        f"Plan interest: {body.requested_plan}\n"
        f"Message:       {body.message or 'none'}\n"
        f"{'─' * 40}\n"
        f"Lead ID: {lead_id}\n"
        f"Created: {now.isoformat()}\n"
    )

    ok = await email_service.send_internal_notification(
        to_email=SALES_NOTIFY_EMAIL,
        subject=subject,
        body_text=body_text,
    )
    if not ok:
        logger.warning("sales_lead_notification_failed", extra={"lead_id": lead_id})

    return {"success": True, "lead_id": lead_id}


@router.post("/founding-clinic")
async def submit_founding_clinic(request: FoundingClinicRequest):
    """
    Accept a Founding Clinic program application.
    Public endpoint — no JWT required. Capped at 10 non-rejected applications.
    """
    db = get_db()

    count = await db.founding_clinic_applications.count_documents({"status": {"$ne": "rejected"}})
    if count >= 10:
        raise HTTPException(status_code=409, detail="All founding clinic spots are taken")

    existing = await db.founding_clinic_applications.find_one({"email": request.email})
    if existing:
        raise HTTPException(status_code=409, detail="This email has already applied")

    doc = {
        "id": str(uuid.uuid4()),
        "name": request.name,
        "clinic_name": request.clinic_name,
        "email": request.email,
        "phone": request.phone,
        "province": request.province,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.founding_clinic_applications.insert_one(doc)

    try:
        await email_service.send_internal_notification(
            to_email=SALES_NOTIFY_EMAIL,
            subject=f"New Founding Clinic Application — {request.clinic_name}",
            body_text=(
                f"New founding clinic application:\n\n"
                f"Clinic: {request.clinic_name}\n"
                f"Name: {request.name}\n"
                f"Email: {request.email}\n"
                f"Phone: {request.phone}\n"
                f"Province: {request.province}\n\n"
                f"Spots taken: {count + 1}/10"
            ),
        )
    except Exception as e:
        logger.error("founding_clinic_notify_failed", extra={"error": str(e)})

    return {
        "success": True,
        "message": "Application received — we'll be in touch within 24 hours.",
        "spots_remaining": max(0, 10 - (count + 1)),
    }


@router.get("/founding-clinic-count")
async def get_founding_clinic_count():
    """Public endpoint — spots remaining in the Founding Clinic program."""
    db = get_db()
    count = await db.founding_clinic_applications.count_documents({"status": {"$ne": "rejected"}})
    return {"spots_taken": count, "spots_remaining": max(0, 10 - count), "is_full": count >= 10}
