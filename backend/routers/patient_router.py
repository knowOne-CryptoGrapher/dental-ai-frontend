from fastapi import APIRouter, HTTPException, Depends, Request
import uuid
from datetime import datetime, timezone
import logging

from models import PatientCreate
from auth import get_db, get_current_user, require_role, log_audit_event, generate_file_number

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["patients"])


@router.get("/patients")
async def get_patients(current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    query = {"practice_id": practice_id}
    # Provider only sees own patients
    if current_user.get("role") == "provider" and current_user.get("provider_id"):
        query["provider_id"] = current_user["provider_id"]
    patients = await db.patients.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return patients


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    patient = await db.patients.find_one({"id": patient_id, "practice_id": current_user.get("practice_id")}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.post("/patients")
async def create_patient(patient: PatientCreate, current_user: dict = Depends(get_current_user), request: Request = None):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=400, detail="No practice associated")

    # Duplicate check
    or_conds = []
    if patient.phone:
        or_conds.append({"phone": patient.phone})
    if patient.email:
        or_conds.append({"email": patient.email})
    if or_conds:
        existing = await db.patients.find_one({"practice_id": practice_id, "$or": or_conds}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=409, detail={
                "message": "Patient with this phone or email already exists",
                "patient": {"id": existing["id"], "name": existing["name"]}
            })

    file_number = await generate_file_number(practice_id)
    doc = {
        "id": str(uuid.uuid4()),
        "practice_id": practice_id,
        "file_number": file_number,
        **patient.model_dump(),
        "consent_given": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.patients.insert_one(doc)

    ip = request.client.host if request else None
    await log_audit_event(current_user["id"], practice_id, "patient_created", "patient", doc["id"],
                          {"name": patient.name}, ip)
    doc.pop("_id", None)
    return doc


@router.patch("/patients/{patient_id}/consent")
async def mark_consent_given(
    patient_id: str,
    current_user: dict = Depends(require_role("admin", "staff")),
    request: Request = None,
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    patient = await db.patients.find_one(
        {"id": patient_id, "practice_id": practice_id},
        {"_id": 0, "id": 1, "name": 1}
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    await db.patients.update_one(
        {"id": patient_id},
        {"$set": {
            "consent_given": True,
            "consent_date": datetime.now(timezone.utc).isoformat(),
            "consent_method": "staff_verified",
        }}
    )
    ip = request.client.host if request else None
    await log_audit_event(
        current_user["id"], practice_id, "patient_consent_given",
        "patient", patient_id, {"name": patient.get("name")}, ip
    )
    return {"success": True, "patient_id": patient_id, "consent_given": True}


@router.put("/patients/{patient_id}")
async def update_patient(patient_id: str, patient: PatientCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    update = patient.model_dump(exclude_unset=True)
    result = await db.patients.update_one(
        {"id": patient_id, "practice_id": current_user.get("practice_id")},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return await db.patients.find_one({"id": patient_id}, {"_id": 0})


@router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, current_user: dict = Depends(require_role("admin"))):
    """Delete patient - Admin only (Staff cannot delete patients)"""
    db = get_db()
    result = await db.patients.delete_one({"id": patient_id, "practice_id": current_user.get("practice_id")})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    await log_audit_event(current_user["id"], current_user["practice_id"], "patient_deleted", "patient", patient_id)
    return {"message": "Patient deleted"}
