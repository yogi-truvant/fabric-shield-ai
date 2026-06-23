"""
FabricShield AI — Approvals API
Human-in-the-loop: approve/reject flagged columns, trigger masking on approval.
"""

import asyncio
import structlog
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.entra import RequireAnalyst, RequireApprover, get_current_user
from backend.core.audit import AuditLogger
from backend.core.masking_engine import MaskingEngine
from backend.models.schemas import (
    ApprovalRecord,
    ApprovalStatus,
    AuditAction,
    BulkApprovalRequest,
    BulkApprovalResponse,
    BulkMaskRequest,
    DatabaseType,
    MaskingResult,
    UserContext,
)
from backend.storage.cosmos_store import CosmosStore

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get(
    "/approvals",
    response_model=List[ApprovalRecord],
    summary="List approval records (paginated)",
    dependencies=[RequireAnalyst],
)
async def list_approvals(
    user: Annotated[UserContext, Depends(get_current_user)],
    status_filter: Optional[ApprovalStatus] = None,
    scan_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[ApprovalRecord]:
    """
    Returns paginated list of approval records for the tenant.
    Filter by status (PENDING, APPROVED, REJECTED, MASKED) or scan_id.
    """
    store = CosmosStore()
    return await store.list_approvals(
        tenant_id=user.tenant_id,
        status_filter=status_filter,
        scan_id=scan_id,
        limit=min(limit, 500),
        offset=offset,
    )


@router.post(
    "/approvals/bulk",
    response_model=BulkApprovalResponse,
    summary="Bulk approve or reject columns",
    dependencies=[RequireApprover],
)
async def bulk_approve_reject(
    request: BulkApprovalRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> BulkApprovalResponse:
    """
    Approve or reject multiple approval records in a single call.
    On APPROVE: triggers masking engine asynchronously.
    Requires Approver or Admin role.
    """
    # Tenant isolation check
    if request.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    store = CosmosStore()
    audit = AuditLogger()
    succeeded = 0
    failed = 0
    errors: List[dict] = []

    for approval_id in request.approval_ids:
        try:
            record = await store.get_approval(
                tenant_id=user.tenant_id,
                approval_id=approval_id,
            )
            if not record:
                errors.append({"approval_id": approval_id, "error": "Not found"})
                failed += 1
                continue

            # Allowed transitions: approve from pending/rejected; reject from
            # pending/approved. MASKED is terminal (use the DB to unmask).
            allowed = {
                "approve": {ApprovalStatus.pending, ApprovalStatus.rejected},
                "reject": {ApprovalStatus.pending, ApprovalStatus.approved},
            }
            if record.status not in allowed.get(request.action, set()):
                errors.append({
                    "approval_id": approval_id,
                    "error": f"Cannot {request.action} a column in status {record.status.value}",
                })
                failed += 1
                continue

            if request.action == "approve":
                record.status = ApprovalStatus.approved
                record.approved_by = user.oid
                record.approved_at = datetime.now(timezone.utc)
                record.rejection_reason = None
            else:
                record.status = ApprovalStatus.rejected
                record.rejection_reason = request.rejection_reason

            await store.upsert_approval(record)

            await audit.log(
                AuditAction.approval_submitted,
                actor=user,
                resource_id=approval_id,
                details={
                    "action": request.action,
                    "column": f"{record.schema_name}.{record.table_name}.{record.column_name}",
                    "entity_type": record.entity_type.value,
                },
            )

            succeeded += 1

        except Exception as exc:
            logger.exception("approvals.bulk_error", approval_id=approval_id)
            errors.append({"approval_id": approval_id, "error": str(exc)})
            failed += 1

    return BulkApprovalResponse(
        processed=len(request.approval_ids),
        succeeded=succeeded,
        failed=failed,
        errors=errors,
    )


async def _mask_record(store, audit, user, record):
    """Apply DDM for one APPROVED record, update status + audit. Shared by single + bulk."""
    if not record.connection_name:
        return MaskingResult(approval_id=record.approval_id, column_id=record.column_id,
                             success=False, error="Approval has no connection_name; re-run the scan.")
    engine = MaskingEngine(tenant_id=user.tenant_id)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: engine.apply_mask(
            connection_name=record.connection_name, db_type=record.database_type,
            schema=record.schema_name, table=record.table_name, column=record.column_name,
            data_type=record.data_type, mask_type=record.recommended_mask,
        ),
    )
    result.approval_id = record.approval_id
    result.column_id = record.column_id
    if result.success:
        record.status = ApprovalStatus.masked
        record.masked_at = result.masked_at
        await store.upsert_approval(record)
        await audit.log(AuditAction.masking_applied, actor=user, resource_id=record.approval_id,
                        details={"schema": record.schema_name, "table": record.table_name,
                                 "column": record.column_name, "mask_type": record.recommended_mask.value,
                                 "ddl": result.ddl_executed})
        try:
            from backend.governance.purview import PurviewClient
            asyncio.create_task(PurviewClient().push_classification(
                schema=record.schema_name, table=record.table_name, column=record.column_name,
                entity_type=record.entity_type, tenant_id=user.tenant_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("approvals.purview_push_failed", error=str(exc))
    else:
        record.status = ApprovalStatus.masking_failed
        await store.upsert_approval(record)
        await audit.log(AuditAction.masking_failed, actor=user, resource_id=record.approval_id,
                        details={"error": result.error}, success=False)
    return result


@router.post(
    "/approvals/bulk-mask",
    response_model=BulkApprovalResponse,
    summary="Mask multiple approved columns at once",
    dependencies=[RequireApprover],
)
async def bulk_mask(
    user: Annotated[UserContext, Depends(get_current_user)],
    request: BulkMaskRequest,
) -> BulkApprovalResponse:
    """Mask the given approved columns, or ALL approved columns for the tenant when no
    ids are supplied. Skips anything not in APPROVED status."""
    store = CosmosStore()
    audit = AuditLogger()
    if request.approval_ids:
        records = []
        for aid in request.approval_ids:
            r = await store.get_approval(tenant_id=user.tenant_id, approval_id=aid)
            if r and r.status == ApprovalStatus.approved:
                records.append(r)
    else:
        approved = await store.list_approvals(
            tenant_id=user.tenant_id, status_filter=ApprovalStatus.approved, limit=500
        )
        records = [r for r in approved
                   if not request.connection_name or r.connection_name == request.connection_name]

    succeeded = 0
    failed = 0
    errors: List[dict] = []
    for record in records:
        res = await _mask_record(store, audit, user, record)
        if res.success:
            succeeded += 1
        else:
            failed += 1
            errors.append({"approval_id": record.approval_id, "error": res.error or "mask failed"})
    return BulkApprovalResponse(processed=len(records), succeeded=succeeded, failed=failed, errors=errors)


@router.post(
    "/approvals/{approval_id}/mask",
    response_model=MaskingResult,
    summary="Apply masking to an approved column",
    dependencies=[RequireApprover],
)
async def apply_masking(
    approval_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
    connection_name: str = "",
    db_type: DatabaseType = DatabaseType.azure_sql,
) -> MaskingResult:
    """
    Apply DDM to an approved column. The approval must be in APPROVED status.
    On success, updates approval status to MASKED.
    Requires Approver or Admin role.
    """
    store = CosmosStore()
    audit = AuditLogger()

    record = await store.get_approval(tenant_id=user.tenant_id, approval_id=approval_id)
    if not record:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if record.status != ApprovalStatus.approved:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mask — approval is in status '{record.status.value}'. Must be APPROVED.",
        )

    # Optional per-call connection override (otherwise use what was captured at scan time).
    if connection_name:
        record.connection_name = connection_name
        record.database_type = db_type

    return await _mask_record(store, audit, user, record)


async def _unmask_record(store, audit, user, record):
    """Drop the DDM mask for a MASKED column and set it back to APPROVED. Returns (ok, error)."""
    if not record.connection_name:
        return False, "Approval has no connection_name; re-run the scan."
    engine = MaskingEngine(tenant_id=user.tenant_id)
    loop = asyncio.get_event_loop()
    ok, err = await loop.run_in_executor(
        None,
        lambda: engine.drop_mask(
            connection_name=record.connection_name, db_type=record.database_type,
            schema=record.schema_name, table=record.table_name, column=record.column_name,
        ),
    )
    details = {"schema": record.schema_name, "table": record.table_name, "column": record.column_name}
    if ok:
        record.status = ApprovalStatus.approved
        record.masked_at = None
        await store.upsert_approval(record)
        await audit.log(AuditAction.masking_removed, actor=user, resource_id=record.approval_id, details=details)
        return True, None
    await audit.log(AuditAction.masking_removed, actor=user, resource_id=record.approval_id,
                    details={**details, "error": err}, success=False)
    return False, err or "Drop mask failed"


@router.post(
    "/approvals/bulk-unmask",
    response_model=BulkApprovalResponse,
    summary="Remove masks from columns (admin/approver)",
    dependencies=[RequireApprover],
)
async def bulk_unmask(
    user: Annotated[UserContext, Depends(get_current_user)],
    request: BulkMaskRequest,
) -> BulkApprovalResponse:
    """Unmask the given masked columns, or ALL masked columns for the tenant when no ids
    are supplied. Skips anything not in MASKED status."""
    store = CosmosStore()
    audit = AuditLogger()
    if request.approval_ids:
        records = []
        for aid in request.approval_ids:
            r = await store.get_approval(tenant_id=user.tenant_id, approval_id=aid)
            if r and r.status == ApprovalStatus.masked:
                records.append(r)
    else:
        masked = await store.list_approvals(
            tenant_id=user.tenant_id, status_filter=ApprovalStatus.masked, limit=500
        )
        records = [r for r in masked
                   if not request.connection_name or r.connection_name == request.connection_name]

    succeeded = 0
    failed = 0
    errors: List[dict] = []
    for record in records:
        ok, err = await _unmask_record(store, audit, user, record)
        if ok:
            succeeded += 1
        else:
            failed += 1
            errors.append({"approval_id": record.approval_id, "error": err or "unmask failed"})
    return BulkApprovalResponse(processed=len(records), succeeded=succeeded, failed=failed, errors=errors)


@router.post(
    "/approvals/{approval_id}/unmask",
    summary="Remove the mask from a single column (admin/approver)",
    dependencies=[RequireApprover],
)
async def unmask_one(
    approval_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict:
    store = CosmosStore()
    audit = AuditLogger()
    record = await store.get_approval(tenant_id=user.tenant_id, approval_id=approval_id)
    if not record:
        raise HTTPException(status_code=404, detail="Approval not found")
    if record.status != ApprovalStatus.masked:
        raise HTTPException(status_code=400, detail=f"Cannot unmask — status is '{record.status.value}', must be MASKED.")
    ok, err = await _unmask_record(store, audit, user, record)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "Unmask failed")
    return {"status": "unmasked", "approval_id": approval_id}


@router.get(
    "/approvals/stats",
    summary="Get approval statistics for the tenant dashboard",
    dependencies=[RequireAnalyst],
)
async def get_approval_stats(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict:
    """Returns count breakdown by status — used for the KPI dashboard.

    'Total PII columns' counts only GENUINE PII: pending + approved + masked +
    masking_failed. Rejected columns (an approver deemed them not sensitive) are
    excluded, so coverage/high-risk percentages are computed against real PII."""
    store = CosmosStore()
    counts = await store.count_approvals_by_status(tenant_id=user.tenant_id)
    pending = counts.get(ApprovalStatus.pending.value, 0)
    approved = counts.get(ApprovalStatus.approved.value, 0)
    masked = counts.get(ApprovalStatus.masked.value, 0)
    masking_failed = counts.get(ApprovalStatus.masking_failed.value, 0)
    rejected = counts.get(ApprovalStatus.rejected.value, 0)

    total_pii = pending + approved + masked + masking_failed   # excludes rejected

    return {
        "total_pii_columns": total_pii,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "masked": masked,
        "masking_failed": masking_failed,
        "masking_coverage_pct": round(masked / max(total_pii, 1) * 100, 1),
        "high_risk_pct": round(pending / max(total_pii, 1) * 100, 1),
    }


@router.post(
    "/approvals/clear",
    summary="Clear approval/scan results for the tenant (optionally one connection)",
    dependencies=[RequireApprover],
)
async def clear_approvals(
    user: Annotated[UserContext, Depends(get_current_user)],
    connection_name: Optional[str] = None,
) -> dict:
    """Delete all approval records for the tenant, or just one connection. Gives a clean
    slate (e.g. after testing). Does NOT remove any masks already applied in the database —
    it only clears FabricShield's tracking so the next scan repopulates from scratch."""
    store = CosmosStore()
    deleted = await store.delete_all_approvals_for_connection(
        tenant_id=user.tenant_id, connection_name=connection_name
    )
    logger.info("approvals.cleared", tenant=user.tenant_id, connection=connection_name, deleted=deleted)
    return {"status": "cleared", "deleted": deleted, "connection_name": connection_name}
