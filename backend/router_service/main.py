"""
Dental AI Global Router Service

Single front door for all API traffic. Routes requests to regional backends
based on practice home_region. Validates JWT on every request.

Logs: practice_id, home_region, target_url, status_code, latency_ms.
Never logs: PHI, request bodies, raw headers.
"""
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from pythonjsonlogger import jsonlogger
from router_config import PRACTICE_CACHE_TTL_SECONDS, ROUTER_ENV, validate_config
from router_proxy import proxy_request
from router_cache import practice_cache

# ── Structured JSON logging ───────────────────────────────────────────────────
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s"
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client

    # Validate config on startup — fail fast if secrets are missing
    errors = validate_config()
    if errors:
        logger.error("router_config_invalid", extra={"errors": errors})
        raise RuntimeError(f"Router config invalid: {errors}")

    _http_client = httpx.AsyncClient()
    logger.info("router_started", extra={
        "environment": ROUTER_ENV,
        "cache_ttl": PRACTICE_CACHE_TTL_SECONDS,
    })
    yield
    # Shutdown
    if _http_client:
        await _http_client.aclose()
    practice_cache.clear()
    logger.info("router_shutdown")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dental AI Router",
    version="1.0.0",
    docs_url=None,    # Disable docs on the router — no need to expose internally
    redoc_url=None,
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health/ready")
async def health_ready():
    return {
        "status": "ready",
        "router_region": "global",
        "environment": ROUTER_ENV,
        "targets": ["ca-west", "ca-east"],
        "cache_ttl": PRACTICE_CACHE_TTL_SECONDS,
        "cache_size": practice_cache.size,
    }


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


# ── Catch-all proxy ───────────────────────────────────────────────────────────
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def catch_all(request: Request):
    """Route all non-health requests to the appropriate regional backend."""
    if _http_client is None:
        raise HTTPException(status_code=503, detail="Router not ready")
    return await proxy_request(request, _http_client)
