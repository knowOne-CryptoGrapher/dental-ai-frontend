"""
CDAnet response, explanation, and reversal code tables.

These are stubs covering the most common codes.  The full CDAnet v4.1 code
sets must be sourced from the Canadian Dental Association specification before
production certification.

This module also owns interpret_cdanet_response — the single authoritative
point where a carrier response changes claim status and an audit entry is
written.
"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


# ── Lifecycle enum ────────────────────────────────────────────────────────────

class InternalClaimStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING  = "pending"
    ERROR    = "error"


# ── Code tables ───────────────────────────────────────────────────────────────

RESPONSE_CODES: dict[str, str] = {
    "A": "Accepted",
    "R": "Rejected",
    "E": "Error",
    "P": "Pending",
    # TODO: Add full CDAnet v4.1 response code set from CDA documentation
}

EXPLANATION_CODES: dict[str, str] = {
    "01": "Procedure not covered under plan",
    "02": "Maximum benefit reached",
    "03": "Waiting period not satisfied",
    "04": "Patient not eligible",
    # TODO: Add complete explanation code set from CDA documentation
}

REVERSAL_REASON_CODES: dict[str, str] = {
    "01": "Claim submitted in error",
    "02": "Patient cancelled treatment",
    "03": "Duplicate claim",
    # TODO: Add complete reversal reason code set from CDA documentation
}


# ── Response interpreter ──────────────────────────────────────────────────────

async def interpret_cdanet_response(claim: dict, response, db) -> InternalClaimStatus:
    """
    Authoritative point where a CDAnet response changes claim status.

    Mutates *claim* in-place with adjudication results and writes an audit log
    entry.  The caller is responsible for persisting the updated claim to
    MongoDB.

    Args:
        claim:    Claim document dict (from MongoDB), mutated in-place.
        response: CdanetResponse instance (from cdanet_mapper.parse_cdanet_response).
        db:       Motor database handle.

    Returns:
        InternalClaimStatus enum value reflecting the outcome.
    """
    from auth import log_audit_event  # deferred to avoid circular import

    code = response.adjudication_code

    if code == "A":
        new_status      = "accepted"
        internal_status = InternalClaimStatus.ACCEPTED
    elif code == "R":
        new_status      = "rejected"
        internal_status = InternalClaimStatus.REJECTED
    elif code == "E":
        new_status      = "error"
        internal_status = InternalClaimStatus.ERROR
    elif code == "P" or code is None:
        new_status      = "pending"
        internal_status = InternalClaimStatus.PENDING
    else:
        new_status      = "error"
        internal_status = InternalClaimStatus.ERROR
        claim["last_error_message"] = f"Unrecognised adjudication code: {code}"
        logger.warning("cdanet_unknown_adjudication_code", extra={"code": code, "claim_id": claim.get("id")})

    # Populate adjudication fields
    claim["status"]                      = new_status
    claim["adjudication_code"]           = response.adjudication_code
    claim["explanation_codes"]           = response.explanation_codes
    claim["amount_approved"]             = response.amount_approved
    claim["amount_patient_responsibility"] = response.amount_patient_responsibility

    if response.claim_reference_number:
        claim["claim_reference_number"] = response.claim_reference_number

    # Audit — codes and amounts only; never subscriber names, policy numbers, or raw response
    await log_audit_event(
        user_id="system",
        practice_id=claim["practice_id"],
        action="claim_response_received",
        resource_type="claim",
        resource_id=claim["id"],
        details={
            "adjudication_code":  response.adjudication_code,
            "explanation_codes":  response.explanation_codes,
            "new_status":         new_status,
        },
    )

    return internal_status
