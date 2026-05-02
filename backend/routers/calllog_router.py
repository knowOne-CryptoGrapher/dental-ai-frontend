"""
Call Logs API Router
Endpoints for viewing and managing call logs from Retell AI
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional

from auth import get_current_user, require_role, get_db

router = APIRouter(prefix="/api/call-logs", tags=["Call Logs"])


@router.get("")
async def get_call_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = 100,
    skip: int = 0,
    emergency_only: bool = False
):
    """
    Get call logs for the current practice.
    Supports filtering by emergency status.
    """
    db = get_db()
    practice_id = current_user.get("practice_id")
    
    query = {"practice_id": practice_id}
    if emergency_only:
        query["emergency_detected"] = True
    
    logs = await db.call_logs.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return logs


@router.get("/{call_id}")
async def get_call_log(
    call_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information for a specific call.
    """
    db = get_db()
    practice_id = current_user.get("practice_id")
    
    log = await db.call_logs.find_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"_id": 0}
    )
    
    if not log:
        raise HTTPException(status_code=404, detail="Call log not found")
    
    return log


@router.get("/emergency/alerts")
async def get_emergency_alerts(
    current_user: dict = Depends(require_role("admin", "staff")),
    acknowledged: Optional[bool] = None,
    limit: int = 50
):
    """
    Get emergency alerts for the practice.
    Requires admin or staff role.
    """
    db = get_db()
    practice_id = current_user.get("practice_id")
    
    query = {"practice_id": practice_id}
    if acknowledged is not None:
        query["acknowledged"] = acknowledged
    
    alerts = await db.emergency_alerts.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return alerts


@router.post("/emergency/alerts/{call_id}/acknowledge")
async def acknowledge_emergency_alert(
    call_id: str,
    current_user: dict = Depends(require_role("admin", "staff"))
):
    """
    Acknowledge an emergency alert.
    Requires admin or staff role.
    """
    db = get_db()
    practice_id = current_user.get("practice_id")
    
    result = await db.emergency_alerts.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged_by": current_user.get("id")
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Emergency alert not found")
    
    return {"status": "success", "message": "Emergency alert acknowledged"}
