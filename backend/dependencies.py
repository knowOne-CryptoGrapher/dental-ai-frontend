"""
Reusable FastAPI dependencies for plan-gated feature enforcement.

ENFORCE_PLAN_GATES (env, default: "false"):
  When set to "true", require_feature() raises HTTP 402 if the caller's
  practice plan does not include the requested feature flag.
  Leave unset or "false" during initial rollout; flip to "true" once all
  existing customers have been verified against the new tier requirements.
"""
import os
import logging
from fastapi import Depends, HTTPException
from auth import get_db, get_current_user
from plans import get_plan

logger = logging.getLogger(__name__)

_ENFORCE: bool = os.getenv("ENFORCE_PLAN_GATES", "false").strip().lower() == "true"


async def _noop() -> None:
    """Placeholder used when plan gate enforcement is disabled."""


def require_feature(flag: str):
    """
    Dependency factory: enforce that the caller's practice plan exposes `flag`.

    Usage:
        @router.get("/some-endpoint")
        async def handler(
            current_user: dict = Depends(get_current_user),
            _gate: None = Depends(require_feature("analytics")),
        ):
            ...

    Raises HTTP 402 when ENFORCE_PLAN_GATES=true and the plan lacks `flag`.
    Is a complete no-op when ENFORCE_PLAN_GATES is unset or not "true".
    super_admin callers are always exempt (no practice_id).
    """
    if not _ENFORCE:
        return _noop

    async def _check(current_user: dict = Depends(get_current_user)) -> None:
        practice_id = current_user.get("practice_id")
        if not practice_id:
            # super_admin or system call — no practice scope, exempt from plan gate
            return
        db = get_db()
        practice = await db.practices.find_one(
            {"id": practice_id},
            {"_id": 0, "subscription_plan": 1},
        ) or {}
        plan = get_plan(practice.get("subscription_plan"))
        if not getattr(plan.features, flag, False):
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Feature '{flag}' is not available on your current plan. "
                    "Upgrade your subscription to access this feature."
                ),
            )

    return _check
