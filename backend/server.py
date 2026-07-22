import os
import time
import uuid
import json
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

# -------------------------------------------------------------------
# Structured logging — must be configured before any other imports
# that call logging.getLogger().
# -------------------------------------------------------------------
from utils.logging_config import configure_logging
from utils.rate_limiter import limiter
configure_logging()

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Load Environment Variables
# -------------------------------------------------------------------
load_dotenv(".env", override=True)

# -------------------------------------------------------------------
# Router Imports
# -------------------------------------------------------------------
from routers.auth_router import router as auth_router
from routers.legal_router import router as legal_router
from routers.practice_router import internal_router
from routers.billing_router import router as billing_router
from routers.stripe_webhook_router import router as stripe_webhook_router
# Deprecated (superseded by /api/auth/signup + POST /api/practices). Kept importable, not mounted.
# from routers.onboarding_router import router as onboarding_router
from routers.llm_router_api import router as llm_router

from routers.analytics_router import router as analytics_router
from routers.appointment_router import router as appointment_router
from routers.calllog_router import router as calllog_router
from routers.insurance_router import router as insurance_router
from routers.claims_router import router as claims_router
from routers.patient_router import router as patient_router
from routers.practice_router import router as practice_router
from routers.practice_config_router import router as practice_config_router
from routers.superadmin_router import router as superadmin_router
from routers.retell_api_router import router as retell_api_router
from routers.retell_webhook_router_v2 import router as retell_webhook_router_v2
from routers.retell_context_router import router as retell_context_router
from routers.pending_actions_router import router as pending_actions_router
from routers.ai_safety_router import router as ai_safety_router
from routers.invite_router import router as invite_router
from routers.knowledge_router import router as knowledge_router
from routers.routing_rules_router import router as routing_rules_router
from routers.ses_webhook_router import router as ses_webhook_router
from routers.sales_router import router as sales_router

# -------------------------------------------------------------------
# LLM Manager Initialization
# -------------------------------------------------------------------
from services.llm_manager import LLMManager
from auth import set_db

def load_json_file(path: str):
    if not path or not os.path.exists(path):
        logger.warning("JSON config file not found", extra={"path": path})
        return {}
    with open(path, "r") as f:
        return json.load(f)

LLM_RULES   = load_json_file(os.getenv("LLM_RULES_PATH"))
LLM_PRICING = load_json_file(os.getenv("LLM_PRICING_PATH"))

llm_manager = LLMManager(
    default_provider=os.getenv("LLM_DEFAULT_PROVIDER"),
    default_model=os.getenv("LLM_DEFAULT_MODEL"),
    escalation_provider=os.getenv("LLM_ESCALATION_PROVIDER"),
    escalation_model=os.getenv("LLM_ESCALATION_MODEL"),
    rules=LLM_RULES,
    pricing=LLM_PRICING,
)

# -------------------------------------------------------------------
# App Initialization
# -------------------------------------------------------------------
app = FastAPI(
    title="Dental AI Backend",
    version="2.0.0",
    description="Backend API for FrontDesk Dental AI",
)

app.state.limiter = limiter


async def _on_rate_limit_exceeded(request: Request, exc: RateLimitExceeded):
    from auth import log_security_event
    from utils.rate_limiter import _get_real_ip
    ip = _get_real_ip(request)
    logger.warning(
        "rate_limit_exceeded",
        extra={"ip": ip, "path": request.url.path, "limit": str(exc.detail)},
    )
    # Fire-and-forget security event — don't let DB errors break the 429 response
    import asyncio
    asyncio.ensure_future(
        log_security_event(
            event_type="rate_limit_exceeded",
            ip_address=ip,
            details={"path": request.url.path, "limit": str(exc.detail)},
        )
    )
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests", "detail": str(exc.detail)},
        headers={"Retry-After": str(retry_after)},
    )


app.add_exception_handler(RateLimitExceeded, _on_rate_limit_exceeded)


@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError):
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    logger.warning(
        "request_validation_error",
        extra={"path": request.url.path, "method": request.method, "errors": errors},
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# -------------------------------------------------------------------
# Request Logging Middleware
# -------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Assigns a short request_id to every inbound request, logs method/path/
    status/latency as structured JSON, and echoes the ID in the response
    header so it can be correlated in Cloud Logging.

    PHI is never logged here — only path, method, status, and latency.
    """

    _SKIP_PATHS = frozenset({"/health/live", "/health/ready", "/health"})

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            if request.url.path not in self._SKIP_PATHS:
                logger.error(
                    "unhandled_request_error",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(exc),
                    },
                    exc_info=True,
                )
            raise

        latency_ms = round((time.monotonic() - start) * 1000, 2)

        if request.url.path not in self._SKIP_PATHS:
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                },
            )

        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestLoggingMiddleware)

# -------------------------------------------------------------------
# CORS Configuration
# -------------------------------------------------------------------

_DEFAULT_ORIGINS = [
    "https://frontdeskdentalai.com",
    "https://www.frontdeskdentalai.com",
    "https://dental-ai-frontend.pages.dev",
]

_cors_env = os.getenv("CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else _DEFAULT_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Startup / Shutdown Events
# -------------------------------------------------------------------

_mongo_client: AsyncIOMotorClient | None = None


@app.on_event("startup")
async def startup_event():
    global _mongo_client

    build_id  = os.getenv("BUILD_ID", "dev")
    env_label = os.getenv("ENV", "production")
    logger.info(
        "server_starting",
        extra={"build_id": build_id, "env": env_label, "version": "2.0.0"},
    )

    mongo_uri = os.getenv("MONGODB_URI")
    db_name   = os.getenv("DATABASE_NAME", "dental_ai")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI environment variable is not set")

    _mongo_client = AsyncIOMotorClient(
        mongo_uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        maxPoolSize=20,
        minPoolSize=2,
    )
    set_db(_mongo_client[db_name])
    logger.info("mongodb_connected", extra={"db_name": db_name})

    llm_manager.initialize()
    logger.info("llm_router_ready", extra={"status": llm_manager.status()})


@app.on_event("shutdown")
async def shutdown_event():
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
    from regions.db_factory import close_all_clients
    await close_all_clients()
    logger.info("server_shutdown")

# -------------------------------------------------------------------
# Health Endpoints
# -------------------------------------------------------------------


@app.get("/health/live", tags=["health"])
async def health_live():
    """Liveness: returns 200 if the process is running."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready():
    """
    Readiness: verifies MongoDB connectivity before accepting traffic.
    Cloud Run uses this to gate traffic during rolling deployments.
    """
    if _mongo_client is None:
        raise HTTPException(status_code=503, detail="DB client not initialised")
    try:
        await _mongo_client.admin.command("ping")
    except Exception as exc:
        logger.error("health_ready_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="DB unavailable")
    return {
        "status": "ready",
        "db": "ok",
        "compute_region": os.getenv("COMPUTE_REGION", "unknown"),
        "db_region": os.getenv("DB_REGION", "unknown"),
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Legacy health endpoint — preserved for backward compatibility."""
    return {"status": "ok", "llm_router": llm_manager.status()}


# -------------------------------------------------------------------
# Include Routers
# -------------------------------------------------------------------

app.include_router(legal_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(stripe_webhook_router)
# Deprecated (superseded by /api/auth/signup + POST /api/practices) — see import comment above.
# app.include_router(onboarding_router)
app.include_router(llm_router)

app.include_router(analytics_router)
app.include_router(appointment_router)
app.include_router(calllog_router)
app.include_router(insurance_router)
app.include_router(claims_router, prefix="/api/claims", tags=["claims"])
app.include_router(patient_router)
app.include_router(practice_router)
app.include_router(practice_config_router)
app.include_router(superadmin_router)
app.include_router(retell_api_router)
app.include_router(retell_webhook_router_v2)
app.include_router(retell_context_router)
app.include_router(internal_router)
app.include_router(pending_actions_router)
app.include_router(ai_safety_router)
app.include_router(invite_router)
app.include_router(knowledge_router)
app.include_router(routing_rules_router)
app.include_router(ses_webhook_router)
app.include_router(sales_router)

from routers.admin_email_router import router as admin_email_router
app.include_router(admin_email_router)

# -------------------------------------------------------------------
# Global Error Handler
# -------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled_exception",
        extra={"request_id": request_id, "path": request.url.path, "error": str(exc)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
