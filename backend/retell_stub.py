"""
Retell AI SDK stub - provides compatible interface when retell-ai package is not available.
This allows the server to start and run without the actual Retell SDK.
Real Retell functionality requires the actual SDK and API key.
"""

import logging

logger = logging.getLogger(__name__)


class CallResponse:
    def __init__(self, call_id="stub_call"):
        self.call_id = call_id


class Call:
    def register_phone_call(self, **kwargs):
        logger.warning("Retell SDK stub: register_phone_call called (no-op)")
        return CallResponse()


class Retell:
    def __init__(self, api_key=None, http_client=None):
        self.api_key = api_key
        self.call = Call()
        if not api_key:
            logger.warning("Retell initialized without API key - using stub mode")

    def verify(self, body, api_key, signature):
        """Stub verification - always passes in development"""
        logger.warning("Retell SDK stub: verify called (no-op)")
        return True
