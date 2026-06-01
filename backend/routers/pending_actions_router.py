from fastapi import APIRouter, HTTPException, Depends
from auth import get_db, require_role, require_practice_scope, log_audit_event
from datetime import datetime, timezone

router = APIRouter(prefix="/api/pending-actions", tags=["pending-actions"])


@router.get("")
async def list_pending_actions(
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
):
    """List all pending AI actions awaiting staff approval."""
    db = get_db()
    actions = await db.pending_actions.find(
        {"practice_id": current_user["practice_id"], "status": "pending"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return actions


@router.post("/{action_id}/approve")
async def approve_action(
    action_id: str,
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
):
    """Approve a pending AI action."""
    db = get_db()
    action = await db.pending_actions.find_one(
        {"id": action_id, "practice_id": current_user["practice_id"]}, {"_id": 0}
    )
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Action already {action['status']}")

    now = datetime.now(timezone.utc).isoformat()
    await db.pending_actions.update_one(
        {"id": action_id},
        {"$set": {"status": "approved", "reviewed_by": current_user["id"], "reviewed_at": now}}
    )
    await log_audit_event(
        current_user["id"], current_user["practice_id"],
        "pending_action_approved", "pending_action", action_id,
        {"action_type": action.get("action_type")},
    )
    return {"status": "approved"}


@router.post("/{action_id}/reject")
async def reject_action(
    action_id: str,
    note: str = "",
    current_user: dict = Depends(require_role("admin", "staff")),
    _scope=Depends(require_practice_scope()),
):
    """Reject a pending AI action."""
    db = get_db()
    action = await db.pending_actions.find_one(
        {"id": action_id, "practice_id": current_user["practice_id"]}, {"_id": 0}
    )
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")

    now = datetime.now(timezone.utc).isoformat()
    await db.pending_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": "rejected",
            "reviewed_by": current_user["id"],
            "reviewed_at": now,
            "review_note": note,
        }}
    )
    await log_audit_event(
        current_user["id"], current_user["practice_id"],
        "pending_action_rejected", "pending_action", action_id,
        {"action_type": action.get("action_type"), "note": note},
    )
    return {"status": "rejected"}
