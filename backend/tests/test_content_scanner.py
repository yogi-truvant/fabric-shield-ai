"""
Unit tests for the content scanner: name-agnostic detection + the name/content merge.
NER (Tier 2) is forced off here so tests are fast and model-independent; graceful
degradation (no model) is itself the path under test.
"""

import pytest

from backend.core import content_scanner
from backend.core.content_scanner import merge_detections, scan_table_values
from backend.models.schemas import (
    DatabaseType, DetectionSource, MaskType, PiiColumnResult, PiiEntityType,
)


@pytest.fixture(autouse=True)
def _disable_ner(monkeypatch):
    # Force the NER tier unavailable so only validators run (deterministic tests).
    monkeypatch.setattr(content_scanner, "_get_nlp", lambda: None)


def _result(col, entity, conf, source):
    return PiiColumnResult(
        database_type=DatabaseType.azure_sql, schema_name="dbo", table_name="t",
        column_name=col, data_type="varchar", entity_type=entity, confidence=conf,
        detection_source=source, recommended_mask=MaskType.default,
    )


def test_detects_cc_from_values_regardless_of_header():
    values_by_column = {
        "CC": ["4111111111111111", "4242424242424242", "5555555555554444"],
        "note": ["hello", "world", "foo"],
    }
    out = scan_table_values("dbo", "payments", "azure_sql", values_by_column, {"CC": "varchar", "note": "varchar"})
    cc = [r for r in out if r.column_name == "CC"]
    assert cc and cc[0].entity_type == PiiEntityType.CREDIT_CARD
    assert cc[0].detection_source == DetectionSource.content
    assert cc[0].sample_match_pct >= 0.7
    assert all(r.column_name != "note" for r in out)


def test_merge_content_only_kept():
    merged = merge_detections([], [_result("CC", PiiEntityType.CREDIT_CARD, 0.95, DetectionSource.content)])
    assert len(merged) == 1 and merged[0].column_name == "CC"


def test_merge_agreement_marks_both_and_boosts():
    name = _result("ssn", PiiEntityType.SSN, 0.90, DetectionSource.rule)
    content = _result("ssn", PiiEntityType.SSN, 0.88, DetectionSource.content)
    merged = merge_detections([name], [content])
    assert len(merged) == 1
    assert merged[0].detection_source == DetectionSource.both
    assert merged[0].confidence > 0.90


def test_merge_disagreement_content_wins_when_more_confident():
    name = _result("x", PiiEntityType.LOCATION, 0.75, DetectionSource.rule)
    content = _result("x", PiiEntityType.CREDIT_CARD, 0.95, DetectionSource.content)
    merged = merge_detections([name], [content])
    assert len(merged) == 1
    assert merged[0].entity_type == PiiEntityType.CREDIT_CARD
