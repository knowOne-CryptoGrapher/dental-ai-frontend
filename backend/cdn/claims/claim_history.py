"""
Claim history manager.
Retrieves and manages claim history from the local DB.
"""


class ClaimHistoryManager:
    async def get_by_practice(self, practice_id: str,
                              db) -> list:
        return await db.claims.find(
            {"practice_id": practice_id}
        ).sort("created_at", -1).to_list(length=100)

    async def get_by_patient(self, patient_id: str,
                             practice_id: str, db) -> list:
        return await db.claims.find(
            {
                "patient_id": patient_id,
                "practice_id": practice_id,
            }
        ).sort("created_at", -1).to_list(length=50)
