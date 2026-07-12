"""
Retell end-to-end call scenario runner.

Simulates a full inbound call to the Dental AI backend:
  1. call_started    → creates call_log
  2. list-providers  → gets available providers
  3. book-appointment → books a slot
  4. call_ended      → updates call_log with transcript
  5. call_analyzed   → posts Retell's post-call analysis
  6. call-summary    → posts agent post-call summary
  7. DB verify       → confirms all writes

Usage:
  cd backend
  python tests/retell_sim/scenario_runner.py \\
    --practice-id <id> --agent-id <id>

Options:
  --practice-id  Practice ID to simulate (required)
  --agent-id     Retell agent ID (required)
  --phone        Caller phone number (default: +16471234567)
  --dry-run      Print payloads without sending
  --cleanup      Delete created test data after run
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import date as _date_cls

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# signing.py is in the same package; allow running as __main__ from backend/
sys.path.insert(0, os.path.dirname(__file__))
from signing import post_webhook, post_function, post_summary, BACKEND_URL

MONGO_URI = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URL')
DB_NAME   = os.environ.get('DATABASE_NAME', 'dental_ai')


# --Payload builders ----------------------------------------------------------

def make_call_started(call_id, practice_id, agent_id, from_number, to_number):
    ts = int(time.time() * 1000)
    return {
        "event": "call_started",
        "call": {
            "call_id": call_id,
            "call_type": "phone_call",
            "agent_id": agent_id,
            "from_number": from_number,
            "to_number": to_number,
            "start_timestamp": ts,
            "retell_llm_dynamic_variables": {"practice_id": practice_id},
            "metadata": {"practice_id": practice_id},
        },
    }


def make_call_ended(call_id, practice_id, agent_id,
                    from_number, to_number, transcript, start_ts):
    end_ts = int(time.time() * 1000)
    return {
        "event": "call_ended",
        "call": {
            "call_id": call_id,
            "call_type": "phone_call",
            "agent_id": agent_id,
            "from_number": from_number,
            "to_number": to_number,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "transcript": transcript,
            "retell_llm_dynamic_variables": {"practice_id": practice_id},
            "metadata": {"practice_id": practice_id},
        },
    }


def make_call_analyzed(call_id, practice_id, agent_id, action_taken, outcome):
    return {
        "event": "call_analyzed",
        "call": {
            "call_id": call_id,
            "call_type": "phone_call",
            "agent_id": agent_id,
            "retell_llm_dynamic_variables": {"practice_id": practice_id},
            "metadata": {"practice_id": practice_id},
            "call_analysis": {
                "action_taken": action_taken,
                "outcome": outcome,
                "call_summary": (
                    f"Patient called to book an appointment. "
                    f"Action: {action_taken}. Outcome: {outcome}."
                ),
            },
        },
    }


def make_summary(call_id, practice_id, follow_up=False):
    # Fields match CallSummaryRequest: practice_id, call_id, reason, outcome,
    # follow_up_needed, tags, transcript, appointment_id, patient_id
    return {
        "call_id": call_id,
        "practice_id": practice_id,
        "reason": "appointment_booking",
        "outcome": "appointment_booked",
        "follow_up_needed": follow_up,
        "tags": ["cleaning", "new_booking"],
        "transcript": "",
    }


def make_book_payload(call_id, practice_id, patient_name, from_number, appt_date):
    # Fields match book_appointment endpoint: date, time, reason, patient_name,
    # patient_phone, practice_id, provider_name, is_emergency
    # Sent in wrapped format so _parse_retell_body auto-injects from_number as phone
    return {
        "name": "book_appointment",
        "call": {
            "call_id": call_id,
            "from_number": from_number,
            "retell_llm_dynamic_variables": {"practice_id": practice_id},
        },
        "args": {
            "practice_id": practice_id,
            "patient_name": patient_name,
            "date": appt_date,
            "time": "09:00",
            "reason": "Cleaning",
            "provider_name": "",
            "is_emergency": False,
        },
    }


SCENARIO_TRANSCRIPT = """\
Agent: Thank you for calling Dental AI. How can I help you today?
User: Hi, I'd like to book a cleaning appointment.
Agent: Of course! Can I get your full name please?
User: My name is Test Patient.
Agent: Thank you Test Patient. When would you like to come in?
User: How about next Tuesday morning?
Agent: Let me check availability for you.
Agent: I have an opening at 9 AM. Does that work?
User: Yes, that's perfect.
Agent: Great! I've booked you in for a cleaning at 9 AM. Is there anything else?
User: No that's all, thank you.
Agent: Have a great day!\
"""


# --Main scenario -------------------------------------------------------------

async def run_scenario(practice_id: str, agent_id: str,
                       from_number: str, dry_run: bool,
                       cleanup: bool):
    call_id    = f"sim-{uuid.uuid4().hex[:16]}"
    to_number  = "+16479876543"
    patient_name = "Test Patient"
    start_ts   = int(time.time() * 1000)

    # Next Tuesday (skip weekends for realistic slot)
    today = _date_cls.today()
    days_until_tuesday = (1 - today.weekday()) % 7 or 7
    appt_date = today.replace(
        day=min(today.day + days_until_tuesday, 28)
    ).isoformat()

    results = {}

    def send(label, fn, *args):
        payload = args[0] if len(args) == 1 else args[1]
        if dry_run:
            print(f"\n[DRY RUN] {label}")
            print(json.dumps(payload, indent=2))
            results[label] = "dry_run"
            return None
        resp = fn(*args)
        status = resp.status_code
        results[label] = status
        ok = "[OK]" if status < 300 else "[FAIL]"
        print(f"{ok} {label}: HTTP {status}")
        if status >= 300:
            print(f"  Response: {resp.text[:300]}")
        return resp

    print(f"\n{'='*60}")
    print(f"Retell Call Simulation")
    print(f"Call ID:     {call_id}")
    print(f"Practice:    {practice_id}")
    print(f"Agent:       {agent_id}")
    print(f"Caller:      {from_number}")
    print(f"Appt date:   {appt_date}")
    print(f"Backend:     {BACKEND_URL}")
    print(f"{'='*60}\n")

    # Step 1 — call_started webhook (signed)
    send("1. call_started",
         post_webhook,
         make_call_started(call_id, practice_id, agent_id,
                           from_number, to_number))
    time.sleep(0.5)

    # Step 2 — list-providers function call (unsigned)
    send("2. list-providers",
         post_function,
         "list-providers",
         {
             "name": "list_providers",
             "call": {
                 "call_id": call_id,
                 "from_number": from_number,
                 "retell_llm_dynamic_variables": {"practice_id": practice_id},
             },
             "args": {"practice_id": practice_id},
         })
    time.sleep(0.3)

    # Step 3 — book-appointment function call (unsigned)
    send("3. book-appointment",
         post_function,
         "book-appointment",
         make_book_payload(call_id, practice_id, patient_name,
                           from_number, appt_date))
    time.sleep(0.3)

    # Step 4 — call_ended webhook (signed)
    send("4. call_ended",
         post_webhook,
         make_call_ended(call_id, practice_id, agent_id,
                         from_number, to_number,
                         SCENARIO_TRANSCRIPT, start_ts))
    time.sleep(0.5)

    # Step 5 — call_analyzed webhook (signed)
    send("5. call_analyzed",
         post_webhook,
         make_call_analyzed(call_id, practice_id, agent_id,
                            "appointment_booked", "success"))
    time.sleep(0.3)

    # Step 6 — call-summary (x-retell-secret, no HMAC)
    send("6. call-summary",
         post_summary,
         make_summary(call_id, practice_id, follow_up=False))
    time.sleep(0.5)

    # Step 7 — DB verification
    if not dry_run:
        print("\n--DB Verification ----------------------------------")
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]

        call_log = await db.call_logs.find_one(
            {"call_id": call_id}, {"_id": 0}
        )
        if call_log:
            summary = call_log.get('call_summary') or {}
            print(f"[OK] call_log found")
            print(f"  status:       {call_log.get('status')}")
            print(f"  call_type:    {call_log.get('call_type')}")
            print(f"  duration:     {call_log.get('duration')}s")
            print(f"  transcript:   {'present' if call_log.get('transcript') else 'MISSING'}")
            print(f"  action_taken: {call_log.get('action_taken')}")
            print(f"  summary.reason:   {summary.get('reason')}")
            print(f"  summary.outcome:  {summary.get('outcome')}")
        else:
            print(f"[FAIL] call_log NOT FOUND for call_id={call_id}")

        # Appointments don't store call_id — look up by patient_name + practice
        appt = await db.appointments.find_one(
            {
                "practice_id": practice_id,
                "patient_name": patient_name,
                "source": "retell_realtime_booking",
            },
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if appt:
            print(f"[OK] appointment found")
            print(f"  id:      {appt.get('id')}")
            print(f"  patient: {appt.get('patient_name')}")
            print(f"  date:    {appt.get('appointment_date')}")
            print(f"  time:    {appt.get('appointment_time')}")
            print(f"  reason:  {appt.get('reason')}")
            print(f"  status:  {appt.get('status')}")
        else:
            print(f"  appointment: not found (check appointments collection manually)")

        pending = await db.pending_actions.find_one(
            {"call_id": call_id}, {"_id": 0}
        )
        if pending:
            print(f"[OK] pending_action: {pending.get('type', 'unknown')}")
        else:
            print(f"  pending_action: none (expected — follow_up_needed=False)")

        if cleanup:
            print("\n--Cleanup ------------------------------------------")
            r1 = await db.call_logs.delete_one({"call_id": call_id})
            r2 = await db.appointments.delete_many({
                "practice_id": practice_id,
                "patient_name": patient_name,
                "source": "retell_realtime_booking",
            })
            r3 = await db.pending_actions.delete_many({"call_id": call_id})
            print(f"  call_logs deleted:       {r1.deleted_count}")
            print(f"  appointments deleted:    {r2.deleted_count}")
            print(f"  pending_actions deleted: {r3.deleted_count}")

        client.close()

    # Summary table
    print(f"\n--Run Summary --------------------------------------")
    for label, result in results.items():
        if result == "dry_run":
            print(f"  [SKIP] {label}: dry_run")
        elif isinstance(result, int):
            ok = "[OK]" if result < 300 else "[FAIL]"
            print(f"  {ok} {label}: HTTP {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retell call scenario runner")
    parser.add_argument("--practice-id", required=True, help="Practice ID to simulate")
    parser.add_argument("--agent-id",    required=True, help="Retell agent ID")
    parser.add_argument("--phone",       default="+16471234567", help="Caller phone number")
    parser.add_argument("--dry-run",     action="store_true",    help="Print payloads without sending")
    parser.add_argument("--cleanup",     action="store_true",    help="Delete test data after run")
    args = parser.parse_args()

    asyncio.run(run_scenario(
        practice_id=args.practice_id,
        agent_id=args.agent_id,
        from_number=args.phone,
        dry_run=args.dry_run,
        cleanup=args.cleanup,
    ))
