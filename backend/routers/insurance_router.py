from fastapi import APIRouter, HTTPException, Depends, Request
import uuid
from datetime import datetime, timezone
import logging

from models import EligibilityCheck, ClaimSubmit, ClaimCreate, ClaimUpdate
from auth import (
    get_db, get_current_user, require_role, require_practice_scope,
    log_audit_event, log_analytics_event,
)
from cdanet.cdanet_mapper import validate_cdanet_readiness, parse_cdanet_response
from cdanet.cdanet_codes import (
    RESPONSE_CODES, EXPLANATION_CODES, REVERSAL_REASON_CODES,
    interpret_cdanet_response,
)
from insurance.itrans_client import ITRANSClient
from dependencies import require_feature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/insurance", tags=["insurance"])

MOCK_CARRIERS = {
    "sun_life":    {"name": "Sun Life Financial",        "method": "itrans"},
    "manulife":    {"name": "Manulife",                  "method": "itrans"},
    "great_west":  {"name": "Great-West Life",           "method": "itrans"},
    "blue_cross":  {"name": "Blue Cross",                "method": "cdanet"},
    "desjardins":  {"name": "Desjardins Insurance",      "method": "itrans"},
    "green_shield":{"name": "Green Shield Canada",       "method": "cdanet"},
    "canada_life": {"name": "Canada Life",               "method": "itrans"},
}


def _get_client() -> ITRANSClient:
    """Return a per-request ITRANSClient (credentials come from Secret Manager in prod)."""
    return ITRANSClient()


# ── Eligibility ───────────────────────────────────────────────────────────────

@router.post("/eligibility")
async def check_eligibility(
    check: EligibilityCheck,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """Check patient insurance eligibility."""
    db = get_db()
    practice_id = current_user["practice_id"]
    carrier_info = MOCK_CARRIERS.get(check.carrier, {"name": check.carrier, "method": "itrans"})

    client = _get_client()
    result = await client.check_eligibility(
        carrier=check.carrier,
        policy_number=check.policy_number,
        patient_name=check.patient_name,
        dob=check.date_of_birth,
    )

    result.update({
        "id":              str(uuid.uuid4()),
        "carrier_name":    carrier_info["name"],
        "checked_at":      datetime.now(timezone.utc).isoformat(),
    })

    await log_audit_event(
        current_user["id"], practice_id,
        "eligibility_checked", "insurance", result["id"],
        {"carrier": check.carrier},
    )
    return result


# ── Claims — create / list / get / update ─────────────────────────────────────

@router.post("/claims", status_code=201)
async def create_claim(
    body: ClaimCreate,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """Create a new claim in draft state."""
    db = get_db()
    practice_id = current_user["practice_id"]

    patient = await db.patients.find_one(
        {"id": body.patient_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    total = sum(p.get("fee", 0) for p in body.procedures)
    claim_doc = {
        "id":               str(uuid.uuid4()),
        "practice_id":      practice_id,
        "patient_id":       body.patient_id,
        "patient_name":     patient.get("name", ""),
        "provider_id":      body.provider_id,
        "appointment_id":   body.appointment_id,
        "carrier":          body.carrier,
        "policy_number":    body.policy_number,
        "group_number":     body.group_number,
        "procedures":       body.procedures,
        "total_amount":     total,
        "status":           "draft",
        "submission_method": MOCK_CARRIERS.get(body.carrier, {}).get("method", "itrans"),
        # CDAnet fields
        "carrier_id":                    body.carrier_id,
        "division_number":               body.division_number,
        "practice_province":             body.practice_province,
        "subscriber_last_name":          body.subscriber_last_name,
        "subscriber_first_name":         body.subscriber_first_name,
        "subscriber_policy_number":      body.subscriber_policy_number,
        "subscriber_certificate_number": body.subscriber_certificate_number,
        "relationship_to_subscriber":    body.relationship_to_subscriber,
        "transaction_type":              body.transaction_type or "claim",
        "cdanet_version":                "4.1",
        "explanation_codes":             [],
        "submission_attempts":           0,
        "created_at":                    datetime.now(timezone.utc).isoformat(),
    }
    await db.insurance_claims.insert_one(claim_doc)

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_created", "claim", claim_doc["id"],
        {"carrier": body.carrier, "total_amount": total},
    )
    claim_doc.pop("_id", None)
    return claim_doc


@router.get("/claims")
async def list_claims(
    status: str = None,
    current_user: dict = Depends(require_role("admin", "staff", "auditor")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """List claims for the authenticated practice."""
    db = get_db()
    practice_id = current_user["practice_id"]
    query: dict = {"practice_id": practice_id}
    if status:
        query["status"] = status
    return await db.insurance_claims.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.get("/claims/{claim_id}")
async def get_claim(
    claim_id: str,
    current_user: dict = Depends(require_role("admin", "staff", "auditor")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """Retrieve a single claim by ID."""
    db = get_db()
    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": current_user["practice_id"]}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.put("/claims/{claim_id}")
async def update_claim(
    claim_id: str,
    body: ClaimUpdate,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """Update mutable fields on a draft or ready_to_submit claim."""
    db = get_db()
    practice_id = current_user["practice_id"]

    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.get("status") not in ("draft", "ready_to_submit", "error"):
        raise HTTPException(status_code=409, detail="Only draft or error claims may be updated")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "procedures" in updates:
        updates["total_amount"] = sum(p.get("fee", 0) for p in updates["procedures"])

    await db.insurance_claims.update_one({"id": claim_id}, {"$set": updates})

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_updated", "claim", claim_id,
        {"updated_fields": list(updates.keys())},
    )
    updated = await db.insurance_claims.find_one({"id": claim_id}, {"_id": 0})
    return updated


# ── Claims — submission lifecycle ─────────────────────────────────────────────

@router.post("/claims/{claim_id}/submit")
async def submit_claim_by_id(
    claim_id: str,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """
    Submit a claim to the carrier.

    Validates CDAnet readiness first.  Returns 422 with a human-readable
    list of missing fields if the claim is not yet ready.
    """
    db = get_db()
    practice_id = current_user["practice_id"]

    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.get("status") in ("submitted", "accepted", "paid"):
        raise HTTPException(status_code=409, detail=f"Claim already in status: {claim['status']}")

    # Validate CDAnet readiness — log and return errors before touching the carrier
    validation_errors = validate_cdanet_readiness(claim)
    if validation_errors:
        await log_audit_event(
            current_user["id"], practice_id,
            "claim_validation_failed", "claim", claim_id,
            {"missing_fields": validation_errors},
        )
        raise HTTPException(
            status_code=422,
            detail={"message": "Claim not ready for submission", "errors": validation_errors},
        )

    # Submit via ITRANS/CDAnet transport
    client = _get_client()
    transport_result = await client.submit_claim(claim)

    if transport_result.get("status") == "validation_failed":
        # Transport-layer validation failure (should be caught above, but belt-and-suspenders)
        raise HTTPException(status_code=422, detail=transport_result.get("errors"))

    # Parse and interpret the response — this mutates claim and writes the audit log
    raw_response = {
        "adjudication_code":             transport_result.get("adjudication_code"),
        "explanation_codes":             transport_result.get("explanation_codes", []),
        "amount_approved":               transport_result.get("amount_approved"),
        "amount_patient_responsibility": transport_result.get("amount_patient_responsibility"),
        "claim_reference_number":        transport_result.get("claim_reference_number"),
    }
    parsed = parse_cdanet_response(raw_response)
    internal_status = await interpret_cdanet_response(claim, parsed, db)

    # Update submission tracking
    now = datetime.now(timezone.utc).isoformat()
    claim["submission_attempts"]  = claim.get("submission_attempts", 0) + 1
    claim["last_submitted_at"]    = now
    claim["submitted_at"]         = claim.get("submitted_at") or now

    await db.insurance_claims.update_one({"id": claim_id}, {"$set": {
        "status":                       claim["status"],
        "adjudication_code":            claim.get("adjudication_code"),
        "explanation_codes":            claim.get("explanation_codes", []),
        "amount_approved":              claim.get("amount_approved"),
        "amount_patient_responsibility":claim.get("amount_patient_responsibility"),
        "claim_reference_number":       claim.get("claim_reference_number"),
        "submission_attempts":          claim["submission_attempts"],
        "last_submitted_at":            now,
        "submitted_at":                 claim["submitted_at"],
    }})

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_submitted", "claim", claim_id,
        {
            "carrier": claim.get("carrier"),
            "total_amount": claim.get("total_amount"),
            "submission_attempts": claim["submission_attempts"],
        },
    )
    await log_analytics_event(practice_id, "claim_submitted", {
        "carrier": claim.get("carrier"),
        "amount":  claim.get("total_amount"),
    })

    # User-facing response — translate codes, never expose raw CDAnet codes
    explanation_messages = [
        EXPLANATION_CODES.get(c, f"Code {c}") for c in claim.get("explanation_codes", [])
    ]
    return {
        "claim_id":                     claim_id,
        "status":                       claim["status"],
        "status_label":                 RESPONSE_CODES.get(claim.get("adjudication_code", ""), claim["status"]),
        "explanation_messages":         explanation_messages,
        "amount_approved":              claim.get("amount_approved"),
        "amount_patient_responsibility":claim.get("amount_patient_responsibility"),
        "claim_reference_number":       claim.get("claim_reference_number"),
        "submission_attempts":          claim["submission_attempts"],
    }


@router.get("/claims/{claim_id}/status")
async def get_claim_status(
    claim_id: str,
    current_user: dict = Depends(require_role("admin", "staff", "auditor")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """Check current status of a submitted claim."""
    db = get_db()
    practice_id = current_user["practice_id"]

    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_status_checked", "claim", claim_id,
        {"current_status": claim.get("status")},
    )

    explanation_messages = [
        EXPLANATION_CODES.get(c, f"Code {c}") for c in claim.get("explanation_codes", [])
    ]
    return {
        "claim_id":                     claim_id,
        "status":                       claim.get("status"),
        "status_label":                 RESPONSE_CODES.get(claim.get("adjudication_code", ""), claim.get("status", "")),
        "explanation_messages":         explanation_messages,
        "amount_approved":              claim.get("amount_approved"),
        "amount_patient_responsibility":claim.get("amount_patient_responsibility"),
        "claim_reference_number":       claim.get("claim_reference_number"),
        "submission_attempts":          claim.get("submission_attempts", 0),
        "last_submitted_at":            claim.get("last_submitted_at"),
    }


@router.post("/claims/{claim_id}/reverse")
async def reverse_claim(
    claim_id: str,
    reason_code: str = "01",
    current_user: dict = Depends(require_role("admin")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """
    Reverse an accepted or paid claim.

    reason_code must be a valid REVERSAL_REASON_CODES key.
    """
    db = get_db()
    practice_id = current_user["practice_id"]

    if reason_code not in REVERSAL_REASON_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason code. Valid codes: {list(REVERSAL_REASON_CODES.keys())}",
        )

    claim = await db.insurance_claims.find_one(
        {"id": claim_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.get("status") not in ("accepted", "paid"):
        raise HTTPException(status_code=409, detail="Only accepted or paid claims may be reversed")

    client = _get_client()
    transport_result = await client.reverse_claim(claim, reason_code)

    if transport_result.get("status") == "reversed":
        await db.insurance_claims.update_one(
            {"id": claim_id},
            {"$set": {
                "status": "reversed",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_reversed", "claim", claim_id,
        {
            "reason_code":        reason_code,
            "reason_description": REVERSAL_REASON_CODES[reason_code],
            "result_status":      transport_result.get("status"),
        },
    )

    return {
        "claim_id":           claim_id,
        "status":             "reversed" if transport_result.get("status") == "reversed" else "error",
        "reason_code":        reason_code,
        "reason_description": REVERSAL_REASON_CODES[reason_code],
        "claim_reference_number": transport_result.get("claim_reference_number"),
    }


# ── Legacy submit endpoint (preserved for backward compatibility) ─────────────

@router.post("/submit-claim")
async def submit_claim_legacy(
    claim: ClaimSubmit,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
    _gate: None = Depends(require_feature("insurance")),
):
    """
    Legacy single-step create-and-submit endpoint.
    Prefer POST /claims followed by POST /claims/:id/submit for new integrations.
    """
    db = get_db()
    practice_id = current_user["practice_id"]
    carrier_info = MOCK_CARRIERS.get(claim.carrier, {"name": claim.carrier, "method": "itrans"})

    total = sum(p.get("fee", 0) for p in claim.procedures)
    patient = await db.patients.find_one(
        {"id": claim.patient_id, "practice_id": practice_id}, {"_id": 0}
    )
    patient_name = patient["name"] if patient else "Unknown"

    claim_doc = {
        "id":               str(uuid.uuid4()),
        "practice_id":      practice_id,
        "patient_id":       claim.patient_id,
        "patient_name":     patient_name,
        "provider_id":      claim.provider_id,
        "appointment_id":   claim.appointment_id,
        "carrier":          claim.carrier,
        "carrier_name":     carrier_info["name"],
        "policy_number":    claim.policy_number,
        "group_number":     claim.group_number,
        "procedures":       claim.procedures,
        "total_amount":     total,
        "status":           "submitted",
        "submission_method":carrier_info["method"],
        "explanation_codes":[],
        "submission_attempts": 1,
        "last_submitted_at":   datetime.now(timezone.utc).isoformat(),
        "response_data": {
            "tracking_number":            f"CLM-{uuid.uuid4().hex[:8].upper()}",
            "estimated_processing_days":  5,
            "message":                    "Claim received and under review (MOCKED)",
        },
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    await db.insurance_claims.insert_one(claim_doc)

    await log_audit_event(
        current_user["id"], practice_id,
        "claim_submitted", "claim", claim_doc["id"],
        {"carrier": claim.carrier, "amount": total},
    )
    await log_analytics_event(practice_id, "claim_submitted", {
        "carrier": claim.carrier, "amount": total,
    })

    claim_doc.pop("_id", None)
    return claim_doc


# ── Carriers ──────────────────────────────────────────────────────────────────

@router.get("/carriers")
async def list_carriers():
    """List supported insurance carriers and their integration method."""
    return [{"id": k, **v} for k, v in MOCK_CARRIERS.items()]
