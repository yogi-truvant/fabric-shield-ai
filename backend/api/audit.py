"""
FabricShield AI — Audit Log API
Read-only view of the immutable audit trail.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends

from backend.auth.entra import RequireAnalyst, get_current_user
from backend.models.schemas import AuditAction, AuditLogListResponse, UserContext
from backend.storage.cosmos_store import CosmosStore

router = APIRouter()


@router.get(
    "/audit",
    response_model=AuditLogListResponse,
    summary="Query the audit log",
    dependencies=[RequireAnalyst],
)
async def get_audit_logs(
    user: Annotated[UserContext, Depends(get_current_user)],
    action: Optional[AuditAction] = None,
    limit: int = 100,
    offset: int = 0,
) -> AuditLogListResponse:
    """
    Returns paginated audit log for the tenant.
    Optionally filter by action type.
    Records are immutable — no delete or update is exposed.
    """
    store = CosmosStore()
    action_filter = action.value if action else None
    logs = await store.list_audit(
        tenant_id=user.tenant_id,
        limit=min(limit, 500),
        offset=offset,
        action_filter=action_filter,
    )
    total = await store.count_audit(tenant_id=user.tenant_id, action_filter=action_filter)
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=offset // max(limit, 1),
        page_size=limit,
    )
