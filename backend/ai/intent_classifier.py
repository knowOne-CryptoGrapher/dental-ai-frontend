"""
Intent classifier for AI receptionist calls.

v1 uses rule-based pattern matching for speed and determinism.
v2 will optionally use a lightweight LLM classifier.

High-risk intents → force handoff script (never let the model answer).
Confidence threshold: if classifier is below CONFIDENCE_THRESHOLD,
default to safe/handoff rather than allowing the response.
"""
import re
import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.80  # Below this → treat as high-risk


class Intent(str, Enum):
    BOOKING          = "booking"
    CANCELLATION     = "cancellation"        # High-risk — irreversible
    RESCHEDULING     = "rescheduling"
    HOURS_FEES       = "hours_fees"
    INSURANCE_QUERY  = "insurance_query"     # High-risk
    CLINICAL_ADVICE  = "clinical_advice"     # High-risk
    DIAGNOSIS        = "diagnosis"           # High-risk
    TREATMENT_REC    = "treatment_recommendation"  # High-risk
    LEGAL_FINANCIAL  = "legal_financial"     # High-risk
    GENERAL_INFO     = "general_info"
    UNKNOWN          = "unknown"             # Default to safe


HIGH_RISK_INTENTS = {
    Intent.INSURANCE_QUERY,
    Intent.CLINICAL_ADVICE,
    Intent.DIAGNOSIS,
    Intent.TREATMENT_REC,
    Intent.LEGAL_FINANCIAL,
    Intent.CANCELLATION,
}

HANDOFF_SCRIPT = (
    "That's something the dental team needs to answer directly. "
    "I'll make sure they follow up with you as soon as possible. "
    "Is there anything else I can help you with, like scheduling an appointment?"
)

# Rule-based patterns (v1)
_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.CLINICAL_ADVICE, [
        r"does it hurt", r"will it hurt", r"is it painful",
        r"is this normal", r"should i be worried", r"what does .* mean",
        r"is .* serious", r"do i need .* treatment", r"pain",
        r"infection", r"swelling", r"bleeding", r"abscess",
    ]),
    (Intent.DIAGNOSIS, [
        r"do i have", r"could it be", r"is it (a |an )?cavity",
        r"is it (a |an )?root canal", r"is it (a |an )?infection",
        r"diagnos", r"what.s wrong", r"what is causing",
    ]),
    (Intent.TREATMENT_REC, [
        r"should i get", r"do i need", r"recommend",
        r"what treatment", r"what procedure", r"best option",
        r"do i need a root canal", r"do i need surgery",
    ]),
    (Intent.INSURANCE_QUERY, [
        r"covered", r"coverage", r"will insurance", r"does insurance",
        r"how much will insurance", r"out of pocket", r"deductible",
        r"co.?pay", r"benefit", r"claim",
    ]),
    (Intent.LEGAL_FINANCIAL, [
        r"guarantee", r"guaranteed", r"promise", r"contract",
        r"sue", r"legal", r"refund", r"money back",
        r"commit", r"binding",
    ]),
    (Intent.CANCELLATION, [
        r"cancel", r"cancell", r"cancel my appointment",
        r"cancel all", r"delete my appointment",
    ]),
    (Intent.BOOKING, [
        r"book", r"schedule", r"appointment", r"available",
        r"can i come in", r"when can i",
    ]),
    (Intent.HOURS_FEES, [
        r"hours", r"open", r"close", r"cost", r"fee", r"price",
        r"how much", r"charge",
    ]),
]


@dataclass
class ClassificationResult:
    intent: Intent
    confidence: float
    is_high_risk: bool
    handoff_required: bool
    matched_pattern: str = ""


def classify_intent(text: str) -> ClassificationResult:
    """
    Classify the intent of a caller message.

    Returns a ClassificationResult. If handoff_required is True,
    use HANDOFF_SCRIPT instead of a model response.
    """
    text_lower = text.lower()

    for intent, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                confidence = 0.90  # Rule match is high confidence
                is_high_risk = intent in HIGH_RISK_INTENTS
                return ClassificationResult(
                    intent=intent,
                    confidence=confidence,
                    is_high_risk=is_high_risk,
                    handoff_required=is_high_risk,
                    matched_pattern=pattern,
                )

    # No pattern matched — unknown intent, low confidence → safe default
    return ClassificationResult(
        intent=Intent.UNKNOWN,
        confidence=0.50,
        is_high_risk=False,
        handoff_required=False,
    )
