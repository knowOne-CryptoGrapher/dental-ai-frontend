"""
Analytics + Conversation Logging Module
---------------------------------------

This module centralizes all logging for:
- Retell conversational events
- Amanda AI receptionist interactions
- Emergency detection events
- Appointment + insurance extraction
- Final transcript storage

This file is intentionally simple, stable, and ITRANS/CDAnet‑safe.
"""

from datetime import datetime, timezone
from auth import get_db


async def log_conversation_event(
    call_id: str,
    user_message: str = None,
    ai_response: str = None,
    emergency: bool = False,
    appointment: dict = None,
    insurance: dict = None,
    transcript: str = None,
    event_type: str = "message",
    practice_id: str = None,
):
    """
    Logs all conversational events for analytics, QA, and auditing.

    This function is intentionally tolerant:
    - Any missing fields are allowed
    - All fields are stored as-is
    - No schema enforcement (Mongo flexible)
    """

    db = get_db()

    doc = {
        "call_id": call_id,
        "practice_id": practice_id,
        "event_type": event_type,
        "user_message": user_message,
        "ai_response": ai_response,
        "emergency": emergency,
        "appointment": appointment,
        "insurance": insurance,
        "transcript": transcript,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await db.conversation_logs.insert_one(doc)
