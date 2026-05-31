"""
Region configuration for Canadian data residency.

Each practice is assigned a home_region at onboarding based on province.
All PHI for that practice is stored and processed in its assigned region.
"""

from enum import Enum


class CanadianRegion(str, Enum):
    CA_WEST = "ca-west"
    CA_EAST = "ca-east"


# Province → region mapping
PROVINCE_TO_REGION: dict[str, CanadianRegion] = {
    # Western Canada
    "BC": CanadianRegion.CA_WEST,
    "AB": CanadianRegion.CA_WEST,
    "SK": CanadianRegion.CA_WEST,
    "MB": CanadianRegion.CA_WEST,
    # Eastern Canada
    "ON": CanadianRegion.CA_EAST,
    "QC": CanadianRegion.CA_EAST,
    "NB": CanadianRegion.CA_EAST,
    "NS": CanadianRegion.CA_EAST,
    "PE": CanadianRegion.CA_EAST,
    "NL": CanadianRegion.CA_EAST,
    # Territories → nearest region
    "NT": CanadianRegion.CA_WEST,
    "YT": CanadianRegion.CA_WEST,
    "NU": CanadianRegion.CA_EAST,
}

# Compute region labels (for health endpoint and audit)
COMPUTE_REGION_LABELS: dict[CanadianRegion, str] = {
    CanadianRegion.CA_WEST: "northamerica-west2 (Calgary)",
    CanadianRegion.CA_EAST: "northamerica-northeast1 (Montreal)",
}

# DB cluster labels (for health endpoint and audit)
DB_CLUSTER_LABELS: dict[CanadianRegion, str] = {
    CanadianRegion.CA_WEST: "atlas-ca-west",
    CanadianRegion.CA_EAST: "atlas-ca-east",
}


def derive_region(province: str) -> CanadianRegion:
    """
    Derive home_region from a two-letter province code.
    Raises ValueError for unrecognised province codes.
    """
    code = province.strip().upper()
    if code not in PROVINCE_TO_REGION:
        raise ValueError(
            f"Unrecognised province code: '{province}'. "
            f"Valid codes: {sorted(PROVINCE_TO_REGION.keys())}"
        )
    return PROVINCE_TO_REGION[code]
