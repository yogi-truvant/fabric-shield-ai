"""
FabricShield AI — Content scanner (opt-in, in-memory)

Detects PII from sampled column VALUES, independent of column names. Two tiers:

  Tier 1  Deterministic value validators (validators.py) — checksum/format checks for
          structured PII (credit card, SSN, IBAN, NPI, DEA, email, phone, IP, ZIP, DOB).
          Name-agnostic: catches a credit-card column named ``CC`` from its values.

  Tier 2  spaCy NER (lazy, optional) — free-text PERSON names and locations/addresses,
          the unstructured PII that validators cannot checksum. Degrades gracefully:
          if the model isn't installed, this tier is skipped and Tier 1 still runs.

DATA SAFETY: callers pass values already sampled in memory; this module never reads a
database, and never logs, caches, or persists raw values — only the derived verdict
(entity type, confidence, match-fraction) leaves the function.
"""

from typing import Dict, List, Optional

import structlog

from backend.core.validators import best_value_entity, confidence_from_match
from backend.models.schemas import (
    DatabaseType as DBType,
    DetectionSource,
    MaskType,
    PiiColumnResult,
    PiiEntityType,
)

logger = structlog.get_logger(__name__)

# ── Tier 2: lazy, optional spaCy NER ─────────────────────────────────────────
_nlp = None
_nlp_unavailable = False
_TEXT_TYPES = {"char", "varchar", "nvarchar", "nchar", "text", "ntext"}
_NER_MIN_MATCH = 0.50
_NER_MAX_VALUES = 60       # cap values sent to NER per column (latency/memory)
_NER_MAX_LEN = 200         # skip very long blobs


def _get_nlp():
    """Load en_core_web_sm once; never raise — NER is optional."""
    global _nlp, _nlp_unavailable
    if _nlp is not None or _nlp_unavailable:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm", disable=["lemmatizer", "tagger", "parser"])
        logger.info("content_scanner.ner_loaded")
    except Exception as exc:  # noqa: BLE001 — model missing/incompatible → skip NER
        logger.warning("content_scanner.ner_unavailable", error=str(exc))
        _nlp_unavailable = True
        _nlp = None
    return _nlp


def _ner_entity(values: List[str]) -> Optional[tuple]:
    """Return (entity, confidence, match_frac) if NER finds enough PERSON/LOCATION, else None."""
    nlp = _get_nlp()
    if nlp is None:
        return None
    sample = [v[:_NER_MAX_LEN] for v in values[:_NER_MAX_VALUES]]
    if not sample:
        return None
    person_hits = loc_hits = 0
    for doc in nlp.pipe(sample):
        labels = {ent.label_ for ent in doc.ents}
        if "PERSON" in labels:
            person_hits += 1
        if "GPE" in labels or "LOC" in labels or "FAC" in labels:
            loc_hits += 1
    total = len(sample)
    person_frac, loc_frac = person_hits / total, loc_hits / total
    if person_frac >= _NER_MIN_MATCH and person_frac >= loc_frac:
        return PiiEntityType.PERSON_NAME, round(0.55 + 0.4 * person_frac, 3), round(person_frac, 3)
    if loc_frac >= _NER_MIN_MATCH:
        return PiiEntityType.LOCATION, round(0.55 + 0.35 * loc_frac, 3), round(loc_frac, 3)
    return None


def _detect_column(
    schema_name: str, table_name: str, database_type: str,
    column_name: str, data_type: str, values: List[str],
) -> Optional[PiiColumnResult]:
    db_type_enum = DBType.fabric if database_type == "fabric" else DBType.azure_sql

    # Tier 1 — deterministic validators (works on any column name).
    best = best_value_entity(values)
    if best is not None:
        entity, mask, frac, strong = best
        return PiiColumnResult(
            database_type=db_type_enum, schema_name=schema_name, table_name=table_name,
            column_name=column_name, data_type=data_type, entity_type=entity,
            confidence=confidence_from_match(frac, strong),
            detection_source=DetectionSource.content, recommended_mask=mask,
            sample_match_pct=round(frac, 3),
        )

    # Tier 2 — NER for free-text names/locations (only on text-ish columns).
    if data_type.lower() in _TEXT_TYPES:
        cleaned = [str(v).strip() for v in values if v is not None and str(v).strip()]
        ner = _ner_entity(cleaned)
        if ner is not None:
            entity, conf, frac = ner
            return PiiColumnResult(
                database_type=db_type_enum, schema_name=schema_name, table_name=table_name,
                column_name=column_name, data_type=data_type, entity_type=entity,
                confidence=conf, detection_source=DetectionSource.ml,
                recommended_mask=MaskType.default, sample_match_pct=frac,
            )
    return None


def scan_table_values(
    schema_name: str, table_name: str, database_type: str,
    values_by_column: Dict[str, List[str]], data_types: Dict[str, str],
) -> List[PiiColumnResult]:
    """Run content detection over one table's sampled values. In-memory only."""
    results: List[PiiColumnResult] = []
    for column, values in values_by_column.items():
        res = _detect_column(
            schema_name, table_name, database_type, column, data_types.get(column, ""), values
        )
        if res is not None:
            results.append(res)
    return results


def merge_detections(
    name_results: List[PiiColumnResult], content_results: List[PiiColumnResult],
) -> List[PiiColumnResult]:
    """Combine name-based and content-based detections, deduped by column.

    - Only name flagged       → keep it.
    - Only content flagged     → keep it (this is the 'CC' case names miss).
    - Both, same entity        → mark source=both, boost confidence.
    - Both, different entity   → trust the content verdict if it's at least as confident
                                 (it saw real data); otherwise keep the name verdict.
    """
    by_key: Dict[tuple, PiiColumnResult] = {}
    for r in name_results:
        by_key[(r.schema_name, r.table_name, r.column_name)] = r

    for c in content_results:
        key = (c.schema_name, c.table_name, c.column_name)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = c
            continue
        if existing.entity_type == c.entity_type:
            existing.detection_source = DetectionSource.both
            existing.confidence = round(min(1.0, max(existing.confidence, c.confidence) + 0.10), 3)
            existing.sample_match_pct = c.sample_match_pct
        elif c.confidence >= existing.confidence:
            by_key[key] = c
    return list(by_key.values())
