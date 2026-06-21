"""
Unit tests for the content-detection value validators. Uses well-known *valid* test
values (with correct checksums) and deliberately-broken ones, so we exercise the actual
checksum logic, not just regex shape.
"""

from backend.core.validators import (
    best_value_entity, confidence_from_match, is_aba_routing, is_credit_card, is_dea,
    is_email, is_iban, is_ip_address, is_npi, is_ssn, luhn_ok,
)
from backend.models.schemas import PiiEntityType


class TestChecksums:
    def test_luhn(self):
        assert luhn_ok("4242424242424242")        # valid Visa test number
        assert not luhn_ok("4242424242424241")

    def test_credit_card(self):
        assert is_credit_card("4111 1111 1111 1111")
        assert is_credit_card("4242-4242-4242-4242")
        assert not is_credit_card("1234567812345678")   # fails Luhn
        assert not is_credit_card("4111")                # too short

    def test_ssn_structural(self):
        assert is_ssn("123-45-6789")
        assert is_ssn("123456789")
        assert not is_ssn("000-45-6789")   # invalid area
        assert not is_ssn("666-45-6789")   # invalid area
        assert not is_ssn("900-45-6789")   # 9xx area
        assert not is_ssn("123-00-6789")   # invalid group
        assert not is_ssn("123-45-0000")   # invalid serial

    def test_iban_mod97(self):
        assert is_iban("GB82 WEST 1234 5698 7654 32")    # canonical valid IBAN
        assert not is_iban("GB00WEST12345698765432")

    def test_aba_routing(self):
        assert is_aba_routing("021000021")   # valid ABA (JPMorgan Chase)
        assert not is_aba_routing("021000020")

    def test_npi(self):
        assert is_npi("1234567893")          # valid NPI check digit
        assert not is_npi("1234567890")

    def test_dea(self):
        assert is_dea("BB1388568")           # valid DEA check digit
        assert not is_dea("BB1388569")

    def test_email_and_ip(self):
        assert is_email("jane.doe@example.com")
        assert not is_email("jane.doe@com")
        assert is_ip_address("192.168.1.10")
        assert is_ip_address("::1")
        assert not is_ip_address("999.1.1.1")


class TestAggregation:
    def test_cc_column_named_anything_is_detected(self):
        # A column called "CC" full of valid cards — name is irrelevant to detection.
        values = ["4111111111111111", "4242424242424242", "5555555555554444", "not-a-card"]
        result = best_value_entity(values)
        assert result is not None
        entity, _mask, frac, strong = result
        assert entity == PiiEntityType.CREDIT_CARD
        assert strong is True
        assert frac >= 0.7

    def test_non_pii_column_returns_none(self):
        assert best_value_entity(["apple", "banana", "cherry", "date"]) is None

    def test_empty_returns_none(self):
        assert best_value_entity([None, "", "  "]) is None

    def test_confidence_strong_beats_weak(self):
        assert confidence_from_match(1.0, strong=True) > confidence_from_match(1.0, strong=False)
