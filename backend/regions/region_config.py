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

# Compute region labels (for health endpoint and audit).
# Both keys currently point at the same real region: as of 2026-09-09, all
# compute runs in northamerica-northeast1 (Montreal) -- the ca-west/ca-east
# split described by this module is a future plan, not yet physically
# implemented. "northamerica-west2 (Calgary)" was never a real GCP region;
# see backend/HANDOFF.md's Cloud Run Region Migration section.
COMPUTE_REGION_LABELS: dict[CanadianRegion, str] = {
    CanadianRegion.CA_WEST: "northamerica-northeast1 (Montreal)",
    CanadianRegion.CA_EAST: "northamerica-northeast1 (Montreal)",
}

# DB cluster labels (for health endpoint and audit).
# Both keys currently point at the same real, single Atlas cluster: as of
# 2026-09-11, confirmed live in northamerica-northeast1 (Montreal) via direct
# hello()/replSetGetConfig() query against the cluster (Atlas's own reported
# region tag: NORTH_AMERICA_NORTHEAST_1). "atlas-ca-west"/"atlas-ca-east"
# were never real cluster names -- there has only ever been one cluster.
DB_CLUSTER_LABELS: dict[CanadianRegion, str] = {
    CanadianRegion.CA_WEST: "northamerica-northeast1 (Montreal), Atlas region NORTH_AMERICA_NORTHEAST_1",
    CanadianRegion.CA_EAST: "northamerica-northeast1 (Montreal), Atlas region NORTH_AMERICA_NORTHEAST_1",
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
