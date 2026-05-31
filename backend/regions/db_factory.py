"""
Region-aware MongoDB client factory.

Rules:
- Never access MongoDB directly; always go through get_db_for_practice().
- The factory caches Motor clients per cluster URI (one client per Atlas cluster).
- PHI must never cross regional boundaries — if a practice's home_region is
  ca-west, all its data reads and writes use the ca-west Atlas cluster.
- On day one, both clusters may point to the same URI. The abstraction
  supports splitting them later without any code changes.
"""
import os
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from regions.region_config import CanadianRegion

logger = logging.getLogger(__name__)

# Module-level client cache — one Motor client per cluster URI
_clients: dict[str, object] = {}


def _get_client(uri: str):
    """Return a cached Motor client for the given URI."""
    from motor.motor_asyncio import AsyncIOMotorClient
    if uri not in _clients:
        _clients[uri] = AsyncIOMotorClient(uri)
        logger.info("db_client_created", extra={"cluster": uri[:40] + "..."})
    return _clients[uri]


def _get_uri_for_region(region: CanadianRegion) -> str:
    """
    Return the MongoDB URI for the given region.

    On day one both env vars may point to the same cluster.
    When you split into two clusters, update the env vars in Secret Manager —
    no code changes needed.
    """
    if region == CanadianRegion.CA_WEST:
        uri = os.getenv("CA_WEST_DB_URI") or os.getenv("MONGODB_URI")
    else:
        uri = os.getenv("CA_EAST_DB_URI") or os.getenv("MONGODB_URI")

    if not uri:
        raise RuntimeError(
            f"No MongoDB URI configured for region {region.value}. "
            "Set CA_WEST_DB_URI and CA_EAST_DB_URI in Secret Manager."
        )
    return uri


async def get_db_for_region(region: CanadianRegion) -> AsyncIOMotorDatabase:
    """Return the Motor database handle for the given region."""
    db_name = os.getenv("DATABASE_NAME", "dental_ai")
    uri = _get_uri_for_region(region)
    client = _get_client(uri)
    return client[db_name]


async def get_db_for_practice(practice_id: str, db=None) -> AsyncIOMotorDatabase:
    """
    Look up a practice's home_region and return its regional DB handle.

    Args:
        practice_id: The practice's ID string.
        db: A DB handle to use for the practice lookup (the global/default handle).
            If None, falls back to the default MONGODB_URI via ca-west client.

    Raises:
        ValueError: If the practice is not found or has an invalid home_region.
    """
    # Use provided db or fall back to default cluster for the lookup
    if db is None:
        db = await get_db_for_region(CanadianRegion.CA_WEST)

    practice = await db.practices.find_one(
        {"id": practice_id}, {"home_region": 1, "_id": 0}
    )
    if not practice:
        raise ValueError(f"Practice not found: {practice_id}")

    home_region_str = practice.get("home_region")
    if not home_region_str:
        # Practices created before region metadata was added default to ca-west
        logger.warning(
            "practice_missing_home_region",
            extra={"practice_id": practice_id},
        )
        return await get_db_for_region(CanadianRegion.CA_WEST)

    try:
        region = CanadianRegion(home_region_str)
    except ValueError:
        logger.error(
            "practice_invalid_home_region",
            extra={"practice_id": practice_id, "home_region": home_region_str},
        )
        raise ValueError(f"Invalid home_region '{home_region_str}' for practice {practice_id}")

    return await get_db_for_region(region)


async def close_all_clients():
    """Close all cached Motor clients. Call on application shutdown."""
    for client in _clients.values():
        client.close()
    _clients.clear()
