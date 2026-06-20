"""
FabricShield AI — Audit Logger
Writes immutable audit records to Cosmos DB and Application Insights.
All operations that touch PII data must call audit.log().
"""

import logging

import structlog
from datetime import datetime, timezone
from typing import Any, Dict, Optional


from backend.config import get_settings
from backend.models.schemas import AuditAction, AuditLog, UserContext

logger = structlog.get_logger(__name__)
# Dedicated stdlib logger so App Insights AzureLogHandler receives custom_dimensions.
_telemetry_logger = logging.getLogger("fabricshield.audit.telemetry")
settings = get_settings()


class AuditLogger:
    """
    Dual-sink audit logger: Cosmos DB (durable, queryable) + App Insights (telemetry).
    Methods are async to avoid blocking the request path.
    """

    def __init__(self):
        self._store = None  # Lazy import to avoid circular deps

    def _get_store(self):
        if self._store is None:
            from backend.storage.cosmos_store import CosmosStore
            self._store = CosmosStore()
        return self._store

    async def log(
        self,
        action: AuditAction,
        actor: UserContext,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """
        Write an audit log entry.
        Always returns the AuditLog regardless of sink failures (best-effort telemetry).
        """
        entry = AuditLog(
            tenant_id=actor.tenant_id,
            action=action,
            actor_oid=actor.oid,
            actor_email=actor.email,
            resource_id=resource_id,
            details=details or {},
            success=success,
            error_message=error_message,
            timestamp=datetime.now(timezone.utc),
            ip_address=ip_address,
        )

        # Sink 1: Cosmos DB (durable, queryable by compliance teams)
        try:
            await self._get_store().append_audit(entry)
        except Exception as exc:
            logger.error("audit.cosmos_write_failed", log_id=entry.log_id, error=str(exc))

        # Sink 2: Application Insights (custom event for alerting/dashboards)
        try:
            self._emit_telemetry(entry)
        except Exception as exc:
            logger.warning("audit.telemetry_failed", log_id=entry.log_id, error=str(exc))

        return entry

    def _emit_telemetry(self, entry: AuditLog) -> None:
        """Emit structured event to Application Insights via standard logger."""
        log_method = _telemetry_logger.info if entry.success else _telemetry_logger.warning
        log_method(
            entry.action.value,
            extra={
                "custom_dimensions": {
                    "tenant_id": entry.tenant_id,
                    "actor_oid": entry.actor_oid,
                    "actor_email": entry.actor_email or "",
                    "resource_id": entry.resource_id or "",
                    "success": str(entry.success),
                    **{f"detail_{k}": str(v) for k, v in entry.details.items()},
                }
            },
        )
