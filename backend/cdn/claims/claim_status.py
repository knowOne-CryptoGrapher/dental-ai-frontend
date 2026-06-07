"""
Claim status checker.
Queries ITRANS for the current status of a submitted claim.
"""


class ClaimStatusChecker:
    async def check(self, itrans_transaction_id: str) -> dict:
        # TODO: Implement when ITRANS credentials arrive
        raise NotImplementedError("ITRANS credentials required")
