"""Tests for patient phone normalization and deduplication."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.phone import normalize_phone, phones_match


# ── normalize_phone ──────────────────────────────────────────────────────────

def test_normalize_phone_e164():
    assert normalize_phone("+1 (604) 555-0100") == "+16045550100"

def test_normalize_phone_no_country_code():
    assert normalize_phone("604-555-0100") == "+16045550100"

def test_normalize_phone_dots():
    assert normalize_phone("(604) 555.0100") == "+16045550100"

def test_normalize_phone_already_e164():
    assert normalize_phone("+16045550100") == "+16045550100"

def test_normalize_phone_unknown():
    assert normalize_phone("unknown") is None

def test_normalize_phone_none():
    assert normalize_phone(None) is None

def test_normalize_phone_empty():
    assert normalize_phone("") is None

def test_normalize_phone_null_string():
    assert normalize_phone("null") is None


# ── phones_match ─────────────────────────────────────────────────────────────

def test_phones_match():
    assert phones_match("604-555-0100", "+1 (604) 555-0100") is True

def test_phones_match_same_normalized():
    assert phones_match("+16045550100", "604-555-0100") is True

def test_phones_match_different_numbers():
    assert phones_match("604-555-0100", "604-555-0101") is False

def test_phones_match_one_none():
    assert phones_match(None, "604-555-0100") is False

def test_phones_match_both_none():
    assert phones_match(None, None) is False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_request() -> MagicMock:
    from fastapi import Request
    req = MagicMock(spec=Request)
    req.body = AsyncMock(return_value=b"")
    return req


# ── register_patient_realtime ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_register_patient_dedup():
    """Same number in different format returns existing patient, no insert."""
    existing = {
        "id": "patient-abc",
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+16045550100",
        "normalized_phone": "+16045550100",
    }
    patients = MagicMock()
    patients.find_one = AsyncMock(return_value=existing)
    mock_db = MagicMock()
    mock_db.patients = patients

    parsed = {
        "practice_id": "practice-001",
        "patient_phone": "+1 (604) 555-0100",
        "patient_name": "Jane Doe",
    }

    with patch("routers.retell_api_router._parse_retell_body", AsyncMock(return_value=parsed)), \
         patch("routers.retell_api_router.get_db", return_value=mock_db):
        result = await register_patient_realtime(_mock_request(), x_retell_signature=None)

    assert result["already_existed"] is True
    assert result["patient"]["id"] == "patient-abc"
    # DB must be queried by normalized_phone, not raw phone
    query = patients.find_one.call_args[0][0]
    assert query.get("normalized_phone") == "+16045550100"
    assert "phone" not in query


@pytest.mark.anyio
async def test_register_patient_blocks_unknown_phone():
    """patient_phone='unknown' raises 400 before touching the DB."""
    patients = MagicMock()
    patients.find_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.patients = patients

    parsed = {
        "practice_id": "practice-001",
        "patient_phone": "unknown",
        "patient_name": "Jane Doe",
    }

    from fastapi import HTTPException
    with patch("routers.retell_api_router._parse_retell_body", AsyncMock(return_value=parsed)), \
         patch("routers.retell_api_router.get_db", return_value=mock_db):
        with pytest.raises(HTTPException) as exc:
            await register_patient_realtime(_mock_request(), x_retell_signature=None)

    assert exc.value.status_code == 400
    patients.find_one.assert_not_called()


# ── book_appointment_realtime ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_book_appointment_dedup():
    """Same phone in different format finds existing patient; no new patient inserted."""
    existing_patient = {
        "id": "patient-existing",
        "name": "John Smith",
        "phone": "+16045550200",
        "normalized_phone": "+16045550200",
        "practice_id": "practice-001",
    }
    patients = MagicMock()
    patients.find_one = AsyncMock(return_value=existing_patient)
    patients.insert_one = AsyncMock()

    providers_cursor = MagicMock()
    providers_cursor.to_list = AsyncMock(return_value=[])
    providers = MagicMock()
    providers.find = MagicMock(return_value=providers_cursor)

    appointments = MagicMock()
    appointments.insert_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.patients = patients
    mock_db.providers = providers
    mock_db.appointments = appointments

    parsed = {
        "practice_id": "practice-001",
        "patient_phone": "+1 (604) 555-0200",
        "patient_name": "John Smith",
        "date": "2026-08-15",
        "time": "10:00",
        "reason": "Cleaning",
        "is_emergency": False,
    }

    with patch("routers.retell_api_router._parse_retell_body", AsyncMock(return_value=parsed)), \
         patch("routers.retell_api_router.get_db", return_value=mock_db):
        result = await book_appointment_realtime(_mock_request(), x_retell_signature=None)

    # Existing patient found — no new patient inserted
    patients.insert_one.assert_not_called()
    # Appointment was booked
    appointments.insert_one.assert_called_once()
    assert result["success"] is True


# ── Import after fixtures to avoid circular issues ────────────────────────────
from routers.retell_api_router import register_patient_realtime, book_appointment_realtime
