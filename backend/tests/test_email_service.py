"""
Unit tests for EmailService and ses_webhook_router.

All SES calls and external HTTP requests are mocked — no real AWS calls made.
Run with:  cd backend && python -m pytest tests/test_email_service.py -v
"""
from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# ── Env vars must be set before importing the module ─────────────────────────
os.environ.setdefault("SES_ACCESS_KEY_ID",     "test-key-id")
os.environ.setdefault("SES_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("SES_REGION",            "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL",        "noreply@frontdeskdentalai.com")
os.environ.setdefault("SES_FROM_NAME",         "Front Desk Dental AI")

from services.email_service import EmailService  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": f"Simulated {code}"}},
        "SendEmail",
    )


def _fresh_service(mock_ses_client=None) -> EmailService:
    """Return a new EmailService with an optional pre-wired SES mock client."""
    svc = EmailService()
    if mock_ses_client is not None:
        svc._client = mock_ses_client
    return svc


_INVITE_VARS = {
    "practice_name": "Sunrise Dental",
    "role":          "staff",
    "invite_url":    "https://app.frontdeskdentalai.com/invite/test-token",
    "expiry_hours":  "24",
}


# ── EmailService.send() tests ─────────────────────────────────────────────────

class TestEmailServiceSend:

    def test_send_success(self):
        """send() returns True and logs email_sent when SES succeeds."""
        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "msg-001"}
        svc = _fresh_service(mock_client)

        result = asyncio.run(
            svc.send(
                to_email="staff@example.com",
                subject="You are invited",
                template_name="invite_staff",
                template_vars=_INVITE_VARS,
                practice_id="practice-123",
            )
        )

        assert result is True
        mock_client.send_email.assert_called_once()
        call_kw = mock_client.send_email.call_args.kwargs
        assert call_kw["Destination"] == {"ToAddresses": ["staff@example.com"]}
        assert call_kw["Tags"] == [{"Name": "practice_id", "Value": "practice-123"}]

    def test_send_missing_practice_id(self):
        """send() returns False without ever calling SES when practice_id is empty."""
        mock_client = MagicMock()
        svc = _fresh_service(mock_client)

        result = asyncio.run(
            svc.send(
                to_email="staff@example.com",
                subject="Invite",
                template_name="invite_staff",
                template_vars=_INVITE_VARS,
                practice_id="",
            )
        )

        assert result is False
        mock_client.send_email.assert_not_called()

    def test_send_throttling_retry(self):
        """send() retries on Throttling and returns True on eventual success (attempt 3)."""
        mock_client = MagicMock()
        mock_client.send_email.side_effect = [
            _client_error("Throttling"),
            _client_error("Throttling"),
            {"MessageId": "msg-002"},
        ]
        svc = _fresh_service(mock_client)

        with patch("services.email_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = asyncio.run(
                svc.send(
                    to_email="staff@example.com",
                    subject="Invite",
                    template_name="invite_staff",
                    template_vars=_INVITE_VARS,
                    practice_id="practice-123",
                )
            )

        assert result is True
        assert mock_client.send_email.call_count == 3
        # Two retries → two sleeps with 1s and 2s backoff
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_send_hard_failure(self):
        """send() returns False on a non-throttling ClientError (no retry)."""
        mock_client = MagicMock()
        mock_client.send_email.side_effect = _client_error("InvalidParameterValue")
        svc = _fresh_service(mock_client)

        result = asyncio.run(
            svc.send(
                to_email="staff@example.com",
                subject="Invite",
                template_name="invite_staff",
                template_vars=_INVITE_VARS,
                practice_id="practice-123",
            )
        )

        assert result is False
        mock_client.send_email.assert_called_once()

    def test_template_rendering(self):
        """_render() substitutes all variables into both HTML and plain text."""
        svc = EmailService()  # no SES client needed for rendering
        html, txt = svc._render("invite_staff", _INVITE_VARS, None)

        assert "Sunrise Dental" in html
        assert "staff" in html
        assert "https://app.frontdeskdentalai.com/invite/test-token" in html
        assert "24" in html

        assert "Sunrise Dental" in txt
        assert "https://app.frontdeskdentalai.com/invite/test-token" in txt

        # Base layout must be applied to HTML
        assert "<!DOCTYPE html>" in html
        assert "Front Desk Dental AI" in html

    def test_tenant_isolation_logged(self, caplog):
        """practice_id must appear in every log record emitted by send()."""
        import logging

        mock_client = MagicMock()
        mock_client.send_email.return_value = {"MessageId": "msg-003"}
        svc = _fresh_service(mock_client)

        with caplog.at_level(logging.INFO, logger="services.email_service"):
            asyncio.run(
                svc.send(
                    to_email="doc@clinic.com",
                    subject="Invite",
                    template_name="invite_staff",
                    template_vars=_INVITE_VARS,
                    practice_id="practice-audit-test",
                )
            )

        practice_id_logged = any(
            "practice-audit-test" in (r.getMessage() + str(r.__dict__))
            for r in caplog.records
        )
        assert practice_id_logged, "practice_id must appear in at least one log record"


# ── ses_webhook_router tests ──────────────────────────────────────────────────

class TestSESWebhookRouter:

    def _make_app(self):
        from fastapi import FastAPI
        from routers.ses_webhook_router import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_ses_webhook_bounce(self):
        """POST bounce notification → event_type=Bounce written to email_events."""
        from fastapi.testclient import TestClient

        bounce_inner = {
            "eventType": "Bounce",
            "bounce": {
                "bounceType":    "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [{"emailAddress": "bounce@example.com"}],
            },
            "mail": {
                "messageId": "ses-msg-1",
                "tags":      {"practice_id": ["practice-xyz"]},
            },
        }
        sns_payload = {
            "Type":             "Notification",
            "MessageId":        "sns-1",
            "TopicArn":         "arn:aws:sns:us-east-1:123:dental-ai-email-events",
            "Message":          json.dumps(bounce_inner),
            "Timestamp":        "2026-06-14T12:00:00.000Z",
            "SigningCertURL":    "https://sns.us-east-1.amazonaws.com/cert.pem",
            "Signature":        "dGVzdA==",
            "SignatureVersion": "1",
        }

        mock_db = MagicMock()
        mock_db.email_events.insert_one = AsyncMock()

        with (
            patch("routers.ses_webhook_router._verify_sns_signature",
                  new_callable=AsyncMock, return_value=True),
            patch("routers.ses_webhook_router.get_db", return_value=mock_db),
        ):
            client = TestClient(self._make_app())
            resp = client.post(
                "/api/webhooks/ses",
                json=sns_payload,
                headers={"x-amz-sns-message-type": "Notification"},
            )

        assert resp.status_code == 200
        mock_db.email_events.insert_one.assert_called_once()
        doc = mock_db.email_events.insert_one.call_args[0][0]
        assert doc["event_type"]   == "Bounce"
        assert doc["practice_id"]  == "practice-xyz"
        assert doc["bounce_type"]  == "Permanent"
        # Recipient must be masked
        assert "bounce@example.com" not in doc["recipient"]
        assert doc["recipient"].endswith("***")

    def test_ses_webhook_subscription_confirmation(self):
        """POST SubscriptionConfirmation → router GETs the SubscribeURL."""
        from fastapi.testclient import TestClient

        subscribe_url = "https://sns.us-east-1.amazonaws.com/confirm?token=abc123"
        sns_payload = {
            "Type":             "SubscriptionConfirmation",
            "MessageId":        "sns-sub-1",
            "TopicArn":         "arn:aws:sns:us-east-1:123:dental-ai-email-events",
            "Token":            "confirm-token",
            "SubscribeURL":     subscribe_url,
            "Message":          "You have chosen to subscribe...",
            "Timestamp":        "2026-06-14T12:00:00.000Z",
            "SigningCertURL":    "https://sns.us-east-1.amazonaws.com/cert.pem",
            "Signature":        "dGVzdA==",
            "SignatureVersion": "1",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx = AsyncMock()
        mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
        mock_httpx.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.get = AsyncMock(return_value=mock_resp)

        with (
            patch("routers.ses_webhook_router._verify_sns_signature",
                  new_callable=AsyncMock, return_value=True),
            patch("routers.ses_webhook_router.httpx.AsyncClient", return_value=mock_httpx),
        ):
            client = TestClient(self._make_app())
            resp = client.post(
                "/api/webhooks/ses",
                json=sns_payload,
                headers={"x-amz-sns-message-type": "SubscriptionConfirmation"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"status": "confirmed"}
        mock_httpx.get.assert_awaited_once_with(subscribe_url)

    def test_ses_webhook_invalid_signature(self):
        """Failed signature verification returns 403."""
        from fastapi.testclient import TestClient

        sns_payload = {
            "Type":             "Notification",
            "MessageId":        "sns-bad",
            "TopicArn":         "arn:aws:sns:us-east-1:123:dental-ai-email-events",
            "Message":          "{}",
            "Timestamp":        "2026-06-14T12:00:00.000Z",
            "SigningCertURL":    "https://evil.example.com/cert.pem",
            "Signature":        "dGVzdA==",
            "SignatureVersion": "1",
        }

        with patch("routers.ses_webhook_router._verify_sns_signature",
                   new_callable=AsyncMock, return_value=False):
            client = TestClient(self._make_app())
            resp = client.post(
                "/api/webhooks/ses",
                json=sns_payload,
                headers={"x-amz-sns-message-type": "Notification"},
            )

        assert resp.status_code == 403
