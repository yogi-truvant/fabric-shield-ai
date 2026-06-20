"""
FabricShield AI — Azure Marketplace SaaS Fulfillment API v2
Implements the required webhook + subscription endpoints for Azure Marketplace listing.
Reference: https://docs.microsoft.com/en-us/azure/marketplace/partner-center-portal/pc-saas-fulfillment-api-v2
"""

import hashlib
import hmac
import structlog
from datetime import datetime, timezone
from typing import Optional

import httpx
import msal
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from backend.config import get_settings
from backend.models.schemas import (
    MarketplaceActivateRequest,
    MarketplacePlan,
    MarketplaceResolveRequest,
    MarketplaceWebhookPayload,
    TenantConfig,
)
from backend.storage.cosmos_store import CosmosStore

logger = structlog.get_logger(__name__)
settings = get_settings()
marketplace_router = APIRouter()

MARKETPLACE_API_BASE = "https://marketplaceapi.microsoft.com/api/saas"
MARKETPLACE_API_VERSION = "2018-08-31"
MARKETPLACE_SCOPE = ["20e940b3-4c77-4b0b-9a53-9e16a1b010a7/.default"]

# Plan → resource limits mapping
PLAN_LIMITS = {
    MarketplacePlan.starter: {"max_databases": 2, "max_scans_per_month": 30},
    MarketplacePlan.growth: {"max_databases": 10, "max_scans_per_month": 200},
    MarketplacePlan.enterprise: {"max_databases": 100, "max_scans_per_month": 5000},
}


def _get_marketplace_token() -> str:
    """Acquire token for Marketplace Fulfillment API."""
    app = msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=f"{settings.entra_authority}/{settings.azure_tenant_id}",
    )
    result = app.acquire_token_for_client(scopes=MARKETPLACE_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Marketplace token failed: {result.get('error_description')}")
    return result["access_token"]


def _verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature on incoming Marketplace webhook.
    Azure sends X-Ms-Signature header.
    """
    if not settings.marketplace_webhook_secret:
        if settings.environment == "production":
            logger.error("marketplace.webhook_secret_missing")
            return False  # Fail closed in production
        logger.warning("marketplace.no_webhook_secret_configured")
        return True  # Dev only

    expected = hmac.new(
        settings.marketplace_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


async def _provision_tenant(
    subscription_id: str,
    plan_id: str,
    purchaser_tenant_id: str,
    purchaser_email: str,
) -> TenantConfig:
    """Create or update a TenantConfig record in Cosmos DB for the new subscriber."""
    store = CosmosStore()

    try:
        plan = MarketplacePlan(plan_id.lower())
    except ValueError:
        plan = MarketplacePlan.starter
        logger.warning("marketplace.unknown_plan", plan_id=plan_id)

    limits = PLAN_LIMITS[plan]

    config = TenantConfig(
        tenant_id=purchaser_tenant_id,
        company_name=purchaser_email.split("@")[-1] if "@" in purchaser_email else "Unknown",
        subscription_id=subscription_id,
        plan=plan,
        activated_at=datetime.now(timezone.utc),
        is_active=True,
        admin_email=purchaser_email,
        max_databases=limits["max_databases"],
        max_scans_per_month=limits["max_scans_per_month"],
    )

    await store.upsert_tenant(config)
    logger.info(
        "marketplace.tenant_provisioned",
        tenant_id=purchaser_tenant_id,
        plan=plan.value,
        subscription_id=subscription_id,
    )
    return config


async def _deprovision_tenant(subscription_id: str) -> None:
    """Mark a subscriber inactive (Unsubscribe/Suspend). Resolved by subscription id."""
    store = CosmosStore()
    config = await store.get_tenant_by_subscription(subscription_id)
    if config:
        config.is_active = False
        config.deactivated_at = datetime.now(timezone.utc)
        await store.upsert_tenant(config)
        logger.info("marketplace.tenant_deprovisioned",
                    tenant_id=config.tenant_id, subscription_id=subscription_id)
    else:
        logger.warning("marketplace.deprovision_no_tenant", subscription_id=subscription_id)

async def _reactivate_tenant(subscription_id: str) -> None:
    """Reactivate a previously provisioned subscriber (Reinstate)."""
    store = CosmosStore()
    config = await store.get_tenant_by_subscription(subscription_id)
    if config:
        config.is_active = True
        config.deactivated_at = None
        await store.upsert_tenant(config)
        logger.info("marketplace.tenant_reactivated",
                    tenant_id=config.tenant_id, subscription_id=subscription_id)
    else:
        logger.warning("marketplace.reactivate_no_tenant", subscription_id=subscription_id)

async def _ack_operation(subscription_id: str, operation_id: str,
                         plan_id=None, quantity=None) -> None:
    """PATCH the operation to Success — required to complete async ops."""
    body = {"status": "Success"}
    if plan_id:
        body["planId"] = plan_id
    if quantity is not None:
        body["quantity"] = quantity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(
                f"{MARKETPLACE_API_BASE}/subscriptions/{subscription_id}/operations/{operation_id}",
                json=body,
                headers={"Authorization": f"Bearer {_get_marketplace_token()}"},
                params={"api-version": MARKETPLACE_API_VERSION},
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("marketplace.ack_failed", subscription_id=subscription_id, error=str(exc))


# ─── Landing Page ─────────────────────────────────────────────────────────────

@marketplace_router.get("/landing", summary="SaaS Landing Page redirect")
async def landing_page(token: str):
    """
    Azure Marketplace redirects here after purchase with a short-lived token.
    We redirect to the frontend which resolves and activates the subscription.
    """
    frontend_url = settings.marketplace_landing_page_url or "https://app.fabricshield.io"
    return RedirectResponse(url=f"{frontend_url}/activate?token={token}")


# ─── Resolve ──────────────────────────────────────────────────────────────────

@marketplace_router.post("/resolve", summary="Resolve Marketplace subscription token")
async def resolve_subscription(request: MarketplaceResolveRequest):
    """
    Exchange the short-lived marketplace token for subscription details.
    Called by our frontend's activation flow.
    """
    token = _get_marketplace_token()
    url = f"{MARKETPLACE_API_BASE}/subscriptions/resolve"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-marketplace-token": request.marketplace_token,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, params={"api-version": MARKETPLACE_API_VERSION})

    if resp.status_code not in (200, 201):
        logger.error("marketplace.resolve_failed", status=resp.status_code, body=resp.text[:300])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token resolution failed: {resp.text[:200]}",
        )

    data = resp.json()
    return {
        "subscription_id": data.get("id"),
        "subscription_name": data.get("subscriptionName"),
        "offer_id": data.get("offerId"),
        "plan_id": data.get("planId"),
        "quantity": data.get("quantity"),
        "purchaser": data.get("purchaser"),
        "beneficiary": data.get("beneficiary"),
    }


# ─── Activate ─────────────────────────────────────────────────────────────────

@marketplace_router.post("/activate", summary="Activate Marketplace subscription")
async def activate_subscription(
    request: MarketplaceActivateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Activate a resolved subscription. Called after the user completes
    the landing page flow.
    """
    token = _get_marketplace_token()

    # 1) RESOLVE — authoritative subscription + beneficiary tenant (never trust the client).
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{MARKETPLACE_API_BASE}/subscriptions/resolve",
            headers={"Authorization": f"Bearer {token}",
                     "x-ms-marketplace-token": request.marketplace_token,
                     "Content-Type": "application/json"},
            params={"api-version": MARKETPLACE_API_VERSION},
        )
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Token resolution failed: {r.text[:200]}")
    sub = r.json()
    subscription_id = sub["id"]
    plan_id = sub["planId"]
    beneficiary = sub.get("beneficiary") or {}
    purchaser_tenant_id = beneficiary.get("tenantId", "")
    purchaser_email = beneficiary.get("emailId", "")

    # 2) ACTIVATE
    payload = {"planId": plan_id}
    if sub.get("quantity"):
        payload["quantity"] = str(sub["quantity"])
    async with httpx.AsyncClient(timeout=15.0) as client:
        a = await client.post(
            f"{MARKETPLACE_API_BASE}/subscriptions/{subscription_id}/activate",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            params={"api-version": MARKETPLACE_API_VERSION},
        )
    if a.status_code not in (200, 202):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Activation failed: {a.text[:200]}")

    # 3) PROVISION with the REAL beneficiary tenant
    background_tasks.add_task(
        _provision_tenant,
        subscription_id=subscription_id,
        plan_id=plan_id,
        purchaser_tenant_id=purchaser_tenant_id,
        purchaser_email=purchaser_email,
    )
    return {"status": "activated", "subscription_id": subscription_id,
            "tenant_id": purchaser_tenant_id}


# ─── Webhook ──────────────────────────────────────────────────────────────────

@marketplace_router.post("/webhook", summary="Azure Marketplace operation webhook")
async def marketplace_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_ms_signature: Optional[str] = Header(None),
):
    """
    Receives async operation notifications from Azure Marketplace.
    Supported actions: Activate, Unsubscribe, ChangePlan, ChangeQuantity, Suspend, Reinstate
    """
    body = await request.body()

    if not _verify_webhook_signature(body, x_ms_signature or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = MarketplaceWebhookPayload.model_validate_json(body)
    logger.info(
        "marketplace.webhook_received",
        action=payload.action,
        subscription_id=payload.subscription_id,
        plan_id=payload.plan_id,
    )

    if payload.action in ("Unsubscribe", "Suspend"):
        background_tasks.add_task(_deprovision_tenant, subscription_id=payload.subscription_id)

    elif payload.action == "Reinstate":
        background_tasks.add_task(_reactivate_tenant, subscription_id=payload.subscription_id)

    elif payload.action in ("ChangePlan", "ChangeQuantity"):
        store = CosmosStore()
        config = await store.get_tenant_by_subscription(payload.subscription_id)
        if config:
            try:
                config.plan = MarketplacePlan(payload.plan_id.lower())
                limits = PLAN_LIMITS[config.plan]
                config.max_databases = limits["max_databases"]
                config.max_scans_per_month = limits["max_scans_per_month"]
                await store.upsert_tenant(config)
            except ValueError:
                logger.warning("marketplace.unknown_plan_change", plan_id=payload.plan_id)

    # ACK the async operation (Azure requires the operation be PATCHed to Success).
    background_tasks.add_task(
        _ack_operation, payload.subscription_id, payload.id,
        payload.plan_id, payload.quantity,
    )
    return {"status": "acknowledged", "activity_id": payload.activity_id}
