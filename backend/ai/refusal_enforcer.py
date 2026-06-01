"""
Refusal enforcement layer.

Detects when the model has answered confidently without grounding in
the retrieved context. Blocks the response and logs a refusal_failure event.

This layer operates AFTER the model responds and BEFORE it reaches the caller.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Phrases that signal the model is answering from training data, not context
FABRICATION_SIGNALS = [
    r"typically",
    r"usually",
    r"in most cases",
    r"generally speaking",
    r"most dental offices",
    r"standard practice",
    r"commonly",
    r"as a rule",
    r"it.s common",
    r"research shows",
    r"studies show",
    r"experts recommend",
    # TODO: Expand from real call transcript analysis
]

REFUSAL_RESPONSE = (
    "I want to make sure I give you accurate information. "
    "For that question, it's best to speak directly with the dental team — "
    "they'll be able to give you a definitive answer. "
    "Can I help you schedule a time to speak with them?"
)


@dataclass
class RefusalResult:
    passed: bool
    response_text: str
    refusal_triggered: bool
    signal_matched: str = ""


def enforce_refusal(response_text: str, context_hash: str) -> RefusalResult:
    """
    Check model output for fabrication signals.

    If a signal is detected, block the response and return REFUSAL_RESPONSE.
    Logs a refusal_failure event for dashboard review.

    Args:
        response_text: The model's raw output.
        context_hash: The context hash from the ContextBundle — stored with the log.
    """
    text_lower = response_text.lower()

    for signal in FABRICATION_SIGNALS:
        if re.search(signal, text_lower):
            logger.warning(
                "refusal_failure",
                extra={
                    "signal": signal,
                    "context_hash": context_hash,
                    # Never log response_text — may contain PHI
                }
            )
            return RefusalResult(
                passed=False,
                response_text=REFUSAL_RESPONSE,
                refusal_triggered=True,
                signal_matched=signal,
            )

    return RefusalResult(
        passed=True,
        response_text=response_text,
        refusal_triggered=False,
    )
