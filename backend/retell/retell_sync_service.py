"""
Sync practice settings to the Retell agent after any config change.

Called after branding, hours, appointment types, or emergency rules are saved.
Always returns a result dict — never raises. Settings save is never blocked by
a Retell API failure; the caller receives a retell_sync warning instead.
"""
import os
import logging
from datetime import datetime, timezone

import httpx

from retell.prompt_renderer import render_prompt

logger = logging.getLogger(__name__)

_RETELL_API_BASE = "https://api.retellai.com"


async def sync_practice(practice: dict, db) -> dict:
    """
    Regenerate the system prompt from current practice settings and push
    it to the Retell agent via the Retell management API.

    Returns:
        {"synced": True}
        {"synced": False, "skipped": True, "reason": "<reason>"}
        {"synced": False, "error": "<error message>"}
    """
    practice_id = practice.get("id")
    retell_cfg = (practice.get("settings") or {}).get("retell") or {}
    agent_id = retell_cfg.get("agent_id")

    if not agent_id:
        logger.info(
            "retell_sync_skipped",
            extra={"practice_id": practice_id, "reason": "no_agent_id"},
        )
        return {"synced": False, "skipped": True, "reason": "no_agent_id"}

    api_key = os.getenv("RETELL_API_KEY", "")
    if not api_key:
        logger.warning(
            "retell_sync_skipped",
            extra={"practice_id": practice_id, "reason": "no_api_key"},
        )
        return {"synced": False, "skipped": True, "reason": "no_api_key"}

    prompt = await render_prompt(practice, db)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{_RETELL_API_BASE}/v1/agents/{agent_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"prompt": prompt},
            )
            resp.raise_for_status()

        logger.info(
            "retell_sync_success",
            extra={
                "practice_id": practice_id,
                "agent_id": agent_id,
                "prompt_length": len(prompt),
            },
        )
        await _log_sync(db, practice_id, agent_id, success=True)
        return {"synced": True}

    except httpx.HTTPStatusError as exc:
        error = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        logger.error(
            "retell_sync_failed",
            extra={"practice_id": practice_id, "agent_id": agent_id, "error": error},
        )
        await _log_sync(db, practice_id, agent_id, success=False, error=error)
        return {"synced": False, "error": error}

    except Exception as exc:
        error = str(exc)
        logger.error(
            "retell_sync_failed",
            extra={"practice_id": practice_id, "agent_id": agent_id, "error": error},
        )
        await _log_sync(db, practice_id, agent_id, success=False, error=error)
        return {"synced": False, "error": error}


async def _log_sync(
    db,
    practice_id: str | None,
    agent_id: str,
    *,
    success: bool,
    error: str | None = None,
) -> None:
    """Write a retell_sync entry to ai_safety_logs. Swallows all exceptions."""
    try:
        await db.ai_safety_logs.insert_one(
            {
                "event_type": "retell_sync",
                "practice_id": practice_id,
                "agent_id": agent_id,
                "success": success,
                "error": error,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        logger.error("retell_sync_log_failed", extra={"error": str(exc)})
