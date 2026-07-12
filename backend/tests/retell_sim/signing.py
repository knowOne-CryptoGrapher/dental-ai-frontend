"""
Retell webhook HMAC signing helper.
Computes the x-retell-signature header value for synthetic call event payloads.

Algorithm (from utils/retell_security.py):
  body_bytes = json.dumps(payload).encode()
  timestamp_ms = int(time.time() * 1000)
  message = body_bytes + str(timestamp_ms).encode()
  signature = hmac.new(
    RETELL_WEBHOOK_SECRET.encode(),
    message,
    hashlib.sha256
  ).hexdigest()
  header = f"v={timestamp_ms},d={signature}"
"""

import hmac
import hashlib
import time
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

WEBHOOK_SECRET = os.environ.get('RETELL_WEBHOOK_SECRET', '')
RETELL_SECRET  = os.environ.get('RETELL_WEBHOOK_SECRET', '')
BACKEND_URL    = os.environ.get(
    'BACKEND_URL',
    'https://dental-ai-backend-cszmxu7emq-uw.a.run.app',
)


def compute_signature(payload: dict) -> tuple[str, str]:
    """
    Returns (signature_header, body_str) for a payload.
    Must be called immediately before sending — timestamp is embedded in the signature.
    """
    body_str   = json.dumps(payload, separators=(',', ':'))
    body_bytes = body_str.encode()
    timestamp_ms = int(time.time() * 1000)
    message    = body_bytes + str(timestamp_ms).encode('utf-8')
    sig_hex    = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()
    header = f"v={timestamp_ms},d={sig_hex}"
    return header, body_str


def post_webhook(payload: dict) -> httpx.Response:
    """POST a signed webhook event to /api/retell/webhook."""
    sig_header, body_str = compute_signature(payload)
    return httpx.post(
        f"{BACKEND_URL}/api/retell/webhook",
        content=body_str,
        headers={
            "Content-Type": "application/json",
            "x-retell-signature": sig_header,
        },
        timeout=15,
    )


def post_function(endpoint: str, payload: dict) -> httpx.Response:
    """POST an unsigned Retell function call to /api/retell/{endpoint}."""
    return httpx.post(
        f"{BACKEND_URL}/api/retell/{endpoint}",
        json=payload,
        timeout=15,
    )


def post_summary(payload: dict) -> httpx.Response:
    """POST a call summary to /api/retell/call-summary with x-retell-secret header."""
    return httpx.post(
        f"{BACKEND_URL}/api/retell/call-summary",
        json=payload,
        headers={"x-retell-secret": RETELL_SECRET},
        timeout=15,
    )
