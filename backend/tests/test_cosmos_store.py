"""
Unit tests for CosmosStore.delete_pending_approvals — the idempotency guard that
stops repeat scans from accumulating duplicate approval records.

These tests mock the Cosmos container, so no live database is required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.storage.cosmos_store import CosmosStore


class _AsyncIter:
    """Minimal async-iterable wrapper so we can fake container.query_items(...)."""

    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        async def _gen():
            for item in self._items:
                yield item

        return _gen()


@pytest.mark.asyncio
async def test_delete_pending_approvals_deletes_each_returned_id():
    store = CosmosStore()
    container = MagicMock()
    container.query_items = MagicMock(
        return_value=_AsyncIter([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    )
    container.delete_item = AsyncMock()

    with patch.object(store, "_container", return_value=container):
        deleted = await store.delete_pending_approvals("tenant-1", "conn-1")

    assert deleted == 3
    assert container.delete_item.await_count == 3
    # Every delete must be scoped to the tenant partition key.
    for call in container.delete_item.await_args_list:
        assert call.kwargs["partition_key"] == "tenant-1"


@pytest.mark.asyncio
async def test_delete_pending_approvals_filters_by_connection_and_pending():
    store = CosmosStore()
    container = MagicMock()
    container.query_items = MagicMock(return_value=_AsyncIter([]))
    container.delete_item = AsyncMock()

    with patch.object(store, "_container", return_value=container):
        await store.delete_pending_approvals("tenant-9", "sales-db")

    # Inspect the parameters passed to the Cosmos query.
    _, kwargs = container.query_items.call_args
    params = {p["name"]: p["value"] for p in kwargs["parameters"]}
    assert params["@tid"] == "tenant-9"
    assert params["@conn"] == "sales-db"
    assert params["@pending"] == "PENDING"


@pytest.mark.asyncio
async def test_connection_scoped_queries_are_tenant_isolated():
    """Regression guard: connection-scoped reads/deletes must always filter by tenant_id,
    so one tenant can never touch another tenant's data."""
    store = CosmosStore()
    captured = {}

    def _query(query, parameters):
        captured["params"] = {p["name"]: p["value"] for p in parameters}
        return _AsyncIter([])

    container = MagicMock()
    container.query_items = MagicMock(side_effect=_query)
    container.delete_item = AsyncMock()
    with patch.object(store, "_container", return_value=container):
        await store.list_all_approvals_for_connection("tenant-A", "conn-1")
        assert captured["params"]["@tid"] == "tenant-A"
        await store.delete_scans_for_connection("tenant-A", "conn-1")
        assert captured["params"]["@tid"] == "tenant-A"


@pytest.mark.asyncio
async def test_count_approvals_by_status_counts_per_status():
    store = CosmosStore()
    container = MagicMock()

    def _query(query, parameters):
        s = {p["name"]: p["value"] for p in parameters}["@s"]
        return _AsyncIter([{"PENDING": 18, "MASKED": 5}.get(s, 0)])

    container.query_items = MagicMock(side_effect=_query)
    with patch.object(store, "_container", return_value=container):
        counts = await store.count_approvals_by_status("tenant-1")

    assert counts["PENDING"] == 18
    assert counts["MASKED"] == 5
    assert counts["APPROVED"] == 0   # statuses with no rows come back as 0, not missing


@pytest.mark.asyncio
async def test_delete_pending_approvals_noop_when_nothing_pending():
    store = CosmosStore()
    container = MagicMock()
    container.query_items = MagicMock(return_value=_AsyncIter([]))
    container.delete_item = AsyncMock()

    with patch.object(store, "_container", return_value=container):
        deleted = await store.delete_pending_approvals("t", "c")

    assert deleted == 0
    container.delete_item.assert_not_awaited()
