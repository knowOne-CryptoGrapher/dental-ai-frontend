"""
Context builder for AI receptionist calls.

Fetches all practice data needed to ground the AI response before any
model call. Returns a ContextBundle — a typed snapshot of practice state
at the time of the call.

A context_hash (SHA-256 of the bundle) is stored with every AI log entry
so auditors can verify exactly what data the model had access to.
"""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ContextBundle:
    practice_id: str
    retrieved_at: str          # ISO8601 timestamp
    context_hash: str          # SHA-256 of the serialized bundle (set after build)
    hours: dict                # Practice hours
    fees: dict                 # Fee schedule
    insurance_notes: str       # Insurance accepted / notes
    appointment_availability: list  # Available slots
    practice_policies: dict    # Cancellation, late arrival, etc.
    patient_record: Optional[dict] = None  # Only if caller is authenticated
    knowledge_context: str = ""  # Formatted knowledge base documents (Enterprise+)
    # Never include: patient health data beyond name and appointment history


async def get_knowledge_context(practice_id: str, db) -> str:
    """
    Fetch practice knowledge documents and format them for LLM context injection.
    Returns an empty string if no documents exist or if the query fails.
    """
    try:
        docs = await db.knowledge.find(
            {"practice_id": practice_id},
            {"_id": 0, "title": 1, "content": 1, "category": 1},
        ).to_list(100)
        if not docs:
            return ""
        lines = ["=== Practice Knowledge Base ==="]
        for doc in docs:
            category = doc.get("category", "General").upper()
            title = doc.get("title", "")
            content = doc.get("content", "")
            lines.append(f"\n[{category}] {title}")
            lines.append(content)
        return "\n".join(lines)
    except Exception:
        return ""


async def build_context(practice_id: str, db, patient_id: str = None) -> ContextBundle:
    """
    Fetch all practice context needed to ground an AI response.

    Args:
        practice_id: The practice making the AI call.
        db: Motor DB handle (practice-scoped).
        patient_id: Optional — only populate patient_record if caller is identified.

    Returns:
        ContextBundle with context_hash populated.
    """
    config = await db.practice_config.find_one(
        {"practice_id": practice_id}, {"_id": 0}
    ) or {}

    now = datetime.now(timezone.utc)
    slots = await db.appointments.find({
        "practice_id": practice_id,
        "start_time": {"$gte": now.isoformat(), "$lte": (now + timedelta(days=7)).isoformat()},
        "status": "available",
    }, {"_id": 0, "start_time": 1, "provider_id": 1, "appointment_type": 1}).to_list(50)

    patient_record = None
    if patient_id:
        patient = await db.patients.find_one(
            {"id": patient_id, "practice_id": practice_id},
            {"_id": 0, "name": 1, "phone": 1}
        )
        if patient:
            recent_appts = await db.appointments.find({
                "practice_id": practice_id,
                "patient_id": patient_id,
            }, {"_id": 0, "start_time": 1, "status": 1, "appointment_type": 1}).sort(
                "start_time", -1
            ).limit(3).to_list(3)
            patient_record = {"name": patient.get("name"), "recent_appointments": recent_appts}

    knowledge_context = await get_knowledge_context(practice_id, db)

    bundle = ContextBundle(
        practice_id=practice_id,
        retrieved_at=now.isoformat(),
        context_hash="",
        hours=config.get("hours", {}),
        fees=config.get("fees", {}),
        insurance_notes=config.get("insurance_notes", ""),
        appointment_availability=slots,
        practice_policies=config.get("policies", {}),
        patient_record=patient_record,
        knowledge_context=knowledge_context,
    )

    bundle_dict = asdict(bundle)
    bundle_dict.pop("context_hash")
    bundle.context_hash = hashlib.sha256(
        json.dumps(bundle_dict, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]

    return bundle


def format_context_for_prompt(bundle: ContextBundle) -> str:
    """
    Format the context bundle as a structured string for injection into the system prompt.

    This is the ONLY source of facts the model is permitted to use.
    """
    lines = [
        "=== PRACTICE CONTEXT (retrieved at call time) ===",
        f"Context ID: {bundle.context_hash}",
        "",
        "HOURS:",
        json.dumps(bundle.hours, indent=2) if bundle.hours else "Not configured.",
        "",
        "FEES:",
        json.dumps(bundle.fees, indent=2) if bundle.fees else "Not configured.",
        "",
        "INSURANCE:",
        bundle.insurance_notes or "Contact the office for insurance details.",
        "",
        "POLICIES:",
        json.dumps(bundle.practice_policies, indent=2) if bundle.practice_policies else "Not configured.",
        "",
        "AVAILABLE APPOINTMENTS (next 7 days):",
    ]
    if bundle.appointment_availability:
        for slot in bundle.appointment_availability[:10]:
            lines.append(f"  - {slot.get('start_time')} ({slot.get('appointment_type', 'General')})")
    else:
        lines.append("  No available appointments found.")

    if bundle.patient_record:
        lines += [
            "",
            "CALLER RECORD:",
            f"  Name: {bundle.patient_record.get('name', 'Unknown')}",
        ]

    if bundle.knowledge_context:
        lines += ["", bundle.knowledge_context]

    lines += [
        "",
        "=== END OF CONTEXT ===",
        "",
        "CRITICAL: You may ONLY answer questions using information in the context above.",
        "If the answer is not in this context, you MUST say: 'I don't have that information.",
        "Please contact the office directly and a team member will be happy to help.'",
    ]
    return "\n".join(lines)
