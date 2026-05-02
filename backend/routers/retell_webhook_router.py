"""
Retell AI Webhook Receiver.

Handles `call_started`, `call_ended`, and `call_analyzed` events:
  - Persists every event to `call_logs` for operator review
  - Detects dental emergencies from transcripts and raises alerts
  - Auto-creates patient records for first-time callers
  - Auto-creates `pending_verification` appointments when booking intent
    is detected in the transcript
  - Attempts to match the caller's preferred provider via last-name
    matching, falling back to the on-call provider for emergencies

Moved out of `server.py` for maintainability. The public custom-function
endpoints used by Retell during a live call live in `retell_api_router.py`.
"""
from fastapi import APIRouter, Request, BackgroundTasks, Response, HTTPException
from datetime import datetime, timedelta, timezone, date
from uuid import uuid4
import hmac
import hashlib
import time
import os
import re
import logging

from auth import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["retell_webhook"])

RETELL_API_KEY = os.environ.get("RETELL_API_KEY", "")


# ==== WEBHOOK ENTRY POINT ====

@router.post("/api/webhooks/retell")
async def retell_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Legacy (unscoped) webhook endpoint. Kept for backward compat with the
    original clinic that's still configured this way. Falls back to the
    first practice in DB when practice_id is missing — DO NOT use for new
    onboarding; use `/api/webhooks/retell/{practice_id}` instead.
    """
    payload = await _read_and_verify_webhook(request)
    background_tasks.add_task(process_retell_webhook, payload, None)
    return Response(status_code=204)


@router.post("/api/webhooks/retell/{practice_id}")
async def retell_webhook_scoped(
    practice_id: str, request: Request, background_tasks: BackgroundTasks
):
    """
    Per-practice webhook. The URL-embedded practice_id is authoritative —
    eliminates the legacy fallback-to-first-practice foot-gun. Retell
    agents provisioned through the onboarding wizard use this endpoint.
    """
    # Validate the practice exists before queueing work
    db = get_db()
    exists = await db.practices.find_one({"id": practice_id}, {"_id": 0, "id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="Practice not found")

    payload = await _read_and_verify_webhook(request)
    background_tasks.add_task(process_retell_webhook, payload, practice_id)
    return Response(status_code=204)


async def _read_and_verify_webhook(request: Request) -> dict:
    """Shared signature-check + body parse for both webhook endpoints."""
    if RETELL_API_KEY:
        signature_header = request.headers.get("x-retell-signature", "")
        if signature_header:
            try:
                body = await request.body()
                parts = signature_header.split(",")
                timestamp_part = parts[0].split("=")[1]
                digest_part = parts[1].split("=")[1]
                request_timestamp = int(timestamp_part)
                current_time_ms = int(time.time() * 1000)
                if abs(current_time_ms - request_timestamp) > 300000:
                    logger.warning("Webhook timestamp too old, but processing anyway")
                message = body + str(request_timestamp).encode("utf-8")
                expected = hmac.new(
                    RETELL_API_KEY.encode(), message, hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(expected, digest_part):
                    logger.warning("Invalid webhook signature, but processing anyway")
                return await request.json()
            except Exception as e:
                logger.error(
                    f"Signature verification error: {e}, processing without verification"
                )
                return await request.json()
    return await request.json()


# ==== BACKGROUND PROCESSING ====

async def process_retell_webhook(payload: dict, override_practice_id: str | None = None):
    """
    Route Retell events to the appropriate handler.

    If override_practice_id is provided (from the scoped URL), it's authoritative
    and used regardless of what the body metadata says. Otherwise we fall back
    to body metadata → dynamic vars → first-practice-in-DB (legacy behavior).
    """
    logger.info(f"Full webhook payload: {payload}")
    try:
        event_type = payload.get("event")
        call_data = payload.get("call", {})
        call_id = call_data.get("call_id")

        logger.info(f"Processing Retell webhook: {event_type} for call {call_id}")

        db = get_db()
        metadata = call_data.get("metadata", {})
        dynamic_vars = call_data.get("retell_llm_dynamic_variables", {})
        body_pid = metadata.get("practice_id") or dynamic_vars.get("practice_id")

        if override_practice_id:
            practice_id = override_practice_id
            if body_pid and body_pid != override_practice_id:
                logger.warning(
                    f"Webhook body practice_id {body_pid} disagrees with URL "
                    f"{override_practice_id}; using URL (authoritative)."
                )
        elif body_pid:
            practice_id = body_pid
        else:
            first_practice = await db.practices.find_one({}, {"_id": 0, "id": 1})
            if first_practice:
                practice_id = first_practice.get("id")
                logger.info(f"No practice_id in webhook, using first practice: {practice_id}")
            else:
                practice_id = "default_practice"
                logger.warning(
                    f"No practice_id found in webhook payload for call {call_id}, "
                    "using default"
                )

        if event_type == "call_started":
            await handle_call_started(call_data, practice_id)
        elif event_type == "call_ended":
            await handle_call_ended(call_data, practice_id)
        elif event_type == "call_analyzed":
            await handle_call_analyzed(call_data, practice_id)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)


# ==== EVENT HANDLERS ====

async def handle_call_started(call_data: dict, practice_id: str):
    """Insert an initial call_logs row when a call begins."""
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.call_logs.insert_one({
        "practice_id": practice_id,
        "call_id": call_data.get("call_id"),
        "event_type": "call_started",
        "from_number": call_data.get("from_number", ""),
        "to_number": call_data.get("to_number", ""),
        "direction": call_data.get("direction", "inbound"),
        "call_status": "started",
        "start_timestamp": call_data.get("start_timestamp", int(time.time() * 1000)),
        "agent_id": call_data.get("agent_id", ""),
        "metadata": call_data.get("metadata", {}),
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    logger.info(f"Call started: {call_data.get('call_id')}")


async def handle_call_ended(call_data: dict, practice_id: str):
    """
    Update call_logs when Retell signals the call has ended.

    Retell now embeds the transcript in the call_ended payload, so we also
    run the analysis step inline instead of waiting for call_analyzed.
    """
    db = get_db()
    call_id = call_data.get("call_id")
    start_ts = call_data.get("start_timestamp", 0)
    end_ts = call_data.get("end_timestamp", int(time.time() * 1000))
    duration = (end_ts - start_ts) // 1000 if start_ts and end_ts else 0

    update_data = {
        "event_type": "call_ended",
        "end_timestamp": end_ts,
        "duration_seconds": duration,
        "call_status": call_data.get("call_status", "completed"),
        "disconnection_reason": call_data.get("disconnection_reason"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    result = await db.call_logs.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": update_data},
    )
    if result.matched_count:
        logger.info(f"Call ended: {call_id}, duration: {duration}s")
    else:
        logger.warning(f"Call log not found for {call_id}, creating new entry")
        await db.call_logs.insert_one({
            "practice_id": practice_id,
            "call_id": call_id,
            **update_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    transcript = call_data.get("transcript", "")
    if transcript:
        logger.info(
            f"✅ Transcript found in call_ended payload for {call_id}, "
            "processing immediately"
        )
        await handle_call_analyzed(call_data, practice_id)


async def handle_call_analyzed(call_data: dict, practice_id: str):
    """
    Full transcript analysis: emergency detection, patient auto-create,
    appointment auto-create, provider matching.
    """
    db = get_db()
    call_id = call_data.get("call_id")
    transcript = call_data.get("transcript", "")

    # Extract provider preference early (used later for appointment assignment)
    preferred_provider_name = None
    if transcript:
        from utils.transcript_parser import extract_provider_preference
        preferred_provider_name = extract_provider_preference(transcript)
        if preferred_provider_name:
            logger.info(
                f"✅ Extracted preferred provider from transcript: {preferred_provider_name}"
            )

    # Debug logging — which nested location holds the extracted data
    logger.info(f"🔍 DEEP ANALYSIS for call {call_id}")
    logger.info(f"📋 Top-level keys in call_data: {list(call_data.keys())}")
    dynamic_vars = call_data.get("retell_llm_dynamic_variables", {})
    call_analysis = call_data.get("call_analysis", {})
    custom_data = call_data.get("custom_analysis_data", {})
    llm_response = call_data.get("llm_response", {})
    logger.info(f"🔹 retell_llm_dynamic_variables keys: {list(dynamic_vars.keys())}")
    logger.info(f"🔹 call_analysis type: {type(call_analysis)}, content: {call_analysis}")
    logger.info(f"🔹 custom_analysis_data: {custom_data}")
    logger.info(f"🔹 llm_response: {llm_response}")

    # ---- Emergency keyword detection ----
    emergency_patterns = {
        "severe pain": ["severe pain", "excruciating", "unbearable"],
        "bleeding": ["bleeding", "hemorrhage", "blood"],
        "trauma": ["accident", "knocked out", "broken tooth"],
        "infection": ["abscess", "swollen", "fever", "pus"],
    }
    user_lines = [
        line.lower()
        for line in transcript.split("\n")
        if any(prefix in line.lower() for prefix in ["user:", "caller:", "customer:"])
    ]
    user_text = " ".join(user_lines)
    emergency_keywords = [
        cat for cat, kws in emergency_patterns.items() if any(kw in user_text for kw in kws)
    ]
    emergency_detected = len(emergency_keywords) > 0

    # ---- Reason classification ----
    t_low = transcript.lower()
    if "cleaning" in t_low or "checkup" in t_low:
        reason = "Cleaning/Checkup"
    elif "pain" in t_low or "hurt" in t_low:
        reason = "Pain/Emergency"
    elif "appointment" in t_low:
        reason = "Appointment Request"
    else:
        reason = "General Inquiry"

    # ---- Persist analysis ----
    now_iso = datetime.now(timezone.utc).isoformat()
    update_data = {
        "event_type": "call_analyzed",
        "transcript": transcript,
        "emergency_detected": emergency_detected,
        "emergency_keywords": emergency_keywords,
        "reason_for_call": reason,
        "call_analysis": call_data.get("call_analysis", {}),
        "updated_at": now_iso,
    }
    result = await db.call_logs.update_one(
        {"practice_id": practice_id, "call_id": call_id},
        {"$set": update_data},
    )
    if result.matched_count:
        logger.info(
            f"Call analyzed: {call_id}, emergency: {emergency_detected}, reason: {reason}"
        )
    else:
        logger.warning(f"Call log not found for {call_id}, creating new entry")
        await db.call_logs.insert_one({
            "practice_id": practice_id,
            "call_id": call_id,
            **update_data,
            "created_at": now_iso,
        })

    # ---- Raise emergency alert ----
    if emergency_detected:
        logger.critical(f"🚨 EMERGENCY DETECTED: {call_id} - {emergency_keywords}")
        await db.emergency_alerts.insert_one({
            "practice_id": practice_id,
            "call_id": call_id,
            "keywords": emergency_keywords,
            "transcript_excerpt": transcript[:500],
            "severity": "high",
            "acknowledged": False,
            "created_at": now_iso,
        })

    # ---- Auto-create / link patient ----
    from_number = call_data.get("from_number", "")
    patient_id = None
    if from_number:
        existing = await db.patients.find_one(
            {"practice_id": practice_id, "phone": from_number}, {"_id": 0}
        )
        if existing:
            patient_id = existing.get("id")
            await db.call_logs.update_one(
                {"practice_id": practice_id, "call_id": call_id},
                {"$set": {"patient_id": patient_id, "patient_name": existing.get("name")}},
            )
            logger.info(f"Linked call {call_id} to existing patient {patient_id}")
        else:
            patient_name, extracted_reason, extracted_email = _extract_caller_details(
                call_data, transcript, dynamic_vars, call_analysis
            )
            if extracted_reason:
                reason = extracted_reason
                logger.info(f"✅ Using extracted reason: {reason}")
            if not patient_name:
                patient_name = f"Caller {from_number[-4:]}"
                logger.warning(
                    f"⚠️ No name extracted for {call_id}, using placeholder: {patient_name}"
                )

            patient_id = str(uuid4())
            name_parts = patient_name.split(maxsplit=1)
            await db.patients.insert_one({
                "id": patient_id,
                "practice_id": practice_id,
                "name": patient_name,
                "first_name": name_parts[0] if name_parts else "",
                "last_name": name_parts[1] if len(name_parts) > 1 else "",
                "phone": from_number,
                "email": extracted_email or None,
                "source": f"retell_call_{call_id}",
                "notes": (
                    "Auto-created from Retell AI call. Please update patient information."
                    if "Caller" in patient_name
                    else f"Created from Retell AI call. Extracted info: {reason}"
                ),
                "created_at": now_iso,
                "updated_at": now_iso,
            })
            await db.call_logs.update_one(
                {"practice_id": practice_id, "call_id": call_id},
                {"$set": {"patient_id": patient_id, "patient_name": patient_name}},
            )
            logger.info(
                f"Auto-created patient: {patient_name} ({from_number}) from call {call_id}"
            )

    # ---- Auto-create appointment on booking intent ----
    if patient_id and transcript:
        booking_keywords = ["appointment", "schedule", "book", "come in", "see the dentist"]
        has_booking_intent = any(kw in t_low for kw in booking_keywords)

        if has_booking_intent or emergency_detected:
            patient_record = await db.patients.find_one({"id": patient_id}, {"_id": 0})
            patient_name_for_apt = (
                patient_record.get("name") if patient_record else "Unknown Patient"
            )

            extracted_date, extracted_time = extract_appointment_datetime_from_transcript(
                transcript
            )
            if extracted_date:
                appointment_date = extracted_date
                logger.info(f"✅ Extracted appointment date from transcript: {extracted_date}")
            else:
                base = datetime.now(timezone.utc).date() if emergency_detected else (
                    datetime.now(timezone.utc) + timedelta(days=3)
                ).date()
                appointment_date = base.isoformat()
                logger.info(f"⚠️ Using default appointment date: {appointment_date}")

            provider_id, provider_name = await _match_provider(
                db, practice_id, preferred_provider_name, emergency_detected
            )

            appointment_id = str(uuid4())
            appointment_doc = {
                "id": appointment_id,
                "practice_id": practice_id,
                "patient_id": patient_id,
                "patient_name": patient_name_for_apt,
                "appointment_date": appointment_date,
                "appointment_time": extracted_time,
                "reason": reason,
                "status": "pending_verification",
                "is_emergency": emergency_detected,
                "notes": f"Auto-created from Retell AI call {call_id}. Please verify with patient.",
                "source": f"retell_call_{call_id}",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            if provider_id:
                appointment_doc["provider_id"] = provider_id
                appointment_doc["provider_name"] = provider_name

            await db.appointments.insert_one(appointment_doc)
            await db.call_logs.update_one(
                {"practice_id": practice_id, "call_id": call_id},
                {"$set": {"appointment_id": appointment_id}},
            )

            provider_info = f"with {provider_name}" if provider_name else "(unassigned provider)"
            logger.info(
                f"Auto-created appointment {appointment_id} for patient "
                f"{patient_name_for_apt} ({patient_id}) on {appointment_date} "
                f"at {extracted_time} {provider_info}"
            )


# ==== HELPERS ====

def _extract_caller_details(
    call_data: dict,
    transcript: str,
    dynamic_vars: dict,
    call_analysis: dict,
) -> tuple[str | None, str | None, str | None]:
    """
    Pull patient_name / reason / email from wherever Retell put them.
    Falls back to the smart transcript parser if Retell's own extraction is empty.

    Returns (patient_name, reason, email) — any or all may be None.
    """
    patient_name = None
    extracted_reason = None
    extracted_email = None

    locations = [
        call_data,
        dynamic_vars,
        call_analysis,
        call_data.get("custom_analysis_data", {}),
        call_data.get("llm_response", {}),
    ]
    name_fields = ["patient_name", "customer_name", "caller_name", "name", "full_name"]
    reason_fields = ["call_reason", "reason", "reason_for_call", "visit_reason"]
    email_fields = ["patient_email", "email", "customer_email"]

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if not patient_name:
            for f in name_fields:
                if loc.get(f):
                    patient_name = str(loc[f]).strip()
                    logger.info(f"✅ Extracted patient_name from {f}: {patient_name}")
                    break
        if not extracted_reason:
            for f in reason_fields:
                if loc.get(f):
                    extracted_reason = str(loc[f]).strip()
                    logger.info(f"✅ Extracted call_reason from {f}: {extracted_reason}")
                    break
        if not extracted_email:
            for f in email_fields:
                if loc.get(f):
                    extracted_email = str(loc[f]).strip()
                    logger.info(f"✅ Extracted email from {f}: {extracted_email}")
                    break

    # Fall back to smart extraction from transcript
    if not patient_name and transcript:
        logger.info("⚠️ Retell extraction failed, attempting smart extraction from transcript")
        from utils.transcript_parser import smart_extract
        smart = smart_extract(transcript, call_data)
        patient_name = smart.get("patient_name")
        extracted_reason = extracted_reason or smart.get("call_reason")
        extracted_email = extracted_email or smart.get("patient_email")
        if patient_name:
            logger.info(f"✅ Smart extraction found name: {patient_name}")

    return patient_name, extracted_reason, extracted_email


async def _match_provider(db, practice_id: str, preferred_name: str | None, is_emergency: bool):
    """Match preferred_name against the active roster; fall back to on-call for emergencies."""
    provider_id = None
    provider_name = None

    if preferred_name:
        logger.info(f"🔍 Attempting to match provider: {preferred_name}")
        providers = await db.providers.find(
            {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]},
            {"_id": 0},
        ).to_list(100)

        search_query = preferred_name.lower().replace("dr.", "").replace("doctor", "").strip()
        partial_matches = []
        for p in providers:
            full = p.get("name", "").lower().replace("dr.", "").strip()
            if search_query == full:
                provider_id = p.get("id")
                provider_name = p.get("name")
                logger.info(f"✅ EXACT MATCH: {provider_name}")
                break
            search_parts = search_query.split()
            prov_parts = full.split()
            if search_parts and prov_parts and search_parts[-1] == prov_parts[-1]:
                partial_matches.append(p)

        if not provider_id and partial_matches:
            logger.warning(
                f"⚠️ No exact match for '{preferred_name}'. "
                f"Found similar: {[p.get('name') for p in partial_matches]}"
            )

    if is_emergency and not provider_id:
        on_call = await db.providers.find_one(
            {"practice_id": practice_id, "on_call": True,
             "$or": [{"active": True}, {"is_active": True}]},
            {"_id": 0},
        )
        if on_call:
            provider_id = on_call.get("id")
            provider_name = on_call.get("name")
            logger.info(f"🚨 Emergency appointment assigned to on-call provider: {provider_name}")

    return provider_id, provider_name


# ---- Date/time extraction from transcript (unchanged logic from server.py) ----

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

_DAY_WORDS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10, "eleventh": 11, "11th": 11, "twelfth": 12, "12th": 12,
    "thirteenth": 13, "13th": 13, "fourteenth": 14, "14th": 14,
    "fifteenth": 15, "15th": 15, "sixteenth": 16, "16th": 16,
    "seventeenth": 17, "17th": 17, "eighteenth": 18, "18th": 18,
    "nineteenth": 19, "19th": 19, "twentieth": 20, "20th": 20,
    "twenty-first": 21, "21st": 21, "twenty-second": 22, "22nd": 22,
    "twenty-third": 23, "23rd": 23, "twenty-fourth": 24, "24th": 24,
    "twenty-fifth": 25, "25th": 25, "twenty-sixth": 26, "26th": 26,
    "twenty-seventh": 27, "27th": 27, "twenty-eighth": 28, "28th": 28,
    "twenty-ninth": 29, "29th": 29, "thirtieth": 30, "30th": 30,
    "thirty-first": 31, "31st": 31,
}

_HOUR_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def extract_appointment_datetime_from_transcript(transcript: str) -> tuple:
    """Extract appointment (date, time) from user lines in the transcript."""
    user_lines = [
        line.lower()
        for line in transcript.split("\n")
        if any(prefix in line.lower() for prefix in ["user:", "caller:", "customer:"])
    ]
    user_text = " ".join(user_lines)

    # Date: month + day (word or numeric)
    date_pattern = (
        r"(" + "|".join(_MONTHS.keys()) + r")\s+"
        r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
        r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
        r"eighteenth|nineteenth|twentieth|twenty-first|twenty-second|twenty-third|"
        r"twenty-fourth|twenty-fifth|twenty-sixth|twenty-seventh|twenty-eighth|"
        r"twenty-ninth|thirtieth|thirty-first|1st|2nd|3rd|\d+th|\d+)"
    )
    date_match = re.search(date_pattern, user_text, re.IGNORECASE)

    appointment_date = None
    if date_match:
        month_str = date_match.group(1).lower()
        day_str = date_match.group(2).lower()
        day = _DAY_WORDS.get(
            day_str,
            int(re.sub(r"[^0-9]", "", day_str)) if re.sub(r"[^0-9]", "", day_str) else 1,
        )
        month = _MONTHS[month_str]
        now = datetime.now(timezone.utc)
        year = now.year
        if month < now.month or (month == now.month and day < now.day):
            year += 1
        try:
            appointment_date = date(year, month, day).isoformat()
        except ValueError:
            appointment_date = None

    # Time: numeric first, then word-based
    appointment_time = "09:00"
    m = re.search(r"\b(\d{1,2}):?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)\b", user_text, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute_str = m.group(2) or "00"
        meridiem = m.group(3)
        if meridiem and "pm" in meridiem.lower() and hour != 12:
            hour += 12
        elif meridiem and "am" in meridiem.lower() and hour == 12:
            hour = 0
        appointment_time = f"{hour:02d}:{minute_str}"
    else:
        m = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
            r"(?:\s+|:)(?:(\d{2})\s*)?(am|pm|a\.m\.|p\.m\.)\b",
            user_text,
            re.IGNORECASE,
        )
        if m:
            hour = _HOUR_WORDS.get(m.group(1).lower(), 9)
            minute_str = m.group(2) or "00"
            meridiem = m.group(3)
            if meridiem and "pm" in meridiem.lower() and hour != 12:
                hour += 12
            elif meridiem and "am" in meridiem.lower() and hour == 12:
                hour = 0
            appointment_time = f"{hour:02d}:{minute_str}"

    return (appointment_date, appointment_time)
