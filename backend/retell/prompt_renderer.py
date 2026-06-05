"""
Async wrapper around the canonical template-based prompt renderer.

Fetches live providers from the DB so the Retell agent always reflects
the practice's current staff, hours, appointment types, and branding.
Delegates all rendering logic to agent.prompt_renderer — no duplication.
"""
from typing import List

from agent.prompt_renderer import render_amanda_prompt


async def render_prompt(practice: dict, db) -> str:
    """
    Fetch active providers for this practice and render the full system prompt.

    Args:
        practice: Full practice document (must include id, name, settings).
        db:       Motor async DB handle.

    Returns:
        Rendered prompt string ready to push to the Retell agent.
    """
    practice_id = practice.get("id")
    providers: List[dict] = []
    if practice_id:
        providers = await db.providers.find(
            {
                "practice_id": practice_id,
                "$or": [{"is_active": True}, {"active": True}],
            },
            {"_id": 0},
        ).to_list(100)

    return render_amanda_prompt(practice, providers)
