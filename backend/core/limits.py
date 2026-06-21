"""
FabricShield AI — Plan-limit enforcement.

Enforces the per-plan limits stored on each tenant's marketplace TenantConfig
(is_active, max_databases, max_scans_per_month).

FAIL-OPEN by design: tenants with no TenantConfig (internal / test / pre-marketplace
tenants such as the demo tenants) and any lookup error are NEVER blocked. We only
ever block when we have an authoritative config that says the tenant is over limit
or suspended. This guarantees enforcement can't accidentally break a live scan.
"""

import structlog
from typing import Optional

from fastapi import HTTPException, status

from backend.models.schemas import TenantConfig
from backend.storage.cosmos_store import CosmosStore

logger = structlog.get_logger(__name__)


async def _get_config(tenant_id: str) -> Optional[TenantConfig]:
    try:
        return await CosmosStore().get_tenant(tenant_id)
    except Exception as exc:  # noqa: BLE001 — never block a request on a lookup failure
        logger.warning("limits.lookup_failed", tenant_id=tenant_id, error=str(exc))
        return None


def _ensure_active(cfg: Optional[TenantConfig]) -> None:
    if cfg is not None and not cfg.is_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your FabricShield subscription is suspended or cancelled. "
                   "Contact your administrator to reactivate.",
        )


async def enforce_can_scan(tenant_id: str, scans_this_month: Optional[int] = None) -> None:
    """Raise if the tenant is suspended or has hit its monthly scan limit. No-op when
    there is no config (internal/test tenant) or the count is unavailable."""
    cfg = await _get_config(tenant_id)
    _ensure_active(cfg)
    if cfg is not None and scans_this_month is not None and scans_this_month >= cfg.max_scans_per_month:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly scan limit reached ({cfg.max_scans_per_month} scans). "
                   "Upgrade your plan for a higher limit.",
        )


async def enforce_can_add_connection(tenant_id: str, current_count: int) -> None:
    """Raise if the tenant is suspended or already at its database/connection limit."""
    cfg = await _get_config(tenant_id)
    _ensure_active(cfg)
    if cfg is not None and current_count >= cfg.max_databases:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Connection limit reached for your plan ({cfg.max_databases} databases). "
                   "Upgrade to connect more.",
        )
