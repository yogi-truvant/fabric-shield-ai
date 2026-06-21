"""
Unit tests for plan-limit enforcement.

The central guarantee is FAIL-OPEN: a tenant with no marketplace config (internal /
test / demo tenants) and any Cosmos lookup error must never be blocked. We only block
when an authoritative config says the tenant is suspended or over its plan limit.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.core.limits import enforce_can_add_connection, enforce_can_scan
from backend.models.schemas import MarketplacePlan, TenantConfig


def _cfg(**overrides) -> TenantConfig:
    base = dict(
        tenant_id="t1",
        company_name="Acme",
        subscription_id="sub-1",
        plan=MarketplacePlan.starter,
        admin_email="admin@acme.com",
    )
    base.update(overrides)
    return TenantConfig(**base)


def _patch_store(return_value=None, side_effect=None):
    store = MagicMock()
    store.get_tenant = AsyncMock(return_value=return_value, side_effect=side_effect)
    return patch("backend.core.limits.CosmosStore", return_value=store)


# ── fail-open ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_allowed_when_no_config():
    with _patch_store(return_value=None):
        await enforce_can_scan("test-tenant", scans_this_month=10_000)  # must not raise


@pytest.mark.asyncio
async def test_scan_allowed_when_lookup_errors():
    with _patch_store(side_effect=RuntimeError("cosmos down")):
        await enforce_can_scan("test-tenant", scans_this_month=10_000)  # must not raise


@pytest.mark.asyncio
async def test_connection_allowed_when_no_config():
    with _patch_store(return_value=None):
        await enforce_can_add_connection("test-tenant", current_count=999)  # must not raise


# ── enforced when an authoritative config exists ─────────────────────────────

@pytest.mark.asyncio
async def test_scan_blocked_when_suspended():
    with _patch_store(return_value=_cfg(is_active=False)):
        with pytest.raises(HTTPException) as exc:
            await enforce_can_scan("t1", scans_this_month=0)
        assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_scan_blocked_over_monthly_limit():
    with _patch_store(return_value=_cfg(max_scans_per_month=30)):
        with pytest.raises(HTTPException) as exc:
            await enforce_can_scan("t1", scans_this_month=30)
        assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_scan_allowed_under_monthly_limit():
    with _patch_store(return_value=_cfg(max_scans_per_month=30)):
        await enforce_can_scan("t1", scans_this_month=29)  # must not raise


@pytest.mark.asyncio
async def test_connection_blocked_at_database_limit():
    with _patch_store(return_value=_cfg(max_databases=2)):
        with pytest.raises(HTTPException) as exc:
            await enforce_can_add_connection("t1", current_count=2)
        assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_connection_allowed_under_database_limit():
    with _patch_store(return_value=_cfg(max_databases=2)):
        await enforce_can_add_connection("t1", current_count=1)  # must not raise
