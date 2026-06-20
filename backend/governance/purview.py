"""
FabricShield AI — Microsoft Purview Integration
Pushes PII/PHI classifications to Purview for enterprise data catalog governance.
Uses the Purview Atlas REST API with Managed Identity auth.
"""

import structlog
from typing import Optional

import httpx
from azure.identity.aio import DefaultAzureCredential

from backend.config import get_settings
from backend.models.schemas import PiiEntityType
from fastapi import APIRouter

logger = structlog.get_logger(__name__)
settings = get_settings()
purview_router = APIRouter()

# Purview custom classification type prefix
CLASSIFICATION_PREFIX = "FabricShield"

# Map internal entity types to Purview system classification names
PURVIEW_CLASSIFICATION_MAP = {
    PiiEntityType.SSN: "MICROSOFT.PERSONAL.US.SSN",
    PiiEntityType.EMAIL: "MICROSOFT.PERSONAL.EMAIL",
    PiiEntityType.PHONE: "MICROSOFT.PERSONAL.PHONENUMBER",
    PiiEntityType.DATE_OF_BIRTH: "MICROSOFT.PERSONAL.DATE.BIRTHDAY",
    PiiEntityType.CREDIT_CARD: "MICROSOFT.FINANCIAL.CREDIT_CARD_NUMBER",
    PiiEntityType.IBAN: "MICROSOFT.FINANCIAL.BANK_ACCOUNT_NUMBER",
    PiiEntityType.IP_ADDRESS: "MICROSOFT.PERSONAL.IPADDRESS",
    PiiEntityType.PERSON_NAME: "MICROSOFT.PERSONAL.NAME",
    PiiEntityType.LOCATION: "MICROSOFT.PERSONAL.PHYSICALADDRESS",
    PiiEntityType.MEDICAL_RECORD: "MICROSOFT.HEALTH.MEDICAL_RECORD_NUMBER",
    PiiEntityType.NPI: "MICROSOFT.HEALTH.NPI",
    PiiEntityType.DEA: "MICROSOFT.HEALTH.DEA_NUMBER",
    PiiEntityType.PHI_GENERIC: f"{CLASSIFICATION_PREFIX}.PHI",
    PiiEntityType.CUSTOM: f"{CLASSIFICATION_PREFIX}.CUSTOM_PII",
}


class PurviewClient:
    """
    Client for Microsoft Purview Atlas REST API.
    Pushes column-level classifications after masking is applied.
    """

    def __init__(self):
        self._credential = DefaultAzureCredential()
        self._endpoint = settings.purview_endpoint.rstrip("/")

    async def _get_token(self) -> str:
        token = await self._credential.get_token(
            "https://purview.azure.net/.default"
        )
        return token.token

    async def push_classification(
        self,
        schema: str,
        table: str,
        column: str,
        entity_type: PiiEntityType,
        tenant_id: str,
        qualified_name: Optional[str] = None,
    ) -> bool:
        """
        Push a classification to a column entity in Purview.
        Returns True on success.

        Note: This assumes the data source is already registered in Purview.
        The qualifiedName must match the Purview asset's qualified name.
        """
        if not self._endpoint:
            logger.warning("purview.not_configured")
            return False

        classification_name = PURVIEW_CLASSIFICATION_MAP.get(
            entity_type, f"{CLASSIFICATION_PREFIX}.PII"
        )

        # Build qualified name if not provided
        if not qualified_name:
            qualified_name = f"mssql://{schema}/{table}/{column}"

        # Atlas API: Add classification to entity
        url = f"{self._endpoint}/catalog/api/atlas/v2/entity/uniqueAttribute/type/azure_sql_column"

        payload = {
            "classifications": [
                {
                    "typeName": classification_name,
                    "attributes": {
                        "source": "FabricShield AI",
                        "tenant_id": tenant_id,
                        "confidence": "high",
                    },
                }
            ]
        }

        try:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"attr:qualifiedName": qualified_name},
                )

            if resp.status_code in (200, 204):
                logger.info(
                    "purview.classification_pushed",
                    schema=schema, table=table, column=column,
                    classification=classification_name,
                )
                return True
            else:
                logger.warning(
                    "purview.classification_failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                )
                return False

        except Exception as exc:
            logger.error("purview.push_error", error=str(exc))
            return False

    async def list_classifications(self, qualified_name: str) -> list:
        """List existing classifications on a Purview entity."""
        if not self._endpoint:
            return []

        url = f"{self._endpoint}/catalog/api/atlas/v2/entity/uniqueAttribute/type/azure_sql_column"
        try:
            token = await self._get_token()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"attr:qualifiedName": qualified_name},
                )
            if resp.status_code == 200:
                entity = resp.json()
                return entity.get("entity", {}).get("classifications", [])
        except Exception as exc:
            logger.warning("purview.list_error", error=str(exc))
        return []


# ─── Purview API Routes ───────────────────────────────────────────────────────

@purview_router.get("/governance/classifications", summary="List Purview classification types")
async def list_classification_types():
    """Returns the classification types FabricShield uses in Purview."""
    return {
        "classification_prefix": CLASSIFICATION_PREFIX,
        "mappings": {
            entity_type.value: classification
            for entity_type, classification in PURVIEW_CLASSIFICATION_MAP.items()
        },
    }
