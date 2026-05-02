import os
import json
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ValidationError
from datetime import datetime

from ai_service import run_ai
from analytics import log_conversation_event
from emergency import detect_emergency
from models import AppointmentRequest, InsuranceInfo, ProviderInfo

router = APIRouter(prefix="/api/retell", tags=["Retell"])

# ============================================================
# 1. Incoming Retell Webhook Payload Schema
# ============================================================

class RetellEvent(BaseModel):
    event: str
    call_id: str
    user_message: str | None = None
    transcript: list | None = None
    metadata: dict | None = None


# ============================================================
# 2. System Prompt Loader (Provider‑Aware)
# ============================================================

def load_provider_prompt(provider: ProviderInfo):
    """
    Builds the dynamic Amanda prompt based on:
    - provider name
    - services
    - insurance rules
    - hours
    - emergency rules
    - tone
    """
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
# 3. Core Retell → AI → Backend Orchestration
# ============================================================

async def process_user_message(call_id: str, message: str, provider: ProviderInfo):
    """
    Main logic pipeline:
    - emergency detection
    - insurance extraction
    - appointment extraction
    - provider‑aware prompt
    - AI response
    - analytics logging
    """

    # Emergency detection
    emergency_flag = detect_emergency(message)

    # Extract appointment request
    appointment = AppointmentRequest.extract(message)

    # Extract insurance info
    insurance = InsuranceInfo.extract(message)

    # Build dynamic prompt
    system_prompt = load_provider_prompt(provider)

    # Run AI
    ai_response = await run_ai(
        system_prompt=system_prompt,
        user_message=message,
        json_mode=False
    )

    # Log analytics
    log_conversation_event(
        call_id=call_id,
        user_message=message,
        ai_response=ai_response,
        emergency=emergency_flag,
        appointment=appointment.dict() if appointment else None,
        insurance=insurance.dict() if insurance else None
    )

    return ai_response


# ============================================================
# 4. Retell Webhook Endpoint
# ============================================================

@router.post("/webhook")
async def retell_webhook(request: Request):
    try:
        payload = await request.json()
        event = RetellEvent(**payload)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Invalid Retell payload")

    # Load provider metadata (passed from Retell)
    provider_data = event.metadata.get("provider") if event.metadata else None
    if not provider_data:
        raise HTTPException(status_code=400, detail="Missing provider metadata")

    provider = ProviderInfo(**provider_data)

    # Only process user messages
    if event.event != "user_message":
        return {"status": "ignored"}

    ai_response = await process_user_message(
        call_id=event.call_id,
        message=event.user_message,
        provider=provider
    )

    return {
        "response": ai_response,
        "call_id": event.call_id
    }


# ============================================================
# 5. Transcript Endpoint (Retell → Backend)
# ============================================================

@router.post("/transcript")
async def retell_transcript(request: Request):
    payload = await request.json()
    call_id = payload.get("call_id")
    transcript = payload.get("transcript")

    if not call_id or not transcript:
        raise HTTPException(status_code=400, detail="Missing transcript data")

    log_conversation_event(
        call_id=call_id,
        transcript=transcript,
        event_type="transcript_finalized"
    )

    return {"status": "transcript_saved"}


# ============================================================
# 6. Health Check
# ============================================================

@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
