"""
FabricShield AI — PII/PHI Detection Engine (METADATA-ONLY)

HARD CONSTRAINT: detection runs purely on column NAME + DATA TYPE metadata.
This module never reads, samples, caches, logs, or transmits table row data.
There is no data-sampling path and no row-value-based ML inference.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import structlog

from backend.config import get_settings
from backend.models.schemas import DatabaseType as DBType
from backend.models.schemas import (
    DetectionSource,
    MaskType,
    PiiColumnResult,
    PiiEntityType,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


# ─── Rule-Based Pattern Catalog ───────────────────────────────────────────────

@dataclass
class ColumnRule:
    """A single column-name rule with its PII type and recommended mask."""
    pattern: re.Pattern
    entity_type: PiiEntityType
    recommended_mask: MaskType
    base_confidence: float = 0.75


# Confidence reflects how UNAMBIGUOUS the column NAME is on its own. Unambiguous PII
# (SSN, email, credit card) scores high; ambiguous identifiers (MRN, patient/encounter
# id, account no., names, locations) score lower ("needs review") and only reach high
# confidence when a content scan confirms the values (the merge adds a boost). The flag
# threshold is 0.6, so downgraded identifiers are still surfaced — just not over-stated.
COLUMN_RULES: List[ColumnRule] = [
    # --- Unambiguous, high-confidence PII (also content-verifiable) ---
    ColumnRule(re.compile(r"credit.?card|cc.?num|card.?num|cvv|cvc|expir", re.I), PiiEntityType.CREDIT_CARD, MaskType.partial, 0.95),
    ColumnRule(re.compile(r"\bssn\b|social.?sec|tax.?id", re.I), PiiEntityType.SSN, MaskType.partial, 0.92),
    ColumnRule(re.compile(r"\bemail\b|e.?mail.?addr", re.I), PiiEntityType.EMAIL, MaskType.email, 0.92),
    ColumnRule(re.compile(r"\bphone\b|\bmobile\b|\bcell\b|\bfax\b|telephone", re.I), PiiEntityType.PHONE, MaskType.partial, 0.82),
    ColumnRule(re.compile(r"dob|date.?of.?birth|birth.?date|birthday", re.I), PiiEntityType.DATE_OF_BIRTH, MaskType.default, 0.85),
    # --- Ambiguous identifiers: downgraded, still flagged for review ---
    ColumnRule(re.compile(r"\biban\b|bank.?acct|account.?num|routing", re.I), PiiEntityType.IBAN, MaskType.partial, 0.68),
    ColumnRule(re.compile(r"\bip.?addr\b|client.?ip|remote.?addr", re.I), PiiEntityType.IP_ADDRESS, MaskType.default, 0.72),
    ColumnRule(re.compile(r"first.?name|last.?name|full.?name|patient.?name|person.?name|given.?name|surname", re.I), PiiEntityType.PERSON_NAME, MaskType.default, 0.70),
    ColumnRule(re.compile(r"\baddress\b|street|postal|zip.?code|city|state|country", re.I), PiiEntityType.LOCATION, MaskType.partial, 0.65),
    # \bmrn\b (not bare 'mrn') so 'CMRN' and similar don't false-match
    ColumnRule(re.compile(r"\bmrn\b|medical.?rec|patient.?id|health.?id|encounter.?id", re.I), PiiEntityType.MEDICAL_RECORD, MaskType.default, 0.65),
    ColumnRule(re.compile(r"\bnpi\b|provider.?id|physician.?id", re.I), PiiEntityType.NPI, MaskType.partial, 0.68),
    ColumnRule(re.compile(r"\bdea\b|dea.?num|prescriber", re.I), PiiEntityType.DEA, MaskType.partial, 0.72),
    ColumnRule(re.compile(r"diagnosis|icd.?\d|procedure|treatment|medication|drug.?name|allerg", re.I), PiiEntityType.PHI_GENERIC, MaskType.default, 0.65),
]

# Recommended mask per entity type (used if an entity is detected without a rule mask).
DEFAULT_MASK_FOR_ENTITY: Dict[PiiEntityType, MaskType] = {
    PiiEntityType.SSN: MaskType.partial,
    PiiEntityType.EMAIL: MaskType.email,
    PiiEntityType.PHONE: MaskType.partial,
    PiiEntityType.DATE_OF_BIRTH: MaskType.default,
    PiiEntityType.CREDIT_CARD: MaskType.partial,
    PiiEntityType.IBAN: MaskType.partial,
    PiiEntityType.IP_ADDRESS: MaskType.default,
    PiiEntityType.PERSON_NAME: MaskType.default,
    PiiEntityType.LOCATION: MaskType.partial,
    PiiEntityType.MEDICAL_RECORD: MaskType.default,
    PiiEntityType.NPI: MaskType.partial,
    PiiEntityType.DEA: MaskType.partial,
    PiiEntityType.PHI_GENERIC: MaskType.default,
    PiiEntityType.CUSTOM: MaskType.default,
}


# ─── Detection Functions ──────────────────────────────────────────────────────

def _apply_rules(column_name: str) -> Optional[Tuple[PiiEntityType, float, MaskType]]:
    """Test a column name against the rule catalog. Returns (entity, confidence, mask) or None.

    Separators (_, -, ., camelCase) are normalized to spaces so \b-anchored rules match
    snake_case columns like ``patient_ssn`` and ``client_ip`` — the dominant SQL convention.
    """
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", column_name)
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", normalized)  # split camelCase
    for rule in COLUMN_RULES:
        if rule.pattern.search(column_name) or rule.pattern.search(normalized):
            return rule.entity_type, rule.base_confidence, rule.recommended_mask
    return None


def _merge_results(
    rule_result: Optional[Tuple[PiiEntityType, float, MaskType]],
    ml_result: Optional[Tuple[PiiEntityType, float]],
    confidence_threshold: float,
) -> Optional[Tuple[PiiEntityType, float, DetectionSource, MaskType]]:
    """Merge a rule verdict with an optional secondary (e.g. name-NER) verdict.
    In metadata-only mode ml_result is always None; retained for forward-compat + tests."""
    if rule_result is None and ml_result is None:
        return None

    if rule_result and ml_result:
        rule_type, rule_conf, rule_mask = rule_result
        ml_type, ml_conf = ml_result
        if rule_type == ml_type:
            merged_conf = min(1.0, max(rule_conf, ml_conf) + 0.15)
            return rule_type, round(merged_conf, 3), DetectionSource.both, rule_mask
        if rule_conf >= ml_conf:
            return rule_type, rule_conf, DetectionSource.rule, rule_mask
        mask = DEFAULT_MASK_FOR_ENTITY.get(ml_type, MaskType.default)
        return ml_type, ml_conf, DetectionSource.ml, mask

    if rule_result:
        rule_type, rule_conf, rule_mask = rule_result
        if rule_conf >= confidence_threshold:
            return rule_type, rule_conf, DetectionSource.rule, rule_mask
        return None

    ml_type, ml_conf = ml_result  # type: ignore[misc]
    if ml_conf >= confidence_threshold:
        mask = DEFAULT_MASK_FOR_ENTITY.get(ml_type, MaskType.default)
        return ml_type, ml_conf, DetectionSource.ml, mask
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_column(
    schema_name: str,
    table_name: str,
    column_name: str,
    data_type: str,
    confidence_threshold: Optional[float] = None,
    database_type: str = "azure_sql",
) -> Optional[PiiColumnResult]:
    """Analyze a single column for PII/PHI using NAME + DATA TYPE only.
    Returns a PiiColumnResult if flagged, else None."""
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.pii_confidence_threshold
    )

    # Skip binary/structural types that cannot carry detectable PII by name semantics.
    non_pii_types = {"image", "varbinary", "binary", "bit", "xml", "geography", "geometry"}
    if data_type.lower() in non_pii_types:
        return None

    rule_result = _apply_rules(column_name)
    merged = _merge_results(rule_result, None, threshold)
    if merged is None:
        return None

    entity_type, confidence, source, mask_type = merged
    db_type_enum = DBType.fabric if database_type == "fabric" else DBType.azure_sql

    return PiiColumnResult(
        database_type=db_type_enum,
        schema_name=schema_name,
        table_name=table_name,
        column_name=column_name,
        data_type=data_type,
        entity_type=entity_type,
        confidence=confidence,
        detection_source=source,
        recommended_mask=mask_type,
    )


def scan_columns(
    column_metadata: List[Dict],
    database_type: str = "azure_sql",
    confidence_threshold: Optional[float] = None,
) -> List[PiiColumnResult]:
    """Scan column metadata dicts (from db_connector.get_schema_metadata).
    No sample_fetcher: detection is metadata-only."""
    results: List[PiiColumnResult] = []
    total = len(column_metadata)
    logger.info("pii_engine.scan_start", total_columns=total)

    for col in column_metadata:
        result = analyze_column(
            schema_name=col["schema_name"],
            table_name=col["table_name"],
            column_name=col["column_name"],
            data_type=col["data_type"],
            confidence_threshold=confidence_threshold,
            database_type=database_type,
        )
        if result:
            results.append(result)

    logger.info(
        "pii_engine.scan_complete",
        total_columns=total,
        flagged=len(results),
        flag_rate=round(len(results) / max(total, 1), 3),
    )
    return results
