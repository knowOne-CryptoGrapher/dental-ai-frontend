from fastapi import APIRouter, HTTPException, Depends, Request
import uuid
from datetime import datetime, timezone
import logging

import os
from models import PracticeCreate, LocationCreate, ProviderCreate
from auth import (
    get_db, get_current_user, require_role, require_practice_access, log_audit_event
)
from plans import enforce_plan_limit
from regions.region_config import derive_region, DB_CLUSTER_LABELS, COMPUTE_REGION_LABELS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["practice"])


# ==== PROVIDER NAME / ROLE NORMALIZATION ====

# Roles that should get a "Dr." title prefix on the name.
DOCTOR_ROLES = {
    "dentist", "orthodontist", "oral surgeon", "periodontist",
    "endodontist", "prosthodontist", "pediatric dentist", "dmd", "dds",
    "doctor", "physician",
}

def _smart_title(word: str) -> str:
    """Title-case a single name word, preserving Mc/Mac/O' prefixes."""
    if not word:
        return word
    low = word.lower()
    if low.startswith("mc") and len(low) > 2:
        return "Mc" + low[2].upper() + low[3:]
    if low.startswith("mac") and len(low) > 3:
        return "Mac" + low[3].upper() + low[4:]
    if low.startswith("o'") and len(low) > 2:
        return "O'" + low[2].upper() + low[3:]
    return low[:1].upper() + low[1:]

def normalize_provider_name_and_role(name: str | None, role: str | None) -> tuple[str | None, str | None]:
    """
    Standardize casing and, for doctor roles, prepend 'Dr.' if missing.
    Examples:
      ("john smith",      "dentist")    -> ("Dr. John Smith",     "Dentist")
      ("kevin mcdonald",  "dentist")    -> ("Dr. Kevin McDonald", "Dentist")
      ("jane doe",        "hygienist")  -> ("Jane Doe",           "Hygienist")
      ("Dr. Sarah smith", "dentist")    -> ("Dr. Sarah Smith",    "Dentist")
    """
    norm_role = None
    if role:
        norm_role = " ".join(w.capitalize() for w in role.strip().split())

    norm_name = None
    if name:
        raw = name.strip()
        has_prefix = raw.lower().startswith(("dr.", "dr ", "doctor "))
        prefix_removed = raw
        if has_prefix:
            prefix_removed = raw.split(" ", 1)[1] if " " in raw else ""
        core = " ".join(_smart_title(w) for w in prefix_removed.split() if w)
        is_doctor = (norm_role or "").lower() in DOCTOR_ROLES
        norm_name = f"Dr. {core}" if (is_doctor or has_prefix) else core

    return norm_name, norm_role

# ==== SUPER ADMIN: PRACTICES ====

@router.get("/admin/practices")
async def list_practices(current_user: dict = Depends(require_role("super_admin"))):
    db = get_db()
    practices = await db.practices.find({}, {"_id": 0}).to_list(500)
    # Enrich with user count
    for p in practices:
        p["user_count"] = await db.users.count_documents({"practice_id": p["id"]})
        p["patient_count"] = await db.patients.count_documents({"practice_id": p["id"]})
        p["location_count"] = await db.locations.count_documents({"practice_id": p["id"]})
    return practices

@router.get("/admin/practices/{practice_id}/residency")
async def get_practice_residency(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin", "admin")),
):
    """
    Return data residency metadata for a practice.
    Used for compliance audits — proves where a clinic's data lives.
    """
    db = get_db()
    practice = await db.practices.find_one(
        {"id": practice_id},
        {"_id": 0, "home_region": 1, "db_cluster": 1, "compute_region": 1, "province": 1, "name": 1},
    )
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    return {
        "practice_id":    practice_id,
        "practice_name":  practice.get("name"),
        "province":       practice.get("province"),
        "home_region":    practice.get("home_region"),
        "db_cluster":     practice.get("db_cluster"),
        "compute_region": practice.get("compute_region"),
        "compliant":      practice.get("home_region") is not None,
    }


@router.post("/admin/practices")
async def create_practice_admin(data: PracticeCreate, current_user: dict = Depends(require_role("super_admin"))):
    db = get_db()
    practice_id = str(uuid.uuid4())

    # Derive region metadata from province if provided
    region_fields: dict = {}
    if data.province:
        try:
            home_region = derive_region(data.province)
            region_fields = {
                "province":       data.province.strip().upper(),
                "home_region":    home_region.value,
                "db_cluster":     DB_CLUSTER_LABELS[home_region],
                "compute_region": os.getenv("COMPUTE_REGION", "northamerica-west2"),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    doc = {
        "id": practice_id,
        "name": data.name,
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "status": "active",
        "billing_status": "active",
        "subscription_plan": "starter",
        "default_timezone": data.default_timezone,
        "default_retention_years": 7,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **region_fields,
    }
    await db.practices.insert_one(doc)
    # Create default location
    await db.locations.insert_one({
        "id": str(uuid.uuid4()), "practice_id": practice_id,
        "name": "Main Office", "timezone": data.default_timezone,
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {k: v for k, v in doc.items() if k != "_id"}

@router.get("/admin/analytics")
async def platform_analytics(current_user: dict = Depends(require_role("super_admin"))):
    db = get_db()
    return {
        "total_practices": await db.practices.count_documents({}),
        "total_users": await db.users.count_documents({}),
        "total_patients": await db.patients.count_documents({}),
        "total_appointments": await db.appointments.count_documents({}),
        "total_calls": await db.call_logs.count_documents({}),
        "total_claims": await db.insurance_claims.count_documents({}),
        "active_practices": await db.practices.count_documents({"status": "active"}),
    }

@router.get("/admin/billing/overview")
async def billing_overview(current_user: dict = Depends(require_role("super_admin"))):
    db = get_db()
    customers = await db.billing_customers.find({}, {"_id": 0}).to_list(500)
    plans = {"starter": 0, "growth": 0, "enterprise": 0}
    for c in customers:
        plan = c.get("plan", "starter")
        plans[plan] = plans.get(plan, 0) + 1
    return {
        "total_customers": len(customers),
        "plan_distribution": plans,
        "active": sum(1 for c in customers if c.get("status") == "active"),
    }

# ==== LOCATIONS ====

@router.get("/locations")
async def get_locations(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id and current_user.get("role") != "super_admin":
        return []
    query = {"practice_id": practice_id} if practice_id else {}
    return await db.locations.find(query, {"_id": 0}).to_list(100)

@router.post("/locations")
async def create_location(loc: LocationCreate, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await enforce_plan_limit(db, current_user["practice_id"], "locations")
    doc = {
        "id": str(uuid.uuid4()),
        "practice_id": current_user["practice_id"],
        "name": loc.name,
        "address": loc.address, "city": loc.city,
        "province": loc.province, "postal_code": loc.postal_code,
        "phone": loc.phone, "timezone": loc.timezone,
        "hours": loc.hours, "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.locations.insert_one(doc)
    await log_audit_event(current_user["id"], current_user["practice_id"], "location_created", "location", doc["id"])
    return {k: v for k, v in doc.items() if k != "_id"}

@router.put("/locations/{location_id}")
async def update_location(location_id: str, loc: LocationCreate, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    update = loc.model_dump(exclude_unset=True)
    result = await db.locations.update_one(
        {"id": location_id, "practice_id": current_user["practice_id"]},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    return await db.locations.find_one({"id": location_id}, {"_id": 0})

@router.delete("/locations/{location_id}")
async def delete_location(location_id: str, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    result = await db.locations.update_one(
        {"id": location_id, "practice_id": current_user["practice_id"]},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"status": "success"}

# ==== PROVIDERS ====

@router.get("/providers")
async def get_providers(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id and current_user.get("role") != "super_admin":
        return []
    return await db.providers.find({"practice_id": practice_id, "is_active": True}, {"_id": 0}).to_list(100)

@router.post("/providers")
async def create_provider(prov: ProviderCreate, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await enforce_plan_limit(db, current_user["practice_id"], "providers")
    
    # Handle legacy location_id field
    location_ids = prov.location_ids or []
    if prov.location_id and prov.location_id not in location_ids:
        location_ids.append(prov.location_id)
    
    # Normalize name + role casing, prepend "Dr." for doctor roles
    norm_name, norm_role = normalize_provider_name_and_role(prov.name, prov.role)

    doc = {
        "id": str(uuid.uuid4()),
        "practice_id": current_user["practice_id"],
        "location_ids": location_ids,
        "name": norm_name,
        "title": prov.title,
        "role": norm_role,
        "appointment_types": prov.appointment_types,
        "working_hours": prov.working_hours,
        "on_call": prov.on_call,
        "specialties": prov.specialties,
        "license_number": prov.license_number,
        "itrans_provider_number": prov.itrans_provider_number,
        "is_active": True,
        "active": True,  # kept in sync for Retell public endpoints
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Legacy fields
        "location_id": prov.location_id,
        "availability": prov.availability,
    }
    await db.providers.insert_one(doc)
    await log_audit_event(current_user["id"], current_user["practice_id"], "provider_created", "provider", doc["id"])
    return {k: v for k, v in doc.items() if k != "_id"}

@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, prov: ProviderCreate, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    update = prov.model_dump(exclude_unset=True)
    # Normalize if name/role were changed
    if "name" in update or "role" in update:
        existing = await db.providers.find_one(
            {"id": provider_id, "practice_id": current_user["practice_id"]},
            {"_id": 0, "name": 1, "role": 1}
        )
        eff_name = update.get("name", (existing or {}).get("name"))
        eff_role = update.get("role", (existing or {}).get("role"))
        norm_name, norm_role = normalize_provider_name_and_role(eff_name, eff_role)
        if "name" in update or norm_name != (existing or {}).get("name"):
            update["name"] = norm_name
        if "role" in update or norm_role != (existing or {}).get("role"):
            update["role"] = norm_role
    # Keep Retell-visible 'active' flag in sync with UI's 'is_active'
    if "is_active" in update:
        update["active"] = update["is_active"]
    result = await db.providers.update_one(
        {"id": provider_id, "practice_id": current_user["practice_id"]},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Provider not found")
    return await db.providers.find_one({"id": provider_id}, {"_id": 0})

@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.providers.update_one(
        {"id": provider_id, "practice_id": current_user["practice_id"]},
        {"$set": {"is_active": False, "active": False}}
    )
    return {"status": "success"}

# ==== PRACTICE USERS MANAGEMENT ====

@router.get("/practice/users")
async def get_practice_users(current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    users = await db.users.find(
        {"practice_id": current_user["practice_id"]},
        {"_id": 0, "password_hash": 0}
    ).to_list(200)
    return users

@router.put("/practice/users/{user_id}/role")
async def update_user_role(user_id: str, request: Request, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    body = await request.json()
    new_role = body.get("role")
    if new_role not in ["admin", "staff", "provider", "auditor"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    result = await db.users.update_one(
        {"id": user_id, "practice_id": current_user["practice_id"]},
        {"$set": {"role": new_role}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await log_audit_event(current_user["id"], current_user["practice_id"], "user_role_updated", "user", user_id, {"new_role": new_role})


# ==== PROVIDER SCHEDULING ====

@router.get("/providers/{provider_id}")
async def get_provider_details(provider_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed provider information"""
    db = get_db()
    provider = await db.providers.find_one(
        {"id": provider_id, "practice_id": current_user["practice_id"]},
        {"_id": 0}
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.get("/providers/{provider_id}/availability")
async def get_provider_availability(
    provider_id: str,
    date: str,
    location_id: str = None,
    appointment_type: str = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get available time slots for a provider on a specific date.
    
    Query params:
    - date: YYYY-MM-DD
    - location_id: optional location filter
    - appointment_type: optional appointment type filter
    """
    from utils.provider_scheduling import get_provider_availability_slots
    
    db = get_db()
    
    # Verify provider belongs to user's practice
    provider = await db.providers.find_one({
        "id": provider_id,
        "practice_id": current_user["practice_id"]
    })
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    slots = await get_provider_availability_slots(
        db, provider_id, date, location_id, appointment_type
    )
    
    return {
        "provider_id": provider_id,
        "provider_name": provider['name'],
        "date": date,
        "location_id": location_id,
        "appointment_type": appointment_type,
        "slots": slots,
        "available_count": sum(1 for s in slots if s['available'])
    }


@router.post("/appointments/route")
async def route_appointment_to_provider(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Smart routing to find best available provider.
    
    Body:
    {
        "appointment_type": str,
        "location_id": str,
        "date": str (YYYY-MM-DD),
        "preferred_provider_id": str (optional),
        "is_emergency": bool (optional)
    }
    """
    from utils.provider_scheduling import route_appointment
    
    db = get_db()
    body = await request.json()
    
    appointment_type = body.get("appointment_type")
    location_id = body.get("location_id")
    date = body.get("date")
    preferred_provider_id = body.get("preferred_provider_id")
    is_emergency = body.get("is_emergency", False)
    
    if not appointment_type or not location_id or not date:
        raise HTTPException(status_code=400, detail="Missing required fields: appointment_type, location_id, date")
    
    result = await route_appointment(
        db, appointment_type, location_id, date, preferred_provider_id, is_emergency
    )
    
    return result

    return {"status": "success"}

@router.delete("/practice/users/{user_id}")
async def deactivate_user(user_id: str, current_user: dict = Depends(require_role("admin"))):
    db = get_db()
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    await db.users.update_one(
        {"id": user_id, "practice_id": current_user["practice_id"]},
        {"$set": {"is_active": False}}
    )
    return {"status": "success"}
