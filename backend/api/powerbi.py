"""
FabricShield AI — Power BI Embedded Token API
Issues secure embed tokens for tenant-specific Power BI dashboards.
Uses Row-Level Security (RLS) to isolate tenant data within shared datasets.
"""

import structlog
from datetime import datetime
from typing import Annotated

import httpx
import msal
from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.entra import RequireViewer, get_current_user
from backend.config import get_settings
from backend.models.schemas import PowerBIEmbedResponse, UserContext

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

POWER_BI_SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


def _get_service_principal_token() -> str:
    """
    Acquire access token for Power BI REST API using our app's service principal.
    Uses client credentials flow (app-only, not on behalf of user).
    """
    app = msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=f"{settings.entra_authority}/{settings.azure_tenant_id}",
    )
    result = app.acquire_token_for_client(scopes=POWER_BI_SCOPE)
    if "access_token" not in result:
        error = result.get("error_description", "Unknown MSAL error")
        logger.error("powerbi.token_acquisition_failed", error=error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to acquire Power BI token",
        )
    return result["access_token"]


async def _generate_embed_token(
    sp_token: str,
    workspace_id: str,
    report_id: str,
    dataset_id: str,
    rls_username: str,
    rls_roles: list,
) -> dict:
    """
    Call Power BI GenerateTokenInGroup REST API to get an embed token.
    Embeds RLS so tenant only sees their own data in the shared dataset.
    """
    url = f"{POWER_BI_API_BASE}/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    payload = {
        "accessLevel": "View",
        "datasetId": dataset_id,
        "allowSaveAs": False,
        "identities": [
            {
                "username": rls_username,
                "roles": rls_roles,
                "datasets": [dataset_id],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {sp_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        logger.error(
            "powerbi.generate_token_failed",
            status=response.status_code,
            body=response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Power BI token generation failed",
        )
    return response.json()


async def _get_embed_url(sp_token: str, workspace_id: str, report_id: str) -> str:
    """Fetch the report embed URL from Power BI API."""
    url = f"{POWER_BI_API_BASE}/groups/{workspace_id}/reports/{report_id}"
    headers = {"Authorization": f"Bearer {sp_token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to fetch Power BI report metadata",
        )
    return response.json()["embedUrl"]


@router.get(
    "/powerbi/token",
    response_model=PowerBIEmbedResponse,
    summary="Get Power BI embed token for the tenant dashboard",
    dependencies=[RequireViewer],
)
async def get_embed_token(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> PowerBIEmbedResponse:
    """
    Returns a short-lived Power BI embed token scoped to the tenant via RLS.
    The frontend PowerBIEmbed component uses this to render the dashboard.
    Token expires in ~1 hour; frontend should re-fetch before expiry.
    """
    if not settings.powerbi_workspace_id or not settings.powerbi_report_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Power BI is not configured for this deployment",
        )

    sp_token = _get_service_principal_token()

    embed_url, token_data = await __import__("asyncio").gather(
        _get_embed_url(sp_token, settings.powerbi_workspace_id, settings.powerbi_report_id),
        _generate_embed_token(
            sp_token=sp_token,
            workspace_id=settings.powerbi_workspace_id,
            report_id=settings.powerbi_report_id,
            dataset_id=settings.powerbi_dataset_id,
            rls_username=user.tenant_id,    # RLS username = tenant_id
            rls_roles=["TenantViewer"],     # RLS role configured in Power BI dataset
        ),
    )

    return PowerBIEmbedResponse(
        embed_url=embed_url,
        access_token=token_data["token"],
        token_id=token_data["tokenId"],
        expiration=datetime.fromisoformat(
            token_data["expiration"].replace("Z", "+00:00")
        ),
        report_id=settings.powerbi_report_id,
        workspace_id=settings.powerbi_workspace_id,
    )
