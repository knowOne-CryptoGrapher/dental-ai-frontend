"""Pure prompt renderer — no DB access, easily unit-tested."""
from pathlib import Path
from typing import List

_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "amanda_template.md"

_DAY_NAMES = [("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"),
              ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"),
              ("sun", "Sunday")]

_TONE_DESCRIPTIONS = {
    "warm_professional": "warm, professional",
    "casual": "friendly, casual",
    "formal": "polished, formal",
}

_TONE_GUIDANCE = {
    "warm_professional": (
        "Be warm, professional, and concise. One question at a time. "
        "Say \"one moment\" while functions run so the caller doesn't "
        "think you've frozen. If the caller sounds upset, slow down "
        "and acknowledge them."
    ),
    "casual": (
        "Be friendly and conversational. Use contractions. Match the "
        "caller's energy. It's okay to occasionally say \"sure thing\" "
        "or \"got it\"."
    ),
    "formal": (
        "Maintain a polished, formal tone. Avoid contractions. "
        "Use full sentences and address the caller formally."
    ),
}


def _format_providers_block(providers: List[dict]) -> str:
    if not providers:
        return "_No active providers on record yet._"
    lines = []
    for p in providers:
        name = p.get("name", "")
        role = p.get("role", "Provider")
        on_call = " (on call for emergencies)" if p.get("on_call") else ""
        lines.append(f"- **{name}** — {role}{on_call}")
    return "\n".join(lines)


def _format_hours_block(hours: dict) -> str:
    weekly = (hours or {}).get("weekly") or {}
    if not weekly:
        return "_Hours not configured._"
    lines = []
    for key, day_name in _DAY_NAMES:
        slot = weekly.get(key)
        if slot and slot.get("open") and slot.get("close"):
            lines.append(f"- {day_name}: {slot['open']}–{slot['close']}")
        else:
            lines.append(f"- {day_name}: Closed")
    tz = (hours or {}).get("timezone", "")
    header = f"(Times shown in {tz})\n" if tz else ""
    return header + "\n".join(lines)


def _format_closed_dates_block(hours: dict) -> str:
    dates = (hours or {}).get("closed_dates") or []
    if not dates:
        return ""
    return (
        "## UPCOMING CLOSURES\n"
        "We are closed on these dates — do not book appointments on them:\n"
        + "\n".join(f"- {d}" for d in dates)
        + "\n"
    )


def _format_appointment_types_block(types: List[dict]) -> str:
    if not types:
        return "_No appointment types configured._"
    return "\n".join(
        f"- **{t.get('name')}** ({t.get('duration_min', 30)} min)"
        for t in types
    )


def _emergency_handoff_line(emergency: dict) -> str:
    phone = (emergency or {}).get("after_hours_handoff_phone")
    policy = (emergency or {}).get("response_policy", "earliest_available")
    if policy in ("transfer", "both") and phone:
        return (
            f"\n  If the caller can't reach us in time (after-hours), "
            f"direct them to our emergency line: {phone}."
        )
    return ""


def render_amanda_prompt(
    practice: dict,
    providers: List[dict],
    appointment_types: List[dict] | None = None,
) -> str:
    """
    Fill the Amanda template with practice-specific values.

    `practice` must be a dict with `id`, `name`, and `settings` keys.
    `providers` is a list of active provider dicts.
    `appointment_types` — if None, pulled from practice.settings.appointment_types.
    """
    settings = practice.get("settings") or {}
    branding = settings.get("branding") or {}
    hours = settings.get("hours") or {}
    emergency = settings.get("emergency") or {}
    types = appointment_types if appointment_types is not None else (
        settings.get("appointment_types") or []
    )

    tone = branding.get("voice_tone", "warm_professional")

    template = _TEMPLATE_PATH.read_text()
    replacements = {
        "{{agent_name}}":       branding.get("agent_name", "Amanda"),
        "{{practice_name}}":    practice.get("name", "our practice"),
        "{{practice_id}}":      practice.get("id", ""),
        "{{greeting}}":         branding.get("greeting", "Thank you for calling."),
        "{{closing}}":          branding.get("closing", "Thank you for calling."),
        "{{voice_tone_desc}}":  _TONE_DESCRIPTIONS.get(tone, _TONE_DESCRIPTIONS["warm_professional"]),
        "{{tone_guidance}}":    _TONE_GUIDANCE.get(tone, _TONE_GUIDANCE["warm_professional"]),
        "{{providers_block}}":  _format_providers_block(providers),
        "{{hours_block}}":      _format_hours_block(hours),
        "{{closed_dates_block}}": _format_closed_dates_block(hours),
        "{{appointment_types_block}}": _format_appointment_types_block(types),
        "{{emergency_handoff_line}}":  _emergency_handoff_line(emergency),
    }
    rendered = template
    for k, v in replacements.items():
        rendered = rendered.replace(k, str(v))
    return rendered
