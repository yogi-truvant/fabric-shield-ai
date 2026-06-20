"""
FabricShield AI — Application Configuration
All settings resolved from environment variables (injected by App Service / Key Vault refs).
Never hardcode secrets. All sensitive values must come from Azure Key Vault references.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "FabricShield AI"
    app_version: str = "1.0.0"
    environment: str = "production"  # development | staging | production
    debug: bool = False
    log_level: str = "INFO"

    # ── Entra ID (Azure AD) ──────────────────────────────────────────────────
    # Multi-tenant app registration
    azure_client_id: str                     # App Registration client ID
    azure_tenant_id: str                     # Our service tenant (for token validation issuer list)
    azure_client_secret: str                 # Key Vault ref: @Microsoft.KeyVault(...)
    entra_authority: str = "https://login.microsoftonline.com"
    # Comma-separated list of allowed customer tenant IDs (or "any" for open multi-tenant)
    allowed_tenant_ids: str = "any"
    # JWT audience = our App Registration's Application ID URI
    jwt_audience: str = ""                   # e.g. api://fabricshield-prod

    @property
    def allowed_tenant_list(self) -> List[str]:
        if self.allowed_tenant_ids == "any":
            return []
        return [t.strip() for t in self.allowed_tenant_ids.split(",")]

    # ── Cosmos DB ────────────────────────────────────────────────────────────
    cosmos_endpoint: str                     # https://<account>.documents.azure.com:443/
    cosmos_key: str = ""                          # Key Vault ref — or use Managed Identity
    cosmos_database: str = "fabricshield"
    cosmos_use_managed_identity: bool = True # When True, cosmos_key is ignored

    # Container names
    cosmos_container_scans: str = "scan_results"
    cosmos_container_approvals: str = "approvals"
    cosmos_container_audit: str = "audit_logs"
    cosmos_container_tenants: str = "tenant_config"

    # ── Key Vault ────────────────────────────────────────────────────────────
    keyvault_url: str = ""                   # https://<vault>.vault.azure.net/

    # ── Power BI ─────────────────────────────────────────────────────────────
    powerbi_workspace_id: str = ""           # Power BI workspace / group ID
    powerbi_report_id: str = ""             # Report ID to embed
    powerbi_dataset_id: str = ""            # Dataset ID for RLS token

    # ── Microsoft Purview ────────────────────────────────────────────────────
    purview_endpoint: str = ""              # https://<account>.purview.azure.com
    purview_collection: str = ""            # Purview collection name

    # ── Azure Marketplace ────────────────────────────────────────────────────
    marketplace_landing_page_url: str = ""
    marketplace_webhook_secret: str = ""    # HMAC secret to validate webhook POSTs

    # ── Application Insights ─────────────────────────────────────────────────
    applicationinsights_connection_string: str = ""

    # ── PII Engine ───────────────────────────────────────────────────────────
    pii_confidence_threshold: float = 0.6  # Minimum confidence to flag

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "https://app.fabricshield.io"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton — call get_settings() everywhere, not Settings()."""
    return Settings()
