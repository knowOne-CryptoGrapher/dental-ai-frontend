"""
Application-level constants.

Bump TERMS_VERSION or PRIVACY_POLICY_VERSION whenever the legal documents
change. The onboarding endpoint rejects registrations that submit an
outdated version — callers must refresh and re-accept.
"""

TERMS_VERSION: str = "1.1"          # Bumped from 1.0 — AI disclaimers added
PRIVACY_POLICY_VERSION: str = "1.0"
