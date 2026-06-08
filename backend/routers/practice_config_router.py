"""Phase 1 practice configuration endpoints."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request

from models import (
    PracticeBranding, PracticeHours, EmergencyRules,
    AppointmentType, PracticeRetellConfig, PracticeInsuranceConfig,
    default_practice_settings,
)
from auth import get_db, require_role, log_audit_event
from retell.retell_sync_service import sync_practice

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/practice", tags=["practice_config"])


def _ensure_tenant_access(current_user: dict, practice_id: str):
    if current_user.get("role") == "super_admin":
        return
    if current_user.get("practice_id") != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")


async def _get_practice_or_404(db, practice_id: str) -> dict:
    doc = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Practice not found")
    # Lazy-populate missing or EMPTY settings subsections with defaults so older
    # / seed-created practices work. Empty dicts ({}) and lists ([]) are
    # treated as missing — otherwise the frontend crashes on `hours.weekly[k]`
    # for practices created via scripts that stubbed empty subsections.
    defaults = default_practice_settings()
    settings = doc.get("settings") or {}
    changed = False
    for k, default_v in defaults.items():
        existing = settings.get(k)
        if existing is None:
            settings[k] = default_v
            changed = True
        elif isinstance(default_v, dict) and isinstance(existing, dict):
            # Empty dict → seed entirely; otherwise fill missing inner keys
            if not existing:
                settings[k] = default_v
                changed = True
            else:
                for ik, iv in default_v.items():
                    if ik not in existing or existing[ik] is None:
                        existing[ik] = iv
                        changed = True
        elif isinstance(default_v, list) and isinstance(existing, list):
            if not existing:
                settings[k] = default_v
                changed = True
    if changed:
        await db.practices.update_one({"id": practice_id}, {"$set": {"settings": settings}})
    doc["settings"] = settings
    return doc


# ==== Full config ====

@router.get("/{practice_id}/config")
async def get_config(practice_id: str, current_user: dict = Depends(require_role("admin", "super_admin"))):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    practice = await _get_practice_or_404(db, practice_id)
    return {
        "practice_id": practice_id,
        "name": practice.get("name"),
        "status": practice.get("status", "active"),
        "default_timezone": practice.get("default_timezone"),
        "settings": practice.get("settings"),
    }


@router.put("/{practice_id}/config")
async def update_config(
    practice_id: str,
    body: dict,
    request: Request,
    current_user: dict = Depends(require_role("admin", "super_admin")),
):
    """Merge-update any subpath under settings. Body is {branding:{...}, hours:{...}, ...}.

    NOTE: `retell` updates are super_admin-only — practice admins cannot
    touch agent_id, phone_number, or any other Retell infrastructure config."""
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    practice = await _get_practice_or_404(db, practice_id)
    _ = practice  # ensures the practice exists / defaults are seeded

    is_super = current_user.get("role") == "super_admin"
    allowed = {"branding", "hours", "emergency", "appointment_types", "insurance"}
    if is_super:
        allowed = allowed | {"retell"}
    elif "retell" in body:
        raise HTTPException(
            status_code=403,
            detail="Retell configuration is super_admin only"
        )
    updates = {}
    for k, v in body.items():
        if k in allowed:
            updates[f"settings.{k}"] = v
    if not updates:
        raise HTTPException(status_code=400, detail="No valid config fields to update")

    await db.practices.update_one({"id": practice_id}, {"$set": updates})
    await log_audit_event(current_user["id"], practice_id, "practice_config_updated",
                          "practice", practice_id, {"keys": list(body.keys())},
                          request.client.host if request.client else None)

    config = await get_config(practice_id, current_user)

    # Re-fetch full practice doc so the prompt renderer sees updated settings.
    _PROMPT_KEYS = {"branding", "hours", "appointment_types", "emergency"}
    if _PROMPT_KEYS & set(body.keys()):
        updated_practice = await _get_practice_or_404(db, practice_id)
        sync_result = await sync_practice(updated_practice, db)
        config["retell_sync"] = "ok" if sync_result.get("synced") else (
            "skipped" if sync_result.get("skipped") else "failed"
        )

    return config


# ==== Branding ====

@router.get("/{practice_id}/branding")
async def get_branding(practice_id: str, current_user: dict = Depends(require_role("admin", "super_admin"))):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    return p["settings"]["branding"]

@router.put("/{practice_id}/branding")
async def update_branding(
    practice_id: str, body: PracticeBranding,
    current_user: dict = Depends(require_role("admin", "super_admin"))
):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    await _get_practice_or_404(db, practice_id)
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.branding": body.model_dump()}}
    )

    # Re-fetch so the prompt renderer sees the freshly saved branding.
    updated_practice = await _get_practice_or_404(db, practice_id)
    sync_result = await sync_practice(updated_practice, db)

    return {
        **body.model_dump(),
        "retell_sync": "ok" if sync_result.get("synced") else (
            "skipped" if sync_result.get("skipped") else "failed"
        ),
    }


# ==== Hours ====

@router.get("/{practice_id}/hours")
async def get_hours(practice_id: str, current_user: dict = Depends(require_role("admin", "super_admin"))):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    return p["settings"]["hours"]

@router.put("/{practice_id}/hours")
async def update_hours(
    practice_id: str, body: PracticeHours,
    current_user: dict = Depends(require_role("admin", "super_admin"))
):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    await _get_practice_or_404(db, practice_id)
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.hours": body.model_dump()}}
    )
    return body.model_dump()


# ==== Emergency rules ====

@router.get("/{practice_id}/emergency-rules")
async def get_emergency_rules(practice_id: str, current_user: dict = Depends(require_role("admin", "super_admin"))):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    return p["settings"]["emergency"]

@router.put("/{practice_id}/emergency-rules")
async def update_emergency_rules(
    practice_id: str, body: EmergencyRules,
    current_user: dict = Depends(require_role("admin", "super_admin"))
):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    await _get_practice_or_404(db, practice_id)
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.emergency": body.model_dump()}}
    )
    return body.model_dump()


# ==== Appointment types ====

@router.get("/{practice_id}/appointment-types")
async def get_appointment_types(practice_id: str, current_user: dict = Depends(require_role("admin", "super_admin"))):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    return p["settings"]["appointment_types"]

@router.post("/{practice_id}/appointment-types")
async def add_appointment_type(
    practice_id: str, body: AppointmentType,
    current_user: dict = Depends(require_role("admin", "super_admin"))
):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    types = list(p["settings"]["appointment_types"])
    if any(t.get("id") == body.id for t in types):
        raise HTTPException(status_code=409, detail=f"Type '{body.id}' already exists")
    types.append(body.model_dump())
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.appointment_types": types}}
    )
    return types

@router.delete("/{practice_id}/appointment-types/{type_id}")
async def delete_appointment_type(
    practice_id: str, type_id: str,
    current_user: dict = Depends(require_role("admin", "super_admin"))
):
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    p = await _get_practice_or_404(db, practice_id)
    types = [t for t in p["settings"]["appointment_types"] if t.get("id") != type_id]
    if len(types) == len(p["settings"]["appointment_types"]):
        raise HTTPException(status_code=404, detail=f"Type '{type_id}' not found")
    await db.practices.update_one(
        {"id": practice_id},
        {"$set": {"settings.appointment_types": types}}
    )
    return types
