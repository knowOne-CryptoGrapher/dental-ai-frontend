"""
ITRANS 2.0 Client (MOCKED)

In production, this would connect to the ITRANS 2.0 API for:
- Eligibility verification
- Claim submission
- Claim status inquiry
- Explanation of Benefits retrieval

ITRANS 2.0 uses JSON payloads over HTTPS.
Endpoint and credentials are configured per practice.
"""
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ITRANSClient:
    """Mock ITRANS 2.0 client"""

    def __init__(self, office_number: str = "", api_key: str = "", endpoint: str = ""):
        self.office_number = office_number
        self.api_key = api_key
        self.endpoint = endpoint or "https://api.itrans2.ca/v2"  # Mock endpoint

    async def check_eligibility(self, carrier: str, policy_number: str, patient_name: str, dob: str = None) -> dict:
        """Check insurance eligibility via ITRANS 2.0 (MOCKED)"""
        logger.info(f"[ITRANS MOCK] Eligibility check: {carrier} / {policy_number} / {patient_name}")

        return {
            "transaction_id": f"ITRANS-{uuid.uuid4().hex[:12].upper()}",
            "status": "eligible",
            "carrier": carrier,
            "policy_number": policy_number,
            "patient_name": patient_name,
            "coverage": {
                "preventive": {"percentage": 100, "annual_max": 1500.00},
                "basic": {"percentage": 80, "annual_max": 2000.00},
                "major": {"percentage": 50, "annual_max": 3000.00},
            },
            "effective_date": "2025-01-01",
            "plan_type": "family",
            "method": "itrans_2.0",
            "mocked": True,
        }

    async def submit_claim(self, claim_data: dict) -> dict:
        """Submit claim via ITRANS 2.0 (MOCKED)"""
        logger.info(f"[ITRANS MOCK] Claim submission: {claim_data.get('total_amount')}")

        return {
            "transaction_id": f"ITRANS-CLM-{uuid.uuid4().hex[:8].upper()}",
            "status": "accepted",
            "tracking_number": f"TRK-{uuid.uuid4().hex[:6].upper()}",
            "estimated_processing": "3-5 business days",
            "method": "itrans_2.0",
            "mocked": True,
        }

    async def get_claim_status(self, tracking_number: str) -> dict:
        """Get claim status via ITRANS 2.0 (MOCKED)"""
        return {
            "tracking_number": tracking_number,
            "status": "processing",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "method": "itrans_2.0",
            "mocked": True,
        }
