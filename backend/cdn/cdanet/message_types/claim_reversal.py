"""
CDAnet Transaction Code 21 — Claim Reversal.
Reverses a previously submitted claim.

TODO: Requires CDAnet Transaction 21 field specification.
"""


class ClaimReversalMessage:
    TRANSACTION_CODE = "21"

    def build(self, original_claim_id: str,
              reason_code: str) -> str:
        # TODO: Implement per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")

    def parse_response(self, response: str) -> dict:
        # TODO: Parse reversal response per CDAnet spec
        raise NotImplementedError("CDAnet vendor spec required")
