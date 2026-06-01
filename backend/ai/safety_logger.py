"""
AI safety logging layer.

Stores a structured log entry for every AI call. Never stores PHI —
only metadata, hashes, and classification results.

All logs are scoped by practice_id — no cross-practice visibility.
"""
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AISafetyLog:
    id: str
    practice_id: str
    call_id: str
    created_at: str
    context_hash: str               # From ContextBundle — auditable
    intent: str                     # From classifier
    intent_confidence: float
    intent_high_risk: bool
    handoff_triggered: bool
    guardrail_triggered: bool
    guardrail_violation_type: str
    refusal_triggered: bool
    refusal_signal: str
    pending_action_id: Optional[str]
    model_used: str
    response_tokens: int
    # Never store: transcript text, prompt, model output, patient data


async def log_ai_safety_event(log: AISafetyLog, db) -> None:
    """Persist a safety log entry to the ai_safety_logs collection."""
    doc = asdict(log)
    doc["practice_id"] = log.practice_id  # Ensure tenant scoping
    await db.ai_safety_logs.insert_one(doc)
    logger.info("ai_safety_log_written", extra={
        "practice_id": log.practice_id,
        "call_id": log.call_id,
        "intent": log.intent,
        "guardrail_triggered": log.guardrail_triggered,
        "refusal_triggered": log.refusal_triggered,
    })
