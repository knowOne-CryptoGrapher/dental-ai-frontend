"""
Emergency Detection Module
--------------------------

Centralized emergency keyword detection for:
- Retell conversational router (Amanda)
- Call analysis pipeline
- ITRANS/CDAnet‑safe emergency escalation

This module is intentionally simple and deterministic.
"""

def detect_emergency(text: str) -> bool:
    """
    Returns True if the message contains emergency indicators.
    This is intentionally conservative and ITRANS/CDAnet‑safe.
    """

    if not text:
        return False

    text_lower = text.lower()

    emergency_keywords = [
        "severe pain",
        "unbearable pain",
        "excruciating",
        "bleeding",
        "blood",
        "hemorrhage",
        "infection",
        "abscess",
        "swollen",
        "fever",
        "tooth broke",
        "broken tooth",
        "fractured tooth",
        "jaw locked",
        "cannot open mouth",
        "cannot close mouth",
        "trauma",
        "accident",
        "hit my face",
        "knocked out",
    ]

    return any(keyword in text_lower for keyword in emergency_keywords)
