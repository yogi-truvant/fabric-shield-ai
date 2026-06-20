"""
FabricShield AI — Cosmos DB Storage Layer
Provides async CRUD operations over scan results, approvals, audit logs, and tenant config.
Uses partition key = tenant_id throughout for multi-tenant isolation.
"""

import structlog
from typing import List, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity.aio import DefaultAzureCredential

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
                credential = DefaultAzureCredential()
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
        query = """
        SELECT c.status, COUNT(1) as cnt
        FROM c WHERE c.tenant_id = @tid
        GROUP BY c.status
        """
        counts = {}
        async for item in self._container(settings.cosmos_container_approvals).query_items(
            query=query, parameters=[{"name": "@tid", "value": tenant_id}]
        ):
            counts[item["status"]] = item["cnt"]
        return counts

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
