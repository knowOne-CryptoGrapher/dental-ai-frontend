from fastapi import APIRouter, HTTPException, Depends
import uuid
from datetime import datetime, timezone
import logging

from models import EligibilityCheck, ClaimSubmit
from auth import get_db, get_current_user, require_role, log_audit_event, log_analytics_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insurance", tags=["insurance"])

# ==== MOCKED ITRANS 2.0 / CDANet RESPONSES ====

MOCK_CARRIERS = {
    "sun_life": {"name": "Sun Life Financial", "method": "itrans"},
    "manulife": {"name": "Manulife", "method": "itrans"},
    "great_west": {"name": "Great-West Life", "method": "itrans"},
    "blue_cross": {"name": "Blue Cross", "method": "cdanet"},
    "desjardins": {"name": "Desjardins Insurance", "method": "itrans"},
    "green_shield": {"name": "Green Shield Canada", "method": "cdanet"},
    "canada_life": {"name": "Canada Life", "method": "itrans"},
}


@router.post("/eligibility")
async def check_eligibility(check: EligibilityCheck, current_user: dict = Depends(require_role("admin", "staff"))):
    """Check patient insurance eligibility (MOCKED)"""
    db = get_db()
    practice_id = current_user.get("practice_id")

    carrier_info = MOCK_CARRIERS.get(check.carrier, {"name": check.carrier, "method": "itrans"})

    # Mock eligibility response
    result = {
        "id": str(uuid.uuid4()),
        "carrier": check.carrier,
        "carrier_name": carrier_info["name"],
        "method": carrier_info["method"],
        "policy_number": check.policy_number,
        "patient_name": check.patient_name,
        "status": "eligible",
        "coverage": {
            "preventive": {"percentage": 100, "annual_max": 1500, "used": 350, "remaining": 1150},
            "basic": {"percentage": 80, "annual_max": 2000, "used": 0, "remaining": 2000},
            "major": {"percentage": 50, "annual_max": 3000, "used": 0, "remaining": 3000},
            "orthodontic": {"percentage": 50, "lifetime_max": 3000, "used": 0, "remaining": 3000},
        },
        "effective_date": "2025-01-01",
        "termination_date": None,
        "dependents_covered": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "note": "MOCKED RESPONSE - Connect ITRANS/CDANet for live data"
    }

    await log_audit_event(current_user["id"], practice_id, "eligibility_checked", "insurance", result["id"],
                          {"carrier": check.carrier, "patient": check.patient_name})
    return result


@router.post("/submit-claim")
async def submit_claim(claim: ClaimSubmit, current_user: dict = Depends(require_role("admin", "staff"))):
    """Submit insurance claim (MOCKED)"""
    db = get_db()
    practice_id = current_user.get("practice_id")
    carrier_info = MOCK_CARRIERS.get(claim.carrier, {"name": claim.carrier, "method": "itrans"})

    total = sum(p.get("fee", 0) for p in claim.procedures)

    # Get patient name
    patient = await db.patients.find_one({"id": claim.patient_id, "practice_id": practice_id}, {"_id": 0})
    patient_name = patient["name"] if patient else "Unknown"

    claim_doc = {
        "id": str(uuid.uuid4()),
        "practice_id": practice_id,
        "patient_id": claim.patient_id,
        "patient_name": patient_name,
        "provider_id": claim.provider_id,
        "appointment_id": claim.appointment_id,
        "carrier": claim.carrier,
        "carrier_name": carrier_info["name"],
        "policy_number": claim.policy_number,
        "group_number": claim.group_number,
        "procedures": claim.procedures,
        "total_amount": total,
        "status": "submitted",
        "submission_method": carrier_info["method"],
        "response_data": {
            "tracking_number": f"CLM-{uuid.uuid4().hex[:8].upper()}",
            "estimated_processing_days": 5,
            "message": "Claim received and under review (MOCKED)"
        },
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.insurance_claims.insert_one(claim_doc)

    await log_audit_event(current_user["id"], practice_id, "claim_submitted", "insurance_claim", claim_doc["id"],
                          {"carrier": claim.carrier, "amount": total})
    await log_analytics_event(practice_id, "claim_submitted", {"carrier": claim.carrier, "amount": total})

    claim_doc.pop("_id", None)
    return claim_doc


@router.get("/claims")
async def get_claims(status: str = None, current_user: dict = Depends(get_current_user)):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    query = {"practice_id": practice_id}
    if status:
        query["status"] = status
    return await db.insurance_claims.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": current_user.get("practice_id")}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/carriers")
async def list_carriers():
    """List supported insurance carriers"""
    return [{"id": k, **v} for k, v in MOCK_CARRIERS.items()]
