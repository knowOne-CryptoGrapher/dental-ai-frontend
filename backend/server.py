"""
Retell conversational router — Amanda AI receptionist

Handles:
- Retell `user_message` events
- Provider-aware Amanda prompt
- Emergency / appointment / insurance extraction
- Multi-tenant, plan-aware LLM routing via LLMRouter
- Analytics logging
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ValidationError
from datetime import datetime
from typing import Optional
import logging

# ------------------------------------------------------------
# FIXED IMPORTS — absolute imports from backend.*
# ------------------------------------------------------------
from backend.db import get_db
from backend.analytics import log_conversation_event
from backend.emergency import detect_emergency

from backend.models import AppointmentRequest, InsuranceInfo, ProviderInfo
from backend.plans import get_plan

from backend.llm.base import ChatMessage
from backend.llm.router import get_default_router
from backend.llm.registry import get_provider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/retell", tags=["Retell"])


# ============================================================
# 1. Incoming Retell Webhook Payload Schema
# ============================================================

class RetellEvent(BaseModel):
    event: str
    call_id: str
    user_message: Optional[str] = None
    transcript: Optional[list] = None
    metadata: Optional[dict] = None


# ============================================================
# 2. System Prompt Loader (Provider‑Aware Amanda)
# ============================================================

def load_provider_prompt(provider: ProviderInfo) -> str:
    return f"""
You are Amanda, the AI receptionist for {provider.name}.
You speak warmly, professionally, and concisely.
You never guess. You only use verified information.

Clinic Details:
- Address: {provider.address}
- Phone: {provider.phone}
- Hours: {provider.hours}
- Services: {", ".join(provider.services)}
- Insurance Accepted: {", ".join(provider.insurance)}

Rules:
1. Never confirm an appointment — only log requests.
2. Never give medical advice.
3. If emergency symptoms appear, escalate using emergency handler.
4. Never hallucinate years or dates.
5. Keep responses short and friendly.
"""


# ============================================================
# 3. Core Retell → LLMRouter → Provider Orchestration
# ============================================================

async def process_user_message(
    call_id: str,
    message: str,
    provider: ProviderInfo,
    practice_id: str,
) -> str:

    db = get_db()

    # 1) Load plan for this practice
    practice = await db.practices.find_one(
        {"id": practice_id},
        {"_id": 0, "subscription_plan": 1}
    ) or {}
    plan = get_plan(practice.get("subscription_plan"))

    # 2) Build system prompt
    system_prompt = load_provider_prompt(provider)

    # 3) Convert to ChatMessage objects
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=message),
    ]

    # 4) Route using LLMRouter
    router = get_default_router()
    routing = router.decide(messages, plan=plan)

    provider_name = routing.provider
    model_name = routing.model

    llm_provider = get_provider(provider_name)
    if llm_provider is None:
        raise RuntimeError(f"Unknown provider: {provider_name}")

    # 5) Execute provider call with fallback chain
    try:
        llm_response = await llm_provider.chat_completion(
            model=model_name,
            messages=messages,
            stream=False,
        )
    except Exception:
        fallback_chain = ["openai", "anthropic", "google", "groq", "stub"]
        fallback_chain = [p for p in fallback_chain if p != provider_name]

        llm_response = None
        for fb in fallback_chain:
            fb_provider = get_provider(fb)
            if fb_provider is None:
                continue
            try:
                llm_response = await fb_provider.chat_completion(
                    model=None,
                    messages=messages,
                    stream=False,
                )
                break
            except Exception:
                continue

        if llm_response is None:
            raise RuntimeError("All LLM providers failed")

    # 6) Emergency / appointment / insurance extraction
    emergency_flag = detect_emergency(message)
    appointment = AppointmentRequest.extract(message)
    insurance = InsuranceInfo.extract(message)

    # 7) Analytics logging
    await log_conversation_event(
        call_id=call_id,
        user_message=message,
        ai_response=llm_response,
        emergency=emergency_flag,
        appointment=appointment.dict() if appointment else None,
        insurance=insurance.dict() if insurance else None,
        practice_id=practice_id,
    )

    return llm_response


# ============================================================
# 4. Retell Webhook Endpoint (Conversational)
# ============================================================

@router.post("/webhook")
async def retell_webhook(request: Request):
    try:
        payload = await request.json()
        event = RetellEvent(**payload)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Invalid Retell payload")

    provider_data = event.metadata.get("provider") if event.metadata else None
    if not provider_data:
        raise HTTPException(status_code=400, detail="Missing provider metadata")

    provider = ProviderInfo(**provider_data)

    practice_id = None
    if event.metadata:
        practice_id = event.metadata.get("practice_id") or provider_data.get("practice_id")
    if not practice_id:
        raise HTTPException(status_code=400, detail="Missing practice_id")

    if event.event != "user_message":
        logger.info(f"Ignoring Retell event type={event.event} for call_id={event.call_id}")
        return {"status": "ignored"}

    if not event.user_message:
        raise HTTPException(status_code=400, detail="Missing user_message")

    ai_response = await process_user_message(
        call_id=event.call_id,
        message=event.user_message,
        provider=provider,
        practice_id=practice_id,
    )

    return {
        "response": ai_response,
        "call_id": event.call_id,
    }


# ============================================================
# 5. Transcript Endpoint (Retell → Backend)
# ============================================================

@router.post("/transcript")
async def retell_transcript(request: Request):
    payload = await request.json()
    call_id = payload.get("call_id")
    transcript = payload.get("transcript")
    practice_id = payload.get("practice_id")

    if not call_id or not transcript:
        raise HTTPException(status_code=400, detail="Missing transcript data")

    await log_conversation_event(
        call_id=call_id,
        transcript=transcript,
        event_type="transcript_finalized",
        practice_id=practice_id,
    )

    return {"status": "transcript_saved"}


# ============================================================
# 6. Health Check
# ============================================================

@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
