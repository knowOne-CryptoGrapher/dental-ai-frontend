"""
ITRANS transmission layer.
Sends encrypted envelopes to the ITRANS network endpoint.

TODO: Requires TELUS Health ITRANS endpoint URL and
network credentials before production use.
"""

# TODO: Replace with real ITRANS endpoint when credentials arrive
ITRANS_ENDPOINT_STUB = "https://itrans-stub.dentalai.internal/submit"
ITRANS_TEST_ENDPOINT = "https://itrans-test.telushealth.com/submit"
ITRANS_PROD_ENDPOINT = None  # TODO: Set when certified


class ITRANSTransport:
    def __init__(self, test_mode: bool = True):
        self.test_mode = test_mode
        self.endpoint = (ITRANS_TEST_ENDPOINT
                         if test_mode else ITRANS_PROD_ENDPOINT)

    async def submit(self, encrypted_envelope: str) -> str:
        # TODO: Implement HTTP transmission to ITRANS endpoint
        raise NotImplementedError("ITRANS credentials required")

    async def check_status(self,
                           transaction_id: str) -> str:
        # TODO: Implement status check against ITRANS
        raise NotImplementedError("ITRANS credentials required")
