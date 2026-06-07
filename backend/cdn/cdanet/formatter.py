"""
CDAnet message formatter.
Constructs fixed-width CDAnet messages for submission to ITRANS.

TODO: Requires CDAnet Software Vendor Agreement with the Canadian
Dental Association before implementing actual field positions and
message specifications. Contact: cda.ca/cdanet
"""

CDANET_VERSION = "04"  # CDAnet version placeholder


class CDAnetFormatter:
    def format_eligibility(self, claim_data: dict) -> str:
        # TODO: Implement CDAnet Transaction Code 01 formatting
        # Requires: CDAnet field position specification
        raise NotImplementedError("CDAnet vendor spec required")

    def format_claim_submission(self, claim_data: dict) -> str:
        # TODO: Implement CDAnet Transaction Code 11 formatting
        # Requires: CDAnet field position specification
        raise NotImplementedError("CDAnet vendor spec required")

    def format_claim_reversal(self, claim_data: dict) -> str:
        # TODO: Implement CDAnet Transaction Code 21 formatting
        # Requires: CDAnet field position specification
        raise NotImplementedError("CDAnet vendor spec required")
