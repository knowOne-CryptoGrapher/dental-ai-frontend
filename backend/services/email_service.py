"""
EmailService — sends transactional email via AWS SES v2.

Design principles:
  - Never raises. All failures return False and log the reason.
  - practice_id is required on every send. Omitting it is a bug, not a runtime error.
  - Templates are loaded from backend/templates/email/ using Python string.Template.
  - SES client is initialised lazily so local-dev imports succeed even without SES vars.
  - Throttling is retried up to 3 times with exponential backoff (1s, 2s, 4s).
  - Recipients on the suppression list (bounced/complained) are silently skipped.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import string
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from auth import get_db

logger = logging.getLogger(__name__)

SES_ACCESS_KEY_ID     = os.environ.get("SES_ACCESS_KEY_ID", "").strip()
SES_SECRET_ACCESS_KEY = os.environ.get("SES_SECRET_ACCESS_KEY", "").strip()
SES_REGION            = os.environ.get("SES_REGION", "us-east-1").strip()
SES_FROM_EMAIL        = os.environ.get("SES_FROM_EMAIL", "").strip()
SES_FROM_NAME         = os.environ.get("SES_FROM_NAME", "Front Desk Dental AI").strip()
SES_CONFIGURATION_SET = os.environ.get("SES_CONFIGURATION_SET", "").strip()

# Resolve template directory relative to this file: backend/services/ → backend/templates/email/
_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "templates", "email")
)
_MAX_RETRIES = 3


class EmailService:
    def __init__(self) -> None:
        self._client = None

    # ── SES client ────────────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            if not SES_ACCESS_KEY_ID or not SES_SECRET_ACCESS_KEY:
                raise RuntimeError("SES credentials not configured — set SES_ACCESS_KEY_ID and SES_SECRET_ACCESS_KEY")
            self._client = boto3.client(
                "sesv2",
                region_name=SES_REGION,
                aws_access_key_id=SES_ACCESS_KEY_ID,
                aws_secret_access_key=SES_SECRET_ACCESS_KEY,
            )
        return self._client

    # ── Template rendering ────────────────────────────────────────────────────

    def _load(self, name: str, ext: str) -> string.Template:
        path = os.path.join(_TEMPLATE_DIR, f"{name}.{ext}")
        with open(path, "r", encoding="utf-8") as fh:
            return string.Template(fh.read())

    def _render(
        self,
        template_name: str,
        template_vars: dict,
        practice_branding: dict | None,
    ) -> tuple[str, str]:
        """Return (html_content, plain_text_content)."""
        branding = practice_branding or {}
        merged: dict = {
            "year": str(datetime.now().year),
            "footer_text": branding.get("footer_text", "Front Desk Dental AI"),
            **template_vars,
        }

        # Render inner body, then wrap in shared base layout
        body_html = self._load(template_name, "html").safe_substitute(merged)
        html_content = self._load("base", "html").safe_substitute({**merged, "body_content": body_html})

        # Plain text is standalone — no base wrapper
        txt_content = self._load(template_name, "txt").safe_substitute(merged)

        return html_content, txt_content

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _mask(email: str) -> str:
        return (email[:3] + "***") if len(email) > 3 else "***"

    async def _is_suppressed(self, email: str, db) -> bool:
        """Check if email is on the suppression list before sending."""
        try:
            h = hashlib.sha256(email.lower().strip().encode()).hexdigest()
            hit = await db.email_suppression_list.find_one({"email_hash": h})
            return hit is not None
        except Exception:
            return False  # fail open — don't block email on DB error

    # ── Public API ────────────────────────────────────────────────────────────

    async def send(
        self,
        *,
        to_email: str,
        subject: str,
        template_name: str,
        template_vars: dict,
        practice_id: str,
        practice_branding: dict | None = None,
        reply_to: str | None = None,
    ) -> bool:
        """
        Send a templated email via SES v2.

        Returns True on success, False on any failure.
        Never raises — all exceptions are caught and logged.
        """
        if not practice_id:
            logger.error(
                "email_blocked_no_tenant",
                extra={"template": template_name, "reason": "practice_id is required"},
            )
            return False

        if not SES_FROM_EMAIL:
            logger.error("email_blocked_no_sender", extra={"practice_id": practice_id})
            return False

        ctx = {"practice_id": practice_id, "to": self._mask(to_email), "template": template_name}

        db = get_db()
        if await self._is_suppressed(to_email, db):
            logger.warning("email_suppressed", extra={**ctx, "reason": "suppression_list"})
            return False

        try:
            html_content, txt_content = self._render(template_name, template_vars, practice_branding)
        except Exception as exc:
            logger.error("email_template_error", extra={**ctx, "error": str(exc)})
            return False

        source = f"{SES_FROM_NAME} <{SES_FROM_EMAIL}>"
        kwargs: dict = {
            "FromEmailAddress": source,
            "Destination": {"ToAddresses": [to_email]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": txt_content, "Charset": "UTF-8"},
                        "Html": {"Data": html_content, "Charset": "UTF-8"},
                    },
                },
            },
            "EmailTags": [{"Name": "practice_id", "Value": practice_id}],
        }
        if reply_to:
            kwargs["ReplyToAddresses"] = [reply_to]
        if SES_CONFIGURATION_SET:
            kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = self._get_client()
                await asyncio.to_thread(client.send_email, **kwargs)
                logger.info("email_sent", extra={**ctx, "attempt": attempt + 1})
                return True

            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code == "TooManyRequestsException" and attempt < _MAX_RETRIES:
                    wait = 2 ** attempt  # 1s → 2s → 4s
                    logger.warning(
                        "email_throttled_retry",
                        extra={**ctx, "retry": attempt + 1, "wait_s": wait},
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(
                    "email_ses_error",
                    extra={**ctx, "error_code": code, "error": str(exc)},
                )
                return False

            except Exception as exc:
                logger.error("email_unexpected_error", extra={**ctx, "error": str(exc)})
                return False

        return False

    async def send_internal_notification(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
    ) -> bool:
        """
        Send an internal platform notification (e.g. sales leads, ops alerts).
        NOT tenant-scoped — does not require practice_id.
        Use only for internal team notifications, never for customer-facing email.
        Suppression list is not checked — internal addresses are always valid.
        """
        if not SES_FROM_EMAIL:
            logger.error("internal_notification_blocked_no_sender")
            return False

        source = f"{SES_FROM_NAME} <{SES_FROM_EMAIL}>"
        ctx = {"to": self._mask(to_email), "subject": subject[:60]}

        kwargs: dict = {
            "FromEmailAddress": source,
            "Destination": {"ToAddresses": [to_email]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
                },
            },
        }
        if SES_CONFIGURATION_SET:
            kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = self._get_client()
                await asyncio.to_thread(client.send_email, **kwargs)
                logger.info(
                    "internal_notification_sent",
                    extra={**ctx, "attempt": attempt + 1},
                )
                return True

            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code == "TooManyRequestsException" and attempt < _MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.warning(
                        "internal_notification_throttled",
                        extra={**ctx, "retry": attempt + 1, "wait_s": wait},
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(
                    "internal_notification_ses_error",
                    extra={**ctx, "error_code": code, "error": str(exc)},
                )
                return False

            except Exception as exc:
                logger.error(
                    "internal_notification_unexpected_error",
                    extra={**ctx, "error": str(exc)},
                )
                return False

        return False

    async def send_admin_notification(
        self,
        *,
        db,
        practice_id: str,
        admin_email: str,
        template_name: str,
        subject: str,
        template_vars: dict,
        practice_branding: dict | None = None,
    ) -> bool:
        """Send a practice admin notification email and log the attempt.

        Templates are loaded from backend/templates/email/admin/<template_name>.{html,txt}.
        Logs every attempt to db.admin_email_logs regardless of outcome.
        Never raises.
        """
        ctx = {
            "practice_id": practice_id,
            "template": template_name,
            "to": self._mask(admin_email),
        }
        now_iso = datetime.utcnow().isoformat()
        success = False

        if await self._is_suppressed(admin_email, db):
            logger.warning("admin_email_suppressed", extra={**ctx, "reason": "suppression_list"})
            return False

        try:
            html_content, txt_content = self._render(
                f"admin/{template_name}", template_vars, practice_branding
            )
            from_addr = (
                f"{SES_FROM_NAME} <{SES_FROM_EMAIL}>"
                if SES_FROM_EMAIL
                else "Dental AI <noreply@dentalai.ca>"
            )
            kwargs: dict = {
                "FromEmailAddress": from_addr,
                "Destination": {"ToAddresses": [admin_email]},
                "Content": {
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Html": {"Data": html_content, "Charset": "UTF-8"},
                            "Text": {"Data": txt_content, "Charset": "UTF-8"},
                        },
                    },
                },
            }
            if SES_CONFIGURATION_SET:
                kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

            for attempt in range(_MAX_RETRIES + 1):
                try:
                    client = self._get_client()
                    await asyncio.to_thread(client.send_email, **kwargs)
                    logger.info("admin_notification_sent", extra={**ctx, "attempt": attempt + 1})
                    success = True
                    break
                except ClientError as exc:
                    code = exc.response["Error"]["Code"]
                    if code == "TooManyRequestsException" and attempt < _MAX_RETRIES:
                        wait = 2 ** attempt
                        logger.warning(
                            "admin_notification_throttled",
                            extra={**ctx, "retry": attempt + 1, "wait_s": wait},
                        )
                        await asyncio.sleep(wait)
                        continue
                    logger.error(
                        "admin_notification_ses_error",
                        extra={**ctx, "error_code": code, "error": str(exc)},
                    )
                    break
                except Exception as exc:
                    logger.error(
                        "admin_notification_unexpected_error",
                        extra={**ctx, "error": str(exc)},
                    )
                    break

        except Exception as exc:
            logger.error("admin_notification_render_error", extra={**ctx, "error": str(exc)})

        try:
            await db.admin_email_logs.insert_one({
                "practice_id": practice_id,
                "template_name": template_name,
                "subject": subject,
                "to": admin_email,
                "success": success,
                "timestamp": now_iso,
            })
        except Exception as exc:
            logger.error("admin_email_log_write_error", extra={**ctx, "error": str(exc)})

        return success


# Module-level singleton used across all routers
email_service = EmailService()
