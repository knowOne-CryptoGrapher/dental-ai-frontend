"""
Rate limiter for auth endpoints.

Uses slowapi (FastAPI-compatible wrapper around limits).  The key function
uses X-Forwarded-For so limits apply to the real client IP behind Cloud Run's
load balancer, not the internal proxy address.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    """Return the originating client IP, honouring X-Forwarded-For."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For may be a comma-separated list; first value is the client
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request) or "unknown"


limiter = Limiter(key_func=_get_real_ip)
