"""
LLM routing audit log.

Every routing decision + the response metadata is appended to the
`llm_routing_logs` collection in MongoDB. Cheap to query, easy to
aggregate for the cost-savings dashboard.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

from auth import get_db

logger = logging.getLogger(__name__)


async def log_routing_decision(
    *,
    call_id: str | None,
    practice_id: str | None,
    provider: str,
    model: str,
    escalated: bool,
    trigger: str | None,
    reason: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    cache_stats: dict | None = None,
    error: str | None = None,
) -> None:
    db = get_db()
    if db is None:
        logger.debug("LLM log: db not initialized; skipping write")
        return
    doc = {
        "id": str(uuid.uuid4()),
        "call_id": call_id,
        "practice_id": practice_id,
        "provider": provider,
        "model": model,
        "escalated": bool(escalated),
        "trigger": trigger,
        "reason": reason,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "latency_ms": int(latency_ms or 0),
        "cache_stats": cache_stats or {},
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.llm_routing_logs.insert_one(doc)
    except Exception as e:
        logger.error(f"LLM log: failed to persist routing decision: {e}")
