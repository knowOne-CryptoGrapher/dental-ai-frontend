# backend/routers/llm_route_and_complete.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from llm.router import get_default_router
from llm.base import ChatMessage
from llm.registry import get_provider
from plans import get_plan
from auth import get_db

router = APIRouter(prefix="/api/llm", tags=["LLM"])


class RouteAndCompleteRequest(BaseModel):
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    practice_id: Optional[str] = None  # multi‑tenant context


@router.post("/route-and-complete")
async def route_and_complete(req: RouteAndCompleteRequest):
    """
    Multi‑tenant LLM routing endpoint.

    Steps:
    1. Resolve subscription plan (if practice_id provided)
    2. Run LLMRouter → choose provider + model
    3. Attempt primary provider call
    4. On failure → fallback chain
    """

    # ------------------------------------------------------------
    # 1) Resolve plan (multi‑tenant)
    # ------------------------------------------------------------
    plan = None
    if req.practice_id:
        db = get_db()
        practice = await db.practices.find_one(
            {"id": req.practice_id},
            {"_id": 0, "subscription_plan": 1},
        ) or {}
        plan = get_plan(practice.get("subscription_plan"))

    # ------------------------------------------------------------
    # 2) Router decides provider + model
    # ------------------------------------------------------------
    llm_router = get_default_router()
    routing = llm_router.decide(req.messages, plan=plan)

    provider_name = routing.provider
    model_name = routing.model

    provider = get_provider(provider_name)
    if provider is None:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown provider: {provider_name}",
        )

    # ------------------------------------------------------------
    # 3) Primary provider call
    # ------------------------------------------------------------
    try:
        return await provider.chat_completion(
            model=model_name,
            messages=req.messages,
            stream=req.stream,
        )

    except Exception as primary_error:
        # ------------------------------------------------------------
        # 4) Fallback chain
        # ------------------------------------------------------------
        fallback_chain = ["openai", "anthropic", "google", "groq", "stub"]
        fallback_chain = [p for p in fallback_chain if p != provider_name]

        for fb in fallback_chain:
            fb_provider = get_provider(fb)
            if fb_provider is None:
                continue

            try:
                return await fb_provider.chat_completion(
                    model=None,  # provider chooses default model
                    messages=req.messages,
                    stream=req.stream,
                )
            except Exception:
                continue

        # If we reach here → all providers failed
        raise HTTPException(
            status_code=500,
            detail="All providers failed — no fallback available.",
        )
