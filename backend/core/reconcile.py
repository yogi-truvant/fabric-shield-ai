"""
FabricShield AI — Approval reconciliation (pure logic, no I/O).

When a scan re-runs, we must NOT:
  - resurface a column that was already approved / masked / rejected,
  - create duplicate pending rows for the same column.

And we SHOULD:
  - add genuinely new columns as pending,
  - de-duplicate any pre-existing duplicate rows for a column (keep the most
    advanced status), and
  - drop stale PENDING rows for columns that are no longer detected.

This module decides *what* to create/delete from the detected set + the existing
rows. The caller performs the actual Cosmos writes.
"""

from collections import defaultdict
from typing import Dict, List, Tuple

from backend.models.schemas import ApprovalStatus

# Higher rank = more advanced / more authoritative; kept over lower-ranked duplicates.
_RANK: Dict[str, int] = {
    ApprovalStatus.masked.value: 5,
    ApprovalStatus.masking_failed.value: 4,
    ApprovalStatus.approved.value: 3,
    ApprovalStatus.rejected.value: 2,
    ApprovalStatus.pending.value: 1,
}

ColumnKey = Tuple[str, str, str]   # (schema, table, column)


def reconcile(
    detected_keys: List[ColumnKey],
    existing: List[dict],
) -> Tuple[List[ColumnKey], List[str]]:
    """Return (keys_to_create_as_pending, approval_ids_to_delete).

    ``existing`` items are dicts: {"key": (schema, table, column), "id": <approval_id>,
    "status": <status value string>}.

    Rules (one distinct row per schema.table.column — the total never explodes):
      * detected & no existing row            -> create pending (new column).
      * detected & MASKED                     -> keep, never resurface (masking is CLOSED).
      * detected & APPROVED / MASKING_FAILED  -> keep as-is (decision in progress).
      * detected & PENDING                    -> keep (de-dupe extras).
      * detected & REJECTED                   -> RE-SURFACE: rejection is per-scan, so a
                                                 re-detected rejected column is reset to a
                                                 fresh pending for re-evaluation.
      * NOT detected & PENDING                -> delete (stale).
      * NOT detected & decided (masked/approved/rejected) -> keep (audit/history).
    """
    by_key: Dict[ColumnKey, List[dict]] = defaultdict(list)
    for row in existing:
        by_key[row["key"]].append(row)

    detected = set(detected_keys)
    to_create: List[ColumnKey] = []
    to_delete: List[str] = []

    # Detected columns: create if new, else de-dupe; re-surface rejected.
    for key in detected:
        rows = by_key.get(key)
        if not rows:
            to_create.append(key)
            continue
        rows_sorted = sorted(rows, key=lambda r: _RANK.get(r["status"], 0), reverse=True)
        best = rows_sorted[0]
        for extra in rows_sorted[1:]:
            to_delete.append(extra["id"])
        if best["status"] == ApprovalStatus.rejected.value:
            # Per-scan rejection: drop the rejected row and re-create as pending.
            to_delete.append(best["id"])
            to_create.append(key)
        # masked / approved / masking_failed / pending: keep 'best' as-is.

    # Columns no longer detected: drop stale pending only, keep decided rows.
    for key, rows in by_key.items():
        if key in detected:
            continue
        for r in rows:
            if r["status"] == ApprovalStatus.pending.value:
                to_delete.append(r["id"])

    return to_create, to_delete
