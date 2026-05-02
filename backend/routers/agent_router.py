"""Phase 1 agent endpoints — per-practice prompt rendering."""
import hashlib
import logging
from fastapi import APIRouter, HTTPException, Depends

from auth import get_db, get_current_user, require_role
from agent.prompt_renderer import render_amanda_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])


def _ensure_tenant_access(current_user: dict, practice_id: str):
    """Allow admins of this practice or super_admins; 404 otherwise
    (don't confirm existence of other tenants' resources)."""
    if current_user.get("role") == "super_admin":
        return
    if current_user.get("practice_id") != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")


@router.get("/{practice_id}/prompt")
async def get_rendered_prompt(
    practice_id: str,
    current_user: dict = Depends(require_role("super_admin")),
):
    """
    Render the full system prompt for a practice. SUPER_ADMIN ONLY —
    the rendered prompt contains internal infrastructure config and
    is not exposed to practice admins.
    """
    _ensure_tenant_access(current_user, practice_id)
    db = get_db()
    practice = await db.practices.find_one({"id": practice_id}, {"_id": 0})
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    providers = await db.providers.find(
        {"practice_id": practice_id, "$or": [{"active": True}, {"is_active": True}]},
        {"_id": 0}
    ).to_list(100)

    prompt = render_amanda_prompt(practice, providers)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    return {
        "practice_id": practice_id,
        "prompt": prompt,
        "hash": prompt_hash,
        "length_chars": len(prompt),
        "provider_count": len(providers),
    }
