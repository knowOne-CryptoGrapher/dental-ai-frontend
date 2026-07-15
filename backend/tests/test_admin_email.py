"""
Unit tests for admin email notification system.

All SES calls are mocked — no real emails are sent.
Tests cover: send_admin_notification(), settings validation, default settings contract.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.admin_email_logs = MagicMock()
    db.admin_email_logs.insert_one = AsyncMock(return_value=None)
    db.practices = MagicMock()
    return db


@pytest.fixture
def email_svc():
    from services.email_service import EmailService
    return EmailService()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSendAdminNotification:

    @pytest.mark.anyio
    async def test_send_success_logs_to_db(self, mock_db, email_svc, tmp_path):
        admin_dir = tmp_path / "admin"
        admin_dir.mkdir()
        (admin_dir / "emergency_alert.html").write_text("<p>$practice_name</p>")
        (admin_dir / "emergency_alert.txt").write_text("$practice_name")
        (tmp_path / "base.html").write_text("<html>$body_content</html>")

        import services.email_service as svc_mod
        original_dir = svc_mod._TEMPLATE_DIR
        svc_mod._TEMPLATE_DIR = str(tmp_path)

        try:
            mock_ses = MagicMock()
            mock_ses.send_email = MagicMock(return_value={})
            email_svc._client = mock_ses

            result = await email_svc.send_admin_notification(
                db=mock_db,
                practice_id="practice-123",
                admin_email="admin@clinic.com",
                template_name="emergency_alert",
                subject="Test",
                template_vars={"practice_name": "Test Clinic"},
            )
        finally:
            svc_mod._TEMPLATE_DIR = original_dir

        assert result is True
        mock_db.admin_email_logs.insert_one.assert_called_once()
        log_doc = mock_db.admin_email_logs.insert_one.call_args[0][0]
        assert log_doc["practice_id"] == "practice-123"
        assert log_doc["template_name"] == "emergency_alert"
        assert log_doc["success"] is True

    @pytest.mark.anyio
    async def test_send_failure_still_logs(self, mock_db, email_svc, tmp_path):
        admin_dir = tmp_path / "admin"
        admin_dir.mkdir()
        (admin_dir / "emergency_alert.html").write_text("<p>$practice_name</p>")
        (admin_dir / "emergency_alert.txt").write_text("$practice_name")
        (tmp_path / "base.html").write_text("<html>$body_content</html>")

        import services.email_service as svc_mod
        from botocore.exceptions import ClientError
        original_dir = svc_mod._TEMPLATE_DIR
        svc_mod._TEMPLATE_DIR = str(tmp_path)

        try:
            error_response = {"Error": {"Code": "MessageRejected", "Message": "rejected"}}
            mock_ses = MagicMock()
            mock_ses.send_email = MagicMock(
                side_effect=ClientError(error_response, "SendEmail")
            )
            email_svc._client = mock_ses

            result = await email_svc.send_admin_notification(
                db=mock_db,
                practice_id="practice-123",
                admin_email="admin@clinic.com",
                template_name="emergency_alert",
                subject="Test",
                template_vars={"practice_name": "Test Clinic"},
            )
        finally:
            svc_mod._TEMPLATE_DIR = original_dir

        assert result is False
        mock_db.admin_email_logs.insert_one.assert_called_once()
        log_doc = mock_db.admin_email_logs.insert_one.call_args[0][0]
        assert log_doc["success"] is False

    @pytest.mark.anyio
    async def test_send_returns_false_on_missing_template(self, mock_db, email_svc, tmp_path):
        import services.email_service as svc_mod
        original_dir = svc_mod._TEMPLATE_DIR
        svc_mod._TEMPLATE_DIR = str(tmp_path)

        try:
            result = await email_svc.send_admin_notification(
                db=mock_db,
                practice_id="practice-123",
                admin_email="admin@clinic.com",
                template_name="nonexistent_template",
                subject="Test",
                template_vars={"practice_name": "Test Clinic"},
            )
        finally:
            svc_mod._TEMPLATE_DIR = original_dir

        assert result is False
        mock_db.admin_email_logs.insert_one.assert_called_once()
        log_doc = mock_db.admin_email_logs.insert_one.call_args[0][0]
        assert log_doc["success"] is False


class TestDefaultSettings:

    def test_default_settings_keys(self):
        from routers.admin_email_router import _DEFAULT_SETTINGS, _VALID_KEYS
        assert "emergency_alerts" in _DEFAULT_SETTINGS
        assert "billing_alerts" in _DEFAULT_SETTINGS
        assert "daily_summary" in _DEFAULT_SETTINGS
        assert _DEFAULT_SETTINGS["emergency_alerts"] is True
        assert _DEFAULT_SETTINGS["daily_summary"] is False
        assert _VALID_KEYS == set(_DEFAULT_SETTINGS.keys())

    def test_invalid_key_rejected(self):
        from routers.admin_email_router import _VALID_KEYS
        assert "unknown_key" not in _VALID_KEYS

    @pytest.mark.anyio
    async def test_update_settings_validates_booleans(self):
        from routers.admin_email_router import update_notification_settings, NotificationSettingsBody
        from fastapi import HTTPException

        body = NotificationSettingsBody(settings={"emergency_alerts": "yes"})
        mock_user = {"practice_id": "practice-123", "role": "admin"}

        with pytest.raises(HTTPException) as exc_info:
            await update_notification_settings(body=body, current_user=mock_user)
        assert exc_info.value.status_code == 422
