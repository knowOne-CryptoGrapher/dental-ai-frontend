"""
Retell AI webhook handler — v2.

Strict HMAC-SHA256 signature verification (never log-and-continue).
Passive event recording only — no auto-patient creation, no auto-appointment
creation, no emergency side-effects. The function-call endpoints in
retell_api_router.py handle all live-call actions.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from auth import get_db
from utils.retell_security import verify_retell_webhook_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/retell", tags=["retell_webhook"])

RETELL_WEBHOOK_SECRET = os.environ.get("RETELL_WEBHOOK_SECRET", "").strip()


# ── Entry point ───────────────────────────────────────────────────────────────

@router.post("/webhook")
async def retell_webhook(request: Request):
    """
    Receives all Retell call lifecycle events.

    Strict signature verification — any failure returns 401 immediately.
    All event processing is passive; no patient or appointment records
    are created here.
    """
    if not RETELL_WEBHOOK_SECRET:
        logger.error("retell_webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        payload = await verify_retell_webhook_signature(request, RETELL_WEBHOOK_SECRET)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("retell_webhook_verify_error", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail="Signature verification failed")

    try:
        event_type = payload.get("event", "")
        call_data = payload.get("call", {})

        logger.info(
            "retell_webhook_received",
            extra={"event_type": event_type, "call_id": call_data.get("call_id")},
        )

        if event_type == "call_started":
            await _handle_call_started(call_data)
        elif event_type == "call_ended":
            await _handle_call_ended(call_data)
        elif event_type == "call_analyzed":
            await _handle_call_analyzed(call_data)
        elif event_type == "call_error":
            await _handle_call_error(call_data)
        else:
            logger.info("retell_webhook_unknown_event", extra={"event_type": event_type})

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("retell_webhook_processing_error", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Webhook processing error")


# ── Practice ID resolution ────────────────────────────────────────────────────

async def _resolve_practice_id(call_data: dict) -> str | None:
    """
    Resolve practice_id in priority order:
      1. call_data.metadata.practice_id      (agent should always set this)
      2. call_data.metadata.agent_id         → look up practice by settings.retell.agent_id
      3. None — never falls back to first-practice-in-DB
    """
    metadata = call_data.get("metadata") or {}
    dynamic_vars = call_data.get("retell_llm_dynamic_variables") or {}

    practice_id = metadata.get("practice_id") or dynamic_vars.get("practice_id")
    if practice_id:
        return practice_id

    agent_id = metadata.get("agent_id") or call_data.get("agent_id")
    if agent_id:
        db = get_db()
        practice = await db.practices.find_one(
            {"settings.retell.agent_id": agent_id},
            {"_id": 0, "id": 1},
        )
        if practice:
            return practice.get("id")
        logger.warning(
            "retell_practice_not_found_for_agent",
            extra={"agent_id": agent_id},
        )

    logger.warning(
        "retell_practice_id_unresolvable",
        extra={"call_id": call_data.get("call_id")},
    )
    return None


# ── Event handlers ────────────────────────────────────────────────────────────

async def _handle_call_started(call_data: dict) -> None:
    """Insert an initial CallLog row when a call begins."""
    call_id = call_data.get("call_id", "")
    from_number = call_data.get("from_number", "")
    to_number = call_data.get("to_number", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    practice_id = await _resolve_practice_id(call_data)

    start_ts = call_data.get("start_timestamp")
    start_time = (
        datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).isoformat()
        if start_ts
        else now_iso
    )

    db = get_db()
    await db.call_logs.insert_one({
        "id": str(uuid4()),
        "call_id": call_id,
        "practice_id": practice_id,
        "patient_phone": from_number,
        "to_number": to_number,
        "status": "active",
        "handled_by": "ai",
        "transcript": "",
        "duration": 0,
        "start_time": start_time,
        "end_time": None,
        "call_summary": None,
        "action_taken": None,
        "call_type": None,
        "agent_id": call_data.get("agent_id", ""),
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    logger.info("retell_call_started", extra={"call_id": call_id, "practice_id": practice_id})


async def _handle_call_ended(call_data: dict) -> None:
    """
    Update CallLog on call end.

    Runs smart_extract passively to tag the call type from the transcript.
    No patient creation, no appointment creation, no emergency actions.
    """
    call_id = call_data.get("call_id", "")
    transcript = call_data.get("transcript", "")

    start_ts = call_data.get("start_timestamp", 0)
    end_ts = call_data.get("end_timestamp", 0)
    duration = (end_ts - start_ts) / 1000 if start_ts and end_ts else 0

    now_iso = datetime.now(timezone.utc).isoformat()
    end_time = (
        datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).isoformat()
        if end_ts
        else now_iso
    )

    call_type = None
    if transcript:
        from utils.transcript_parser import smart_extract
        tags = smart_extract(transcript, call_data)
        call_type = tags.get("call_reason")

    db = get_db()
    result = await db.call_logs.update_one(
        {"call_id": call_id},
        {"$set": {
            "status": "completed",
            "duration": duration,
            "end_time": end_time,
            "transcript": transcript,
            "call_type": call_type,
            "updated_at": now_iso,
        }},
    )
    if result.matched_count == 0:
        logger.warning("retell_call_ended_no_log", extra={"call_id": call_id})

    logger.info(
        "retell_call_ended",
        extra={"call_id": call_id, "duration": duration, "call_type": call_type},
    )


async def _handle_call_analyzed(call_data: dict) -> None:
    """Store Retell's post-call analysis dict on the CallLog."""
    call_id = call_data.get("call_id", "")
    call_analysis = call_data.get("call_analysis") or {}
    action_taken = call_analysis.get("action_taken") or call_analysis.get("outcome")

    now_iso = datetime.now(timezone.utc).isoformat()
    db = get_db()
    result = await db.call_logs.update_one(
        {"call_id": call_id},
        {"$set": {
            "call_summary": call_analysis,
            "action_taken": action_taken,
            "updated_at": now_iso,
        }},
    )
    if result.matched_count == 0:
        logger.warning("retell_call_analyzed_no_log", extra={"call_id": call_id})

    logger.info("retell_call_analyzed", extra={"call_id": call_id})


async def _handle_call_error(call_data: dict) -> None:
    """Mark CallLog as errored and store error details."""
    call_id = call_data.get("call_id", "")
    error_details = {
        "error_type": call_data.get("error_type") or call_data.get("disconnection_reason"),
        "message": call_data.get("error_message") or call_data.get("error"),
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    db = get_db()
    result = await db.call_logs.update_one(
        {"call_id": call_id},
        {"$set": {
            "status": "error",
            "call_summary": {"error": error_details},
            "updated_at": now_iso,
        }},
    )
    if result.matched_count == 0:
        logger.warning("retell_call_error_no_log", extra={"call_id": call_id})

    logger.error("retell_call_error", extra={"call_id": call_id, "details": error_details})
