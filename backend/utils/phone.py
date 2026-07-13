"""
Phone number normalization for Dental AI.

All patient phone numbers are normalized to E.164 format before storage
and lookup. This ensures consistent deduplication regardless of how
Retell, the LLM, or staff format the number.
"""
import re

# Default country code for Canadian dental clinics
DEFAULT_COUNTRY_CODE = "1"


def normalize_phone(raw: str | None) -> str | None:
    """
    Normalize a phone number to E.164 format (+1XXXXXXXXXX for North American numbers).

    Returns None if the input is missing, "unknown", or cannot be normalized to
    a valid 10-digit North American number.

    Examples:
        "+1 (604) 555-0100"  -> "+16045550100"
        "604-555-0100"       -> "+16045550100"
        "(604) 555.0100"     -> "+16045550100"
        "+16045550100"       -> "+16045550100"
        "unknown"            -> None
        ""                   -> None
        None                 -> None
    """
    if not raw or str(raw).strip().lower() in ("unknown", "none", "null", ""):
        return None

    # Strip everything except digits and leading +
    digits_only = re.sub(r"[^\d+]", "", str(raw).strip())

    # Remove leading +
    if digits_only.startswith("+"):
        digits_only = digits_only[1:]

    # Strip leading country code if present (1 for North America)
    if digits_only.startswith("1") and len(digits_only) == 11:
        digits_only = digits_only[1:]

    # Must be exactly 10 digits at this point
    if len(digits_only) != 10 or not digits_only.isdigit():
        return None

    return f"+{DEFAULT_COUNTRY_CODE}{digits_only}"


def phones_match(a: str | None, b: str | None) -> bool:
    """
    Compare two phone numbers after normalization.
    Returns True if both normalize to the same E.164 number.
    """
    na, nb = normalize_phone(a), normalize_phone(b)
    if na is None or nb is None:
        return False
    return na == nb
