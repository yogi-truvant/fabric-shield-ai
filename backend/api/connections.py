"""
FabricShield AI - Connections API
Manage data-source connections (hybrid auth). Metadata + secrets stored in Key Vault:
  tenant-{tenant}-{name}-server / -database / -meta(JSON) / -sqlpassword
Requires the backend managed identity to have Key Vault Secrets Officer (read+write).
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Annotated, List, Optional

import structlog
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.entra import RequireAdmin, RequireAnalyst, get_current_user
from backend.config import get_settings
from backend.core.db_connector import DatabaseConnector
from backend.core.limits import enforce_can_add_connection
from backend.storage.cosmos_store import CosmosStore
from backend.models.schemas import (
    ConnectionAuthMode, ConnectionCreateRequest, ConnectionInfo,
    ConnectionTestResult, DatabaseType, UserContext,
)

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

_kv: Optional[SecretClient] = None


def _kv_client() -> SecretClient:
    global _kv
    if _kv is None:
        _kv = SecretClient(vault_url=settings.keyvault_url, credential=ManagedIdentityCredential())
    return _kv


def _get(name: str) -> Optional[str]:
    try:
        return _kv_client().get_secret(name).value
    except ResourceNotFoundError:
        return None


@router.get("/connections", response_model=List[ConnectionInfo], dependencies=[RequireAnalyst])
async def list_connections(user: Annotated[UserContext, Depends(get_current_user)]) -> List[ConnectionInfo]:
    """List the tenant's registered connections (no passwords returned)."""
    pfx = f"tenant-{user.tenant_id}-"
    kv = _kv_client()

    def _list() -> List[ConnectionInfo]:
        out: List[ConnectionInfo] = []
        for prop in kv.list_properties_of_secrets():
            n = prop.name or ""
            if not (n.startswith(pfx) and n.endswith("-server")):
                continue
            name = n[len(pfx):-len("-server")]
            info = {
                "name": name,
                "server": _get(f"{pfx}{name}-server") or "",
                "database": _get(f"{pfx}{name}-database") or "",
                "database_type": "azure_sql",
                "auth_mode": "service_principal",
            }
            meta = _get(f"{pfx}{name}-meta")
            if meta:
                try:
                    m = json.loads(meta)
                    info.update(
                        database_type=m.get("database_type", "azure_sql"),
                        auth_mode=m.get("auth_mode", "service_principal"),
                        sql_username=m.get("sql_username"),
                        created_by=m.get("created_by"),
                        created_at=m.get("created_at"),
                    )
                except (ValueError, TypeError):
                    pass
            out.append(ConnectionInfo(**info))
        return out

    return await asyncio.get_event_loop().run_in_executor(None, _list)


@router.post("/connections", response_model=ConnectionInfo, status_code=status.HTTP_201_CREATED,
             dependencies=[RequireAdmin])
async def create_connection(
    req: ConnectionCreateRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> ConnectionInfo:
    """Register a connection. SQL-auth passwords are stored in Key Vault, never returned."""
    if req.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id does not match authenticated tenant")
    if req.auth_mode == ConnectionAuthMode.sql and not (req.sql_username and req.sql_password):
        raise HTTPException(status_code=400, detail="sql_username and sql_password are required for SQL auth")

    # Plan enforcement (fail-open for internal/test tenants and on lookup errors).
    kv = _kv_client()
    tpfx = f"tenant-{user.tenant_id}-"

    def _count_connections() -> int:
        return sum(
            1 for p in kv.list_properties_of_secrets()
            if (p.name or "").startswith(tpfx) and (p.name or "").endswith("-server")
        )

    try:
        current = await asyncio.get_event_loop().run_in_executor(None, _count_connections)
    except Exception:  # noqa: BLE001
        current = 0
    await enforce_can_add_connection(user.tenant_id, current)

    pfx = f"tenant-{user.tenant_id}-{req.name}"
    created_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "database_type": req.database_type.value,
        "auth_mode": req.auth_mode.value,
        "sql_username": req.sql_username,
        "created_by": user.email or user.oid,
        "created_at": created_at,
    }

    def _write():
        kv.set_secret(f"{pfx}-server", req.server)
        kv.set_secret(f"{pfx}-database", req.database)
        kv.set_secret(f"{pfx}-meta", json.dumps(meta))
        if req.auth_mode == ConnectionAuthMode.sql:
            kv.set_secret(f"{pfx}-sqlpassword", req.sql_password)

    try:
        await asyncio.get_event_loop().run_in_executor(None, _write)
    except Exception as exc:  # noqa: BLE001
        logger.error("connections.write_failed", name=req.name, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Could not store connection: {exc}")

    logger.info("connections.created", tenant=user.tenant_id, name=req.name, auth_mode=req.auth_mode.value)
    return ConnectionInfo(
        name=req.name, server=req.server, database=req.database, database_type=req.database_type,
        auth_mode=req.auth_mode, sql_username=req.sql_username, created_by=meta["created_by"], created_at=created_at,
    )


@router.post("/connections/{name}/test", response_model=ConnectionTestResult, dependencies=[RequireAnalyst])
async def test_connection(
    name: str,
    user: Annotated[UserContext, Depends(get_current_user)],
    db_type: DatabaseType = DatabaseType.azure_sql,
) -> ConnectionTestResult:
    """Metadata-only reachability check for a registered connection."""
    connector = DatabaseConnector(customer_tenant_id=user.tenant_id)
    ok, msg, count = await asyncio.get_event_loop().run_in_executor(
        None, lambda: connector.test_connection(name, db_type)
    )
    return ConnectionTestResult(success=ok, message=msg, table_count=count)


@router.get("/connections/{name}/schemas", response_model=List[str], dependencies=[RequireAnalyst])
async def list_connection_schemas(
    name: str,
    user: Annotated[UserContext, Depends(get_current_user)],
    db_type: DatabaseType = DatabaseType.azure_sql,
) -> List[str]:
    """List the schemas (containing tables) for a connection, to drive the Scan picker.
    Metadata-only: reads INFORMATION_SCHEMA only, never any row data."""
    connector = DatabaseConnector(customer_tenant_id=user.tenant_id)
    try:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: connector.list_schemas(name, db_type)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("connections.list_schemas_failed", name=name, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Could not list schemas: {exc}")


@router.delete("/connections/{name}", dependencies=[RequireAdmin])
async def delete_connection(name: str, user: Annotated[UserContext, Depends(get_current_user)]) -> dict:
    """Remove a connection and its secrets."""
    pfx = f"tenant-{user.tenant_id}-{name}"
    kv = _kv_client()

    def _delete():
        for suffix in ("-server", "-database", "-meta", "-sqlpassword"):
            try:
                kv.begin_delete_secret(f"{pfx}{suffix}")
            except ResourceNotFoundError:
                pass

    await asyncio.get_event_loop().run_in_executor(None, _delete)

    # Which connections still exist for this tenant AFTER the delete above?
    tpfx = f"tenant-{user.tenant_id}-"

    def _remaining_names() -> List[str]:
        out = []
        for p in kv.list_properties_of_secrets():
            n = p.name or ""
            if n.startswith(tpfx) and n.endswith("-server"):
                out.append(n[len(tpfx):-len("-server")])
        return out

    try:
        remaining = await asyncio.get_event_loop().run_in_executor(None, _remaining_names)
    except Exception:  # noqa: BLE001 — if listing fails, fall back to a clean reset
        remaining = []

    # Cascade: clear scans + approvals so the dashboard resets. Audit is preserved (immutable).
    store = CosmosStore()
    if not remaining:
        # Last connection removed → full fresh state: wipe ALL approvals + scans for the tenant.
        approvals_removed = await store.delete_all_approvals_for_connection(user.tenant_id, None)
        scans_removed = await store.delete_scans_for_connection(user.tenant_id, None)
    else:
        # Other connections remain → drop this one's records, plus any orphaned/stale ones.
        approvals_removed = await store.delete_all_approvals_for_connection(user.tenant_id, name)
        approvals_removed += await store.delete_orphan_approvals(user.tenant_id, remaining)
        scans_removed = await store.delete_scans_for_connection(user.tenant_id, name)
        scans_removed += await store.delete_orphan_scans(user.tenant_id, remaining)

    logger.info("connections.deleted", tenant=user.tenant_id, name=name, remaining=len(remaining),
                approvals_removed=approvals_removed, scans_removed=scans_removed)
    return {"status": "deleted", "name": name, "remaining_connections": len(remaining),
            "approvals_removed": approvals_removed, "scans_removed": scans_removed}
