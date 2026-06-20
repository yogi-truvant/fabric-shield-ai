"""
Unit tests for the PII detection engine.
Tests rule-based, ML-based, and merged detection paths.
"""

from backend.core.pii_engine import (
    _apply_rules,
    _merge_results,
    analyze_column,
)
from backend.models.schemas import DetectionSource, MaskType, PiiEntityType


class TestRuleBasedDetection:
    def test_ssn_column_name(self):
        result = _apply_rules("patient_ssn")
        assert result is not None
        entity, conf, mask = result
        assert entity == PiiEntityType.SSN
        assert conf >= 0.85
        assert mask == MaskType.partial

    def test_email_column_name(self):
        result = _apply_rules("email_address")
        assert result is not None
        entity, conf, mask = result
        assert entity == PiiEntityType.EMAIL
        assert mask == MaskType.email

    def test_dob_column_name(self):
        result = _apply_rules("date_of_birth")
        assert result is not None
        entity, conf, _ = result
        assert entity == PiiEntityType.DATE_OF_BIRTH

    def test_mrn_column_name(self):
        result = _apply_rules("mrn")
        assert result is not None
        entity, _, _ = result
        assert entity == PiiEntityType.MEDICAL_RECORD

    def test_non_pii_column(self):
        result = _apply_rules("product_description")
        assert result is None

    def test_credit_card(self):
        result = _apply_rules("cc_number")
        assert result is not None
        entity, _, _ = result
        assert entity == PiiEntityType.CREDIT_CARD

    def test_case_insensitive(self):
        result = _apply_rules("EMAIL_ADDR")
        assert result is not None


class TestMergeResults:
    def test_both_agree_boosts_confidence(self):
        rule = (PiiEntityType.EMAIL, 0.75, MaskType.email)
        ml = (PiiEntityType.EMAIL, 0.80)
        result = _merge_results(rule, ml, 0.5)
        assert result is not None
        _, conf, source, _ = result
        assert source == DetectionSource.both
        assert conf >= 0.90  # boosted

    def test_rule_only_above_threshold(self):
        rule = (PiiEntityType.SSN, 0.90, MaskType.partial)
        result = _merge_results(rule, None, 0.6)
        assert result is not None
        _, _, source, _ = result
        assert source == DetectionSource.rule

    def test_rule_only_below_threshold_excluded(self):
        rule = (PiiEntityType.CUSTOM, 0.40, MaskType.default)
        result = _merge_results(rule, None, 0.6)
        assert result is None

    def test_disagreement_takes_higher_confidence(self):
        rule = (PiiEntityType.EMAIL, 0.75, MaskType.email)
        ml = (PiiEntityType.PERSON_NAME, 0.85)
        result = _merge_results(rule, ml, 0.5)
        assert result is not None
        entity, conf, source, _ = result
        assert entity == PiiEntityType.PERSON_NAME
        assert source == DetectionSource.ml
        assert conf == 0.85


class TestAnalyzeColumn:
    """Detection is METADATA-ONLY: name + data type. No row samples are ever passed."""

    def test_ssn_column_flagged_by_name(self):
        result = analyze_column(
            schema_name="dbo",
            table_name="patients",
            column_name="ssn",
            data_type="varchar",
        )
        assert result is not None
        assert result.entity_type == PiiEntityType.SSN
        assert result.confidence >= 0.8
        assert result.detection_source == DetectionSource.rule

    def test_result_carries_no_data_sample(self):
        # The result model must not expose any field derived from real row data.
        result = analyze_column("dbo", "patients", "ssn", "varchar")
        assert result is not None
        assert not hasattr(result, "sample_value_hint")

    def test_image_column_skipped(self):
        result = analyze_column(
            schema_name="dbo",
            table_name="documents",
            column_name="profile_photo",
            data_type="image",
        )
        assert result is None

    def test_non_pii_column_not_flagged(self):
        result = analyze_column(
            schema_name="dbo",
            table_name="products",
            column_name="product_name",
            data_type="varchar",
        )
        assert result is None
