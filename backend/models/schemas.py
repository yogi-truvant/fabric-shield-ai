"""
FabricShield AI — Pydantic Schemas
All request/response models used across the API surface.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class DatabaseType(str, Enum):
    azure_sql = "azure_sql"
    fabric = "fabric"


class DetectionSource(str, Enum):
    rule = "rule"
    ml = "ml"
    both = "both"


class PiiEntityType(str, Enum):
    SSN = "SSN"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    CREDIT_CARD = "CREDIT_CARD"
    IBAN = "IBAN"
    IP_ADDRESS = "IP_ADDRESS"
    PERSON_NAME = "PERSON_NAME"
    LOCATION = "LOCATION"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    NPI = "NPI"
    DEA = "DEA"
    PHI_GENERIC = "PHI_GENERIC"
    CUSTOM = "CUSTOM"


class ApprovalStatus(str, Enum):
    pending = "PENDING"
    approved = "APPROVED"
    rejected = "REJECTED"
    masked = "MASKED"
    masking_failed = "MASKING_FAILED"


class MaskType(str, Enum):
    default = "default"
    email = "email"
    partial = "partial"
    random = "random"


class UserRole(str, Enum):
    viewer = "viewer"
    analyst = "analyst"
    approver = "approver"
    admin = "admin"
    system = "system"


class AuditAction(str, Enum):
    scan_started = "scan.started"
    scan_completed = "scan.completed"
    scan_failed = "scan.failed"
    approval_submitted = "approval.submitted"
    masking_applied = "masking.applied"
    masking_failed = "masking.failed"
    purview_push = "purview.classification_pushed"
    tenant_provisioned = "marketplace.tenant_provisioned"
    tenant_deprovisioned = "marketplace.tenant_deprovisioned"


# ─── Shared Base ─────────────────────────────────────────────────────────────

class TenantAwareBase(BaseModel):
    tenant_id: str = Field(..., description="Entra ID tenant GUID of the customer")


# ─── Scan ────────────────────────────────────────────────────────────────────

class ScanRequest(TenantAwareBase):
    database_type: DatabaseType
    connection_name: str = Field(..., description="Friendly name / Key Vault secret prefix")
    schema_names: List[str] = Field(default=["dbo"], description="DB schemas to scan")
    include_tables: Optional[List[str]] = Field(None, description="Allowlist of table names")
    exclude_tables: Optional[List[str]] = Field(None, description="Denylist of table names")


class PiiColumnResult(BaseModel):
    column_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    database_type: DatabaseType
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    entity_type: PiiEntityType
    confidence: float = Field(..., ge=0.0, le=1.0)
    detection_source: DetectionSource
    recommended_mask: MaskType


class ScanResult(TenantAwareBase):
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connection_name: str
    database_type: DatabaseType
    schemas_scanned: List[str]
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running | completed | failed
    pii_columns: List[PiiColumnResult] = []
    error: Optional[str] = None
    triggered_by: str = ""  # OID of user who triggered scan


class ScanResponse(BaseModel):
    scan_id: str
    status: str
    message: str


# ─── Approvals ───────────────────────────────────────────────────────────────

class ApprovalRecord(TenantAwareBase):
    approval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scan_id: str
    column_id: str
    schema_name: str
    table_name: str
    column_name: str
    entity_type: PiiEntityType
    confidence: float
    detection_source: DetectionSource
    recommended_mask: MaskType
    connection_name: str = ""            # which DB connection the mask runs against
    data_type: str = "varchar"           # real column type — drives the DDM function
    database_type: DatabaseType = DatabaseType.azure_sql
    status: ApprovalStatus = ApprovalStatus.pending
    approved_by: Optional[str] = None       # OID of approver
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    masked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BulkApprovalRequest(TenantAwareBase):
    approval_ids: List[str] = Field(..., min_length=1, max_length=500)
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: Optional[str] = None


class BulkApprovalResponse(BaseModel):
    processed: int
    succeeded: int
    failed: int
    errors: List[Dict[str, str]] = []


# ─── Masking ─────────────────────────────────────────────────────────────────

class MaskingRequest(TenantAwareBase):
    approval_id: str
    column_id: str
    mask_type: MaskType
    partial_prefix_size: Optional[int] = Field(None, ge=0, le=10)
    partial_suffix: Optional[str] = None
    partial_suffix_size: Optional[int] = Field(None, ge=0, le=10)


class MaskingResult(BaseModel):
    approval_id: str
    column_id: str
    success: bool
    ddl_executed: Optional[str] = None
    error: Optional[str] = None
    masked_at: Optional[datetime] = None


# ─── Audit ───────────────────────────────────────────────────────────────────

class AuditLog(TenantAwareBase):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: AuditAction
    actor_oid: str
    actor_email: Optional[str] = None
    resource_id: Optional[str] = None       # scan_id, approval_id, etc.
    details: Dict[str, Any] = {}
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None


class AuditLogListResponse(BaseModel):
    logs: List[AuditLog]
    total: int
    page: int
    page_size: int


# ─── Power BI ────────────────────────────────────────────────────────────────

class PowerBIEmbedResponse(BaseModel):
    embed_url: str
    access_token: str
    token_id: str
    expiration: datetime
    report_id: str
    workspace_id: str


# ─── Marketplace ─────────────────────────────────────────────────────────────

class MarketplacePlan(str, Enum):
    starter = "starter"
    growth = "growth"
    enterprise = "enterprise"


class TenantConfig(BaseModel):
    tenant_id: str
    company_name: str
    subscription_id: str                    # Azure Marketplace subscription ID
    plan: MarketplacePlan
    activated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    is_active: bool = True
    admin_email: str
    max_databases: int = 5                  # Plan limits
    max_scans_per_month: int = 100
    metered_scan_count: int = 0


class MarketplaceResolveRequest(BaseModel):
    marketplace_token: str


class MarketplaceActivateRequest(BaseModel):
    # Resolve-first: the server resolves this token to the authoritative subscription,
    # plan, and beneficiary tenant. Never trust a client-supplied tenant id.
    marketplace_token: str


class MarketplaceWebhookPayload(BaseModel):
    # Azure sends camelCase; accept by alias and by field name.
    model_config = ConfigDict(populate_by_name=True)
    id: str                                 # operation id (used to ACK the operation)
    activity_id: str = Field(alias="activityId")
    subscription_id: str = Field(alias="subscriptionId")
    offer_id: str = Field(alias="offerId")
    publisher_id: str = Field(alias="publisherId")
    plan_id: str = Field(alias="planId")
    quantity: Optional[int] = None
    status: Optional[str] = None
    action: str                             # Activate|Unsubscribe|ChangePlan|ChangeQuantity|Suspend|Reinstate


# ─── Connections (data source registry) ───────────────────────────────────────

class ConnectionAuthMode(str, Enum):
    service_principal = "service_principal"   # cross-tenant Entra token, no stored creds
    sql = "sql"                               # SQL login + password (stored in Key Vault)


class ConnectionCreateRequest(TenantAwareBase):
    name: str = Field(..., pattern=r"^[a-zA-Z0-9-]{1,40}$", description="Connection key (KV-safe)")
    server: str = Field(..., description="e.g. myserver.database.windows.net")
    database: str
    database_type: DatabaseType = DatabaseType.azure_sql
    auth_mode: ConnectionAuthMode = ConnectionAuthMode.service_principal
    sql_username: Optional[str] = None
    sql_password: Optional[str] = None


class ConnectionInfo(BaseModel):
    name: str
    server: str
    database: str
    database_type: DatabaseType = DatabaseType.azure_sql
    auth_mode: ConnectionAuthMode = ConnectionAuthMode.service_principal
    sql_username: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    table_count: Optional[int] = None


# ─── User Context (injected by auth middleware) ───────────────────────────────

class UserContext(BaseModel):
    oid: str                                # Object ID from JWT
    email: Optional[str] = None
    name: Optional[str] = None
    tenant_id: str
    roles: List[UserRole] = []

    def has_role(self, *roles: UserRole) -> bool:
        return any(r in self.roles for r in roles)

    def require_role(self, *roles: UserRole) -> None:
        from fastapi import HTTPException, status
        if not self.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {[r.value for r in roles]}",
            )
