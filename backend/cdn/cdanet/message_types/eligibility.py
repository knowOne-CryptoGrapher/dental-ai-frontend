"""
CDAnet Transaction Code 01 — Eligibility Check.
Checks patient insurance eligibility before claim submission.

TODO: Requires CDAnet Transaction 01 field specification.
"""


class EligibilityMessage:
    TRANSACTION_CODE = "01"

    def build(self, patient_id: str, carrier_id: str,
              provider_number: str) -> str:
        # TODO: Implement per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")

    def parse_response(self, response: str) -> dict:
        # TODO: Parse eligibility response per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")
