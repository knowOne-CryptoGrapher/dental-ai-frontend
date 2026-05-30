"""
PHI redaction helpers.

Use redact_phi() before logging any dict that may contain patient data.
Use mask_phone() for inline log messages that reference a phone number.

Fields treated as PHI (case-insensitive key match):
  - name / patient_name / first_name / last_name / full_name / customer_name
  - phone / patient_phone / phone_number / from_number / to_number
  - email / patient_email
  - date_of_birth / dob
  - insurance_policy_number / policy_number / insurance_group_number / group_number
  - health_card_number
  - emergency_contact_name / emergency_contact_phone
  - transcript   -- AI call transcripts always contain PHI
  - notes        -- clinical free-text
  - address / street
"""
import re
from typing import Any

_PHI_FIELDS = frozenset({
    "name", "patient_name", "first_name", "last_name", "full_name", "customer_name",
    "phone", "patient_phone", "phone_number", "from_number", "to_number",
    "email", "patient_email",
    "date_of_birth", "dob",
    "insurance_policy_number", "policy_number",
    "insurance_group_number", "group_number",
    "health_card_number",
    "emergency_contact_name", "emergency_contact_phone",
    "transcript",
    "notes",
    "address", "street",
})

_MASK = "[REDACTED]"
_MAX_DEPTH = 6


def redact_phi(data: Any, _depth: int = 0) -> Any:
    """
    Return a deep copy of *data* with all PHI field values replaced by [REDACTED].
    Works recursively on dicts and lists; non-container values are returned as-is.
    """
    if _depth > _MAX_DEPTH:
        return data
    if isinstance(data, dict):
        return {
            k: (_MASK if k.lower() in _PHI_FIELDS else redact_phi(v, _depth + 1))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact_phi(item, _depth + 1) for item in data]
    return data


def mask_phone(phone: str) -> str:
    """Return a masked phone number showing only the last 4 digits."""
    if not phone:
        return "[no-phone]"
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "***"
