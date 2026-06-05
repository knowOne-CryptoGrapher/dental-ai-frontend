"""
External LLM Routing API.

Exposes:

  • POST /api/llm/chat/completions  — OpenAI-compatible streaming endpoint
                                       Retell uses as its Custom LLM.
                                       Internally routes between providers.

  • POST /api/llm/route             — Returns the routing decision for
                                       a given message list (no completion).
                                       Useful for tests + dashboards.

  • GET  /api/llm/providers         — Lists registered providers.

  • GET  /api/llm/stats             — Aggregate routing stats (super_admin).
                                       Powers the cost-savings dashboard.

  • GET  /api/llm/logs              — Recent routing log entries (super_admin).

The /chat/completions endpoint is intentionally unauthenticated so Retell
can call it. Use a network-level secret (e.g., `X-Retell-Signature` header,
or a path-prefix shared secret) before going to production.
"""
from __future__ import annotations
import json
import time
import uuid
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_db, require_role
from llm.base import ChatMessage
from llm.registry import get_provider, list_providers as _list_providers
from llm.router import LLMRouter, get_default_router
from llm.cache import get_call_cache
from llm.logging import log_routing_decision
from llm.pricing import get_price
from llm.router import (
    DEFAULT_PROVIDER, DEFAULT_MODEL, ESCALATION_PROVIDER, ESCALATION_MODEL,
)
from plans import get_plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["llm"])


# ── Request shapes ────────────────────────────────────────────────────


class _Msg(BaseModel):
    role: str
    content: str
    name: str | None = None


class ChatCompletionsRequest(BaseModel):
    """OpenAI-compatible Chat Completions request (subset Retell uses)."""
    model: str | None = None  # ignored — the router decides
    messages: list[_Msg]
    temperature: float | None = 0.7
    max_tokens: int | None = None
    stream: bool | None = True
    # Retell-specific extras
    metadata: dict[str, Any] | None = None
    call_id: str | None = None
    user: str | None = None


class RouteOnlyRequest(BaseModel):
    messages: list[_Msg]
    practice_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────


def _to_chat_messages(msgs: list[_Msg]) -> list[ChatMessage]:
    return [ChatMessage(role=m.role, content=m.content, name=m.name) for m in msgs]  # type: ignore[arg-type]


def _extract_call_id(req: ChatCompletionsRequest) -> str | None:
    if req.call_id:
        return req.call_id
    md = req.metadata or {}
    return md.get("call_id") or md.get("retell_call_id")


def _sse(event_obj: dict) -> bytes:
    return f"data: {json.dumps(event_obj)}\n\n".encode("utf-8")


async def get_routing_rules(practice_id: str, db) -> list:
    """Fetch enabled routing rules for a practice, sorted by priority asc.
    Returns an empty list on any failure so the LLM call is never blocked."""
    try:
        rules = await db.routing_rules.find(
            {"practice_id": practice_id, "enabled": True},
            {"_id": 0, "priority": 1, "condition": 1, "action": 1},
        ).sort("priority", 1).to_list(100)
        return rules
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers():
    """Public — list which providers the backend has credentials for."""
    return {"providers": _list_providers()}


@router.post("/route")
async def route_only(req: RouteOnlyRequest):
    """Pure routing decision, no completion. Useful for diagnostics / tests.
    If `practice_id` is provided, plan-tier rules are applied."""
    plan = None
    if req.practice_id:
        try:
            practice = await get_db().practices.find_one(
                {"id": req.practice_id}, {"_id": 0, "subscription_plan": 1}
            )
            if practice:
                plan = get_plan(practice.get("subscription_plan"))
        except Exception:
            pass
    decision = get_default_router().decide(_to_chat_messages(req.messages), plan=plan)
    return decision.as_log_dict()


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionsRequest, request: Request):
    """OpenAI-compatible streaming chat completions endpoint that Retell
    invokes for every conversational turn. Internally:
      1. Decides which provider+model to use
      2. Streams the chosen provider's response back as SSE
      3. Logs the decision + token counts
    """
    started = time.monotonic()
    chat_msgs = _to_chat_messages(req.messages)

    # 1. Route — plan-aware if metadata.practice_id is provided
    llm_router: LLMRouter = get_default_router()
    practice_id = (req.metadata or {}).get("practice_id")
    plan = None
    if practice_id:
        try:
            db = get_db()
            practice = await db.practices.find_one(
                {"id": practice_id}, {"_id": 0, "subscription_plan": 1}
            )
            if practice:
                plan = get_plan(practice.get("subscription_plan"))
        except Exception as e:
            logger.warning(f"plan lookup failed for {practice_id}: {e}")

        # Inject custom routing rules into the system message (additive; no change to escalation logic)
        try:
            rules = await get_routing_rules(practice_id, get_db())
            if rules:
                rules_lines = ["=== Custom Routing Rules (evaluate in order) ==="]
                for rule in rules:
                    rules_lines.append(
                        f"Rule {rule['priority']}: If {rule['condition']}, then {rule['action']}."
                    )
                rules_text = "\n".join(rules_lines)
                for i, msg in enumerate(chat_msgs):
                    if msg.role == "system":
                        chat_msgs[i] = ChatMessage(
                            role="system",
                            content=rules_text + "\n\n" + msg.content,
                            name=msg.name,
                        )
                        break
        except Exception as e:
            logger.warning(f"routing rules injection failed for {practice_id}: {e}")

    decision = llm_router.decide(chat_msgs, plan=plan)

    # Apply custom model preference for Elite practices — overrides default routing when set
    if practice_id and plan and getattr(plan.features, "custom_model_selection", False):
        try:
            pref_doc = await get_db().practices.find_one(
                {"id": practice_id}, {"_id": 0, "model_preference": 1}
            ) or {}
            model_pref = pref_doc.get("model_preference")
            if model_pref == "gpt-4o":
                decision.provider = "openai"
                decision.model = "gpt-4o"
                decision.reason = "custom_model_selection:gpt-4o"
            elif model_pref == "claude-sonnet":
                decision.provider = ESCALATION_PROVIDER
                decision.model = ESCALATION_MODEL
                decision.reason = "custom_model_selection:claude-sonnet"
            # gpt-4o-mini and null both use default routing — no override needed
        except Exception as e:
            logger.warning(f"model preference override failed for {practice_id}: {e}")

    call_id = _extract_call_id(req)

    try:
        provider = get_provider(decision.provider)
    except KeyError as e:
        # Provider not registered → fall back to stub so Retell doesn't 500.
        logger.warning(f"LLM router: provider '{decision.provider}' unavailable ({e}); falling back to stub")
        provider = get_provider("stub")
        decision.provider = "stub"
        decision.reason += " | fallback to stub"

    cache = get_call_cache()

    # ── Streaming path ────────────────────────────────────────────────
    if req.stream is None or req.stream:
        async def gen():
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            created = int(time.time())
            base = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": decision.model,
            }
            input_tokens = 0
            output_tokens = 0
            error_msg: str | None = None
            try:
                async for chunk in provider.stream(
                    chat_msgs, decision.model,
                    temperature=req.temperature or 0.7,
                    max_tokens=req.max_tokens,
                ):
                    if chunk.delta:
                        yield _sse({
                            **base,
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": chunk.delta},
                                "finish_reason": None,
                            }],
                        })
                    if chunk.input_tokens:
                        input_tokens = chunk.input_tokens
                    if chunk.output_tokens:
                        output_tokens = chunk.output_tokens
                    if chunk.finish_reason:
                        yield _sse({
                            **base,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": chunk.finish_reason}],
                        })
                yield b"data: [DONE]\n\n"
            except Exception as e:
                error_msg = str(e)
                logger.exception(f"LLM stream error: {e}")
                yield _sse({
                    **base,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": f"[error: {error_msg}]"},
                        "finish_reason": "error",
                    }],
                })
                yield b"data: [DONE]\n\n"
            finally:
                latency_ms = int((time.monotonic() - started) * 1000)
                await log_routing_decision(
                    call_id=call_id, practice_id=practice_id,
                    provider=decision.provider, model=decision.model,
                    escalated=decision.escalated, trigger=decision.trigger,
                    reason=decision.reason,
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    latency_ms=latency_ms, cache_stats=cache.stats(),
                    error=error_msg,
                )

        return StreamingResponse(gen(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-LLM-Provider": decision.provider,
            "X-LLM-Model": decision.model,
            "X-LLM-Escalated": "1" if decision.escalated else "0",
            "X-LLM-Trigger": decision.trigger or "",
        })

    # ── Non-streaming path ────────────────────────────────────────────
    try:
        result = await provider.complete(
            chat_msgs, decision.model,
            temperature=req.temperature or 0.7,
            max_tokens=req.max_tokens,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await log_routing_decision(
            call_id=call_id, practice_id=practice_id,
            provider=decision.provider, model=decision.model,
            escalated=decision.escalated, trigger=decision.trigger,
            reason=decision.reason,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            latency_ms=latency_ms, cache_stats=cache.stats(),
        )
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": decision.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": result.finish_reason,
            }],
            "usage": {
                "prompt_tokens": result.input_tokens,
                "completion_tokens": result.output_tokens,
                "total_tokens": result.input_tokens + result.output_tokens,
            },
            "x_router": decision.as_log_dict(),
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - started) * 1000)
        await log_routing_decision(
            call_id=call_id, practice_id=practice_id,
            provider=decision.provider, model=decision.model,
            escalated=decision.escalated, trigger=decision.trigger,
            reason=decision.reason,
            latency_ms=latency_ms, cache_stats=cache.stats(),
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=f"Upstream LLM error: {e}")


# ── End-of-call hook ──────────────────────────────────────────────────


@router.post("/calls/{call_id}/end")
async def end_call(call_id: str):
    """Drop per-call cache. Call this from Retell's `call_ended` webhook."""
    get_call_cache().end_call(call_id)
    return {"call_id": call_id, "cache": "cleared"}


# ── Analytics (super_admin only) ──────────────────────────────────────


@router.get("/stats")
async def llm_stats(
    current_user: dict = Depends(require_role("super_admin")),
    practice_id: str | None = None,
    days: int = 7,
):
    """Aggregate routing stats — powers the cost-savings dashboard.
    Returns counts/tokens/latency split by provider/model/escalation."""
    db = get_db()
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    match: dict = {"timestamp": {"$gte": cutoff}}
    if practice_id:
        match["practice_id"] = practice_id

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": {"provider": "$provider", "model": "$model", "escalated": "$escalated"},
            "calls": {"$sum": 1},
            "input_tokens": {"$sum": "$input_tokens"},
            "output_tokens": {"$sum": "$output_tokens"},
            "avg_latency_ms": {"$avg": "$latency_ms"},
        }},
        {"$sort": {"calls": -1}},
    ]
    rows = await db.llm_routing_logs.aggregate(pipeline).to_list(100)

    total_turns = sum(r["calls"] for r in rows)
    escalated_turns = sum(r["calls"] for r in rows if r["_id"].get("escalated"))
    total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in rows)

    # ── Cost-savings ROI ──────────────────────────────────────────────
    # `actual_cost` = $ that was actually spent given how each turn was
    #   routed (cheap default for most, escalation model when triggered).
    # `if_all_escalated_cost` = $ it would have cost if we had used the
    #   escalation model for every turn — the natural baseline.
    # `savings` = if_all_escalated_cost − actual_cost.
    escalation_price = get_price(ESCALATION_PROVIDER, ESCALATION_MODEL)
    actual_cost = 0.0
    if_all_escalated_cost = 0.0
    by_model_cost: list[dict] = []

    for r in rows:
        provider = r["_id"]["provider"]
        model = r["_id"]["model"]
        in_tok = r["input_tokens"]
        out_tok = r["output_tokens"]
        price = get_price(provider, model)
        row_actual = price.cost(in_tok, out_tok)
        row_baseline = escalation_price.cost(in_tok, out_tok)
        actual_cost += row_actual
        if_all_escalated_cost += row_baseline
        by_model_cost.append({
            "provider": provider,
            "model": model,
            "escalated": r["_id"]["escalated"],
            "calls": r["calls"],
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 1),
            "input_price_per_million": price.input_per_million,
            "output_price_per_million": price.output_per_million,
            "cost_usd": round(row_actual, 6),
        })

    savings_usd = if_all_escalated_cost - actual_cost
    savings_pct = (savings_usd / if_all_escalated_cost) if if_all_escalated_cost > 0 else 0.0

    # Top triggers
    trigger_pipeline = [
        {"$match": {**match, "escalated": True}},
        {"$group": {"_id": "$trigger", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    triggers = await db.llm_routing_logs.aggregate(trigger_pipeline).to_list(20)

    return {
        "window_days": days,
        "practice_id": practice_id,
        "totals": {
            "turns": total_turns,
            "escalated_turns": escalated_turns,
            "escalation_rate": round(escalated_turns / total_turns, 4) if total_turns else 0,
            "input_tokens": sum(r["input_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
            "total_tokens": total_tokens,
        },
        "cost": {
            "actual_usd": round(actual_cost, 6),
            "if_all_escalated_usd": round(if_all_escalated_cost, 6),
            "savings_usd": round(savings_usd, 6),
            "savings_pct": round(savings_pct, 4),
            "baseline_provider": ESCALATION_PROVIDER,
            "baseline_model": ESCALATION_MODEL,
            "baseline_input_per_million": escalation_price.input_per_million,
            "baseline_output_per_million": escalation_price.output_per_million,
        },
        "by_model": by_model_cost,
        "top_triggers": [{"trigger": t["_id"], "count": t["count"]} for t in triggers],
        "cache": get_call_cache().stats(),
    }


@router.get("/logs")
async def llm_logs(
    current_user: dict = Depends(require_role("super_admin")),
    practice_id: str | None = None,
    limit: int = 50,
):
    db = get_db()
    q: dict = {}
    if practice_id:
        q["practice_id"] = practice_id
    cur = db.llm_routing_logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(min(limit, 500))
    return {"logs": await cur.to_list(limit)}
