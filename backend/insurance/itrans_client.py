"""
ITRANS 2.0 Client (STUB)

In production this connects to the ITRANS 2.0 API for:
- Eligibility verification
- Claim submission
- Claim status inquiry
- Explanation of Benefits retrieval

ITRANS 2.0 uses JSON payloads over HTTPS.
Endpoint and credentials are configured per practice.

CDAnet mapping is handled by cdanet/cdanet_mapper.py.
This module owns transport only — payload construction and response
interpretation live in the cdanet package.
"""
import uuid
from datetime import datetime, timezone
import logging

from cdanet.cdanet_mapper import (
    validate_cdanet_readiness,
    build_cdanet_request,
    parse_cdanet_response,
)

logger = logging.getLogger(__name__)


class ITRANSClient:
    """
    ITRANS 2.0 / CDAnet transport client.

    All methods are stubs that return mock responses.
    TODO: Replace stub transport with actual ITRANS/CDAnet ICD call.
    """

    def __init__(self, office_number: str = "", api_key: str = "", endpoint: str = ""):
        self.office_number = office_number
        self.api_key       = api_key
        self.endpoint      = endpoint or "https://api.itrans2.ca/v2"  # TODO: replace with production endpoint

    async def check_eligibility(
        self,
        carrier: str,
        policy_number: str,
        patient_name: str,
        dob: str = None,
    ) -> dict:
        """
        Check insurance eligibility via ITRANS 2.0.

        TODO: Replace stub transport with actual ITRANS/CDAnet ICD call.
        """
        logger.info(
            "itrans_eligibility_check",
            extra={"carrier": carrier},
            # policy_number and patient_name are PHI — not logged
        )

        # TODO: Replace stub transport with actual ITRANS/CDAnet ICD call
        return {
            "transaction_id": f"ITRANS-{uuid.uuid4().hex[:12].upper()}",
            "status": "eligible",
            "carrier": carrier,
            "coverage": {
                "preventive": {"percentage": 100, "annual_max": 1500.00},
                "basic":      {"percentage": 80,  "annual_max": 2000.00},
                "major":      {"percentage": 50,  "annual_max": 3000.00},
            },
            "effective_date": "2025-01-01",
            "plan_type": "family",
            "method": "itrans_2.0",
            "mocked": True,
        }

    async def submit_claim(self, claim_data: dict) -> dict:
        """
        Submit a claim via ITRANS 2.0.

        Validates CDAnet readiness before attempting transport.
        Returns a validation_failed response (not an exception) when required
        fields are missing so the router can surface errors to the caller.

        TODO: Replace stub transport with actual ITRANS/CDAnet ICD call.
        """
        # Validate before transport — callers can also call validate_cdanet_readiness
        # directly (e.g. to show the user missing fields before they hit Submit).
        validation_errors = validate_cdanet_readiness(claim_data)
        if validation_errors:
            logger.info(
                "itrans_claim_validation_failed",
                extra={"claim_id": claim_data.get("id"), "error_count": len(validation_errors)},
            )
            return {
                "status": "validation_failed",
                "errors": validation_errors,
                "mocked": True,
            }

        _payload = build_cdanet_request(claim_data)  # raises ValueError on invalid data

        # TODO: Replace stub transport with actual ITRANS/CDAnet ICD call
        # Send _payload to self.endpoint and await carrier response
        raw_response: dict = {
            "adjudication_code":             "A",
            "explanation_codes":             [],
            "amount_approved":               claim_data.get("total_amount", 0.0),
            "amount_patient_responsibility": 0.0,
            "claim_reference_number":        f"TRK-{uuid.uuid4().hex[:6].upper()}",
            "mocked": True,
        }

        parsed = parse_cdanet_response(raw_response)

        return {
            "transaction_id":               f"ITRANS-CLM-{uuid.uuid4().hex[:8].upper()}",
            "status":                       "accepted" if parsed.success else "rejected",
            "claim_reference_number":       parsed.claim_reference_number,
            "adjudication_code":            parsed.adjudication_code,
            "explanation_codes":            parsed.explanation_codes,
            "amount_approved":              parsed.amount_approved,
            "amount_patient_responsibility":parsed.amount_patient_responsibility,
            "estimated_processing":         "3-5 business days",
            "method":                       "itrans_2.0",
            "mocked":                       True,
        }

    async def get_claim_status(self, tracking_number: str) -> dict:
        """
        Retrieve claim status via ITRANS 2.0.

        TODO: Replace stub transport with actual ITRANS/CDAnet ICD call.
        """
        # TODO: Replace stub transport with actual ITRANS/CDAnet ICD call
        raw_response: dict = {
            "adjudication_code": "P",
            "explanation_codes": [],
            "mocked": True,
        }
        parsed = parse_cdanet_response(raw_response)

        return {
            "tracking_number": tracking_number,
            "status": "processing",
            "adjudication_code": parsed.adjudication_code,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "method": "itrans_2.0",
            "mocked": True,
        }

    async def reverse_claim(self, claim_data: dict, reason_code: str) -> dict:
        """
        Submit a claim reversal via ITRANS 2.0.

        TODO: Replace stub transport with actual ITRANS/CDAnet ICD call.
        """
        logger.info(
            "itrans_reversal_submitted",
            extra={"claim_id": claim_data.get("id"), "reason_code": reason_code},
        )

        # TODO: Replace stub transport with actual ITRANS/CDAnet ICD call
        raw_response: dict = {
            "adjudication_code": "A",
            "explanation_codes": [],
            "claim_reference_number": f"REV-{uuid.uuid4().hex[:6].upper()}",
            "mocked": True,
        }
        parsed = parse_cdanet_response(raw_response)

        return {
            "transaction_id":         f"ITRANS-REV-{uuid.uuid4().hex[:8].upper()}",
            "status":                 "reversed" if parsed.success else "error",
            "claim_reference_number": parsed.claim_reference_number,
            "reason_code":            reason_code,
            "method":                 "itrans_2.0",
            "mocked":                 True,
        }
