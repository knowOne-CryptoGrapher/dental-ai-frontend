"""
CDAnet mapping layer.

Owns three responsibilities:
  1. validate_cdanet_readiness  — check a claim dict has all required fields
  2. build_cdanet_request       — turn a claim dict into a CDAnet payload dict
  3. parse_cdanet_response      — turn a raw carrier response into CdanetResponse

Transport (network I/O) lives in insurance/itrans_client.py; this module is
pure data transformation.  No function here may log a raw payload.  Only
claim_id and transaction_type are safe to log.
"""
import logging
from pydantic import BaseModel

from utils.phi_redaction import redact_phi  # noqa: F401  # imported for callers' convenience

logger = logging.getLogger(__name__)


# ── CdanetResponse model ──────────────────────────────────────────────────────

class CdanetResponse(BaseModel):
    success: bool
    adjudication_code: str | None = None
    explanation_codes: list[str] = []
    amount_approved: float | None = None
    amount_patient_responsibility: float | None = None
    claim_reference_number: str | None = None
    raw: dict = {}  # Stored internally only — never logged, never exposed across practices


# ── Required field declarations ───────────────────────────────────────────────

_REQUIRED_FIELDS = (
    "carrier_id",
    "subscriber_policy_number",
    "subscriber_certificate_number",
    "cdanet_version",
    "transaction_type",
    "practice_province",
)

_FIELD_LABELS: dict[str, str] = {
    "carrier_id":                   "Carrier ID (CDAnet carrier code)",
    "subscriber_policy_number":     "Subscriber policy number",
    "subscriber_certificate_number":"Subscriber certificate number",
    "cdanet_version":               "CDAnet version",
    "transaction_type":             "Transaction type (claim, reversal, eligibility, predetermination)",
    "practice_province":            "Practice province (required for carrier routing)",
}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_cdanet_readiness(claim: dict) -> list[str]:
    """
    Return a list of human-readable messages for missing or invalid fields.

    Returns an empty list if the claim is ready for CDAnet submission.

    Callable independently from build_cdanet_request so the frontend can show
    the user what information is needed before attempting submission.
    """
    errors = []
    for field in _REQUIRED_FIELDS:
        if not claim.get(field):
            errors.append(f"Missing required field: {_FIELD_LABELS.get(field, field)}")
    return errors


# ── Request builder ───────────────────────────────────────────────────────────

def build_cdanet_request(claim: dict) -> dict:
    """
    Build a dict representing the CDAnet v4.1 request structure.

    Raises ValueError listing all missing fields if validate_cdanet_readiness
    finds problems.  Never logs the payload — only claim_id and
    transaction_type are logged.
    """
    errors = validate_cdanet_readiness(claim)
    if errors:
        raise ValueError(f"Claim not ready for CDAnet submission: {errors}")

    # TODO: Replace with actual CDAnet v4.1 field mappings per CDA specification
    payload: dict = {
        "version":          claim.get("cdanet_version", "4.1"),
        "transaction_type": claim.get("transaction_type"),
        "carrier_id":       claim.get("carrier_id"),
        "division_number":  claim.get("division_number"),
        "practice_province":claim.get("practice_province"),
        "subscriber": {
            "policy_number":      claim.get("subscriber_policy_number"),
            "certificate_number": claim.get("subscriber_certificate_number"),
            "last_name":          claim.get("subscriber_last_name"),
            "first_name":         claim.get("subscriber_first_name"),
            "relationship":       claim.get("relationship_to_subscriber", "self"),
        },
        "procedures":   claim.get("procedures", []),
        "total_amount": claim.get("total_amount", 0.0),
        # TODO: Add remaining CDAnet v4.1 fields: treatment dates, tooth numbers,
        #       surfaces, missing teeth, ortho info, recall date, etc.
    }

    logger.info(
        "cdanet_request_built",
        extra={
            "claim_id":        claim.get("id"),
            "transaction_type": claim.get("transaction_type"),
        },
    )
    return payload


# ── Response parser ───────────────────────────────────────────────────────────

def parse_cdanet_response(raw: dict) -> CdanetResponse:
    """
    Parse a raw carrier response dict into a CdanetResponse.

    Never logs the raw argument — it may contain PHI.
    """
    # TODO: Replace with actual CDAnet v4.1 response field parsing
    return CdanetResponse(
        success=raw.get("adjudication_code") == "A",
        adjudication_code=raw.get("adjudication_code"),
        explanation_codes=raw.get("explanation_codes", []),
        amount_approved=raw.get("amount_approved"),
        amount_patient_responsibility=raw.get("amount_patient_responsibility"),
        claim_reference_number=raw.get("claim_reference_number"),
        raw=raw,
    )
