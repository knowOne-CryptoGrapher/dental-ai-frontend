"""
Practice context and knowledge endpoints for Retell AI agents.

  GET  /api/practice/me         — practice config for the agent's JWT session
  POST /api/knowledge/query     — keyword-scored knowledge base search
  POST /api/retell/call-summary — agent posts call outcome after hang-up
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from auth import get_db, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["retell_context"])

RETELL_WEBHOOK_SECRET = os.environ.get("RETELL_WEBHOOK_SECRET", "").strip()
RETELL_API_KEY        = os.environ.get("RETELL_API_KEY", "").strip()

_optional_bearer = HTTPBearer(auto_error=False)


# ── Request models ────────────────────────────────────────────────────────────

class KnowledgeQueryRequest(BaseModel):
    question: str
    practice_id: str


class CallSummaryRequest(BaseModel):
    practice_id: str
    call_id: str
    reason: str
    outcome: str   # "appointment_booked"|"info_provided"|"transferred"|"voicemail"|"abandoned"
    follow_up_needed: bool = False
    tags: list[str] = []
    transcript: Optional[str] = None
    appointment_id: Optional[str] = None
    patient_id: Optional[str] = None


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _verify_webhook_secret(x_retell_secret: str | None = Header(None)) -> None:
    """Dependency: RETELL_WEBHOOK_SECRET header for agent-posted endpoints."""
    if not RETELL_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if x_retell_secret != RETELL_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


async def _knowledge_auth(
    x_retell_api_key: str | None = Header(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> None:
    """
    Dual-auth for knowledge/query.
    Accepts RETELL_API_KEY header (Retell agent path) OR any Bearer JWT
    (frontend / authenticated staff path).

    Backlog: validate JWT's practice_id matches body.practice_id before
    returning documents (cross-practice scoping hardening).
    """
    if x_retell_api_key is not None:
        if RETELL_API_KEY and x_retell_api_key == RETELL_API_KEY:
            return
        raise HTTPException(status_code=401, detail="Invalid API key")
    if credentials and credentials.credentials:
        return  # JWT present — full validation handled by require_role on gated routes
    raise HTTPException(status_code=401, detail="Authentication required")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/practice/me")
async def get_practice_context(
    current_user: dict = Depends(require_role("admin", "staff", "provider")),
):
    """
    Returns the full practice context needed to bootstrap a Retell agent:
    hours, active providers, appointment types, emergency rules, branding.
    """
    practice_id = current_user.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=400, detail="No practice_id on user record")

    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    settings      = practice.get("settings") or {}
    branding      = settings.get("branding") or {}
    practice_name = practice.get("name", "")

    providers = await db.providers.find(
        {"practice_id": practice_id, "$or": [{"is_active": True}, {"active": True}]},
        {"_id": 0, "name": 1, "role": 1, "specialties": 1, "title": 1},
    ).to_list(100)

    return {
        "practice_id": practice_id,
        "practice_name": practice_name,
        "timezone": practice.get("timezone", "America/Toronto"),
        "subscription_plan": practice.get("subscription_plan", ""),
        "hours": settings.get("hours", {}),
        "providers": [
            {
                "name": p.get("name", ""),
                "role": p.get("role", ""),
                "specialties": p.get("specialties") or [],
                "title": p.get("title", ""),
            }
            for p in providers
        ],
        "appointment_types": settings.get("appointment_types", []),
        "emergency_rules": settings.get("emergency", {}),
        "branding": {
            "greeting_name": branding.get("greeting_name") or practice_name,
            "voice_style": branding.get("voice_style") or "professional",
        },
    }


@router.post("/knowledge/query")
async def query_knowledge_base(
    body: KnowledgeQueryRequest,
    _auth=Depends(_knowledge_auth),
):
    """
    Keyword-scored search against the practice's active knowledge base.

    Scoring:
      >= 2 unique keyword matches → confidence "high"
         1 keyword match         → confidence "low"
         0 matches               → {"answer": null, "confidence": "none"}
    """
    db = get_db()
    docs = await db.knowledge_documents.find(
        {"practice_id": body.practice_id, "is_active": True},
        {"_id": 0, "title": 1, "content": 1},
    ).to_list(200)

    if not docs:
        return {"answer": None, "source": None, "confidence": "none"}

    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "i", "to", "do",
        "of", "in", "on", "at", "for", "with", "and", "or", "not",
    }
    question_words = [
        w.lower().strip("?.!,")
        for w in body.question.split()
        if len(w) > 2 and w.lower().strip("?.!,") not in stop_words
    ]

    if not question_words:
        return {"answer": None, "source": None, "confidence": "none"}

    best_score = 0
    best_doc: dict | None = None

    for doc in docs:
        content_lower = (doc.get("content") or "").lower()
        score = sum(1 for w in question_words if w in content_lower)
        if score > best_score:
            best_score = score
            best_doc = doc

    if best_score == 0 or best_doc is None:
        return {"answer": None, "source": None, "confidence": "none"}

    return {
        "answer": best_doc.get("content"),
        "source": best_doc.get("title"),
        "confidence": "high" if best_score >= 2 else "low",
    }


@router.post("/retell/call-summary")
async def ingest_call_summary(
    body: CallSummaryRequest,
    _auth=Depends(_verify_webhook_secret),
):
    """
    Agent posts call outcome after hang-up.

    Upserts the CallLog by call_id. If follow_up_needed=True, inserts a
    pending_actions record for the practice team to action.
    """
    transcript_value = body.transcript or ""
    now_iso = datetime.now(timezone.utc).isoformat()
    db = get_db()

    summary_doc = {
        "reason": body.reason,
        "outcome": body.outcome,
        "tags": body.tags,
        "appointment_id": body.appointment_id,
        "patient_id": body.patient_id,
    }

    update_doc: dict = {
        "$set": {
            "practice_id": body.practice_id,
            "status": "completed",
            "call_summary": summary_doc,
            "action_taken": body.outcome,
            "updated_at": now_iso,
        },
        "$setOnInsert": {
            "id": str(uuid4()),
            "call_id": body.call_id,
            "patient_phone": "",
            "duration": 0,
            "handled_by": "ai",
            "created_at": now_iso,
        },
    }

    if transcript_value.strip():
        update_doc["$set"]["transcript"] = transcript_value

    await db.call_logs.update_one(
        {"call_id": body.call_id},
        update_doc,
        upsert=True,
    )

    if body.follow_up_needed:
        await db.pending_actions.insert_one({
            "id": str(uuid4()),
            "type": "follow_up",
            "practice_id": body.practice_id,
            "call_id": body.call_id,
            "reason": body.reason,
            "status": "pending",
            "created_at": now_iso,
        })
        logger.info(
            "retell_follow_up_created",
            extra={"call_id": body.call_id, "practice_id": body.practice_id},
        )

    logger.info(
        "retell_call_summary_ingested",
        extra={
            "call_id": body.call_id,
            "practice_id": body.practice_id,
            "outcome": body.outcome,
            "follow_up_needed": body.follow_up_needed,
        },
    )
    return {"success": True}
