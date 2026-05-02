"""
Retell AI Webhook Handler
Processes incoming call events from Retell AI voice assistant
"""
from fastapi import APIRouter, Request, BackgroundTasks, Response, HTTPException, status
from datetime import datetime, timezone
from typing import Optional
import logging
import os
import hmac
import hashlib
import time
import json

from auth import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# Get Retell API key from environment
RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "")


async def verify_retell_webhook_signature(request: Request, api_key: str, timestamp_tolerance_seconds: int = 300) -> dict:
    """Verify Retell webhook signature using HMAC-SHA256"""
    body = await request.body()
    signature_header = request.headers.get("x-retell-signature")
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook signature header")
    
    try:
        parts = signature_header.split(",")
        timestamp_part = parts[0].split("=")[1]
        digest_part = parts[1].split("=")[1]
        request_timestamp = int(timestamp_part)
    except (IndexError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature header format")
    
    current_time_ms = int(time.time() * 1000)
    time_difference_ms = current_time_ms - request_timestamp
    
    if abs(time_difference_ms) > (timestamp_tolerance_seconds * 1000):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook timestamp too old")
    
    message_to_sign = body + str(request_timestamp).encode('utf-8')
    expected_digest = hmac.new(api_key.encode('utf-8'), message_to_sign, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_digest, digest_part):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
    
    return json.loads(body.decode('utf-8'))


def detect_emergency_keywords(transcript: str) -> list:
    """Detect emergency keywords in call transcript"""
    emergency_keywords = {
        "severe pain": ["severe pain", "excruciating", "unbearable pain"],
        "bleeding": ["bleeding", "hemorrhage", "blood"],
        "tooth fracture": ["tooth broke", "fractured tooth", "broken tooth"],
        "infection": ["infection", "abscess", "swollen", "fever"],
        "jaw issues": ["jaw locked", "cannot close mouth", "cannot open mouth"],
        "trauma": ["accident", "trauma", "hit", "fell", "knocked out"],
    }
    
    detected = []
    transcript_lower = transcript.lower()
    
    for category, keywords in emergency_keywords.items():
        for keyword in keywords:
            if keyword in transcript_lower:
                detected.append(category)
                break
    
    return list(set(detected))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Get Retell API key from environment
RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "")


@router.post("/retell")
async def handle_retell_webhook(
    request: Request,
    background_tasks: BackgroundTasks
) -> Response:
    """
    Handle incoming Retell AI webhooks.
    Verifies signature and processes call events.
    
    Events handled:
    - call_started: Initial call connection
    - call_ended: Call completion with basic info
    - call_analyzed: Full call analysis with transcript
    """
    
    # Verify webhook signature for security
    if not RETELL_API_KEY:
        logger.error("RETELL_API_KEY not configured")
        return Response(status_code=204)
    
    try:
        payload = await verify_retell_webhook_signature(
            request,
            RETELL_API_KEY,
            timestamp_tolerance_seconds=300
        )
    except HTTPException as e:
        logger.warning(f"Webhook signature verification failed: {e.detail}")
        return Response(status_code=204)  # Return 204 to prevent retries
    
    event_type = payload.get("event")
    call_data = payload.get("call", {})
    call_id = call_data.get("call_id")
    
    logger.info(f"Received webhook event: {event_type} for call {call_id}")
    
    # Extract practice_id from metadata or dynamic variables
    metadata = call_data.get("metadata", {})
    dynamic_vars = call_data.get("retell_llm_dynamic_variables", {})
    practice_id = metadata.get("practice_id") or dynamic_vars.get("practice_id")
    
    if not practice_id:
        # For now, use a default practice_id if not provided
        # In production, this should be configured during call initiation
        practice_id = "default_practice"
        logger.warning(f"No practice_id found in webhook payload for call {call_id}, using default")
    
    # Process webhook in background to respond quickly
    background_tasks.add_task(
        process_webhook_event,
        event_type,
        call_data,
        practice_id
    )
    
    # Return 204 No Content to acknowledge receipt
    return Response(status_code=204)


async def process_webhook_event(event_type: str, call_data: dict, practice_id: str):
    """
    Process webhook event in background.
    """
    try:
        if event_type == "call_started":
            await handle_call_started(call_data, practice_id)
        elif event_type == "call_ended":
            await handle_call_ended(call_data, practice_id)
        elif event_type == "call_analyzed":
            await handle_call_analyzed(call_data, practice_id)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {str(e)}", exc_info=True)


async def handle_call_started(call_data: dict, practice_id: str):
    """
    Handle call_started event - creates initial call log.
    """
    db = get_db()
    
    call_log = {
        "practice_id": practice_id,
        "call_id": call_data.get("call_id"),
        "event_type": "call_started",
        "call_type": call_data.get("call_type", "phone_call"),
        "from_number": call_data.get("from_number", ""),
        "to_number": call_data.get("to_number", ""),
        "direction": call_data.get("direction", "inbound"),
        "call_status": call_data.get("call_status", "registered"),
        "agent_id": call_data.get("agent_id", ""),
        "start_timestamp": call_data.get("start_timestamp", 0),
        "metadata": call_data.get("metadata", {}),
        "retell_llm_dynamic_variables": call_data.get("retell_llm_dynamic_variables", {}),
        "opt_out_sensitive_data_storage": call_data.get("opt_out_sensitive_data_storage", False),
        "emergency_detected": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Extract patient information from dynamic variables
    dynamic_vars = call_data.get("retell_llm_dynamic_variables", {})
    if dynamic_vars.get("customer_name") or dynamic_vars.get("patient_name"):
        call_log["patient_name"] = dynamic_vars.get("customer_name") or dynamic_vars.get("patient_name")
    
    # Attempt to find existing patient by phone number
    from_number = call_data.get("from_number", "")
    if from_number:
        existing_patient = await db.patients.find_one({
            "practice_id": practice_id,
            "phone": from_number
        }, {"_id": 0})
        
        if existing_patient:
            call_log["patient_id"] = existing_patient.get("id")
            call_log["patient_name"] = f"{existing_patient.get('name', '')}"
    
    # Insert call log
    await db.call_logs.insert_one(call_log)
    
    logger.info(f"Call started recorded: {call_log['call_id']}")


async def handle_call_ended(call_data: dict, practice_id: str):
    """
    Handle call_ended event - updates call log with completion info.
    """
    db = get_db()
    call_id = call_data.get("call_id")
    
    # Calculate duration if timestamps are available
    start_ts = call_data.get("start_timestamp")
    end_ts = call_data.get("end_timestamp")
    duration_seconds = None
    if start_ts and end_ts:
        duration_seconds = (end_ts - start_ts) // 1000
    
    update_data = {
        "event_type": "call_ended",
        "end_timestamp": end_ts,
        "duration_seconds": duration_seconds,
        "call_status": call_data.get("call_status", "completed"),
        "disconnection_reason": call_data.get("disconnection_reason"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    result = await db.call_logs.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        logger.warning(f"Call log not found for call_id: {call_id}")
        return
    
    logger.info(f"Call ended recorded: {call_id}, duration: {duration_seconds} seconds")


async def handle_call_analyzed(call_data: dict, practice_id: str):
    """
    Handle call_analyzed event - stores detailed call analysis.
    """
    db = get_db()
    call_id = call_data.get("call_id")
    
    # Extract transcript and detect emergencies
    transcript = call_data.get("transcript", "")
    emergency_keywords = detect_emergency_keywords(transcript)
    emergency_detected = len(emergency_keywords) > 0
    
    # Extract call analysis data
    call_analysis = call_data.get("call_analysis", {})
    
    # Extract reason for call from transcript or analysis
    reason_for_call = extract_reason_for_call(transcript, call_analysis)
    
    update_data = {
        "event_type": "call_analyzed",
        "transcript": transcript,
        "call_analysis": call_analysis,
        "emergency_detected": emergency_detected,
        "emergency_keywords": emergency_keywords,
        "reason_for_call": reason_for_call,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    result = await db.call_logs.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        logger.warning(f"Call log not found for call_id: {call_id}")
        return
    
    # Handle emergency situations
    if emergency_detected:
        await handle_emergency_detection(db, call_id, practice_id, emergency_keywords, transcript)
    
    # Auto-create patient if needed
    await auto_create_patient_from_call(db, call_id, practice_id, call_data, transcript)
    
    logger.info(f"Call analyzed: {call_id}, emergency_detected: {emergency_detected}, reason: {reason_for_call}")


def extract_reason_for_call(transcript: str, call_analysis: dict) -> Optional[str]:
    """
    Extract the primary reason for the call from analysis or transcript.
    """
    # Check if call analysis contains extracted reason
    if "call_reason" in call_analysis:
        return call_analysis["call_reason"]
    
    # Fallback: check transcript for common appointment reasons
    transcript_lower = transcript.lower()
    
    reasons = {
        "Cleaning": ["cleaning", "checkup", "check-up", "routine visit", "dental exam"],
        "Emergency": ["pain", "urgent", "emergency", "hurts"],
        "Follow-up": ["follow up", "follow-up", "see how"],
        "Consultation": ["consultation", "consult", "advice", "question"],
        "Whitening": ["whitening", "bleaching", "whiten"],
        "Root Canal": ["root canal", "endodontic"],
        "Extraction": ["extraction", "pull", "remove tooth"],
        "Filling": ["filling", "cavity"],
    }
    
    for reason, keywords in reasons.items():
        for keyword in keywords:
            if keyword in transcript_lower:
                return reason
    
    return "General Inquiry"


async def handle_emergency_detection(
    db,
    call_id: str,
    practice_id: str,
    emergency_keywords: list[str],
    transcript: str
):
    """
    Handle emergency detection by creating alert and logging.
    """
    logger.critical(f"🚨 EMERGENCY DETECTED in call {call_id}: {emergency_keywords}")
    
    # Create emergency alert document
    await db.emergency_alerts.insert_one({
        "practice_id": practice_id,
        "call_id": call_id,
        "keywords": emergency_keywords,
        "transcript_excerpt": transcript[:500] if transcript else "",
        "severity": "high",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
    })
    
    logger.info(f"Emergency alert created for call {call_id}")


async def auto_create_patient_from_call(
    db,
    call_id: str,
    practice_id: str,
    call_data: dict,
    transcript: str
):
    """
    Automatically create patient record if caller is not already in system.
    """
    from_number = call_data.get("from_number", "")
    if not from_number:
        return
    
    # Check if patient already exists
    existing_patient = await db.patients.find_one({
        "practice_id": practice_id,
        "phone": from_number
    }, {"_id": 0})
    
    if existing_patient:
        # Update call log with patient_id
        await db.call_logs.update_one(
            {"practice_id": practice_id, "call_id": call_id},
            {"$set": {"patient_id": existing_patient.get("id")}}
        )
        return
    
    # Extract patient name from dynamic variables or transcript
    dynamic_vars = call_data.get("retell_llm_dynamic_variables", {})
    patient_name = dynamic_vars.get("customer_name") or dynamic_vars.get("patient_name")
    
    if not patient_name:
        # Try to extract name from transcript using simple heuristics
        # In production, use NLP model for better extraction
        logger.info(f"Could not extract patient name from call {call_id}")
        return
    
    # Create new patient record
    from uuid import uuid4
    patient_id = str(uuid4())
    
    # Parse name
    name_parts = patient_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    patient_doc = {
        "id": patient_id,
        "practice_id": practice_id,
        "name": patient_name,
        "first_name": first_name,
        "last_name": last_name,
        "phone": from_number,
        "email": None,
        "source": f"phone_call_{call_id}",
        "notes": f"Auto-created from Retell AI call on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.patients.insert_one(patient_doc)
    
    # Update call log with new patient_id
    await db.call_logs.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": {"patient_id": patient_id}}
    )
    
    logger.info(f"New patient created: {patient_id} ({patient_name}) from call {call_id}")
