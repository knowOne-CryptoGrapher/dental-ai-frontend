from fastapi import APIRouter, Depends
from auth import get_db, require_role, require_practice_scope

router = APIRouter(prefix="/api/ai-safety", tags=["ai-safety"])


@router.get("/logs")
async def get_safety_logs(
    filter_type: str = None,
    current_user: dict = Depends(require_role("admin", "auditor")),
    _scope=Depends(require_practice_scope()),
):
    """
    Query AI safety logs for the practice. Powers the safety dashboard.

    filter_type options:
      insurance_statements  — guardrail_triggered=True
      clinical_statements   — intents: clinical_advice, diagnosis, treatment_recommendation
      refusal_failures      — refusal_triggered=True
      guardrail_triggers    — guardrail_triggered=True
    """
    db = get_db()
    query = {"practice_id": current_user["practice_id"]}

    if filter_type == "insurance_statements":
        query["guardrail_triggered"] = True
    elif filter_type == "clinical_statements":
        query["intent"] = {"$in": ["clinical_advice", "diagnosis", "treatment_recommendation"]}
    elif filter_type == "refusal_failures":
        query["refusal_triggered"] = True
    elif filter_type == "guardrail_triggers":
        query["guardrail_triggered"] = True

    logs = await db.ai_safety_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    return logs
