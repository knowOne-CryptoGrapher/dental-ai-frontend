# backend/routers/claims_router.py
"""Claims API router — CDAnet/ITRANS claim submission via ITRANS 2.0."""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from auth import get_db, get_current_user, require_role
from dependencies import require_feature
from models import CdanetClaimCreate
from cdn.claims.submit_claim import ClaimSubmitter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["claims"])


def _claim_response(claim: dict) -> dict:
    return {
        "id": claim["id"],
        "practice_id": claim["practice_id"],
        "status": claim["status"],
        "error_code": claim.get("error_code"),
        "error_message": claim.get("error_message"),
        "created_at": claim["created_at"],
        "updated_at": claim["updated_at"],
    }


@router.get("")
async def list_claims(
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("insurance")),
):
    """Return all claims for the caller's practice, sorted newest first."""
    db = get_db()
    cursor = db.claims.find(
        {"practice_id": current_user.get("practice_id")},
        {"_id": 0},
    ).sort("created_at", -1)
    return await cursor.to_list(length=200)


@router.post("/submit")
async def submit_claim(
    body: CdanetClaimCreate,
    response: Response,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("insurance")),
):
    """
    Submit a dental claim via CDAnet/ITRANS.
    Returns HTTP 202 while ITRANS certification is pending;
    will return HTTP 200 once credentials are live.
    """
    practice_id = current_user.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=403, detail="No practice associated with this account")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    claim_id = str(uuid.uuid4())

    claim_doc = {
        "id": claim_id,
        "practice_id": practice_id,
        "patient_id": body.patient_id,
        "provider_id": body.provider_id,
        "appointment_id": body.appointment_id,
        "service_date": body.service_date,
        "cdanet_payload": None,
        "itrans_envelope": None,
        "itrans_response": None,
        "status": "pending",
        "error_code": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.claims.insert_one(claim_doc)

    submitter = ClaimSubmitter(test_mode=True)
    try:
        result = await submitter.submit(body.model_dump(), vendor_id=practice_id)
        update_now = datetime.now(timezone.utc).isoformat()
        await db.claims.update_one(
            {"id": claim_id},
            {"$set": {
                "status": "submitted",
                "cdanet_payload": result.get("cdanet_payload"),
                "itrans_envelope": result.get("itrans_envelope"),
                "itrans_response": result.get("itrans_response"),
                "updated_at": update_now,
            }}
        )
        claim_doc["status"] = "submitted"
        claim_doc["updated_at"] = update_now
        return _claim_response(claim_doc)

    except NotImplementedError:
        update_now = datetime.now(timezone.utc).isoformat()
        pending_msg = "CDAnet submission pending vendor certification"
        await db.claims.update_one(
            {"id": claim_id},
            {"$set": {
                "error_message": pending_msg,
                "updated_at": update_now,
            }}
        )
        claim_doc["error_message"] = pending_msg
        claim_doc["updated_at"] = update_now
        response.status_code = 202
        return _claim_response(claim_doc)

    except Exception as exc:
        logger.error("claim_submission_error", extra={"claim_id": claim_id, "error": str(exc)})
        err_msg = str(exc)
        update_now = datetime.now(timezone.utc).isoformat()
        await db.claims.update_one(
            {"id": claim_id},
            {"$set": {
                "status": "error",
                "error_message": err_msg,
                "updated_at": update_now,
            }}
        )
        raise HTTPException(status_code=500, detail="Claim submission failed")


@router.get("/{claim_id}/status")
async def get_claim_status(
    claim_id: str,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("insurance")),
):
    """Return the current status of a claim scoped to the caller's practice."""
    db = get_db()
    claim = await db.claims.find_one(
        {"id": claim_id, "practice_id": current_user.get("practice_id")},
        {"_id": 0},
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _claim_response(claim)


@router.get("/{claim_id}/raw")
async def get_claim_raw(
    claim_id: str,
    current_user: dict = Depends(require_role("admin")),
    _gate: None = Depends(require_feature("insurance")),
):
    """
    Return the raw CDAnet payload and ITRANS envelope for a claim.
    Admin only — raw payloads must never cross practice boundaries.
    """
    db = get_db()
    claim = await db.claims.find_one(
        {"id": claim_id, "practice_id": current_user.get("practice_id")},
        {"_id": 0},
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    # Never log raw CDAnet/ITRANS payloads — may contain PHI
    return {
        "claim_id": claim["id"],
        "cdanet_payload": claim.get("cdanet_payload"),
        "itrans_envelope": claim.get("itrans_envelope"),
        "itrans_response": claim.get("itrans_response"),
    }
