"""
Human-in-the-loop action gate.

High-risk AI actions are intercepted and stored as pending_actions.
Staff approve or reject from the dashboard. Unapproved actions
auto-expire after PENDING_ACTION_TTL_HOURS.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

HIGH_RISK_ACTIONS = {
    "complex_booking",        # Multi-provider or multi-appointment bookings
    "insurance_change",       # Any change to insurance on file
    "multi_cancel",           # Cancelling more than one appointment
    "outbound_commit",        # Outbound SMS/email containing commitments
}

PENDING_ACTION_TTL_HOURS = 4


async def gate_action(
    action_type: str,
    action_payload: dict,
    ai_summary: str,
    call_id: str,
    practice_id: str,
    patient_id: str = None,
    db=None,
) -> dict:
    """
    Gate a high-risk action through human approval.

    Returns a response dict the AI can use to inform the caller the action
    is pending staff review.
    """
    if action_type not in HIGH_RISK_ACTIONS:
        return {"gated": False}

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=PENDING_ACTION_TTL_HOURS)

    pending = {
        "id":             str(uuid.uuid4()),
        "practice_id":    practice_id,
        "call_id":        call_id,
        "patient_id":     patient_id,
        "action_type":    action_type,
        "action_payload": action_payload,
        "ai_summary":     ai_summary,
        "status":         "pending",
        "created_at":     now.isoformat(),
        "expires_at":     expires_at.isoformat(),
    }

    if db:
        await db.pending_actions.insert_one(pending)
        logger.info(
            "pending_action_created",
            extra={
                "practice_id": practice_id,
                "action_type": action_type,
                "pending_action_id": pending["id"],
            }
        )

    return {
        "gated": True,
        "pending_action_id": pending["id"],
        "caller_message": (
            "I've flagged that for the team to confirm. "
            "They'll reach out to you within the next few hours to finalize. "
            "Is there anything else I can help you with?"
        ),
    }


async def expire_pending_actions(db) -> None:
    """Mark expired pending actions. Run as a scheduled task."""
    now = datetime.now(timezone.utc).isoformat()
    result = await db.pending_actions.update_many(
        {"status": "pending", "expires_at": {"$lt": now}},
        {"$set": {"status": "expired"}}
    )
    if result.modified_count:
        logger.info("pending_actions_expired", extra={"count": result.modified_count})
