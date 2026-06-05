from fastapi import APIRouter, HTTPException, Depends, Request
import uuid
from datetime import datetime, timezone
import logging

from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError

from models import AppointmentCreate, ManualAppointmentCreate
from auth import get_db, get_current_user, require_role, log_audit_event, log_analytics_event, detect_emergency

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["appointments"])


def _booking_key(practice_id: str, provider_id: str, date: str, time: str) -> str:
    """Slot-lock key stored on active appointments.

    A unique sparse index on this field (see scripts/add_booking_key_index.py)
    makes the conflict check atomic at the storage layer: two concurrent
    inserts with the same key cannot both succeed — only one gets written,
    the other raises MongoDuplicateKeyError which we map to HTTP 409.
    """
    return f"{practice_id}|{provider_id}|{date}|{time}"


@router.get("/appointments")
async def get_appointments(
    status: str = None, provider_id: str = None, location_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    query = {"practice_id": practice_id}
    if status:
        query["status"] = status
    if provider_id:
        query["provider_id"] = provider_id
    if location_id:
        query["location_id"] = location_id
    if current_user.get("role") == "provider" and current_user.get("provider_id"):
        query["provider_id"] = current_user["provider_id"]
    return await db.appointments.find(query, {"_id": 0}).sort("appointment_date", 1).to_list(2000)


@router.post("/appointments")
async def create_appointment(apt: AppointmentCreate, current_user: dict = Depends(get_current_user)):
    from utils.provider_scheduling import validate_provider_availability, check_provider_conflicts
    
    db = get_db()
    practice_id = current_user.get("practice_id")
    is_emergency = await detect_emergency(apt.notes or "")

    # Validate and enrich provider data if provider_id is provided
    provider_name = None
    provider_location = None
    
    if apt.provider_id:
        provider = await db.providers.find_one({"id": apt.provider_id}, {"_id": 0})
        if provider:
            # provider['name'] already includes "Dr." prefix for doctor roles
            # via normalize_provider_name_and_role; render as-is.
            provider_name = provider['name']
            
            # Get location name if location_id is provided
            if apt.location_id:
                location = await db.locations.find_one({"id": apt.location_id}, {"_id": 0})
                if location:
                    provider_location = location.get('name')
            
            # Validate provider availability
            validation = validate_provider_availability(
                provider,
                apt.appointment_date,
                apt.appointment_time,
                apt.location_id or "",
                apt.service_type or apt.reason or ""
            )
            
            if not validation["available"]:
                logger.warning(f"Provider availability issue: {validation['reason']}")
                # Don't block booking, just log warning
            
            # Check for double-booking
            has_conflict = await check_provider_conflicts(
                db, apt.provider_id, apt.appointment_date, apt.appointment_time
            )
            
            if has_conflict:
                raise HTTPException(
                    status_code=409,
                    detail=f"Provider {provider_name} is already booked at {apt.appointment_time}"
                )

    doc = {
        "id": str(uuid.uuid4()),
        "practice_id": practice_id,
        "location_id": apt.location_id,
        "provider_id": apt.provider_id,
        "provider_name": provider_name,
        "provider_location": provider_location,
        **apt.model_dump(),
        "status": "pending_verification",
        "is_emergency": is_emergency,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Set the slot-lock key so the unique sparse index prevents concurrent
    # double-inserts even when check_provider_conflicts races.
    if apt.provider_id and practice_id:
        doc["booking_key"] = _booking_key(
            practice_id, apt.provider_id,
            apt.appointment_date, apt.appointment_time,
        )

    try:
        await db.appointments.insert_one(doc)
    except MongoDuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=f"Provider {provider_name or apt.provider_id} is already booked at {apt.appointment_time}",
        )

    await log_audit_event(current_user["id"], practice_id, "appointment_created", "appointment", doc["id"],
                          {"patient_name": apt.patient_name, "date": apt.appointment_date, "emergency": is_emergency})
    if is_emergency:
        await log_analytics_event(practice_id, "emergency_routed", {"appointment_id": doc["id"]})

    doc.pop("_id", None)
    return doc


@router.put("/appointments/{appointment_id}")
async def update_appointment(appointment_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    db = get_db()
    body = await request.json()
    allowed = ["appointment_date", "appointment_time", "service_type", "status", "notes", "provider_id", "location_id"]
    update = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="No update data")

    practice_id = current_user.get("practice_id")
    mongo_op: dict = {"$set": update}

    cancelling   = update.get("status") in ("cancelled", "no_show")
    rescheduling = any(k in update for k in ("appointment_date", "appointment_time", "provider_id"))

    if cancelling:
        # Free the slot so it can be booked again.
        mongo_op["$unset"] = {"booking_key": ""}

    elif rescheduling and practice_id:
        # Fetch the current doc to fill in any scheduling fields not present in
        # the update (e.g. only the date is changing, not the time or provider).
        current = await db.appointments.find_one(
            {"id": appointment_id, "practice_id": practice_id},
            {"_id": 0, "provider_id": 1, "appointment_date": 1,
             "appointment_time": 1, "status": 1},
        )
        if current and current.get("provider_id") and current.get("status") not in ("cancelled", "no_show"):
            eff_provider = update.get("provider_id",        current["provider_id"])
            eff_date     = update.get("appointment_date",   current["appointment_date"])
            eff_time     = update.get("appointment_time",   current["appointment_time"])
            update["booking_key"] = _booking_key(practice_id, eff_provider, eff_date, eff_time)
            # mongo_op["$set"] already references `update` by reference — no re-assign needed

    try:
        result = await db.appointments.update_one(
            {"id": appointment_id, "practice_id": practice_id},
            mongo_op,
        )
    except MongoDuplicateKeyError:
        raise HTTPException(status_code=409, detail="That time slot is already booked for this provider")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "success"}


@router.delete("/appointments/{appointment_id}")
async def cancel_appointment(appointment_id: str, current_user: dict = Depends(require_role("admin", "staff"))):
    """Cancel appointment - Admin and Staff only"""
    db = get_db()
    result = await db.appointments.update_one(
        {"id": appointment_id, "practice_id": current_user.get("practice_id")},
        # Unset booking_key so the unique index releases the slot immediately,
        # allowing a new appointment to be booked for the same provider+time.
        {"$set": {"status": "cancelled"}, "$unset": {"booking_key": ""}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    await log_audit_event(current_user["id"], current_user["practice_id"], "appointment_cancelled", "appointment", appointment_id)
    return {"status": "success"}


@router.post("/appointments/{appointment_id}/verify")
async def verify_appointment(appointment_id: str, request: Request, current_user: dict = Depends(require_role("admin", "staff"))):
    db = get_db()
    body = await request.json()
    apt = await db.appointments.find_one({"id": appointment_id, "practice_id": current_user.get("practice_id")}, {"_id": 0})
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if apt.get("status") not in ["pending_verification", "pending_review"]:
        raise HTTPException(status_code=400, detail="Not pending verification")

    await db.appointments.update_one(
        {"id": appointment_id},
        {"$set": {"status": "scheduled", "verified_at": datetime.now(timezone.utc).isoformat(), "verified_by": body.get("verified_by", current_user["full_name"])}}
    )
    await db.notifications.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"type": "appointment_confirmed", "title": "Appointment Confirmed", "status": "read"}}
    )
    return {"status": "success", "appointment": apt}


# ==== STATS ====

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return {"today_appointments": 0, "total_patients": 0, "total_calls": 0, "scheduled_appointments": 0, "pending_claims": 0, "locations": 0, "providers": 0}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "today_appointments": await db.appointments.count_documents({"practice_id": practice_id, "appointment_date": today, "status": "scheduled"}),
        "total_patients": await db.patients.count_documents({"practice_id": practice_id}),
        "total_calls": await db.call_logs.count_documents({"practice_id": practice_id}),
        "scheduled_appointments": await db.appointments.count_documents({"practice_id": practice_id, "status": "scheduled"}),
        "pending_claims": await db.insurance_claims.count_documents({"practice_id": practice_id, "status": {"$in": ["submitted", "pending"]}}),
        "locations": await db.locations.count_documents({"practice_id": practice_id, "is_active": True}),
        "providers": await db.providers.count_documents({"practice_id": practice_id, "is_active": True}),
    }


# ==== MANUAL APPOINTMENT CREATION ====

@router.post("/practices/{practice_id}/appointments")
async def create_appointment_manual(
    practice_id: str,
    body: ManualAppointmentCreate,
    request: Request,
    current_user: dict = Depends(require_role("admin", "staff", "provider")),
):
    """Staff/admin/provider create a manual appointment directly."""
    # Verify caller belongs to this practice
    if current_user.get("role") != "super_admin" and current_user.get("practice_id") != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")

    db = get_db()

    # Validate practice exists and get appointment types
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    apt_types = (practice.get("settings") or {}).get("appointment_types") or []
    type_map = {t["id"]: t for t in apt_types}
    if body.appointment_type not in type_map:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown appointment type '{body.appointment_type}'. Valid: {list(type_map)}",
        )
    apt_type_obj = type_map[body.appointment_type]

    # Validate provider belongs to practice
    provider_name = None
    if body.provider_id:
        provider = await db.providers.find_one(
            {"id": body.provider_id, "practice_id": practice_id},
            {"_id": 0, "name": 1},
        )
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found in this practice")
        provider_name = provider["name"]

    # Find or create patient by phone
    phone_clean = body.phone.strip()
    patient = await db.patients.find_one(
        {"practice_id": practice_id, "phone": phone_clean},
        {"_id": 0, "id": 1, "name": 1},
    )
    if patient:
        patient_id = patient["id"]
    else:
        patient_id = str(uuid.uuid4())
        await db.patients.insert_one({
            "id": patient_id,
            "practice_id": practice_id,
            "name": body.full_name.strip(),
            "phone": phone_clean,
            "email": body.email,
            "consent_given": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    now = datetime.now(timezone.utc)
    apt_id = str(uuid.uuid4())
    apt_doc = {
        "id": apt_id,
        "practice_id": practice_id,
        "patient_id": patient_id,
        "patient_name": body.full_name.strip(),
        "patient_phone": phone_clean,
        "appointment_date": body.date,
        "appointment_time": body.time,
        "service_type": apt_type_obj["name"],
        "duration_minutes": apt_type_obj.get("duration_min", 30),
        "provider_id": body.provider_id,
        "provider_name": provider_name,
        "notes": body.notes,
        "status": "scheduled",
        "source": "manual",
        "created_by": current_user["id"],
        "is_emergency": False,
        "created_at": now.isoformat(),
    }
    await db.appointments.insert_one(apt_doc)
    apt_doc.pop("_id", None)

    # Log to ai_safety_logs — manual appointments never trigger Retell sync
    await db.ai_safety_logs.insert_one({
        "event_type": "appointment_created_manual",
        "practice_id": practice_id,
        "user_id": current_user["id"],
        "appointment_id": apt_id,
        "created_at": now.isoformat(),
    })

    await log_audit_event(
        current_user["id"], practice_id, "appointment_created_manual",
        "appointment", apt_id,
        {"patient_name": body.full_name, "date": body.date, "type": body.appointment_type},
        request.client.host if request.client else None,
    )

    return apt_doc
