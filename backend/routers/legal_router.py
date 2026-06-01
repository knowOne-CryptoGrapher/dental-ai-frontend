from fastapi import APIRouter
from config import TERMS_VERSION, PRIVACY_POLICY_VERSION

router = APIRouter(tags=["legal"])


@router.get("/legal/versions")
async def get_legal_versions():
    """
    Return current legal document versions.
    Frontend uses this to validate version sync before registration.
    No authentication required — public endpoint.
    """
    return {
        "terms_version":   TERMS_VERSION,
        "privacy_version": PRIVACY_POLICY_VERSION,
    }
