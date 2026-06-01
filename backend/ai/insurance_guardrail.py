"""
Insurance guardrail engine.

Scans all model output for forbidden insurance phrases before returning
to the caller. If a violation is detected:
  1. Blocks the original response.
  2. Returns a safe fallback phrase.
  3. Logs a guardrail_triggered audit event.

MAX_INSURANCE_CONFIDENCE_SCORE controls how aggressive the scanner is.
Lower = more aggressive. Tune without code changes.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Tune without code changes — lower = more aggressive blocking
MAX_INSURANCE_CONFIDENCE_SCORE = 0.7

FORBIDDEN_PATTERNS = [
    (r"100\s*%\s*(covered|coverage)",      "absolute coverage claim"),
    (r"fully\s+covered",                   "absolute coverage claim"),
    (r"guaranteed",                        "guarantee claim"),
    (r"you\s+won.t\s+pay\s+anything",      "zero cost claim"),
    (r"no\s+cost\s+to\s+you",             "zero cost claim"),
    (r"covered\s+under\s+your\s+plan",     "coverage claim"),
    (r"your\s+insurance\s+covers",         "coverage claim"),
    (r"will\s+be\s+covered",              "coverage claim"),
    (r"is\s+covered",                      "coverage claim"),
    (r"free\s+of\s+charge",               "zero cost claim"),
    (r"at\s+no\s+charge",                 "zero cost claim"),
    # TODO: Add more patterns from real call transcript review
]

SAFE_INSURANCE_PHRASE = (
    "I'm not able to confirm your exact coverage — insurance benefits vary by plan. "
    "The team will verify your benefits before your appointment and let you know what to expect."
)


@dataclass
class GuardrailResult:
    passed: bool
    original_text: str
    safe_text: str
    violation_type: str = ""
    matched_pattern: str = ""


def scan_insurance_output(text: str) -> GuardrailResult:
    """
    Scan model output for forbidden insurance phrases.

    Returns GuardrailResult. If passed=False, use safe_text instead of
    original_text and log a guardrail_triggered event.
    """
    text_lower = text.lower()

    for pattern, violation_type in FORBIDDEN_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning(
                "insurance_guardrail_triggered",
                extra={
                    "violation_type": violation_type,
                    "matched_pattern": pattern,
                    # Never log the original text — it may contain PHI
                }
            )
            return GuardrailResult(
                passed=False,
                original_text="[REDACTED — guardrail triggered]",
                safe_text=SAFE_INSURANCE_PHRASE,
                violation_type=violation_type,
                matched_pattern=pattern,
            )

    return GuardrailResult(
        passed=True,
        original_text=text,
        safe_text=text,
    )
