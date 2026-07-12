"""
Unit tests for the v2 Retell integration:
  - POST /api/retell/webhook      (retell_webhook_router_v2)
  - GET  /api/practice/me         (retell_context_router)
  - POST /api/knowledge/query     (retell_context_router)
  - POST /api/retell/call-summary (retell_context_router)

All DB and Retell API calls are mocked — no real MongoDB or Retell API calls.
Run with:
  cd backend && MONGODB_URI=$(...) .\\venv\\Scripts\\python.exe -m pytest tests/test_retell_v2.py -v
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

# Set env vars before any module-level reads at import time
os.environ.setdefault("RETELL_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("RETELL_API_KEY",        "test-retell-api-key")
os.environ.setdefault("SES_ACCESS_KEY_ID",     "test-ses-key")
os.environ.setdefault("SES_SECRET_ACCESS_KEY", "test-ses-secret")
os.environ.setdefault("SES_FROM_EMAIL",        "noreply@test.com")

from fastapi import FastAPI                          # noqa: E402
from fastapi.testclient import TestClient            # noqa: E402
from auth import get_current_user                    # noqa: E402
from routers.retell_webhook_router_v2 import router as webhook_router   # noqa: E402
from routers.retell_context_router import (          # noqa: E402
    router as context_router,
    _knowledge_auth,
    _verify_webhook_secret,
)


# ── App factories ─────────────────────────────────────────────────────────────

def _make_webhook_app() -> FastAPI:
    app = FastAPI()
    app.include_router(webhook_router)
    return app


def _make_context_app(mock_user: dict | None = None) -> FastAPI:
    """
    Context router app with dependency overrides.
    Always bypasses _knowledge_auth and _verify_webhook_secret.
    Optionally injects a mock JWT user to satisfy require_role.
    """
    app = FastAPI()
    app.include_router(context_router)
    app.dependency_overrides[_knowledge_auth]        = lambda: None
    app.dependency_overrides[_verify_webhook_secret] = lambda: None
    if mock_user is not None:
        app.dependency_overrides[get_current_user] = lambda: mock_user
    return app


# ── DB mock helpers ───────────────────────────────────────────────────────────

def _mock_webhook_db() -> MagicMock:
    db = MagicMock()
    db.call_logs.insert_one  = AsyncMock()
    db.call_logs.update_one  = AsyncMock(return_value=MagicMock(matched_count=1))
    db.practices.find_one    = AsyncMock(return_value=None)
    return db


def _mock_context_db(
    practice: dict | None = None,
    providers: list | None = None,
    docs: list | None = None,
) -> MagicMock:
    db = MagicMock()
    db.practices.find_one = AsyncMock(return_value=practice)

    providers_cursor = MagicMock()
    providers_cursor.to_list = AsyncMock(return_value=providers or [])
    db.providers.find.return_value = providers_cursor

    docs_cursor = MagicMock()
    docs_cursor.to_list = AsyncMock(return_value=docs or [])
    db.knowledge_documents.find.return_value = docs_cursor

    db.call_logs.update_one       = AsyncMock(return_value=MagicMock(matched_count=1))
    db.pending_actions.insert_one = AsyncMock()
    return db


# ── Shared fixtures ───────────────────────────────────────────────────────────

_MOCK_USER = {
    "id":          "user-001",
    "practice_id": "practice-xyz",
    "role":        "admin",
    "email":       "admin@mapleclinic.ca",
    "is_active":   True,
}

_MOCK_PRACTICE = {
    "id":                "practice-xyz",
    "name":              "Maple Dental Clinic",
    "timezone":          "America/Vancouver",
    "subscription_plan": "enterprise",
    "settings": {
        "hours":             {"mon": "9-5", "tue": "9-5"},
        "appointment_types": ["Cleaning", "Checkup"],
        "emergency":         {"after_hours_number": "+16041234567"},
        "branding": {
            "greeting_name": "Maple Dental",
            "voice_style":   "friendly",
        },
    },
}

_CALL_STARTED_PAYLOAD = {
    "event": "call_started",
    "call": {
        "call_id":         "call-abc-123",
        "from_number":     "+16041234567",
        "to_number":       "+16045559999",
        "agent_id":        "agent-001",
        "start_timestamp": 1_700_000_000_000,
        "metadata":        {"practice_id": "practice-xyz"},
    },
}

_CALL_ENDED_PAYLOAD = {
    "event": "call_ended",
    "call": {
        "call_id":         "call-abc-123",
        "from_number":     "+16041234567",
        "start_timestamp": 1_700_000_000_000,
        "end_timestamp":   1_700_000_180_000,  # 180 s duration
        "transcript":      "Agent: How can I help?\nUser: I need a cleaning.",
        "metadata":        {"practice_id": "practice-xyz"},
    },
}

_CALL_ANALYZED_PAYLOAD = {
    "event": "call_analyzed",
    "call": {
        "call_id":  "call-abc-123",
        "metadata": {"practice_id": "practice-xyz"},
        "call_analysis": {
            "outcome":      "appointment_booked",
            "action_taken": "appointment_booked",
            "summary":      "Patient requested a cleaning.",
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Webhook tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhookSignature:

    def test_webhook_invalid_signature(self):
        """POST with bad signature → 401. No DB writes of any kind."""
        mock_db = _mock_webhook_db()
        with (
            patch(
                "routers.retell_webhook_router_v2.verify_retell_webhook_signature",
                new_callable=AsyncMock,
                side_effect=HTTPException(status_code=401, detail="Invalid webhook signature"),
            ),
            patch("routers.retell_webhook_router_v2.get_db", return_value=mock_db),
        ):
            resp = TestClient(_make_webhook_app()).post(
                "/api/retell/webhook",
                json=_CALL_STARTED_PAYLOAD,
                headers={"x-retell-signature": "bad,sig"},
            )

        assert resp.status_code == 401
        mock_db.call_logs.insert_one.assert_not_called()
        mock_db.call_logs.update_one.assert_not_called()


class TestWebhookCallStarted:

    def test_webhook_call_started(self):
        """Valid call_started → 200, CallLog inserted with correct fields."""
        mock_db = _mock_webhook_db()
        with (
            patch(
                "routers.retell_webhook_router_v2.verify_retell_webhook_signature",
                new_callable=AsyncMock,
                return_value=_CALL_STARTED_PAYLOAD,
            ),
            patch("routers.retell_webhook_router_v2.get_db", return_value=mock_db),
        ):
            resp = TestClient(_make_webhook_app()).post(
                "/api/retell/webhook", json=_CALL_STARTED_PAYLOAD
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_db.call_logs.insert_one.assert_called_once()

        doc = mock_db.call_logs.insert_one.call_args[0][0]
        assert doc["call_id"]       == "call-abc-123"
        assert doc["patient_phone"] == "+16041234567"
        assert doc["status"]        == "active"
        assert doc["handled_by"]    == "ai"
        assert doc["transcript"]    == ""
        assert doc["duration"]      == 0


class TestWebhookCallEnded:

    def test_webhook_call_ended(self):
        """Valid call_ended → 200, CallLog updated. No patient or appointment created."""
        mock_db = _mock_webhook_db()
        with (
            patch(
                "routers.retell_webhook_router_v2.verify_retell_webhook_signature",
                new_callable=AsyncMock,
                return_value=_CALL_ENDED_PAYLOAD,
            ),
            patch("routers.retell_webhook_router_v2.get_db", return_value=mock_db),
            # smart_extract is a local import inside _handle_call_ended;
            # patch at source module to prevent real transcript parsing
            patch(
                "utils.transcript_parser.smart_extract",
                return_value={"call_reason": "cleaning"},
            ),
        ):
            resp = TestClient(_make_webhook_app()).post(
                "/api/retell/webhook", json=_CALL_ENDED_PAYLOAD
            )

        assert resp.status_code == 200
        mock_db.call_logs.update_one.assert_called_once()

        update_filter, update_op = mock_db.call_logs.update_one.call_args[0]
        assert update_filter                    == {"call_id": "call-abc-123"}
        assert update_op["$set"]["status"]      == "completed"
        assert update_op["$set"]["duration"]    == 180.0
        assert "cleaning" in update_op["$set"]["transcript"].lower()

        # Critical: no auto-patient or auto-appointment side-effects
        mock_db.patients.insert_one.assert_not_called()
        mock_db.appointments.insert_one.assert_not_called()


class TestWebhookCallAnalyzed:

    def test_webhook_call_analyzed(self):
        """Valid call_analyzed → 200, CallLog updated with call_summary and action_taken."""
        mock_db = _mock_webhook_db()
        with (
            patch(
                "routers.retell_webhook_router_v2.verify_retell_webhook_signature",
                new_callable=AsyncMock,
                return_value=_CALL_ANALYZED_PAYLOAD,
            ),
            patch("routers.retell_webhook_router_v2.get_db", return_value=mock_db),
        ):
            resp = TestClient(_make_webhook_app()).post(
                "/api/retell/webhook", json=_CALL_ANALYZED_PAYLOAD
            )

        assert resp.status_code == 200
        mock_db.call_logs.update_one.assert_called_once()

        _, update_op = mock_db.call_logs.update_one.call_args[0]
        assert update_op["$set"]["call_summary"]["outcome"] == "appointment_booked"
        assert update_op["$set"]["action_taken"]            == "appointment_booked"


class TestWebhookUnknownEvent:

    def test_webhook_unknown_event(self):
        """Valid signature, unrecognised event type → 200, no DB writes."""
        unknown_payload = {
            "event": "call_transferred",
            "call":  {"call_id": "call-xyz", "metadata": {}},
        }
        mock_db = _mock_webhook_db()
        with (
            patch(
                "routers.retell_webhook_router_v2.verify_retell_webhook_signature",
                new_callable=AsyncMock,
                return_value=unknown_payload,
            ),
            patch("routers.retell_webhook_router_v2.get_db", return_value=mock_db),
        ):
            resp = TestClient(_make_webhook_app()).post(
                "/api/retell/webhook", json=unknown_payload
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_db.call_logs.insert_one.assert_not_called()
        mock_db.call_logs.update_one.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Context router tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPracticeMe:

    def test_practice_me(self):
        """Authenticated GET /api/practice/me → 200 with all required fields."""
        mock_db = _mock_context_db(
            practice=_MOCK_PRACTICE,
            providers=[
                {
                    "name":        "Dr. Sarah Lee",
                    "role":        "General Dentist",
                    "specialties": ["Implants"],
                    "title":       "Dr.",
                },
            ],
        )
        with patch("routers.retell_context_router.get_db", return_value=mock_db):
            resp = TestClient(_make_context_app(mock_user=_MOCK_USER)).get(
                "/api/practice/me"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["practice_id"]               == "practice-xyz"
        assert data["practice_name"]             == "Maple Dental Clinic"
        assert data["timezone"]                  == "America/Vancouver"
        assert data["subscription_plan"]         == "enterprise"
        assert len(data["providers"])            == 1
        assert data["providers"][0]["name"]      == "Dr. Sarah Lee"
        assert data["branding"]["greeting_name"] == "Maple Dental"
        assert data["branding"]["voice_style"]   == "friendly"
        assert "hours"             in data
        assert "appointment_types" in data
        assert "emergency_rules"   in data


class TestKnowledgeQuery:

    def test_knowledge_query_match(self):
        """Question with keyword matches → non-null answer, high or low confidence."""
        mock_db = _mock_context_db(docs=[
            {
                "title":   "Insurance FAQ",
                "content": "We accept Blue Cross and Sun Life dental insurance plans.",
            },
        ])
        with patch("routers.retell_context_router.get_db", return_value=mock_db):
            resp = TestClient(_make_context_app()).post(
                "/api/knowledge/query",
                json={
                    "question":    "Do you accept Blue Cross dental insurance?",
                    "practice_id": "practice-xyz",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"]     is not None
        assert data["confidence"] in ("high", "low")
        assert data["source"]     == "Insurance FAQ"

    def test_knowledge_query_no_match(self):
        """Question with no keyword matches → answer null, confidence none."""
        mock_db = _mock_context_db(docs=[
            {
                "title":   "Parking Info",
                "content": "Free parking is available behind the building.",
            },
        ])
        with patch("routers.retell_context_router.get_db", return_value=mock_db):
            resp = TestClient(_make_context_app()).post(
                "/api/knowledge/query",
                json={
                    "question":    "What are your x-ray prices?",
                    "practice_id": "practice-xyz",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"]     is None
        assert data["confidence"] == "none"


class TestCallSummary:

    def test_call_summary_ingestion(self):
        """POST /api/retell/call-summary → 200, CallLog upserted, no follow-up created."""
        mock_db = _mock_context_db()
        with patch("routers.retell_context_router.get_db", return_value=mock_db):
            resp = TestClient(_make_context_app()).post(
                "/api/retell/call-summary",
                json={
                    "practice_id":      "practice-xyz",
                    "call_id":          "call-abc-123",
                    "reason":           "Patient requested a cleaning.",
                    "outcome":          "appointment_booked",
                    "follow_up_needed": False,
                    "tags":             ["cleaning", "new_patient"],
                    "transcript":       "Agent: Hi! User: I need a cleaning.",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"success": True}
        mock_db.call_logs.update_one.assert_called_once()

        call_args = mock_db.call_logs.update_one.call_args
        assert call_args[1].get("upsert") is True
        assert call_args[0][1]["$set"]["action_taken"] == "appointment_booked"

        # follow_up_needed=False → no pending_action
        mock_db.pending_actions.insert_one.assert_not_called()

    def test_call_summary_follow_up(self):
        """follow_up_needed=True → CallLog upserted AND pending_action inserted."""
        mock_db = _mock_context_db()
        with patch("routers.retell_context_router.get_db", return_value=mock_db):
            resp = TestClient(_make_context_app()).post(
                "/api/retell/call-summary",
                json={
                    "practice_id":      "practice-xyz",
                    "call_id":          "call-abc-456",
                    "reason":           "Billing question could not be resolved.",
                    "outcome":          "transferred",
                    "follow_up_needed": True,
                    "tags":             ["billing"],
                    "transcript":       "",
                },
            )

        assert resp.status_code == 200
        mock_db.call_logs.update_one.assert_called_once()
        mock_db.pending_actions.insert_one.assert_called_once()

        pending_doc = mock_db.pending_actions.insert_one.call_args[0][0]
        assert pending_doc["type"]        == "follow_up"
        assert pending_doc["practice_id"] == "practice-xyz"
        assert pending_doc["call_id"]     == "call-abc-456"
        assert pending_doc["status"]      == "pending"
