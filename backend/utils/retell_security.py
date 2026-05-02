"""
Retell AI Webhook Security Utilities
Handles HMAC-SHA256 signature verification for webhook authentication
"""
import hmac
import hashlib
import time
import json
from typing import Optional
from fastapi import HTTPException, Request, status
import logging

logger = logging.getLogger(__name__)


async def verify_retell_webhook_signature(
    request: Request,
    api_key: str,
    timestamp_tolerance_seconds: int = 300
) -> dict:
    """
    Verify Retell webhook signature using HMAC-SHA256.
    
    Args:
        request: FastAPI Request object
        api_key: Retell API key for signature verification
        timestamp_tolerance_seconds: Maximum age of webhook in seconds (default 5 minutes)
    
    Returns:
        dict: Parsed webhook payload if signature is valid
    
    Raises:
        HTTPException: If signature is invalid or missing
    """
    
    # Get the raw body for signature computation
    body = await request.body()
    
    # Extract signature header
    signature_header = request.headers.get("x-retell-signature")
    if not signature_header:
        logger.warning("Missing webhook signature header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature header"
        )
    
    # Parse signature header format: v={timestamp},d={hex_digest}
    try:
        parts = signature_header.split(",")
        timestamp_part = parts[0].split("=")[1]
        digest_part = parts[1].split("=")[1]
        request_timestamp = int(timestamp_part)
    except (IndexError, ValueError):
        logger.warning(f"Invalid signature header format: {signature_header}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature header format"
        )
    
    # Check timestamp is within tolerance (prevent replay attacks)
    current_time_ms = int(time.time() * 1000)
    time_difference_ms = current_time_ms - request_timestamp
    
    if abs(time_difference_ms) > (timestamp_tolerance_seconds * 1000):
        logger.warning(f"Webhook timestamp too old: {time_difference_ms}ms difference")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook timestamp too old or too far in future"
        )
    
    # Compute expected signature
    # Format: body + timestamp as string
    message_to_sign = body + str(request_timestamp).encode('utf-8')
    expected_digest = hmac.new(
        api_key.encode('utf-8'),
        message_to_sign,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_digest, digest_part):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse and return the JSON body
    try:
        payload = json.loads(body.decode('utf-8'))
        return payload
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook body")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in webhook body"
        )


def detect_emergency_keywords(transcript: str) -> list[str]:
    """
    Detect emergency keywords in call transcript.
    
    Args:
        transcript: Call transcript text
    
    Returns:
        list: Detected emergency keywords/categories
    """
    
    emergency_keywords = {
        # Immediate threats
        "severe pain": ["severe pain", "excruciating", "unbearable pain", "intense pain"],
        "bleeding": ["bleeding", "hemorrhage", "blood", "bleeding heavily"],
        "tooth fracture": ["tooth broke", "fractured tooth", "broken tooth", "cracked tooth", "chipped tooth"],
        "infection": ["infection", "abscess", "swollen", "fever", "pus"],
        "jaw issues": ["jaw locked", "cannot close mouth", "cannot open mouth", "tmj", "jaw pain"],
        "difficulty breathing": ["breathing", "shortness of breath", "difficulty breathing", "asthma"],
        "trauma": ["accident", "trauma", "hit", "fell", "knocked out", "injury"],
        "allergic reaction": ["allergic", "anaphylaxis", "swelling", "hives", "reaction"],
    }
    
    detected = []
    transcript_lower = transcript.lower()
    
    for category, keywords in emergency_keywords.items():
        for keyword in keywords:
            if keyword in transcript_lower:
                detected.append(category)
                break  # Only add category once
    
    return list(set(detected))  # Remove duplicates
