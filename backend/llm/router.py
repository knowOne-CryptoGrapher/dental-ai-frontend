"""
LLMRouter — picks (provider, model) for each conversation turn.

Default policy:
  • Use a cheap/fast model for every turn unless a rule forces escalation.
  • Escalate to a high-quality model when an insurance, treatment-plan,
    complex-scheduling, or uncertainty signal is detected.
  • Decision is logged so we can audit cost and accuracy over time.

Configuration is environment-driven and rule-based. Routing rules are
declarative and can be loaded from env / DB without touching code.
"""
from __future__ import annotations
import os
import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Iterable

from .base import ChatMessage

logger = logging.getLogger(__name__)


# ── Default model identifiers (env-overridable) ───────────────────────
DEFAULT_PROVIDER = os.environ.get("LLM_DEFAULT_PROVIDER", "groq")
DEFAULT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "llama-3.3-70b-versatile")
ESCALATION_PROVIDER = os.environ.get("LLM_ESCALATION_PROVIDER", "anthropic")
ESCALATION_MODEL = os.environ.get("LLM_ESCALATION_MODEL", "claude-haiku-4-5-20251001")
# NOTE: Three-tier routing (groq → openai → anthropic) requires a router refactor
# to support two escalation levels; not implemented. Use env overrides per tier.


# ── Rules ─────────────────────────────────────────────────────────────


@dataclass
class RoutingRule:
    """One escalation rule. If `matches(messages)` returns True, the
    router uses (escalation_provider, escalation_model) and records
    `name` as the trigger."""
    name: str
    keywords: list[str] = field(default_factory=list)
    min_turns: int | None = None  # complex-scheduling: needs at least N user turns
    regex: str | None = None
    description: str = ""

    def matches(self, messages: list[ChatMessage]) -> bool:
        if self.min_turns is not None:
            user_turns = sum(1 for m in messages if m.role == "user")
            if user_turns < self.min_turns:
                return False
        last_user = next((m.content.lower() for m in reversed(messages) if m.role == "user"), "")
        last_assistant = next((m.content.lower() for m in reversed(messages) if m.role == "assistant"), "")
        haystack = last_user + " || " + last_assistant
        if self.regex:
            if re.search(self.regex, haystack, re.IGNORECASE):
                return True
        for kw in self.keywords:
            if kw.lower() in haystack:
                return True
        return False


# ── Default escalation rules ──────────────────────────────────────────
DEFAULT_RULES: list[RoutingRule] = [
    RoutingRule(
        name="insurance_question",
        description="Insurance, coverage, claims, CDANet, fee guides — high accuracy needed.",
        keywords=[
            "insurance", "coverage", "covered", "deductible", "co-pay", "copay",
            "claim", "policy", "in-network", "out of network", "out-of-network",
            "predetermination", "ppo", "hmo", "delta dental", "blue cross",
            "preauthorization", "cdanet", "fee guide",
        ],
    ),
    RoutingRule(
        name="treatment_plan",
        description="Treatment plan, procedures, cost estimates.",
        keywords=[
            "treatment plan", "procedure", "estimate", "how much", "what would",
            "root canal", "crown", "implant", "extraction", "surgery", "wisdom tooth",
            "wisdom teeth", "veneer", "bridge", "denture", "filling cost",
        ],
    ),
    RoutingRule(
        name="clinical",
        description="Clinical or medical content — escalate for accuracy.",
        keywords=[
            "diagnosis", "symptom", "infection", "prescription", "treatment",
        ],
    ),
    RoutingRule(
        name="complex_scheduling",
        description="Multi-turn scheduling conversation — escalate to handle nuance.",
        min_turns=4,
        keywords=[
            "earliest", "different time", "another day", "options", "before", "after",
            "morning slot", "afternoon slot", "next available", "any other",
            "reschedule", "move my appointment", "change my appointment",
        ],
    ),
    RoutingRule(
        name="legal_longform",
        description="Legal or contractual content.",
        keywords=["contract", "agreement", "acquisition", "legal", "terms", "binding"],
    ),
    RoutingRule(
        name="uncertainty",
        description="Assistant or user expressed uncertainty — escalate this turn.",
        keywords=["uncertain", "ambiguous", "confused"],
        regex=r"\b(i'?m not sure|let me check|i don'?t know|let me transfer|hold on|not certain)\b",
    ),
]


# ── Decision ──────────────────────────────────────────────────────────


@dataclass
class RoutingDecision:
    provider: str
    model: str
    escalated: bool
    trigger: str | None = None  # rule name, or None for default
    reason: str = ""

    def as_log_dict(self) -> dict:
        return asdict(self)


# ── Router ────────────────────────────────────────────────────────────


class LLMRouter:
    def __init__(
        self,
        rules: Iterable[RoutingRule] | None = None,
        *,
        default_provider: str = DEFAULT_PROVIDER,
        default_model: str = DEFAULT_MODEL,
        escalation_provider: str = ESCALATION_PROVIDER,
        escalation_model: str = ESCALATION_MODEL,
    ):
        self.rules = list(rules) if rules is not None else list(DEFAULT_RULES)
        self.default_provider = default_provider
        self.default_model = default_model
        self.escalation_provider = escalation_provider
        self.escalation_model = escalation_model

    def decide(self, messages: list[ChatMessage], *, plan=None) -> RoutingDecision:
        """
        Pick a (provider, model) for this turn.

        If a `plan` (plans.Plan) is passed, the plan's LLM config OVERRIDES
        the router's default/escalation models. This is how plan tiers gate
        model access:
          • Basic plan → allow_escalation=False, so even an insurance
            keyword still routes to the cheap model.
          • Professional/Enterprise → escalation enabled with full rules.
        """
        if plan is not None:
            default_provider = plan.llm.default_provider
            default_model = plan.llm.default_model
            esc_provider = plan.llm.escalation_provider
            esc_model = plan.llm.escalation_model
            allow_esc = plan.llm.allow_escalation
        else:
            default_provider = self.default_provider
            default_model = self.default_model
            esc_provider = self.escalation_provider
            esc_model = self.escalation_model
            allow_esc = True

        if allow_esc:
            for rule in self.rules:
                if rule.matches(messages):
                    return RoutingDecision(
                        provider=esc_provider,
                        model=esc_model,
                        escalated=True,
                        trigger=rule.name,
                        reason=rule.description,
                    )
        # Default path (or escalation forbidden by plan)
        reason = "default — no escalation triggered"
        if not allow_esc:
            for rule in self.rules:
                if rule.matches(messages):
                    reason = f"plan disallows escalation (would have triggered: {rule.name})"
                    break
        return RoutingDecision(
            provider=default_provider,
            model=default_model,
            escalated=False,
            trigger=None,
            reason=reason,
        )

    @classmethod
    def from_env(cls) -> "LLMRouter":
        # Optional JSON file at LLM_RULES_PATH overrides defaults
        rules: list[RoutingRule] = list(DEFAULT_RULES)
        path = os.environ.get("LLM_RULES_PATH")
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                rules = [RoutingRule(**r) for r in data]
                logger.info(f"LLM: loaded {len(rules)} routing rules from {path}")
            except Exception as e:
                logger.warning(f"LLM: failed to load routing rules from {path}: {e} — using defaults")
        return cls(rules=rules)


# Module-level default router (cheap to construct; safe to share)
_default_router: LLMRouter | None = None


def get_default_router() -> LLMRouter:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter.from_env()
    return _default_router


def reset_router_for_tests() -> None:
    global _default_router
    _default_router = None
