"""
ITRANS response parser.
Parses raw ITRANS responses into structured claim results.

TODO: Requires ITRANS response format specification.
"""


class ITRANSParser:
    def parse(self, raw_response: str) -> dict:
        # TODO: Implement per ITRANS response spec
        raise NotImplementedError("ITRANS spec required")

    def extract_error(self, raw_response: str) -> dict:
        # TODO: Extract error codes from ITRANS response
        raise NotImplementedError("ITRANS spec required")
