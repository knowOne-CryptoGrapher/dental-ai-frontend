"""
AWS SES event webhook via SNS.

AWS SNS POSTs bounce, complaint, delivery, and reject notifications here.
Every request is signature-verified against the SNS signing certificate before
any data is parsed or persisted. Unsigned or tampered messages are rejected 403.

Endpoint: POST /api/webhooks/ses
"""
from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, HTTPException, Request

from auth import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ses_webhook"])


# ── SNS signature verification ────────────────────────────────────────────────

def _is_valid_cert_url(url: str) -> bool:
    """Only accept signing certs served from AWS SNS endpoints."""
    return url.startswith("https://sns.") and ".amazonaws.com/" in url


def _build_sign_string(payload: dict) -> str:
    """
    Construct the canonical string AWS signs.
    Field order and inclusion rules are defined by the SNS spec.
    """
    msg_type = payload.get("Type", "")
    if msg_type in ("SubscriptionConfirmation", "UnsubscribeConfirmation"):
        keys = ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"]
    else:
        # Notification — Subject is optional and only included when present
        keys = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]

    parts: list[str] = []
    for key in keys:
        if key in payload:
            parts.append(key)
            parts.append(payload[key])
    return "\n".join(parts) + "\n"


async def _verify_sns_signature(payload: dict) -> bool:
    """
    Download the SNS signing certificate and verify the message signature.
    Returns False on any failure rather than raising, so the caller can log
    and return 403 cleanly.
    """
    try:
        cert_url = payload.get("SigningCertURL", "")
        if not _is_valid_cert_url(cert_url):
            logger.warning("sns_invalid_cert_url", extra={"url": cert_url[:120]})
            return False

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(cert_url)
            cert_pem = resp.content

        cert = x509.load_pem_x509_certificate(cert_pem)
        public_key = cert.public_key()

        sign_string = _build_sign_string(payload)
        signature = base64.b64decode(payload.get("Signature", ""))

        # SNS signs with SHA1+RSA — we must verify with the same algorithm
        public_key.verify(
            signature,
            sign_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA1(),  # noqa: S303 — required by AWS SNS specification
        )
        return True
    except Exception as exc:
        logger.warning("sns_signature_invalid", extra={"error": str(exc)})
        return False


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@router.post("/api/webhooks/ses")
async def ses_webhook(request: Request):
    msg_type = request.headers.get("x-amz-sns-message-type", "")

    try:
        raw = await request.body()
        payload = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not await _verify_sns_signature(payload):
        logger.warning("sns_rejected", extra={"msg_type": msg_type})
        raise HTTPException(status_code=403, detail="SNS signature verification failed")

    # Subscription handshake — confirm automatically
    if msg_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL", "")
        if subscribe_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.get(subscribe_url)
                logger.info("sns_confirmed", extra={"topic": payload.get("TopicArn")})
            except Exception as exc:
                logger.error("sns_confirm_failed", extra={"error": str(exc)})
        return {"status": "confirmed"}

    if msg_type == "Notification":
        try:
            inner = json.loads(payload.get("Message", "{}"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid SNS Message JSON")
        await _handle_ses_event(inner, payload)

    return {"received": True}


# ── Event handler ─────────────────────────────────────────────────────────────

async def _handle_ses_event(inner: dict, raw_sns_payload: dict) -> None:
    event_type  = inner.get("eventType", "")
    mail        = inner.get("mail", {})
    ses_msg_id  = mail.get("messageId", "")

    # practice_id is injected as an SES message tag on every send
    tags        = mail.get("tags", {})
    pid_list    = tags.get("practice_id", [])
    practice_id = pid_list[0] if pid_list else None

    bounce_type              = None
    bounce_subtype           = None
    complaint_feedback_type  = None
    recipient: str | None    = None

    if event_type == "Bounce":
        b = inner.get("bounce", {})
        bounce_type    = b.get("bounceType")
        bounce_subtype = b.get("bounceSubType")
        recips         = b.get("bouncedRecipients", [])
        if recips:
            recipient = recips[0].get("emailAddress")
        logger.warning(
            "ses_bounce",
            extra={"practice_id": practice_id, "type": bounce_type, "subtype": bounce_subtype},
        )

    elif event_type == "Complaint":
        c = inner.get("complaint", {})
        complaint_feedback_type = c.get("complaintFeedbackType")
        recips = c.get("complainedRecipients", [])
        if recips:
            recipient = recips[0].get("emailAddress")
        logger.warning(
            "ses_complaint",
            extra={"practice_id": practice_id, "feedback_type": complaint_feedback_type},
        )

    elif event_type == "Delivery":
        d = inner.get("delivery", {})
        recips = d.get("recipients", [])
        if recips:
            recipient = recips[0]
        logger.info("ses_delivery", extra={"practice_id": practice_id})

    else:
        logger.info("ses_event", extra={"event_type": event_type, "practice_id": practice_id})

    # Mask email before storing in any log field; raw_event is DB-only
    masked = (recipient[:3] + "***") if recipient and len(recipient) > 3 else (recipient or "")

    db = get_db()
    await db.email_events.insert_one(
        {
            "id":                       str(uuid.uuid4()),
            "event_type":               event_type,
            "ses_message_id":           ses_msg_id,
            "practice_id":              practice_id,
            "recipient":                masked,
            "bounce_type":              bounce_type,
            "bounce_subtype":           bounce_subtype,
            "complaint_feedback_type":  complaint_feedback_type,
            "raw_event":                raw_sns_payload,
            "received_at":              datetime.now(timezone.utc),
        }
    )
