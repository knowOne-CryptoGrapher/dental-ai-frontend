"""
CDAnet Transaction Code 11 — Claim Submission.
Submits a dental claim to the carrier via ITRANS.

TODO: Requires CDAnet Transaction 11 field specification.
"""


class ClaimSubmissionMessage:
    TRANSACTION_CODE = "11"

    def build(self, claim_data: dict) -> str:
        # TODO: Implement per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")

    def parse_response(self, response: str) -> dict:
        # TODO: Parse claim response per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")
