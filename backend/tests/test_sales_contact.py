"""
Unit tests for POST /api/sales/contact.

All DB and email calls are mocked — no real MongoDB or SES calls made.
Run with:  cd backend && .\\venv\\Scripts\\python.exe -m pytest tests/test_sales_contact.py -v
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

# SES vars must be set before importing anything that reads them at module load
os.environ.setdefault("SES_ACCESS_KEY_ID",     "test-key-id")
os.environ.setdefault("SES_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("SES_FROM_EMAIL",        "noreply@frontdeskdentalai.com")

from fastapi import FastAPI                  # noqa: E402
from fastapi.testclient import TestClient    # noqa: E402

from routers.sales_router import router      # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


_VALID_PAYLOAD: dict = {
    "name":           "Jane Smith",
    "email":          "jane@mapleclinic.ca",
    "phone":          "+1 (604) 555-0100",
    "clinic_size":    "6-15",
    "message":        "Interested in your enterprise plan.",
    "requested_plan": "enterprise",
}


def _mock_db():
    db = MagicMock()
    db.sales_leads.insert_one = AsyncMock()
    return db


# ── Success path ──────────────────────────────────────────────────────────────

class TestSalesContactSuccess:

    def test_valid_payload_returns_200(self):
        """Valid payload → 200 with success=True and a non-empty lead_id."""
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=True),
        ):
            resp = TestClient(_make_app()).post("/api/sales/contact", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data.get("lead_id"), "lead_id must be present and non-empty"

    def test_lead_inserted_into_sales_leads(self):
        """insert_one is called exactly once; document contains all expected fields."""
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=True),
        ):
            TestClient(_make_app()).post("/api/sales/contact", json=_VALID_PAYLOAD)

        mock_db.sales_leads.insert_one.assert_called_once()
        doc = mock_db.sales_leads.insert_one.call_args[0][0]
        assert doc["name"]           == "Jane Smith"
        assert doc["email"]          == "jane@mapleclinic.ca"
        assert doc["clinic_size"]    == "6-15"
        assert doc["requested_plan"] == "enterprise"
        assert doc["status"]         == "new"
        assert "id" in doc
        assert "created_at" in doc

    def test_send_internal_notification_called_with_correct_args(self):
        """send_internal_notification receives the sales notify email and lead details."""
        mock_db = _mock_db()
        mock_notify = AsyncMock(return_value=True)
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification", mock_notify),
        ):
            TestClient(_make_app()).post("/api/sales/contact", json=_VALID_PAYLOAD)

        mock_notify.assert_called_once()
        kw = mock_notify.call_args.kwargs
        # Destination — SALES_NOTIFY_EMAIL default
        assert kw["to_email"] == "sales@dentalai.ca"
        # Subject must include plan title and lead name
        assert "Enterprise" in kw["subject"]
        assert "Jane Smith" in kw["subject"]
        # Body must include identifiable lead details
        assert "jane@mapleclinic.ca" in kw["body_text"]
        assert "6-15" in kw["body_text"]
        assert "enterprise" in kw["body_text"]

    def test_no_auth_required(self):
        """Endpoint is public — no Authorization header → must not return 401."""
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=True),
        ):
            resp = TestClient(_make_app()).post("/api/sales/contact", json=_VALID_PAYLOAD)
            # Explicit: no Authorization header passed; must not 401
        assert resp.status_code != 401

    def test_email_failure_is_non_fatal(self):
        """If send_internal_notification returns False, still 200 — lead is already stored."""
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=False),
        ):
            resp = TestClient(_make_app()).post("/api/sales/contact", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_db.sales_leads.insert_one.assert_called_once()


# ── Required field validation ─────────────────────────────────────────────────

class TestSalesContactRequiredFields:

    def _post(self, payload: dict):
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=True),
        ):
            return TestClient(_make_app()).post("/api/sales/contact", json=payload)

    def test_missing_name_returns_422(self):
        payload = {**_VALID_PAYLOAD}; del payload["name"]
        assert self._post(payload).status_code == 422

    def test_missing_email_returns_422(self):
        payload = {**_VALID_PAYLOAD}; del payload["email"]
        assert self._post(payload).status_code == 422

    def test_missing_clinic_size_returns_422(self):
        payload = {**_VALID_PAYLOAD}; del payload["clinic_size"]
        assert self._post(payload).status_code == 422

    def test_missing_requested_plan_returns_422(self):
        payload = {**_VALID_PAYLOAD}; del payload["requested_plan"]
        assert self._post(payload).status_code == 422

    def test_invalid_email_format_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "email": "not-an-email"}).status_code == 422

    def test_optional_phone_can_be_omitted(self):
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "phone"}
        assert self._post(payload).status_code == 200

    def test_optional_message_can_be_omitted(self):
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "message"}
        assert self._post(payload).status_code == 200


# ── Enum field_validator coverage ─────────────────────────────────────────────

class TestSalesContactFieldValidators:
    """
    These tests verify that the @field_validator decorators on SalesContactRequest
    (added in Part 2, models.py) actually fire and reject out-of-range values.
    """

    def _post(self, payload: dict):
        mock_db = _mock_db()
        with (
            patch("routers.sales_router.get_db", return_value=mock_db),
            patch("routers.sales_router.email_service.send_internal_notification",
                  new_callable=AsyncMock, return_value=True),
        ):
            return TestClient(_make_app()).post("/api/sales/contact", json=payload)

    # clinic_size — invalid values

    def test_invalid_clinic_size_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "clinic_size": "100+"}).status_code == 422

    def test_clinic_size_numeric_only_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "clinic_size": "5"}).status_code == 422

    def test_clinic_size_empty_string_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "clinic_size": ""}).status_code == 422

    # requested_plan — invalid values

    def test_plan_basic_returns_422(self):
        """basic is a valid product plan but not a valid sales contact plan."""
        assert self._post({**_VALID_PAYLOAD, "requested_plan": "basic"}).status_code == 422

    def test_plan_professional_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "requested_plan": "professional"}).status_code == 422

    def test_plan_empty_string_returns_422(self):
        assert self._post({**_VALID_PAYLOAD, "requested_plan": ""}).status_code == 422

    # clinic_size — all valid values

    def test_all_valid_clinic_sizes_accepted(self):
        """Every value in _VALID_CLINIC_SIZES must produce 200."""
        for size in ("1-5", "6-15", "16-50", "50+"):
            resp = self._post({**_VALID_PAYLOAD, "clinic_size": size})
            assert resp.status_code == 200, (
                f"clinic_size={size!r} was unexpectedly rejected: {resp.text}"
            )

    # requested_plan — all valid values

    def test_all_valid_plans_accepted(self):
        """Both values in _VALID_SALES_PLANS must produce 200."""
        for plan in ("enterprise", "elite"):
            resp = self._post({**_VALID_PAYLOAD, "requested_plan": plan})
            assert resp.status_code == 200, (
                f"requested_plan={plan!r} was unexpectedly rejected: {resp.text}"
            )
