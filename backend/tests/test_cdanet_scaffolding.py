"""
Phase 7 CDAnet + ITRANS scaffolding tests.
These tests verify structural correctness only.
Full integration tests require:
  - CDAnet Software Vendor Agreement (CDA)
  - ITRANS credentials (TELUS Health)
  - Official CDA test vectors
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


# ── Module imports ────────────────────────────────────────────────────────

def test_cdanet_formatter_imports():
    from cdn.cdanet.formatter import CDAnetFormatter, CDANET_VERSION  # noqa: F401


def test_cdanet_validator_imports():
    from cdn.cdanet.validator import CDAnetValidator  # noqa: F401


def test_cdanet_message_type_imports():
    from cdn.cdanet.message_types.eligibility import EligibilityMessage  # noqa: F401
    from cdn.cdanet.message_types.claim_submission import ClaimSubmissionMessage  # noqa: F401
    from cdn.cdanet.message_types.claim_reversal import ClaimReversalMessage  # noqa: F401


def test_cdanet_test_vectors_imports():
    from cdn.cdanet.test_vectors.vectors import TEST_VECTORS  # noqa: F401


def test_itrans_envelope_imports():
    from cdn.itrans.envelope import ITRANSEnvelope  # noqa: F401


def test_itrans_crypto_imports():
    from cdn.itrans.crypto import ITRANSCrypto  # noqa: F401


def test_itrans_transport_imports():
    from cdn.itrans.transport import ITRANSTransport, ITRANS_TEST_ENDPOINT  # noqa: F401


def test_itrans_parser_imports():
    from cdn.itrans.parser import ITRANSParser  # noqa: F401


def test_claims_imports():
    from cdn.claims.submit_claim import ClaimSubmitter  # noqa: F401
    from cdn.claims.claim_status import ClaimStatusChecker  # noqa: F401
    from cdn.claims.claim_history import ClaimHistoryManager  # noqa: F401


# ── Class instantiation ───────────────────────────────────────────────────

def test_cdanet_formatter_instantiates():
    from cdn.cdanet.formatter import CDAnetFormatter
    CDAnetFormatter()


def test_cdanet_validator_instantiates():
    from cdn.cdanet.validator import CDAnetValidator
    CDAnetValidator()


def test_eligibility_message_instantiates():
    from cdn.cdanet.message_types.eligibility import EligibilityMessage
    EligibilityMessage()


def test_claim_submission_message_instantiates():
    from cdn.cdanet.message_types.claim_submission import ClaimSubmissionMessage
    ClaimSubmissionMessage()


def test_claim_reversal_message_instantiates():
    from cdn.cdanet.message_types.claim_reversal import ClaimReversalMessage
    ClaimReversalMessage()


def test_itrans_envelope_instantiates():
    from cdn.itrans.envelope import ITRANSEnvelope
    ITRANSEnvelope()


def test_itrans_crypto_instantiates():
    from cdn.itrans.crypto import ITRANSCrypto
    ITRANSCrypto()


def test_itrans_transport_instantiates():
    from cdn.itrans.transport import ITRANSTransport
    ITRANSTransport(test_mode=True)


def test_itrans_parser_instantiates():
    from cdn.itrans.parser import ITRANSParser
    ITRANSParser()


def test_claim_status_checker_instantiates():
    from cdn.claims.claim_status import ClaimStatusChecker
    ClaimStatusChecker()


def test_claim_history_manager_instantiates():
    from cdn.claims.claim_history import ClaimHistoryManager
    ClaimHistoryManager()


# ── ClaimSubmitter wires all six CDN dependencies ─────────────────────────

def test_claim_submitter_instantiates_with_all_dependencies():
    from cdn.claims.submit_claim import ClaimSubmitter
    from cdn.cdanet.formatter import CDAnetFormatter
    from cdn.cdanet.validator import CDAnetValidator
    from cdn.itrans.envelope import ITRANSEnvelope
    from cdn.itrans.crypto import ITRANSCrypto
    from cdn.itrans.transport import ITRANSTransport
    from cdn.itrans.parser import ITRANSParser

    s = ClaimSubmitter(test_mode=True)
    assert isinstance(s.formatter, CDAnetFormatter)
    assert isinstance(s.validator, CDAnetValidator)
    assert isinstance(s.envelope, ITRANSEnvelope)
    assert isinstance(s.crypto, ITRANSCrypto)
    assert isinstance(s.transport, ITRANSTransport)
    assert isinstance(s.parser, ITRANSParser)


# ── Sync stubs raise NotImplementedError ──────────────────────────────────

class TestCDAnetFormatterStubs:
    def test_format_eligibility_raises(self):
        from cdn.cdanet.formatter import CDAnetFormatter
        with pytest.raises(NotImplementedError):
            CDAnetFormatter().format_eligibility({})

    def test_format_claim_submission_raises(self):
        from cdn.cdanet.formatter import CDAnetFormatter
        with pytest.raises(NotImplementedError):
            CDAnetFormatter().format_claim_submission({})

    def test_format_claim_reversal_raises(self):
        from cdn.cdanet.formatter import CDAnetFormatter
        with pytest.raises(NotImplementedError):
            CDAnetFormatter().format_claim_reversal({})


class TestCDAnetValidatorStubs:
    def test_validate_raises(self):
        from cdn.cdanet.validator import CDAnetValidator
        with pytest.raises(NotImplementedError):
            CDAnetValidator().validate("", "01")

    def test_validate_carrier_id_raises(self):
        from cdn.cdanet.validator import CDAnetValidator
        with pytest.raises(NotImplementedError):
            CDAnetValidator().validate_carrier_id("123")


class TestEligibilityMessageStubs:
    def test_build_raises(self):
        from cdn.cdanet.message_types.eligibility import EligibilityMessage
        with pytest.raises(NotImplementedError):
            EligibilityMessage().build("patient-1", "carrier-1", "prov-1")

    def test_parse_response_raises(self):
        from cdn.cdanet.message_types.eligibility import EligibilityMessage
        with pytest.raises(NotImplementedError):
            EligibilityMessage().parse_response("")


class TestClaimSubmissionMessageStubs:
    def test_build_raises(self):
        from cdn.cdanet.message_types.claim_submission import ClaimSubmissionMessage
        with pytest.raises(NotImplementedError):
            ClaimSubmissionMessage().build({})

    def test_parse_response_raises(self):
        from cdn.cdanet.message_types.claim_submission import ClaimSubmissionMessage
        with pytest.raises(NotImplementedError):
            ClaimSubmissionMessage().parse_response("")


class TestClaimReversalMessageStubs:
    def test_build_raises(self):
        from cdn.cdanet.message_types.claim_reversal import ClaimReversalMessage
        with pytest.raises(NotImplementedError):
            ClaimReversalMessage().build("claim-1", "R01")

    def test_parse_response_raises(self):
        from cdn.cdanet.message_types.claim_reversal import ClaimReversalMessage
        with pytest.raises(NotImplementedError):
            ClaimReversalMessage().parse_response("")


class TestITRANSEnvelopeStubs:
    def test_wrap_raises(self):
        from cdn.itrans.envelope import ITRANSEnvelope
        with pytest.raises(NotImplementedError):
            ITRANSEnvelope().wrap("cdanet-message", "vendor-1")

    def test_unwrap_raises(self):
        from cdn.itrans.envelope import ITRANSEnvelope
        with pytest.raises(NotImplementedError):
            ITRANSEnvelope().unwrap("envelope-data")


class TestITRANSCryptoStubs:
    def test_encrypt_raises(self):
        from cdn.itrans.crypto import ITRANSCrypto
        with pytest.raises(NotImplementedError):
            ITRANSCrypto().encrypt("payload")

    def test_decrypt_raises(self):
        from cdn.itrans.crypto import ITRANSCrypto
        with pytest.raises(NotImplementedError):
            ITRANSCrypto().decrypt("encrypted")

    def test_sign_raises(self):
        from cdn.itrans.crypto import ITRANSCrypto
        with pytest.raises(NotImplementedError):
            ITRANSCrypto().sign("payload")

    def test_verify_raises(self):
        from cdn.itrans.crypto import ITRANSCrypto
        with pytest.raises(NotImplementedError):
            ITRANSCrypto().verify("payload", "sig")


class TestITRANSParserStubs:
    def test_parse_raises(self):
        from cdn.itrans.parser import ITRANSParser
        with pytest.raises(NotImplementedError):
            ITRANSParser().parse("")

    def test_extract_error_raises(self):
        from cdn.itrans.parser import ITRANSParser
        with pytest.raises(NotImplementedError):
            ITRANSParser().extract_error("")


# ── Async stubs raise NotImplementedError ─────────────────────────────────

class TestITRANSTransportAsyncStubs:
    def test_submit_raises(self):
        from cdn.itrans.transport import ITRANSTransport
        with pytest.raises(NotImplementedError):
            asyncio.run(ITRANSTransport(test_mode=True).submit("envelope"))

    def test_check_status_raises(self):
        from cdn.itrans.transport import ITRANSTransport
        with pytest.raises(NotImplementedError):
            asyncio.run(ITRANSTransport(test_mode=True).check_status("txn-1"))


class TestClaimStatusCheckerAsyncStub:
    def test_check_raises(self):
        from cdn.claims.claim_status import ClaimStatusChecker
        with pytest.raises(NotImplementedError):
            asyncio.run(ClaimStatusChecker().check("txn-1"))


class TestClaimSubmitterAsyncStub:
    def test_submit_raises(self):
        from cdn.claims.submit_claim import ClaimSubmitter
        with pytest.raises(NotImplementedError):
            asyncio.run(ClaimSubmitter(test_mode=True).submit({}, vendor_id="v1"))


# ── ClaimHistoryManager is implemented, not a stub ────────────────────────

def _make_mock_db(results: list) -> MagicMock:
    """Build a mock Motor DB where claims.find().sort().to_list() returns results."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value.to_list = AsyncMock(return_value=results)
    mock_db = MagicMock()
    mock_db.claims.find.return_value = mock_cursor
    return mock_db


class TestClaimHistoryManagerImplemented:
    def test_get_by_practice_returns_list(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([])
        result = asyncio.run(ClaimHistoryManager().get_by_practice("practice-1", mock_db))
        assert isinstance(result, list)

    def test_get_by_patient_returns_list(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([])
        result = asyncio.run(ClaimHistoryManager().get_by_patient("patient-1", "practice-1", mock_db))
        assert isinstance(result, list)

    def test_get_by_practice_scopes_query_to_practice_id(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([])
        asyncio.run(ClaimHistoryManager().get_by_practice("practice-abc", mock_db))
        mock_db.claims.find.assert_called_once_with({"practice_id": "practice-abc"})

    def test_get_by_patient_scopes_query_to_patient_and_practice(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([])
        asyncio.run(ClaimHistoryManager().get_by_patient("patient-xyz", "practice-abc", mock_db))
        mock_db.claims.find.assert_called_once_with({
            "patient_id": "patient-xyz",
            "practice_id": "practice-abc",
        })

    def test_get_by_practice_does_not_raise_not_implemented(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([{"id": "claim-1"}])
        # Should not raise NotImplementedError
        asyncio.run(ClaimHistoryManager().get_by_practice("practice-1", mock_db))

    def test_get_by_patient_does_not_raise_not_implemented(self):
        from cdn.claims.claim_history import ClaimHistoryManager
        mock_db = _make_mock_db([{"id": "claim-1"}])
        asyncio.run(ClaimHistoryManager().get_by_patient("patient-1", "practice-1", mock_db))


# ── TEST_VECTORS structure ────────────────────────────────────────────────

class TestTestVectors:
    def test_has_eligibility_key(self):
        from cdn.cdanet.test_vectors.vectors import TEST_VECTORS
        assert "eligibility" in TEST_VECTORS

    def test_has_claim_submission_key(self):
        from cdn.cdanet.test_vectors.vectors import TEST_VECTORS
        assert "claim_submission" in TEST_VECTORS

    def test_has_claim_reversal_key(self):
        from cdn.cdanet.test_vectors.vectors import TEST_VECTORS
        assert "claim_reversal" in TEST_VECTORS

    def test_values_are_lists(self):
        from cdn.cdanet.test_vectors.vectors import TEST_VECTORS
        for key, val in TEST_VECTORS.items():
            assert isinstance(val, list), f"TEST_VECTORS['{key}'] must be a list"

    def test_vectors_are_empty_pending_cda_agreement(self):
        """Vectors must not be populated until official CDA test data is received."""
        from cdn.cdanet.test_vectors.vectors import TEST_VECTORS
        for key, val in TEST_VECTORS.items():
            assert val == [], (
                f"TEST_VECTORS['{key}'] must remain empty until official CDA "
                "test vectors are received — do not fabricate test data"
            )


# ── Constants ─────────────────────────────────────────────────────────────

def test_cdanet_version_is_set():
    from cdn.cdanet.formatter import CDANET_VERSION
    assert isinstance(CDANET_VERSION, str) and CDANET_VERSION


def test_itrans_test_endpoint_is_non_empty_https_url():
    from cdn.itrans.transport import ITRANS_TEST_ENDPOINT
    assert isinstance(ITRANS_TEST_ENDPOINT, str)
    assert ITRANS_TEST_ENDPOINT, "ITRANS_TEST_ENDPOINT must not be empty"
    assert ITRANS_TEST_ENDPOINT.startswith("https://"), (
        "ITRANS_TEST_ENDPOINT must use HTTPS"
    )


# ── Transaction codes ─────────────────────────────────────────────────────

def test_transaction_codes_match_cdanet_spec():
    from cdn.cdanet.message_types.eligibility import EligibilityMessage
    from cdn.cdanet.message_types.claim_submission import ClaimSubmissionMessage
    from cdn.cdanet.message_types.claim_reversal import ClaimReversalMessage
    assert EligibilityMessage.TRANSACTION_CODE == "01"
    assert ClaimSubmissionMessage.TRANSACTION_CODE == "11"
    assert ClaimReversalMessage.TRANSACTION_CODE == "21"


# ── ITRANSTransport test_mode routing ─────────────────────────────────────

def test_itrans_transport_test_mode_uses_test_endpoint():
    from cdn.itrans.transport import ITRANSTransport, ITRANS_TEST_ENDPOINT
    t = ITRANSTransport(test_mode=True)
    assert t.test_mode is True
    assert t.endpoint == ITRANS_TEST_ENDPOINT


def test_itrans_transport_prod_mode_endpoint_is_none_until_certified():
    from cdn.itrans.transport import ITRANSTransport, ITRANS_PROD_ENDPOINT
    assert ITRANS_PROD_ENDPOINT is None, (
        "ITRANS_PROD_ENDPOINT must remain None until TELUS Health certification is complete"
    )
    t = ITRANSTransport(test_mode=False)
    assert t.endpoint is None
