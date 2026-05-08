# backend/routers/llm_route_and_complete.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from llm.router import route_message
from llm.providers import get_provider
from llm.models import ChatMessage

router = APIRouter(prefix="/api/llm", tags=["LLM"])

class RouteAndCompleteRequest(BaseModel):
    messages: List[ChatMessage]
    stream: Optional[bool] = False


@router.post("/route-and-complete")
async def route_and_complete(req: RouteAndCompleteRequest):
    """
    1. Run router → choose provider + model
    2. Attempt provider call
    3. If provider fails → fallback to next provider
    """

    # Step 1 — Run router
    routing = route_message(req.messages)

    provider_name = routing.provider
    model_name = routing.model

    # Step 2 — Try primary provider
    provider = get_provider(provider_name)

    try:
        return await provider.chat_completion(
            model=model_name,
            messages=req.messages,
            stream=req.stream
        )

    except Exception as e:
        # Step 3 — Fallback logic
        fallback_chain = ["openai", "anthropic", "google", "groq", "stub"]

        # Remove the failed provider
        fallback_chain = [p for p in fallback_chain if p != provider_name]

        for fallback_provider_name in fallback_chain:
            fallback_provider = get_provider(fallback_provider_name)
            if fallback_provider is None:
                continue

            try:
                return await fallback_provider.chat_completion(
                    model=None,  # provider decides default model
                    messages=req.messages,
                    stream=req.stream
                )
            except Exception:
                continue

        raise HTTPException(
            status_code=500,
            detail="All providers failed — no fallback available."
        )
