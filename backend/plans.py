"""
Plan tiers — single source of truth.

Every plan-aware part of the codebase reads from `PLANS` here:
  • billing_router  — pricing + Stripe Price ID env wiring
  • llm/router      — what models the plan is allowed to use
  • superadmin      — plan selector validation
  • practice_config — feature gates (insurance, analytics, custom routing)
  • frontend        — fetched via /api/billing/plans + /api/billing/features

Adding a new plan? Add it here. Don't add plan branching elsewhere.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field, asdict


# ──────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PlanLLM:
    """Plan-specific LLM routing constraints."""
    default_provider: str
    default_model: str
    escalation_provider: str
    escalation_model: str
    allow_escalation: bool = True
    rate_limit_per_min: int = 30


@dataclass(frozen=True)
class PlanFeatures:
    """Boolean feature gates."""
    voice_ai_calls: bool = True
    appointments: bool = True
    patients: bool = True
    call_logs: bool = True
    calendar: bool = True
    analytics: bool = False
    insurance: bool = False
    insurance_preview: bool = False
    audit_log: bool = False
    multi_location: bool = False
    custom_voice: bool = False
    custom_routing_rules: bool = False
    knowledge_base: bool = False
    sip_telephony: bool = False
    dedicated_support: bool = False
    baa_available: bool = False
    custom_model_selection: bool = False


@dataclass(frozen=True)
class PlanLimits:
    calls_per_month: int
    providers_max: int
    locations_max: int
    users_max: int


@dataclass
class Plan:
    id: str
    name: str
    price_usd: float
    description: str
    stripe_price_id_env: str
    limits: PlanLimits
    features: PlanFeatures
    llm: PlanLLM
    sort_order: int = 0
    public: bool = True

    @property
    def stripe_price_id(self) -> str:
        return os.environ.get(self.stripe_price_id_env, "").strip()

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price_usd": self.price_usd,
            "description": self.description,
            "calls_included": self.limits.calls_per_month,
            "providers_max": self.limits.providers_max,
            "locations_max": self.limits.locations_max,
            "users_max": self.limits.users_max,
            "features": asdict(self.features),
            "recurring": bool(self.stripe_price_id),
            "sort_order": self.sort_order,
            "self_serve_enabled": self.id in SELF_SERVE_TIERS_ENABLED,
        }


# ──────────────────────────────────────────────────────────────────────
# LLM Profiles
# ──────────────────────────────────────────────────────────────────────

_BASIC_LLM = PlanLLM(
    default_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
    default_model=os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
    escalation_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
    escalation_model=os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
    allow_escalation=False,
    rate_limit_per_min=30,
)

_PRO_LLM = PlanLLM(
    default_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
    default_model=os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
    escalation_provider=os.environ.get("LLM_ESCALATION_PROVIDER", "anthropic"),
    escalation_model=os.environ.get("LLM_ESCALATION_MODEL", "claude-haiku-4-5-20251001"),
    allow_escalation=True,
    rate_limit_per_min=120,
)

_ENT_LLM = PlanLLM(
    default_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
    default_model=os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
    escalation_provider=os.environ.get("LLM_ESCALATION_PROVIDER", "anthropic"),
    escalation_model=os.environ.get("LLM_ESCALATION_MODEL", "claude-haiku-4-5-20251001"),
    allow_escalation=True,
    rate_limit_per_min=600,
)

_ELITE_LLM = PlanLLM(
    default_provider=os.environ.get("LLM_DEFAULT_PROVIDER", "openai"),
    default_model=os.environ.get("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
    escalation_provider=os.environ.get("LLM_ESCALATION_PROVIDER", "anthropic"),
    escalation_model=os.environ.get("LLM_ESCALATION_MODEL", "claude-haiku-4-5-20251001"),
    allow_escalation=True,
    rate_limit_per_min=2000,  # Elite gets the highest throughput
)


# ──────────────────────────────────────────────────────────────────────
# Plan Definitions
# ──────────────────────────────────────────────────────────────────────

PLANS: dict[str, Plan] = {
    "basic": Plan(
        id="basic", name="Basic", price_usd=399.0, sort_order=0,
        description="Perfect for solo practitioners. Single location, cheap-model AI receptionist.",
        stripe_price_id_env="STRIPE_PRICE_BASIC",
        limits=PlanLimits(calls_per_month=250, providers_max=5, locations_max=1, users_max=5),
        features=PlanFeatures(audit_log=True),
        llm=_BASIC_LLM,
    ),
    "professional": Plan(
        id="professional", name="Professional", price_usd=599.0, sort_order=1,
        description="Multi-provider, smart-routing AI receptionist with full analytics and insurance.",
        stripe_price_id_env="STRIPE_PRICE_PROFESSIONAL",
        limits=PlanLimits(calls_per_month=750, providers_max=15, locations_max=5, users_max=25),
        features=PlanFeatures(
            analytics=True, insurance=True, audit_log=True, multi_location=True
        ),
        llm=_PRO_LLM,
    ),
    "enterprise": Plan(
        id="enterprise", name="Enterprise", price_usd=999.0, sort_order=2,
        description="Multi-location DSOs. Custom voice, SIP telephony, KB, and routing rules.",
        stripe_price_id_env="STRIPE_PRICE_ENTERPRISE",
        limits=PlanLimits(calls_per_month=2500, providers_max=50, locations_max=25, users_max=200),
        features=PlanFeatures(
            analytics=True, insurance=True, audit_log=True, multi_location=True,
            custom_voice=True, custom_routing_rules=True, knowledge_base=True, sip_telephony=True
        ),
        llm=_ENT_LLM,
    ),
    "elite": Plan(
        id="elite", name="Elite", price_usd=1499.0, sort_order=3,
        description="Unlimited-scale AI receptionist with maximum throughput, custom models, and enterprise-grade features.",
        stripe_price_id_env="STRIPE_PRICE_ELITE",
        limits=PlanLimits(calls_per_month=10000, providers_max=200, locations_max=100, users_max=1000),
        features=PlanFeatures(
            analytics=True, insurance=True, audit_log=True, multi_location=True,
            custom_voice=True, custom_routing_rules=True, knowledge_base=True, sip_telephony=True,
            dedicated_support=True, baa_available=True, custom_model_selection=True,
        ),
        llm=_ELITE_LLM,
    ),
    "founding_clinic_basic": Plan(
        id="founding_clinic_basic", name="Founding Clinic (Basic)", price_usd=299.0, sort_order=99,
        public=False,
        description="Founding Clinic Program — locked-in early-adopter rate.",
        stripe_price_id_env="STRIPE_PRICE_FOUNDING_CLINIC",
        limits=PlanLimits(calls_per_month=250, providers_max=5, locations_max=1, users_max=5),
        features=PlanFeatures(audit_log=True, insurance_preview=True),
        llm=_BASIC_LLM,
    ),
}

DEFAULT_PLAN_ID = "basic"

# Self-serve NEW-account signup gate — which plan ids can be chosen at
# registration today. Independent of PLANS (all plans that structurally
# exist) and Plan.public (billing-page upgrade visibility for existing
# customers) — this only governs brand-new self-serve signups. Superadmin
# manual assignment, founding-clinic provisioning, and billing-page upgrades
# all bypass this entirely. Expand as tiers open up (e.g. once ITRANS/CDAnet
# clears): {"basic", "professional", "enterprise", "elite"}.
SELF_SERVE_TIERS_ENABLED: set[str] = {"basic"}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def get_plan(plan_id: str | None) -> Plan:
    if not plan_id:
        return PLANS[DEFAULT_PLAN_ID]
    return PLANS.get(plan_id.lower(), PLANS[DEFAULT_PLAN_ID])


def list_plans() -> list[Plan]:
    return sorted(PLANS.values(), key=lambda p: p.sort_order)


def is_valid_plan_id(plan_id: str | None) -> bool:
    return bool(plan_id) and plan_id.lower() in PLANS


async def enforce_plan_limit(db, practice_id: str, limit_name: str) -> None:
    from fastapi import HTTPException
    practice = await db.practices.find_one(
        {"id": practice_id}, {"_id": 0, "subscription_plan": 1}
    ) or {}
    plan = get_plan(practice.get("subscription_plan"))

    if limit_name == "locations":
        used = await db.locations.count_documents({"practice_id": practice_id, "is_active": True})
        cap = plan.limits.locations_max
        label = "locations"
    elif limit_name == "providers":
        used = await db.providers.count_documents(
            {"practice_id": practice_id, "$or": [{"is_active": True}, {"active": True}]}
        )
        cap = plan.limits.providers_max
        label = "providers"
    elif limit_name == "users":
        used = await db.users.count_documents({"practice_id": practice_id, "is_active": True})
        cap = plan.limits.users_max
        label = "users"
    else:
        raise ValueError(f"Unknown limit_name: {limit_name}")

    if used >= cap:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Plan limit reached: your {plan.name} plan allows {cap} {label} "
                f"(currently using {used}). Upgrade your plan to add more."
            ),
        )
