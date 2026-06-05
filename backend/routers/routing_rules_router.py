from fastapi import APIRouter, HTTPException, Depends, Response
from datetime import datetime, timezone
import logging
import uuid

from auth import get_db, get_current_user
from dependencies import require_feature
from models import RoutingRule, RoutingRuleCreate, RoutingRuleUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["routing-rules"])


@router.get("/routing-rules")
async def list_routing_rules(
    all: bool = False,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("custom_routing_rules")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        return []
    query = {"practice_id": practice_id}
    if not all:
        query["enabled"] = True
    rules = await db.routing_rules.find(
        query, {"_id": 0}
    ).sort("priority", 1).to_list(1000)
    return rules


@router.post("/routing-rules", status_code=201)
async def create_routing_rule(
    body: RoutingRuleCreate,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("custom_routing_rules")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=403, detail="No practice context")

    now = datetime.now(timezone.utc)
    rule = RoutingRule(
        id=str(uuid.uuid4()),
        practice_id=practice_id,
        name=body.name,
        condition=body.condition,
        action=body.action,
        priority=body.priority,
        enabled=body.enabled,
        created_at=now,
        updated_at=now,
        created_by=current_user.get("id", ""),
    )
    rule_dict = rule.model_dump()
    await db.routing_rules.insert_one({**rule_dict})
    return rule_dict


@router.put("/routing-rules/{rule_id}")
async def update_routing_rule(
    rule_id: str,
    body: RoutingRuleUpdate,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("custom_routing_rules")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    existing = await db.routing_rules.find_one(
        {"id": rule_id, "practice_id": practice_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.routing_rules.update_one({"id": rule_id}, {"$set": updates})

    updated = await db.routing_rules.find_one({"id": rule_id}, {"_id": 0})
    return updated


@router.delete("/routing-rules/{rule_id}", status_code=204)
async def delete_routing_rule(
    rule_id: str,
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("custom_routing_rules")),
):
    db = get_db()
    practice_id = current_user.get("practice_id")
    result = await db.routing_rules.delete_one(
        {"id": rule_id, "practice_id": practice_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    return Response(status_code=204)
