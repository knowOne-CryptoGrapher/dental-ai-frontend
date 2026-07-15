"""
Admin notification settings and test endpoint.

GET  /api/admin/notifications/settings  — read current settings (with defaults)
POST /api/admin/notifications/settings  — merge-update settings
POST /api/admin/notifications/test      — send a live test email for a given template
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from auth import get_db, require_role
from services.email_service import email_service

router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])

_DEFAULT_SETTINGS: dict = {
    "emergency_alerts": True,
    "new_patient_alerts": True,
    "booking_alerts": True,
    "cancellation_alerts": True,
    "daily_summary": False,
    "billing_alerts": True,
    "plan_change_alerts": True,
    "system_alerts": False,
}

_VALID_KEYS = set(_DEFAULT_SETTINGS.keys())


class NotificationSettingsBody(BaseModel):
    settings: dict


class TestNotificationBody(BaseModel):
    template_name: str


@router.get("/settings")
async def get_notification_settings(
    current_user: dict = Depends(require_role("admin")),
):
    db = get_db()
    practice_id = current_user["practice_id"]
    if not practice_id:
        raise HTTPException(status_code=403, detail="Practice scope required")
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0, "settings": 1}) or {}
    saved = (practice.get("settings") or {}).get("email_notifications") or {}
    return {**_DEFAULT_SETTINGS, **saved}


@router.post("/settings")
async def update_notification_settings(
    body: NotificationSettingsBody,
    current_user: dict = Depends(require_role("admin")),
):
    unknown = set(body.settings.keys()) - _VALID_KEYS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown notification keys: {sorted(unknown)}")
    non_bool = {k: v for k, v in body.settings.items() if not isinstance(v, bool)}
    if non_bool:
        raise HTTPException(status_code=422, detail=f"All values must be boolean: {list(non_bool)}")

    db = get_db()
    practice_id = current_user["practice_id"]
    if not practice_id:
        raise HTTPException(status_code=403, detail="Practice scope required")

    patch = {f"settings.email_notifications.{k}": v for k, v in body.settings.items()}
    await db.practices.update_one({"id": practice_id}, {"$set": patch})

    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0, "settings": 1}) or {}
    saved = (practice.get("settings") or {}).get("email_notifications") or {}
    return {**_DEFAULT_SETTINGS, **saved}


@router.post("/test")
async def test_notification(
    body: TestNotificationBody,
    current_user: dict = Depends(require_role("admin")),
):
    db = get_db()
    practice_id = current_user["practice_id"]
    if not practice_id:
        raise HTTPException(status_code=403, detail="Practice scope required")

    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0}) or {}
    admin_email = (practice.get("settings") or {}).get("admin_email") or current_user.get("email")
    if not admin_email:
        raise HTTPException(status_code=422, detail="No admin email configured for this practice")

    practice_name = practice.get("name", "Your Practice")
    frontend_url = "https://app.dentalai.ca"

    sent = await email_service.send_admin_notification(
        db=db,
        practice_id=practice_id,
        admin_email=admin_email,
        template_name=body.template_name,
        subject=f"[TEST] Dental AI — {body.template_name}",
        template_vars={
            "practice_name": practice_name,
            "caller_phone": "+1-555-000-0000",
            "emergency_type": "Test Emergency",
            "transcript_excerpt": "This is a test notification from Dental AI.",
            "call_time": "2026-07-14 12:00 UTC",
            "patient_name": "Test Patient",
            "patient_phone": "+1-555-000-0001",
            "appointment_date": "2026-07-15",
            "appointment_time": "10:00 AM",
            "provider_name": "Dr. Test",
            "reason": "Cleaning",
            "registered_at": "2026-07-14 12:00 UTC",
            "plan_name": "Professional",
            "old_plan": "Basic",
            "new_plan": "Professional",
            "effective_date": "2026-07-14",
            "amount_due": "See billing portal",
            "due_date": "Please update your payment method",
            "portal_url": f"{frontend_url}/billing",
            "summary_date": "2026-07-14",
            "total_calls": "5",
            "appointments_booked": "3",
            "new_patients": "1",
            "emergencies": "0",
            "dashboard_url": f"{frontend_url}/dashboard",
        },
        practice_branding=practice.get("settings"),
    )
    return {"sent": sent, "to": email_service._mask(admin_email)}
