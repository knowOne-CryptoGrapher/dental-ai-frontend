"""
JWT validation and reverse proxy logic.

Responsibilities:
1. Validate JWT and extract claims.
2. Resolve practice_id → home_region (cache → internal API → error).
3. Map home_region → target base URL.
4. Proxy request to regional backend.

PHI safety:
- Never log request bodies.
- Never log raw headers.
- Never log PHI fields.
- Log only: practice_id, home_region, target_url, status_code, latency_ms, request_id.
"""
import time
import uuid
import logging
import httpx
import jwt
from fastapi import Request, Response, HTTPException
from router_config import (
    JWT_SECRET, INTERNAL_API_KEY, REGION_URLS,
    PROXY_TIMEOUT_SECONDS,
)
from router_cache import practice_cache

logger = logging.getLogger(__name__)

# Headers that must not be forwarded (hop-by-hop)
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "host",  # httpx sets this correctly for the target
})

JWT_ALGORITHM = "HS256"


# ── JWT validation ────────────────────────────────────────────────────────────

def validate_jwt(token: str) -> dict:
    """
    Validate a JWT and return its claims.
    Raises HTTPException 401 on any validation failure.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    required = {"sub", "practice_id", "role", "exp"}
    missing = required - set(claims.keys())
    if missing:
        raise HTTPException(
            status_code=401,
            detail=f"Token missing required claims: {missing}",
        )
    return claims


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be Bearer token")
    return auth[len("Bearer "):]


# ── Practice region resolution ────────────────────────────────────────────────

async def resolve_practice_region(practice_id: str, client: httpx.AsyncClient) -> str:
    """
    Resolve a practice_id to its home_region.

    Checks the LRU cache first. On miss, calls the backend internal endpoint.
    Caches the result.

    Raises HTTPException 502 if the internal endpoint is unreachable.
    Raises HTTPException 404 if the practice is not found.
    """
    cached = practice_cache.get(practice_id)
    if cached:
        return cached

    # Use ca-west as the default target for internal lookups
    # (practices collection is shared on day one)
    target = REGION_URLS.get("ca-west", next(iter(REGION_URLS.values())))
    url = f"{target}/internal/practices/{practice_id}/meta"

    try:
        resp = await client.get(
            url,
            headers={"X-Internal-Key": INTERNAL_API_KEY},
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        logger.error("practice_meta_lookup_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="Failed to resolve practice region")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Practice not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Practice meta endpoint error")

    data = resp.json()
    home_region = data.get("home_region")
    if not home_region:
        raise HTTPException(status_code=502, detail="Practice has no home_region set")

    practice_cache.set(practice_id, home_region)
    return home_region


# ── Proxy ─────────────────────────────────────────────────────────────────────

async def proxy_request(request: Request, client: httpx.AsyncClient) -> Response:
    """
    Full request lifecycle:
    1. Validate JWT.
    2. Resolve practice region (cache or internal API).
    3. Map region → target URL.
    4. Proxy request to regional backend.
    5. Return response.
    """
    start = time.monotonic()
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())[:8]

    # 1. JWT validation
    token = _extract_token(request)
    claims = validate_jwt(token)
    practice_id = claims["practice_id"]

    # 2. Region resolution
    home_region = await resolve_practice_region(practice_id, client)

    # 3. Target URL
    base_url = REGION_URLS.get(home_region)
    if not base_url:
        raise HTTPException(status_code=500, detail=f"No backend configured for region: {home_region}")

    target_url = f"{base_url}{request.url.path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # 4. Build forwarded headers — strip hop-by-hop, add routing metadata
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    forward_headers["X-Request-Id"] = request_id
    forward_headers["X-Routed-By"] = "dental-ai-router"
    forward_headers["X-Forwarded-For"] = (
        request.headers.get("X-Forwarded-For")
        or (request.client.host if request.client else "unknown")
    )
    forward_headers["X-Forwarded-Proto"] = request.headers.get("X-Forwarded-Proto", "https")

    # 5. Proxy
    body = await request.body()
    try:
        backend_response = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
            timeout=PROXY_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        logger.error(
            "proxy_timeout",
            extra={
                "practice_id": practice_id,
                "home_region": home_region,
                "target_url": target_url,
                "request_id": request_id,
            },
        )
        raise HTTPException(status_code=504, detail="Backend request timed out")
    except httpx.RequestError as exc:
        logger.error(
            "proxy_error",
            extra={
                "practice_id": practice_id,
                "home_region": home_region,
                "target_url": target_url,
                "error": str(exc),
                "request_id": request_id,
            },
        )
        raise HTTPException(status_code=502, detail="Backend unreachable")

    latency_ms = round((time.monotonic() - start) * 1000)

    # Structured log — PHI-safe
    logger.info(
        "request_proxied",
        extra={
            "practice_id": practice_id,
            "home_region": home_region,
            "target_url": target_url,
            "status_code": backend_response.status_code,
            "latency_ms": latency_ms,
            "request_id": request_id,
        },
    )

    # Forward response headers (strip hop-by-hop)
    response_headers = {
        k: v for k, v in backend_response.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    response_headers["X-Request-Id"] = request_id

    return Response(
        content=backend_response.content,
        status_code=backend_response.status_code,
        headers=response_headers,
        media_type=backend_response.headers.get("content-type"),
    )
