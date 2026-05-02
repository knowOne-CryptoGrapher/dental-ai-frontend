from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
import logging

from auth import get_db, get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/call-logs")
async def get_call_logs(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    return await db.call_logs.find({"practice_id": practice_id}, {"_id": 0}).sort("timestamp", -1).to_list(1000)


@router.get("/call-logs/{call_id}")
async def get_call_detail(call_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    call = await db.call_logs.find_one({"call_id": call_id, "practice_id": current_user.get("practice_id")}, {"_id": 0})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("/active-calls")
async def get_active_calls(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    # Auto-cleanup stale active calls
    ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    await db.call_logs.update_many(
        {"practice_id": practice_id, "status": "active", "start_time": {"$lt": ten_min_ago}},
        {"$set": {"status": "completed", "end_time": datetime.now(timezone.utc).isoformat()}}
    )
    return await db.call_logs.find({"practice_id": practice_id, "status": "active"}, {"_id": 0}).to_list(100)


@router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    return await db.notifications.find(
        {"practice_id": practice_id, "status": {"$ne": "dismissed"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    await db.notifications.update_one(
        {"id": notification_id, "practice_id": current_user.get("practice_id")},
        {"$set": {"status": "read"}}
    )
    return {"status": "success"}


@router.post("/notifications/{notification_id}/dismiss")
async def dismiss(notification_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    await db.notifications.update_one(
        {"id": notification_id, "practice_id": current_user.get("practice_id")},
        {"$set": {"status": "dismissed"}}
    )
    return {"status": "success"}


# ==== ANALYTICS DASHBOARD ====

@router.get("/analytics/dashboard")
async def analytics_dashboard(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return {"metrics": {}, "trends": {}}

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    events = await db.analytics_events.find(
        {"practice_id": practice_id, "date_key": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0}
    ).to_list(10000)

    m = {
        "call_volume": {"total_calls": 0, "calls_answered": 0, "calls_missed": 0, "emergency_calls": 0},
        "appointments": {"total_requested": 0, "pending": 0, "confirmed": 0},
        "consent": {"total_intakes": 0, "consent_given": 0, "consent_rate": 0},
        "duplicates": {"duplicates_prevented": 0},
        "emergency": {"emergency_routed": 0},
        "insurance": {"claims_submitted": 0, "claims_approved": 0, "claims_denied": 0}
    }

    for e in events:
        et = e.get("event_type")
        if et == "call_answered":
            m["call_volume"]["calls_answered"] += 1; m["call_volume"]["total_calls"] += 1
        elif et == "call_missed":
            m["call_volume"]["calls_missed"] += 1; m["call_volume"]["total_calls"] += 1
        elif et == "emergency_routed":
            m["emergency"]["emergency_routed"] += 1; m["call_volume"]["emergency_calls"] += 1
        elif et == "appointment_requested":
            m["appointments"]["total_requested"] += 1
        elif et == "claim_submitted":
            m["insurance"]["claims_submitted"] += 1
        elif et == "claim_approved":
            m["insurance"]["claims_approved"] += 1
        elif et == "claim_denied":
            m["insurance"]["claims_denied"] += 1

    # Also get live counts
    m["appointments"]["confirmed"] = await db.appointments.count_documents({"practice_id": practice_id, "status": "scheduled"})
    m["appointments"]["pending"] = await db.appointments.count_documents({"practice_id": practice_id, "status": "pending_verification"})
    m["appointments"]["total_requested"] = await db.appointments.count_documents({"practice_id": practice_id})
    m["consent"]["total_intakes"] = await db.patients.count_documents({"practice_id": practice_id})
    m["consent"]["consent_given"] = await db.patients.count_documents({"practice_id": practice_id, "consent_given": True})
    if m["consent"]["total_intakes"] > 0:
        m["consent"]["consent_rate"] = round((m["consent"]["consent_given"] / m["consent"]["total_intakes"]) * 100, 1)

    return {"metrics": m, "trends": {}, "date_range": {"start": start_date, "end": end_date}}


@router.get("/analytics/provider")
async def provider_analytics(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    provider_id = current_user.get("provider_id")
    if not practice_id:
        return {}
    query = {"practice_id": practice_id}
    if provider_id:
        query["provider_id"] = provider_id
    return {
        "total_appointments": await db.appointments.count_documents(query),
        "scheduled": await db.appointments.count_documents({**query, "status": "scheduled"}),
        "completed": await db.appointments.count_documents({**query, "status": "completed"}),
        "cancelled": await db.appointments.count_documents({**query, "status": "cancelled"}),
        "patients": await db.patients.count_documents({"practice_id": practice_id, "provider_id": provider_id}) if provider_id else 0,
    }


@router.get("/analytics/platform")
async def platform_analytics(current_user: dict = Depends(require_role("super_admin"))):
    db = get_db()
    return {
        "total_practices": await db.practices.count_documents({}),
        "active_practices": await db.practices.count_documents({"status": "active"}),
        "total_users": await db.users.count_documents({}),
        "total_patients": await db.patients.count_documents({}),
        "total_appointments": await db.appointments.count_documents({}),
        "total_calls": await db.call_logs.count_documents({}),
        "total_claims": await db.insurance_claims.count_documents({}),
    }


# ==== AUDIT LOGS ====

@router.get("/audit-logs")
async def get_audit_logs(limit: int = 100, current_user: dict = Depends(require_role("admin", "auditor"))):
    db = get_db()
    practice_id = current_user.get("practice_id")
    query = {"practice_id": practice_id} if practice_id else {}
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"logs": logs, "total": len(logs)}


# ==== SETTINGS ====

@router.get("/settings/voice")
async def get_voice_config(current_user: dict = Depends(get_current_user)):
    db = get_db()
    config = await db.settings.find_one({"practice_id": current_user.get("practice_id"), "type": "voice"}, {"_id": 0})
    return config or {"voice_model": "Polly.Joanna"}


@router.post("/settings/voice")
async def update_voice_config(request: dict, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.settings.update_one(
        {"practice_id": current_user["practice_id"], "type": "voice"},
        {"$set": {"practice_id": current_user["practice_id"], "type": "voice", "voice_model": request.get("voice_model", "Polly.Joanna")}},
        upsert=True
    )
    return {"status": "success"}


@router.get("/settings/data-retention")
async def get_retention(current_user: dict = Depends(get_current_user)):
    db = get_db()
    policy = await db.settings.find_one({"practice_id": current_user.get("practice_id"), "type": "data_retention"}, {"_id": 0})
    return policy or {"retention_years": 7, "auto_archive_enabled": False}


@router.post("/settings/data-retention")
async def update_retention(request: dict, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.settings.update_one(
        {"practice_id": current_user["practice_id"], "type": "data_retention"},
        {"$set": {
            "practice_id": current_user["practice_id"], "type": "data_retention",
            "retention_years": request.get("retention_years", 7),
            "auto_archive_enabled": request.get("auto_archive_enabled", False),
        }},
        upsert=True
    )
    return {"status": "success"}


@router.get("/settings/insurance")
async def get_insurance_settings(current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    config = await db.settings.find_one({"practice_id": current_user["practice_id"], "type": "insurance"}, {"_id": 0})
    return config or {"itrans_office_number": "", "carriers": [], "cdanet_enabled": False}


@router.post("/settings/insurance")
async def update_insurance_settings(request: dict, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.settings.update_one(
        {"practice_id": current_user["practice_id"], "type": "insurance"},
        {"$set": {"practice_id": current_user["practice_id"], "type": "insurance", **request}},
        upsert=True
    )
    return {"status": "success"}
