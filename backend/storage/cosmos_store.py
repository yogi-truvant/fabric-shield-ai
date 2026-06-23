"""
FabricShield AI — Cosmos DB Storage Layer
Provides async CRUD operations over scan results, approvals, audit logs, and tenant config.
Uses partition key = tenant_id throughout for multi-tenant isolation.
"""

import structlog
from typing import List, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity.aio import ManagedIdentityCredential

from backend.config import get_settings
from backend.models.schemas import (
    ApprovalRecord,
    ApprovalStatus,
    AuditLog,
    ScanResult,
    TenantConfig,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


class CosmosStore:
    """
    Async Cosmos DB client wrapper.
    Uses Managed Identity when cosmos_use_managed_identity is True.
    All containers use tenant_id as partition key.
    """

    _client: Optional[CosmosClient] = None

    def _get_client(self) -> CosmosClient:
        if CosmosStore._client is None:
            if settings.cosmos_use_managed_identity:
                credential = ManagedIdentityCredential()
                CosmosStore._client = CosmosClient(
                    url=settings.cosmos_endpoint,
                    credential=credential,
                )
            else:
                CosmosStore._client = CosmosClient(
                    url=settings.cosmos_endpoint,
                    credential=settings.cosmos_key,
                )
        return CosmosStore._client

    def _container(self, name: str):
        return (
            self._get_client()
            .get_database_client(settings.cosmos_database)
            .get_container_client(name)
        )

    # ── Scans ─────────────────────────────────────────────────────────────────

    async def upsert_scan(self, scan: ScanResult) -> None:
        item = scan.model_dump(mode="json")
        item["id"] = scan.scan_id
        await self._container(settings.cosmos_container_scans).upsert_item(item)

    async def count_scans_since(self, tenant_id: str, since_iso: str) -> int:
        """Count scans started on/after an ISO timestamp (used for monthly plan limits)."""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid AND c.started_at >= @since"
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@since", "value": since_iso},
        ]
        async for value in self._container(settings.cosmos_container_scans).query_items(
            query=query, parameters=params
        ):
            return int(value)
        return 0

    async def delete_scans_for_connection(
        self, tenant_id: str, connection_name: Optional[str] = None
    ) -> int:
        """Delete scan records — for one connection, or ALL of the tenant's if name is None
        (full reset when the last connection is removed)."""
        if connection_name:
            query = "SELECT c.id FROM c WHERE c.tenant_id = @tid AND c.connection_name = @conn"
            params = [
                {"name": "@tid", "value": tenant_id},
                {"name": "@conn", "value": connection_name},
            ]
        else:
            query = "SELECT c.id FROM c WHERE c.tenant_id = @tid"
            params = [{"name": "@tid", "value": tenant_id}]
        container = self._container(settings.cosmos_container_scans)
        ids = [item["id"] async for item in container.query_items(query=query, parameters=params)]
        for _id in ids:
            await container.delete_item(item=_id, partition_key=tenant_id)
        return len(ids)

    async def delete_orphan_approvals(self, tenant_id: str, live_connections: List[str]) -> int:
        """Delete approval records that belong to no live connection (null/empty/stale
        connection_name). Keeps the dashboard honest after a connection is removed."""
        return await self._delete_orphans(settings.cosmos_container_approvals, tenant_id, live_connections)

    async def delete_orphan_scans(self, tenant_id: str, live_connections: List[str]) -> int:
        """Delete scan records that belong to no live connection."""
        return await self._delete_orphans(settings.cosmos_container_scans, tenant_id, live_connections)

    async def _delete_orphans(self, container_name: str, tenant_id: str, live_connections: List[str]) -> int:
        container = self._container(container_name)
        ids: List[str] = []
        async for item in container.query_items(
            query="SELECT c.id, c.connection_name FROM c WHERE c.tenant_id = @tid",
            parameters=[{"name": "@tid", "value": tenant_id}],
        ):
            conn = item.get("connection_name")
            if not conn or conn not in live_connections:
                ids.append(item["id"])
        for _id in ids:
            await container.delete_item(item=_id, partition_key=tenant_id)
        return len(ids)

    async def get_scan(self, tenant_id: str, scan_id: str) -> Optional[ScanResult]:
        try:
            item = await self._container(settings.cosmos_container_scans).read_item(
                item=scan_id, partition_key=tenant_id
            )
            return ScanResult(**item)
        except CosmosHttpResponseError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def list_scans(self, tenant_id: str, limit: int = 20) -> List[ScanResult]:
        query = (
            "SELECT * FROM c WHERE c.tenant_id = @tid "
            "ORDER BY c.started_at DESC OFFSET 0 LIMIT @limit"
        )
        items = []
        async for item in self._container(settings.cosmos_container_scans).query_items(
            query=query,
            parameters=[
                {"name": "@tid", "value": tenant_id},
                {"name": "@limit", "value": limit},
            ],
        ):
            items.append(ScanResult(**item))
        return items

    # ── Approvals ─────────────────────────────────────────────────────────────

    async def upsert_approval(self, approval: ApprovalRecord) -> None:
        item = approval.model_dump(mode="json")
        item["id"] = approval.approval_id
        await self._container(settings.cosmos_container_approvals).upsert_item(item)

    async def get_approval(self, tenant_id: str, approval_id: str) -> Optional[ApprovalRecord]:
        try:
            item = await self._container(settings.cosmos_container_approvals).read_item(
                item=approval_id, partition_key=tenant_id
            )
            return ApprovalRecord(**item)
        except CosmosHttpResponseError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def list_approvals(
        self,
        tenant_id: str,
        status_filter: Optional[ApprovalStatus] = None,
        scan_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[ApprovalRecord]:
        conditions = ["c.tenant_id = @tid"]
        params = [{"name": "@tid", "value": tenant_id}]

        if status_filter:
            conditions.append("c.status = @status")
            params.append({"name": "@status", "value": status_filter.value})

        if scan_id:
            conditions.append("c.scan_id = @scan_id")
            params.append({"name": "@scan_id", "value": scan_id})

        where = " AND ".join(conditions)
        query = (
            f"SELECT * FROM c WHERE {where} "
            f"ORDER BY c.created_at DESC OFFSET {offset} LIMIT {limit}"
        )

        items = []
        async for item in self._container(settings.cosmos_container_approvals).query_items(
            query=query, parameters=params
        ):
            items.append(ApprovalRecord(**item))
        return items

    async def count_approvals_by_status(self, tenant_id: str) -> dict:
        """Counts per status for the KPI dashboard.

        Uses a targeted COUNT per status rather than GROUP BY: Cosmos GROUP BY can return
        empty under some query plans / continuation handling, which silently zeroed the
        dashboard tiles. SELECT VALUE COUNT(1) always returns exactly one number."""
        container = self._container(settings.cosmos_container_approvals)
        counts: dict = {}
        for status in ApprovalStatus:
            query = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid AND c.status = @s"
            params = [
                {"name": "@tid", "value": tenant_id},
                {"name": "@s", "value": status.value},
            ]
            counts[status.value] = 0
            async for value in container.query_items(query=query, parameters=params):
                counts[status.value] = int(value)
        return counts

    async def delete_pending_approvals(self, tenant_id: str, connection_name: str) -> int:
        """Remove still-PENDING approvals for a connection so a re-scan supersedes them
        instead of accumulating. Approved/rejected/masked records are preserved for audit."""
        query = (
            "SELECT c.id FROM c WHERE c.tenant_id = @tid "
            "AND c.connection_name = @conn AND c.status = @pending"
        )
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@conn", "value": connection_name},
            {"name": "@pending", "value": ApprovalStatus.pending.value},
        ]
        container = self._container(settings.cosmos_container_approvals)
        ids = [item["id"] async for item in container.query_items(query=query, parameters=params)]
        for _id in ids:
            await container.delete_item(item=_id, partition_key=tenant_id)
        return len(ids)

    async def list_all_approvals_for_connection(
        self, tenant_id: str, connection_name: str
    ) -> List[ApprovalRecord]:
        """All approvals (any status) for a connection — used to reconcile a re-scan."""
        query = "SELECT * FROM c WHERE c.tenant_id = @tid AND c.connection_name = @conn"
        params = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@conn", "value": connection_name},
        ]
        items = []
        async for item in self._container(settings.cosmos_container_approvals).query_items(
            query=query, parameters=params
        ):
            items.append(ApprovalRecord(**item))
        return items

    async def delete_approval(self, tenant_id: str, approval_id: str) -> None:
        """Delete a single approval by id (partitioned by tenant)."""
        try:
            await self._container(settings.cosmos_container_approvals).delete_item(
                item=approval_id, partition_key=tenant_id
            )
        except CosmosHttpResponseError as exc:
            if exc.status_code != 404:
                raise

    async def delete_all_approvals_for_connection(
        self, tenant_id: str, connection_name: Optional[str] = None
    ) -> int:
        """Clear approvals — for one connection, or all of the tenant's if name is None."""
        if connection_name:
            query = "SELECT c.id FROM c WHERE c.tenant_id = @tid AND c.connection_name = @conn"
            params = [
                {"name": "@tid", "value": tenant_id},
                {"name": "@conn", "value": connection_name},
            ]
        else:
            query = "SELECT c.id FROM c WHERE c.tenant_id = @tid"
            params = [{"name": "@tid", "value": tenant_id}]
        container = self._container(settings.cosmos_container_approvals)
        ids = [item["id"] async for item in container.query_items(query=query, parameters=params)]
        for _id in ids:
            await container.delete_item(item=_id, partition_key=tenant_id)
        return len(ids)

    # ── Audit Logs ────────────────────────────────────────────────────────────

    async def append_audit(self, entry: AuditLog) -> None:
        """Append-only audit log. Never update or delete audit records."""
        item = entry.model_dump(mode="json")
        item["id"] = entry.log_id
        # Use create_item (not upsert) to enforce immutability
        await self._container(settings.cosmos_container_audit).create_item(item)

    async def list_audit(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None,
    ) -> List[AuditLog]:
        conditions = ["c.tenant_id = @tid"]
        params = [{"name": "@tid", "value": tenant_id}]

        if action_filter:
            conditions.append("c.action = @action")
            params.append({"name": "@action", "value": action_filter})

        where = " AND ".join(conditions)
        query = (
            f"SELECT * FROM c WHERE {where} "
            f"ORDER BY c.timestamp DESC OFFSET {offset} LIMIT {limit}"
        )

        items = []
        async for item in self._container(settings.cosmos_container_audit).query_items(
            query=query, parameters=params
        ):
            items.append(AuditLog(**item))
        return items

    async def count_audit(self, tenant_id: str, action_filter: Optional[str] = None) -> int:
        """Total audit records for the tenant (for accurate pagination), independent of page size."""
        conditions = ["c.tenant_id = @tid"]
        params = [{"name": "@tid", "value": tenant_id}]
        if action_filter:
            conditions.append("c.action = @action")
            params.append({"name": "@action", "value": action_filter})
        where = " AND ".join(conditions)
        query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        async for value in self._container(settings.cosmos_container_audit).query_items(
            query=query, parameters=params
        ):
            return int(value)
        return 0

    # ── Tenant Config ─────────────────────────────────────────────────────────

    async def upsert_tenant(self, config: TenantConfig) -> None:
        item = config.model_dump(mode="json")
        item["id"] = config.tenant_id
        await self._container(settings.cosmos_container_tenants).upsert_item(item)

    async def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        try:
            item = await self._container(settings.cosmos_container_tenants).read_item(
                item=tenant_id, partition_key=tenant_id
            )
            return TenantConfig(**item)
        except CosmosHttpResponseError as exc:
            if exc.status_code == 404:
                return None
            raise

    async def get_tenant_by_subscription(
        self, subscription_id: str
    ) -> Optional[TenantConfig]:
        """Resolve a tenant from a Marketplace subscription id (cross-partition query).
        Used by the webhook, which only carries subscription_id."""
        query = "SELECT * FROM c WHERE c.subscription_id = @sub"
        params = [{"name": "@sub", "value": subscription_id}]
        async for item in self._container(settings.cosmos_container_tenants).query_items(
            query=query, parameters=params
        ):
            return TenantConfig(**item)
        return None
