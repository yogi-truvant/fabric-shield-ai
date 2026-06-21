"""Unit tests for approval reconciliation — the rule that re-scans don't resurface or
duplicate already-handled columns."""

from backend.core.reconcile import reconcile


def _row(key, id_, status):
    return {"key": key, "id": id_, "status": status}


K_EMAIL = ("clinical", "Demographics", "Email")
K_SSN = ("clinical", "Demographics", "SSN")
K_NEW = ("billing", "Accounts", "IBAN")


def test_new_column_is_created():
    to_create, to_delete = reconcile([K_EMAIL], existing=[])
    assert to_create == [K_EMAIL]
    assert to_delete == []


def test_already_masked_column_is_not_resurfaced():
    existing = [_row(K_EMAIL, "a1", "MASKED")]
    to_create, to_delete = reconcile([K_EMAIL], existing)
    assert to_create == []          # not re-created
    assert to_delete == []          # kept as-is


def test_rejected_column_is_resurfaced_as_pending():
    # Rejection is per-scan: a re-detected rejected column comes back for re-evaluation.
    existing = [_row(K_EMAIL, "a1", "REJECTED")]
    to_create, to_delete = reconcile([K_EMAIL], existing)
    assert to_create == [K_EMAIL]   # fresh pending
    assert to_delete == ["a1"]      # old rejected row removed (stays distinct)


def test_rejected_column_not_detected_is_kept():
    # If it's no longer detected, the rejected row is left untouched (history).
    existing = [_row(K_EMAIL, "a1", "REJECTED")]
    to_create, to_delete = reconcile([K_SSN], existing)
    assert K_SSN in to_create
    assert to_delete == []


def test_duplicates_are_deduped_keeping_most_advanced():
    existing = [
        _row(K_EMAIL, "pending1", "PENDING"),
        _row(K_EMAIL, "masked1", "MASKED"),
        _row(K_EMAIL, "pending2", "PENDING"),
    ]
    to_create, to_delete = reconcile([K_EMAIL], existing)
    assert to_create == []
    # keeps the MASKED row, deletes the two pending duplicates
    assert set(to_delete) == {"pending1", "pending2"}


def test_stale_pending_dropped_when_not_detected():
    existing = [_row(K_SSN, "p1", "PENDING")]
    to_create, to_delete = reconcile([K_EMAIL], existing)   # SSN no longer detected
    assert to_create == [K_EMAIL]
    assert to_delete == ["p1"]


def test_decided_rows_kept_when_not_detected():
    existing = [_row(K_SSN, "m1", "MASKED")]
    to_create, to_delete = reconcile([K_EMAIL], existing)   # SSN gone, but it was masked
    assert to_create == [K_EMAIL]
    assert to_delete == []          # masked history preserved


def test_mixed_scenario():
    existing = [
        _row(K_EMAIL, "e1", "MASKED"),        # detected, decided -> keep, no create
        _row(K_SSN, "s1", "PENDING"),         # detected, pending -> keep
        _row(K_SSN, "s2", "PENDING"),         # duplicate -> delete
        _row(("x", "y", "z"), "stale", "PENDING"),  # not detected, pending -> delete
    ]
    to_create, to_delete = reconcile([K_EMAIL, K_SSN, K_NEW], existing)
    assert to_create == [K_NEW] or to_create == [K_NEW]   # only the brand-new column
    assert "stale" in to_delete
    assert "s2" in to_delete
    assert "e1" not in to_delete and "s1" not in to_delete
