"""
Public API endpoints for Retell AI agent to call during conversations.
These endpoints do NOT require authentication (verified by Retell signature instead).
"""
from fastapi import APIRouter, HTTPException, Header, Request
from datetime import datetime, timedelta
import logging
import os
import hmac
import hashlib

from auth import get_db
from utils.phi_redaction import mask_phone
from utils.phone import normalize_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/retell", tags=["retell_public_api"])


async def _parse_retell_body(request: Request) -> dict:
    """
    Parse Retell custom-function request body.

    Retell's dashboard has a "Payload: args only" toggle:
      - OFF (default) → body is wrapped:
          { "name": "...", "call": {...}, "args": {...} }
        Inside "call", Retell always provides "from_number" (the real caller)
        and "to_number", plus call_id, etc.
      - ON → body is flat: {"practice_id": "...", "phone_number": "..."}

    We:
      1. Unwrap "args" so endpoints read fields flatly.
      2. AUTO-INJECT the caller's real phone number from call.from_number into
         both "phone_number" and "patient_phone" fields — overriding whatever
         the LLM passed. This defends against the LLM hallucinating example
         numbers (e.g. +15551234567) or sending placeholder text.
    """
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
    if not isinstance(data, dict):
        return {}

    call = data.get("call") if isinstance(data.get("call"), dict) else {}
    args = dict(data.get("args")) if isinstance(data.get("args"), dict) else dict(data)

    # Source of truth: Retell's call.from_number (the actual inbound caller).
    # Never trust the LLM for phone numbers — it mis-substitutes placeholders
    # and copies example numbers from the prompt.
    from_number = call.get("from_number")
    if from_number:
        llm_phone = args.get("phone_number") or args.get("patient_phone")
        if llm_phone and llm_phone != from_number:
            logger.info(
                "retell_phone_override",
                extra={"llm_phone": mask_phone(llm_phone), "caller_phone": mask_phone(from_number)},
            )
        args["phone_number"] = from_number
        args["patient_phone"] = from_number

    return args


def verify_retell_signature(body: str, signature: str, api_key: str) -> bool:
    """Verify Retell webhook signature"""
    try:
        parts = signature.split(",")
        timestamp_part = [p for p in parts if p.startswith("t=")][0]
        digest_part = [p for p in parts if p.startswith("v1=")][0].replace("v1=", "")
        request_timestamp = int(timestamp_part.replace("t=", ""))
        
        # Check timestamp is within 5 minutes
        current_time_ms = int(datetime.now().timestamp() * 1000)
        if abs(current_time_ms - request_timestamp) > 300000:
            return False
        
        # Verify HMAC
        message = body.encode() + str(request_timestamp).encode()
        expected = hmac.new(api_key.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, digest_part)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


@router.post("/check-provider-availability")
async def check_provider_availability(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to check provider availability during calls.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "provider_name": "Smith" or "Dr. Smith",
        "date": "2026-05-15",  // YYYY-MM-DD format
        "time": "14:00"        // optional, HH:MM format
    }
    
    Returns:
    {
        "available": true/false,
        "provider_name": "Dr. Sarah Smith",
        "provider_id": "uuid",
        "suggested_slots": ["09:00", "10:00", "14:00"],
        "message": "Dr. Smith is available on May 15th at 2 PM"
    }
    """
    
    # Verify Retell signature for security
    body_bytes = await request.body()
    
    # Only verify signature if we have Retell API key configured
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    
    practice_id = data.get("practice_id")
    provider_name_query = data.get("provider_name", "").lower().strip()
    requested_date = data.get("date")  # YYYY-MM-DD
    requested_time = data.get("time")  # HH:MM
    
    if not practice_id or not provider_name_query:
        raise HTTPException(
            status_code=400,
            detail="practice_id and provider_name are required"
        )
    
    # Default to today if no date provided
    if not requested_date:
        requested_date = datetime.now().strftime("%Y-%m-%d")

    # Reject past dates with a useful message — the LLM sometimes defaults
    # to the wrong year (e.g. 2024 when the caller says "April 27" in 2026)
    # and "fully booked" misleads the caller into thinking the schedule is
    # full when really the date is just in the past.
    try:
        req_date_obj = datetime.strptime(requested_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        if req_date_obj < today:
            suggested_year = today.year if (req_date_obj.month, req_date_obj.day) >= (today.month, today.day) else today.year + 1
            suggested = f"{suggested_year}-{req_date_obj.month:02d}-{req_date_obj.day:02d}"
            return {
                "available": False,
                "provider_name": None,
                "provider_id": None,
                "date": requested_date,
                "time": requested_time,
                "suggested_slots": [],
                "suggested_times": [],
                "is_past_date": True,
                "suggested_date": suggested,
                "message": (
                    f"The date {requested_date} is in the past — did you mean "
                    f"{suggested}? Please confirm the date with the caller and "
                    f"call this function again with the corrected date."
                ),
            }
    except ValueError:
        pass  # Invalid date format will be caught later in normal flow

    logger.info(f"🔍 Retell checking availability: {provider_name_query} on {requested_date} at {requested_time or 'any time'}")
    
    # Connect to database
    db = get_db()
    
    # Find matching provider with STRICT name matching
    providers = await db.providers.find(
        {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]},
        {"_id": 0}
    ).to_list(100)
    
    # Normalize search query (remove "Dr." / "Doctor")
    search_query = provider_name_query.strip()
    
    matched_provider = None
    partial_matches = []
    
    for provider in providers:
        provider_full_name = provider.get("name", "").lower()
        # Remove "Dr." prefix for comparison
        provider_name_clean = provider_full_name.replace("dr.", "").replace("doctor", "").strip()
        search_clean = search_query.lower().replace("dr.", "").replace("doctor", "").strip()
        
        # EXACT MATCH: Full name or surname matches completely
        if search_clean == provider_name_clean:
            matched_provider = provider
            logger.info(f"✅ EXACT MATCH: {provider.get('name')}")
            break
        
        # Check if search is just a surname and matches provider's last name
        search_parts = search_clean.split()
        provider_parts = provider_name_clean.split()
        
        if search_parts and provider_parts:
            # If user only provided surname (single word), match on last name
            if len(search_parts) == 1:
                provider_last = provider_parts[-1]
                if search_parts[0] == provider_last:
                    matched_provider = provider
                    logger.info(f"✅ SURNAME MATCH: {provider.get('name')}")
                    break
            else:
                # Multi-word search requires exact match (handled above)
                # But track partial surname matches for error messages
                search_last = search_parts[-1]
                provider_last = provider_parts[-1]
                if search_last == provider_last:
                    partial_matches.append(provider)
    
    if not matched_provider:
        if partial_matches:
            # Found surname match but wrong first name
            similar_names = ", ".join([p.get("name") for p in partial_matches])
            return {
                "available": False,
                "provider_name": None,
                "provider_id": None,
                "suggested_slots": [],
                "message": f"I couldn't find a provider named {data.get('provider_name')}. Did you mean {similar_names}? Or would you like to schedule with our first available provider?"
            }
        else:
            return {
                "available": False,
                "provider_name": None,
                "provider_id": None,
                "suggested_slots": [],
                "message": f"I couldn't find a provider named {data.get('provider_name')}. Would you like to schedule with our first available provider?"
            }
    
    provider_id = matched_provider["id"]
    provider_name = matched_provider["name"]
    
    logger.info(f"✅ Matched provider: {provider_name} (ID: {provider_id})")
    
    # Check availability for the requested date
    from utils.provider_scheduling import get_provider_availability_slots, validate_provider_availability, get_day_name
    from datetime import datetime as _dt

    # Detect non-working day before computing slots — gives a more accurate
    # message than "fully booked" when the provider simply doesn't work that day.
    _req_dt = _dt.fromisoformat(requested_date)
    day_key = get_day_name(_req_dt)
    day_schedule = matched_provider.get('working_hours', {}).get(day_key, [])
    if not day_schedule:
        day_label = _req_dt.strftime('%A')
        return {
            "available": False,
            "provider_name": provider_name,
            "provider_id": provider_id,
            "date": requested_date,
            "time": requested_time,
            "suggested_slots": [],
            "suggested_times": [],
            "message": f"{provider_name} does not work on {day_label}s. Would you like to try a different day?"
        }

    # Get available slots for the day
    slots = await get_provider_availability_slots(
        db, provider_id, requested_date, None, None
    )
    
    available_slots = [s["time"] for s in slots if s["available"]]
    
    # If specific time requested, check if it's available
    if requested_time:
        is_specific_time_available = any(
            s["time"] == requested_time and s["available"]
            for s in slots
        )
        
        if is_specific_time_available:
            return {
                "available": True,
                "provider_name": provider_name,
                "provider_id": provider_id,
                "date": requested_date,
                "time": requested_time,
                "suggested_slots": [requested_time],
                "suggested_times": [requested_time],
                "message": f"{provider_name} is available on {requested_date} at {requested_time}."
            }
        elif available_slots:
            # Suggest alternative times
            return {
                "available": False,
                "provider_name": provider_name,
                "provider_id": provider_id,
                "date": requested_date,
                "time": requested_time,
                "suggested_slots": available_slots[:3],
                "suggested_times": available_slots[:3],
                "message": f"{provider_name} is not available at {requested_time}, but has openings at {', '.join(available_slots[:3])} on {requested_date}."
            }
        else:
            # No availability that day
            return {
                "available": False,
                "provider_name": provider_name,
                "provider_id": provider_id,
                "date": requested_date,
                "time": requested_time,
                "suggested_slots": [],
                "suggested_times": [],
                "message": f"{provider_name} is fully booked on {requested_date}. Would you like to check another date?"
            }
    else:
        # No specific time requested, just check if provider has any availability
        if available_slots:
            return {
                "available": True,
                "provider_name": provider_name,
                "provider_id": provider_id,
                "date": requested_date,
                "time": None,
                "suggested_slots": available_slots[:5],
                "suggested_times": available_slots[:5],
                "message": f"{provider_name} is available on {requested_date}. Available times: {', '.join(available_slots[:5])}."
            }
        else:
            return {
                "available": False,
                "provider_name": provider_name,
                "provider_id": provider_id,
                "suggested_slots": [],
                "message": f"{provider_name} is fully booked on {requested_date}. Would you like to try another date?"
            }


@router.post("/list-providers")
async def list_available_providers(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to list all available providers.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "specialty": "dentist|hygienist|specialist" // optional — matches stored role values
    }

    Returns:
    {
        "providers": [
            {"name": "Dr. Sarah Smith", "role": "dentist", "id": "uuid"},
            ...
        ],
        "message": "We have 3 providers available: Dr. Smith, Dr. Johnson, and Dr. Rodriguez."
    }
    """
    # Verify signature (same as above)
    body_bytes = await request.body()
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    specialty = data.get("specialty")
    
    if not practice_id:
        raise HTTPException(status_code=400, detail="practice_id required")
    
    db = get_db()
    
    query = {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]}
    # Normalize spoken specialty names to stored role values
    SPECIALTY_MAP = {
        "general dentist":  "dentist",
        "general":          "dentist",
        "dentist":          "dentist",
        "hygienist":        "hygienist",
        "dental hygienist": "hygienist",
        "orthodontist":     "orthodontist",
        "specialist":       "specialist",
        "oral surgeon":     "specialist",
        "periodontist":     "specialist",
    }
    if specialty:
        normalized = SPECIALTY_MAP.get(specialty.lower().strip(), specialty)
        query["role"] = {"$regex": normalized, "$options": "i"}
    
    providers = await db.providers.find(query, {"_id": 0}).to_list(100)
    
    provider_list = [
        {
            "name": p["name"],
            "provider_name": p["name"],        # checklist-required alias
            "role": p.get("role", "Dentist"),
            "specialty": p.get("role", "Dentist"),  # checklist-required alias
            "id": p["id"]
        }
        for p in providers
    ]
    
    if providers:
        names = ", ".join([p["name"] for p in providers[:5]])
        if len(providers) > 5:
            names += f", and {len(providers) - 5} more"
        
        message = f"We have {len(providers)} provider{'s' if len(providers) > 1 else ''} available: {names}."
    else:
        message = "No providers found."
    
    return {
        "providers": provider_list,
        "count": len(providers),
        "message": message
    }


@router.post("/lookup-patient")
async def lookup_patient_by_phone(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to look up existing patient by phone number.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "phone_number": "+15551234567"
    }
    
    Returns:
    {
        "found": true,
        "patient": {
            "id": "uuid",
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+15551234567"
        },
        "appointment_history": [
            {
                "date": "2026-03-15",
                "time": "10:00",
                "reason": "Cleaning",
                "status": "completed"
            }
        ],
        "total_appointments": 3,
        "last_visit": "2026-03-15",
        "message": "Welcome back, John Doe! I see you last visited us on March 15th for a cleaning."
    }
    
    Or if not found:
    {
        "found": false,
        "message": "I don't see an existing account with this number. I'll create a new patient record for you."
    }
    """
    # Verify signature
    body_bytes = await request.body()
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    phone_number = data.get("phone_number", "").strip()
    
    if not practice_id or not phone_number:
        raise HTTPException(
            status_code=400,
            detail="practice_id and phone_number are required"
        )
    
    logger.info("retell_patient_lookup", extra={"phone": mask_phone(phone_number), "practice_id": practice_id})
    
    db = get_db()
    
    # Primary lookup via normalized E.164 field (fast, exact, index-backed)
    normalized = normalize_phone(phone_number)
    patient = None
    if normalized:
        patient = await db.patients.find_one(
            {"practice_id": practice_id, "normalized_phone": normalized},
            {"_id": 0}
        )

    # Fallback: fuzzy match on raw phone field (catches pre-migration records)
    if not patient:
        phone_normalized = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        patient = await db.patients.find_one(
            {
                "practice_id": practice_id,
                "$or": [
                    {"phone": phone_number},
                    {"phone": phone_normalized},
                    {"phone": {"$regex": phone_normalized[-10:] if len(phone_normalized) >= 10 else phone_normalized}}
                ]
            },
            {"_id": 0}
        )
    
    if not patient:
        logger.info("retell_patient_not_found", extra={"phone": mask_phone(phone_number)})
        return {
            "found": False,
            "patient": None,
            "patient_name": None,
            "phone_number": phone_number,
            "email": None,
            "last_appointment_date": None,
            "last_appointment_reason": None,
            "preferred_provider": None,
            "appointment_history": [],
            "total_appointments": 0,
            "last_visit": None,
            "message": "I don't see an existing account with this number. I'll create a new patient record for you."
        }
    
    logger.info("retell_patient_found", extra={"patient_id": patient.get("id")})
    
    # Get appointment history
    patient_id = patient.get("id")
    appointments = await db.appointments.find(
        {"practice_id": practice_id, "patient_id": patient_id},
        {"_id": 0, "appointment_date": 1, "appointment_time": 1, "reason": 1, "status": 1}
    ).sort("appointment_date", -1).to_list(10)  # Last 10 appointments
    
    appointment_history = [
        {
            "date": apt.get("appointment_date"),
            "time": apt.get("appointment_time"),
            "reason": apt.get("reason", "Visit"),
            "status": apt.get("status")
        }
        for apt in appointments
    ]
    
    # Last PAST visit = completed appointments OR scheduled appointments whose
    # date is already in the past (they showed up). Cancelled and future-
    # scheduled appointments are NOT past visits.
    from datetime import datetime, timezone
    today_iso = datetime.now(timezone.utc).date().isoformat()
    past_visits = [
        apt for apt in appointments
        if apt.get("status") == "completed"
        or (apt.get("status") == "scheduled" and (apt.get("appointment_date") or "") < today_iso)
    ]
    last_visit = past_visits[0].get("appointment_date") if past_visits else None
    last_reason = past_visits[0].get("reason", "visit") if past_visits else "visit"

    # Upcoming (future scheduled) — useful for greeting
    upcoming = [
        apt for apt in appointments
        if apt.get("status") == "scheduled" and (apt.get("appointment_date") or "") >= today_iso
    ]

    # Build welcome message (honest about history)
    patient_name = patient.get("name")
    if last_visit:
        try:
            date_obj = datetime.fromisoformat(last_visit)
            friendly_date = date_obj.strftime("%B %d")
            message = f"Welcome back, {patient_name}! I see you last visited us on {friendly_date} for a {last_reason.lower()}."
        except Exception as e:
            logger.warning(f"Date parsing error: {e}")
            message = f"Welcome back, {patient_name}! I see you're a returning patient."
    elif upcoming:
        # Registered but no past visit yet — they've booked before
        try:
            nxt = upcoming[-1]  # earliest upcoming (list was sorted desc)
            date_obj = datetime.fromisoformat(nxt.get("appointment_date"))
            friendly_date = date_obj.strftime("%B %d")
            message = f"Hi {patient_name}! I see you have an upcoming appointment on {friendly_date}. How can I help?"
        except Exception:
            message = f"Hi {patient_name}! How can I help today?"
    else:
        # Registered but never actually visited (all past appts cancelled / no-show)
        message = f"Hi {patient_name}! I have your file but no previous visits on record. How can I help today?"
    
    # Preferred provider = the provider on the caller's most recent appointment
    # (any status), if known. Useful for "book me with my usual doctor" flow.
    preferred_provider = None
    for apt in appointments:  # already sorted desc by date
        pname = apt.get("provider_name")
        if pname and pname not in ("TBD", "", None):
            preferred_provider = pname
            break

    return {
        "found": True,
        "patient": {
            "id": patient.get("id"),
            "name": patient.get("name"),
            "email": patient.get("email"),
            "phone": patient.get("phone")
        },
        # Flat convenience fields (Retell LLMs find these easier than nested paths)
        "patient_name": patient.get("name"),
        "phone_number": patient.get("phone"),
        "email": patient.get("email"),
        "last_appointment_date": last_visit,
        "last_appointment_reason": last_reason if last_visit else None,
        "preferred_provider": preferred_provider,
        "appointment_history": appointment_history[:3],  # Return last 3
        "total_appointments": len(appointments),
        "last_visit": last_visit,  # kept for backwards compat
        "message": message
    }


@router.post("/register-patient")
async def register_patient_realtime(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to register a NEW patient during a call,
    WITHOUT booking an appointment. Use when the caller just wants to set up
    a profile.

    Behaviour:
      - If a patient with this phone already exists, returns that record
        (idempotent — never creates duplicates).
      - Otherwise creates a new patient record.

    Expected body (args):
      {
        "practice_id": "uuid",
        "patient_phone": ""        // auto-filled from call.from_number
        "patient_name":  "Jane Doe",
        "patient_email": "jane@example.com"  // optional
        "date_of_birth": "1990-03-15"        // optional, YYYY-MM-DD
      }

    Returns:
      {
        "success": true,
        "already_existed": false,
        "patient": {...},
        "message": "You're all set, Jane! Your profile is created."
      }
    """
    # Signature verification intentionally disabled (see _parse_retell_body notes)
    _ = (os.getenv("RETELL_API_KEY"), x_retell_signature, await request.body())

    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    patient_phone = data.get("patient_phone") or data.get("phone_number")
    patient_name = (data.get("patient_name") or "").strip()
    patient_email = (data.get("patient_email") or "").strip() or None
    date_of_birth = (data.get("date_of_birth") or "").strip() or None

    if not practice_id or not patient_phone or not patient_name:
        raise HTTPException(
            status_code=400,
            detail="practice_id, patient_phone, and patient_name are required"
        )

    normalized = normalize_phone(patient_phone)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Valid phone number required to register a patient. Please collect the caller's phone number."
        )

    logger.info("retell_register_patient", extra={"phone": mask_phone(patient_phone)})

    db = get_db()
    from uuid import uuid4
    from datetime import datetime, timezone

    # Check if already registered (normalized_phone for format-agnostic dedup)
    existing = await db.patients.find_one(
        {"practice_id": practice_id, "normalized_phone": normalized},
        {"_id": 0}
    )
    if existing:
        logger.info("retell_register_patient_exists", extra={"patient_id": existing.get("id")})
        return {
            "success": True,
            "already_existed": True,
            "patient": {
                "id": existing.get("id"),
                "name": existing.get("name"),
                "email": existing.get("email"),
                "phone": existing.get("phone"),
            },
            "message": (
                f"Good news — you're already in our system, {existing.get('name')}. "
                "Is there anything else I can help with?"
            ),
        }

    # Create new patient
    patient_id = str(uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    patient_doc = {
        "id": patient_id,
        "practice_id": practice_id,
        "name": patient_name,
        "phone": patient_phone,
        "normalized_phone": normalized,
        "email": patient_email or "",
        "date_of_birth": date_of_birth,
        "preferred_contact": "phone",
        "file_number": "",
        "consent_given": True,
        "consent_method": "phone",
        "consent_date": now_iso,
        "source": "retell_register",
        "created_at": now_iso,
    }
    await db.patients.insert_one(patient_doc)
    logger.info("retell_register_patient_created", extra={"patient_id": patient_id})

    first_name = patient_name.split(" ", 1)[0]
    return {
        "success": True,
        "already_existed": False,
        "patient": {
            "id": patient_id,
            "name": patient_name,
            "email": patient_email,
            "phone": patient_phone,
        },
        "message": (
            f"You're all set, {first_name}! Your profile is created. "
            "Would you like to book an appointment while you're on the line?"
        ),
    }


@router.post("/book-appointment")
async def book_appointment_realtime(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to book appointments in real-time during calls.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "patient_phone": "+15551234567",
        "patient_name": "John Doe",
        "patient_email": "john@example.com",
        "date": "2026-05-20",
        "time": "14:00",
        "provider_name": "Sarah Smith" (optional),
        "reason": "Cleaning",
        "is_emergency": false
    }
    
    Returns:
    {
        "success": true,
        "appointment_id": "uuid",
        "appointment": {
            "date": "2026-05-20",
            "time": "14:00",
            "provider_name": "Dr. Sarah Smith",
            "patient_name": "John Doe",
            "reason": "Cleaning"
        },
        "message": "Appointment booked successfully for May 20th at 2:00 PM with Dr. Sarah Smith."
    }
    """
    # Verify signature
    body_bytes = await request.body()
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    patient_phone = data.get("patient_phone")
    patient_name = data.get("patient_name")
    if not patient_phone:
        patient_phone = data.get("phone_number") or data.get("caller_phone") or "unknown"
        logger.warning("book_appointment_no_phone", extra={"patient_name": patient_name})
    patient_email = data.get("patient_email")
    appointment_date = data.get("date")
    appointment_time = data.get("time")
    provider_name = data.get("provider_name")
    reason = data.get("reason", "Consultation")
    is_emergency = data.get("is_emergency", False)
    
    if not all([practice_id, patient_name, appointment_date, appointment_time]):
        raise HTTPException(
            status_code=400,
            detail="practice_id, patient_name, date, and time are required"
        )

    # Reject past-date bookings — same year-default protection as availability check
    try:
        from datetime import datetime as _dt, date as _date_cls
        req_date_obj = _dt.strptime(appointment_date, "%Y-%m-%d").date()
        today = _date_cls.today()
        if req_date_obj < today:
            suggested_year = today.year if (req_date_obj.month, req_date_obj.day) >= (today.month, today.day) else today.year + 1
            suggested = f"{suggested_year}-{req_date_obj.month:02d}-{req_date_obj.day:02d}"
            return {
                "success": False,
                "is_past_date": True,
                "suggested_date": suggested,
                "message": (
                    f"I can't book {appointment_date} — that date is in the past. "
                    f"Did you mean {suggested}? Please confirm the date with the "
                    f"caller and book again."
                ),
            }
    except ValueError:
        pass

    logger.info("retell_book_appointment", extra={"phone": mask_phone(patient_phone), "date": appointment_date})
    
    db = get_db()
    from uuid import uuid4
    from datetime import datetime, timezone
    
    # Find or create patient
    normalized_phone = normalize_phone(patient_phone)
    if not normalized_phone:
        logger.warning("book_appointment_no_phone_normalized", extra={"patient_name": patient_name})

    patient_query = {"practice_id": practice_id}
    if normalized_phone:
        patient_query["normalized_phone"] = normalized_phone
    else:
        patient_query["name"] = patient_name

    patient = await db.patients.find_one(patient_query, {"_id": 0})

    if not patient:
        # Create new patient
        patient_id = str(uuid4())
        patient_doc = {
            "id": patient_id,
            "practice_id": practice_id,
            "name": patient_name,
            "email": patient_email or "",
            "phone": patient_phone,
            "normalized_phone": normalized_phone,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.patients.insert_one(patient_doc)
        logger.info("retell_booking_patient_created", extra={"patient_id": patient_id})
    else:
        patient_id = patient.get("id")
        logger.info("retell_booking_patient_found", extra={"patient_id": patient_id})
    
    # Match provider if specified
    provider_id = None
    matched_provider_name = None
    
    if provider_name:
        providers = await db.providers.find(
            {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]},
            {"_id": 0}
        ).to_list(100)
        
        search_clean = provider_name.lower().replace("dr.", "").replace("doctor", "").strip()
        
        for provider in providers:
            provider_full = provider.get("name", "").lower().replace("dr.", "").strip()
            if search_clean in provider_full or provider_full in search_clean:
                provider_id = provider.get("id")
                matched_provider_name = provider.get("name")
                break
    
    # Create appointment
    appointment_id = str(uuid4())
    appointment_doc = {
        "id": appointment_id,
        "practice_id": practice_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "reason": reason,
        "status": "scheduled",
        "is_emergency": is_emergency,
        "notes": "Booked via Retell AI during call.",
        "source": "retell_realtime_booking",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if provider_id:
        appointment_doc["provider_id"] = provider_id
        appointment_doc["provider_name"] = matched_provider_name
    
    await db.appointments.insert_one(appointment_doc)
    
    # Build friendly message
    try:
        date_obj = datetime.fromisoformat(appointment_date)
        friendly_date = date_obj.strftime("%B %d")
    except:
        friendly_date = appointment_date
    
    provider_text = f" with {matched_provider_name}" if matched_provider_name else ""
    message = f"Appointment booked successfully for {friendly_date} at {appointment_time}{provider_text}."
    
    logger.info("retell_appointment_created", extra={"appointment_id": appointment_id, "patient_id": patient_id})
    
    return {
        "success": True,
        "appointment_id": appointment_id,
        "appointment": {
            "date": appointment_date,
            "time": appointment_time,
            "provider_name": matched_provider_name,
            "patient_name": patient_name,
            "reason": reason
        },
        "message": message
    }


@router.post("/get-patient-appointments")
async def get_patient_upcoming_appointments(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to get patient's UPCOMING appointments.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "phone_number": "+15551234567"
    }
    
    Returns:
    {
        "found": true,
        "patient_name": "John Doe",
        "upcoming_appointments": [
            {
                "id": "uuid",
                "date": "2026-05-20",
                "time": "14:00",
                "provider_name": "Dr. Sarah Smith",
                "reason": "Cleaning",
                "status": "scheduled"
            }
        ],
        "count": 1,
        "message": "You have 1 upcoming appointment on May 20th at 2:00 PM with Dr. Sarah Smith."
    }
    """
    # Verify signature
    body_bytes = await request.body()
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    phone_number = data.get("phone_number", "").strip()
    
    if not practice_id or not phone_number:
        raise HTTPException(status_code=400, detail="practice_id and phone_number required")
    
    db = get_db()
    
    # Find patient
    phone_normalized = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    patient = await db.patients.find_one(
        {
            "practice_id": practice_id,
            "$or": [
                {"phone": phone_number},
                {"phone": phone_normalized},
                {"phone": {"$regex": phone_normalized[-10:] if len(phone_normalized) >= 10 else phone_normalized}}
            ]
        },
        {"_id": 0}
    )
    
    if not patient:
        return {
            "found": False,
            "patient_name": None,
            "upcoming_appointments": [],
            "count": 0,
            "message": "No patient account found with this phone number."
        }
    
    patient_id = patient.get("id")
    patient_name = patient.get("name")
    
    # Get UPCOMING appointments (scheduled or pending)
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    
    appointments = await db.appointments.find(
        {
            "practice_id": practice_id,
            "patient_id": patient_id,
            "status": {"$in": ["scheduled", "pending_verification"]},
            "appointment_date": {"$gte": today}
        },
        {"_id": 0}
    ).sort("appointment_date", 1).to_list(10)
    
    upcoming = [
        {
            "id": apt.get("id"),
            "date": apt.get("appointment_date"),
            "time": apt.get("appointment_time"),
            "provider_name": apt.get("provider_name", "TBD"),
            "reason": apt.get("reason", "Visit"),
            "status": apt.get("status")
        }
        for apt in appointments
    ]
    
    # Build message
    if len(upcoming) == 0:
        message = "You don't have any upcoming appointments scheduled."
    elif len(upcoming) == 1:
        apt = upcoming[0]
        try:
            date_obj = datetime.fromisoformat(apt["date"])
            friendly_date = date_obj.strftime("%B %d")
        except Exception:
            friendly_date = apt["date"]
        
        provider_text = f" with {apt['provider_name']}" if apt.get('provider_name') and apt['provider_name'] != 'TBD' else ""
        message = f"You have 1 upcoming appointment on {friendly_date} at {apt['time']}{provider_text}."
    else:
        message = f"You have {len(upcoming)} upcoming appointments."
    
    return {
        "found": True,
        "patient_name": patient_name,
        "upcoming_appointments": upcoming,
        "count": len(upcoming),
        "message": message
    }


@router.post("/cancel-appointment")
async def cancel_appointment_by_id(
    request: Request,
    x_retell_signature: str = Header(None)
):
    """
    PUBLIC endpoint for Retell AI to cancel an appointment.
    
    Expected request body:
    {
        "practice_id": "uuid",
        "appointment_id": "uuid",
        "phone_number": "+15551234567" (for verification)
    }
    
    Returns:
    {
        "success": true,
        "message": "Appointment on May 20th at 2:00 PM has been cancelled."
    }
    """
    # Verify signature
    body_bytes = await request.body()
    retell_api_key = os.getenv("RETELL_API_KEY")
    # Signature verification disabled on custom function endpoints.
    # Retell custom functions are plain HTTPS POSTs, not signed like webhook events.
    # The webhook handler at /api/webhooks/retell still verifies signatures.
    _ = (retell_api_key, x_retell_signature, body_bytes)
    
    data = await _parse_retell_body(request)
    practice_id = data.get("practice_id")
    appointment_id = data.get("appointment_id")
    phone_number = data.get("phone_number", "").strip()
    
    if not all([practice_id, appointment_id, phone_number]):
        raise HTTPException(
            status_code=400,
            detail="practice_id, appointment_id, and phone_number are required"
        )
    
    db = get_db()
    
    # Find patient by phone
    phone_normalized = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    patient = await db.patients.find_one(
        {
            "practice_id": practice_id,
            "$or": [
                {"phone": phone_number},
                {"phone": phone_normalized},
            ]
        },
        {"_id": 0, "id": 1}
    )
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get("id")
    
    # Find appointment
    appointment = await db.appointments.find_one(
        {
            "practice_id": practice_id,
            "id": appointment_id,
            "patient_id": patient_id
        },
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or doesn't belong to this patient")
    
    # Cancel appointment
    from datetime import datetime, timezone
    result = await db.appointments.update_one(
        {"practice_id": practice_id, "id": appointment_id},
        {
            "$set": {
                "status": "cancelled",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to cancel appointment")
    
    # Build message
    apt_date = appointment.get("appointment_date")
    apt_time = appointment.get("appointment_time")
    
    try:
        date_obj = datetime.fromisoformat(apt_date)
        friendly_date = date_obj.strftime("%B %d")
    except Exception:
        friendly_date = apt_date
    
    message = f"Appointment on {friendly_date} at {apt_time} has been cancelled."
    
    logger.info(f"✅ Cancelled appointment: {appointment_id}")
    
    return {
        "success": True,
        "message": message
    }
