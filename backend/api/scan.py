"""
FabricShield AI — Scan API
POST /scan triggers an async PII scan. GET /scan/{scan_id} returns status.
"""

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.auth.entra import RequireAnalyst, get_current_user
from backend.core.audit import AuditLogger
from backend.core.content_scanner import merge_detections, scan_table_values
from backend.core.db_connector import DatabaseConnector
from backend.core.limits import enforce_can_scan
from backend.core.pii_engine import scan_columns
from backend.models.schemas import (
    AuditAction,
    ScanRequest,
    ScanResponse,
    ScanResult,
    UserContext,
)
from backend.storage.cosmos_store import CosmosStore

logger = structlog.get_logger(__name__)
router = APIRouter()


def _content_scan(connector, request, column_metadata):
    """Worker-thread helper: sample each table's VALUES (in memory) and detect PII by
    content. One query per table. Returns a list of PiiColumnResult. Never stores values."""
    tables: dict = {}
    types: dict = {}
    for col in column_metadata:
        key = (col["schema_name"], col["table_name"])
        tables.setdefault(key, []).append(col["column_name"])
        types[(col["schema_name"], col["table_name"], col["column_name"])] = col.get("data_type", "")

    results = []
    for (schema, table), columns in tables.items():
        try:
            values = connector.fetch_table_sample(
                request.connection_name, request.database_type, schema, table,
                columns, limit=request.content_sample_size,
            )
        except Exception as exc:  # noqa: BLE001 — skip tables we can't sample
            logger.warning("scan.sample_failed", table=f"{schema}.{table}", error=str(exc))
            continue
        dt = {c: types.get((schema, table, c), "") for c in columns}
        results.extend(scan_table_values(schema, table, request.database_type.value, values, dt))
    return results


async def _run_scan(
    scan_result: ScanResult,
    request: ScanRequest,
    user: UserContext,
) -> None:
    """Background task: execute scan, write results to Cosmos DB."""
    store = CosmosStore()
    audit = AuditLogger()
    connector = DatabaseConnector(customer_tenant_id=request.tenant_id)

    try:
        # Emit audit event: scan started
        await audit.log(
            AuditAction.scan_started,
            actor=user,
            resource_id=scan_result.scan_id,
            details={
                "connection_name": request.connection_name,
                "db_type": request.database_type.value,
                "schemas": request.schema_names,
            },
        )

        # Fetch schema metadata
        column_metadata = connector.get_schema_metadata(
            connection_name=request.connection_name,
            db_type=request.database_type,
            schema_names=request.schema_names,
            include_tables=request.include_tables,
            exclude_tables=request.exclude_tables,
        )

        # Metadata-only PII detection — NO row data is read. Offload to a worker thread.
        loop = asyncio.get_event_loop()
        pii_columns = await loop.run_in_executor(
            None,
            lambda: scan_columns(
                column_metadata=column_metadata,
                database_type=request.database_type.value,
            ),
        )

        # Opt-in content scan: sample VALUES in memory to catch PII the column names miss
        # (e.g. a credit-card column named 'CC'). Never stored. Failure degrades to
        # metadata-only results rather than failing the whole scan.
        if request.content_scan:
            try:
                content_cols = await loop.run_in_executor(
                    None, lambda: _content_scan(connector, request, column_metadata)
                )
                pii_columns = merge_detections(pii_columns, content_cols)
            except Exception as exc:  # noqa: BLE001
                logger.warning("scan.content_scan_failed", scan_id=scan_result.scan_id, error=str(exc))

        scan_result.pii_columns = pii_columns
        scan_result.status = "completed"
        scan_result.completed_at = datetime.now(timezone.utc)

        # Persist scan result
        await store.upsert_scan(scan_result)

        # Create approval records for each flagged column.
        # First supersede any still-pending approvals for this connection so repeat
        # scans don't accumulate duplicates (approved/masked records are preserved).
        from backend.models.schemas import ApprovalRecord, ApprovalStatus
        await store.delete_pending_approvals(request.tenant_id, request.connection_name)
        for col in pii_columns:
            approval = ApprovalRecord(
                tenant_id=request.tenant_id,
                scan_id=scan_result.scan_id,
                column_id=col.column_id,
                schema_name=col.schema_name,
                table_name=col.table_name,
                column_name=col.column_name,
                entity_type=col.entity_type,
                confidence=col.confidence,
                detection_source=col.detection_source,
                recommended_mask=col.recommended_mask,
                connection_name=request.connection_name,
                data_type=col.data_type,
                database_type=request.database_type,
                status=ApprovalStatus.pending,
            )
            await store.upsert_approval(approval)

        await audit.log(
            AuditAction.scan_completed,
            actor=user,
            resource_id=scan_result.scan_id,
            details={
                "columns_scanned": len(column_metadata),
                "pii_columns_found": len(pii_columns),
                "duration_ms": int(
                    (scan_result.completed_at - scan_result.started_at).total_seconds() * 1000
                ),
            },
        )

        logger.info(
            "scan.completed",
            scan_id=scan_result.scan_id,
            tenant_id=request.tenant_id,
            pii_found=len(pii_columns),
        )

    except Exception as exc:
        logger.exception("scan.failed", scan_id=scan_result.scan_id, error=str(exc))
        scan_result.status = "failed"
        scan_result.error = str(exc)
        scan_result.completed_at = datetime.now(timezone.utc)
        await store.upsert_scan(scan_result)
        await audit.log(
            AuditAction.scan_failed,
            actor=user,
            resource_id=scan_result.scan_id,
            details={"error": str(exc)},
            success=False,
        )


@router.post(
    "/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a PII/PHI scan",
    dependencies=[RequireAnalyst],
)
async def trigger_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> ScanResponse:
    """
    Initiates an async PII scan against the specified database.
    Returns immediately with scan_id; poll GET /scan/{scan_id} for status.
    Requires Analyst or Admin role.
    """
    # Enforce tenant isolation: tenant_id in request must match JWT tenant
    if request.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_id in request does not match authenticated tenant",
        )

    # Plan enforcement (fail-open: internal/test tenants without a TenantConfig and any
    # lookup failure are never blocked; only authoritative over-limit/suspended configs block).
    store = CosmosStore()
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    try:
        scans_this_month = await store.count_scans_since(request.tenant_id, month_start)
    except Exception:  # noqa: BLE001
        scans_this_month = None
    await enforce_can_scan(request.tenant_id, scans_this_month)

    scan_result = ScanResult(
        tenant_id=request.tenant_id,
        connection_name=request.connection_name,
        database_type=request.database_type,
        schemas_scanned=request.schema_names,
        started_at=datetime.now(timezone.utc),
        status="running",
        triggered_by=user.oid,
    )

    # Persist initial state immediately so callers can poll
    await store.upsert_scan(scan_result)

    background_tasks.add_task(_run_scan, scan_result, request, user)

    return ScanResponse(
        scan_id=scan_result.scan_id,
        status="running",
        message=f"Scan {scan_result.scan_id} initiated. Poll GET /scan/{scan_result.scan_id} for status.",
    )


@router.get(
    "/scan/{scan_id}",
    response_model=ScanResult,
    summary="Get scan status and results",
    dependencies=[RequireAnalyst],
)
async def get_scan(
    scan_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> ScanResult:
    """Returns the current state of a scan. Tenant-isolated."""
    store = CosmosStore()
    result = await store.get_scan(tenant_id=user.tenant_id, scan_id=scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scan not found")
    if result.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return result


@router.get(
    "/scans",
    response_model=list[ScanResult],
    summary="List recent scans for the tenant",
    dependencies=[RequireAnalyst],
)
async def list_scans(
    user: Annotated[UserContext, Depends(get_current_user)],
    limit: int = 20,
) -> list[ScanResult]:
    """Returns the most recent N scans for the authenticated tenant."""
    store = CosmosStore()
    return await store.list_scans(tenant_id=user.tenant_id, limit=limit)
