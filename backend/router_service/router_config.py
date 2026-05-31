"""
Router configuration loaded from environment variables.

All sensitive values come from Secret Manager via service.yaml secretKeyRef.
Non-sensitive values are plain env vars.
"""
import os

# ── Secrets (from Secret Manager) ────────────────────────────────────────────
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

# ── Regional backend base URLs ────────────────────────────────────────────────
API_WEST_BASE_URL: str = os.getenv("API_WEST_BASE_URL", "https://api-west.dentalai.ca")
API_EAST_BASE_URL: str = os.getenv("API_EAST_BASE_URL", "https://api-east.dentalai.ca")

REGION_URLS: dict[str, str] = {
    "ca-west": API_WEST_BASE_URL,
    "ca-east": API_EAST_BASE_URL,
}

# ── Cache config ──────────────────────────────────────────────────────────────
# TTL=0 disables caching (useful for staging/debug)
PRACTICE_CACHE_TTL_SECONDS: int = int(os.getenv("PRACTICE_CACHE_TTL_SECONDS", "30"))

# ── Proxy config ──────────────────────────────────────────────────────────────
PROXY_TIMEOUT_SECONDS: int = int(os.getenv("PROXY_TIMEOUT_SECONDS", "30"))

# ── Router metadata ───────────────────────────────────────────────────────────
ROUTER_ENV: str = os.getenv("ROUTER_ENV", "production")


# ── Validation on startup ─────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """Return list of missing required config values."""
    errors = []
    if not JWT_SECRET:
        errors.append("JWT_SECRET is not set")
    if not INTERNAL_API_KEY:
        errors.append("INTERNAL_API_KEY is not set")
    return errors
