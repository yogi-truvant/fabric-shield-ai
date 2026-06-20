"""
FabricShield AI — Entra ID (Azure AD) JWT Authentication
Validates tokens issued by any Entra ID tenant (multi-tenant app).
Extracts user context including roles from app role assignments.
"""

import logging
from typing import Annotated, List, Optional

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    from jose import JWTError, jwt
except ImportError:
    raise ImportError("Install python-jose[cryptography]")

from backend.config import get_settings
from backend.models.schemas import UserContext, UserRole

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=True)

# JWKS cache: 1 hour TTL, keyed by tenant_id
_jwks_cache: TTLCache = TTLCache(maxsize=50, ttl=3600)


def _get_jwks(tenant_id: str) -> dict:
    """Fetch JWKS from the tenant's OpenID Connect well-known endpoint."""
    cache_key = f"jwks:{tenant_id}"
    if cache_key in _jwks_cache:
        return _jwks_cache[cache_key]

    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        keys = response.json()
        _jwks_cache[cache_key] = keys
        return keys
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS for tenant %s: %s", tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable — cannot validate token",
        )


def _get_signing_key(token: str, tenant_id: str):
    """Extract the correct signing key for the token's kid header."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token header: {exc}",
        )

    jwks = _get_jwks(tenant_id)
    kid = header.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    # Key not found — may be stale cache; invalidate and retry once
    cache_key = f"jwks:{tenant_id}"
    _jwks_cache.pop(cache_key, None)
    jwks = _get_jwks(tenant_id)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find signing key for token",
    )


def _extract_roles(claims: dict) -> List[UserRole]:
    """
    Map Entra ID app roles to internal UserRole enum.
    App roles are configured in the App Registration manifest.
    Expected role values: "Viewer", "Analyst", "Approver", "Admin"
    """
    raw_roles: List[str] = claims.get("roles", [])
    role_map = {
        "Viewer": UserRole.viewer,
        "Analyst": UserRole.analyst,
        "Approver": UserRole.approver,
        "Admin": UserRole.admin,
    }
    mapped = [role_map[r] for r in raw_roles if r in role_map]
    # Default: if no roles assigned, treat as viewer
    return mapped if mapped else [UserRole.viewer]


def validate_token(token: str) -> UserContext:
    """
    Full JWT validation:
    1. Decode header to get tid (tenant_id) and kid
    2. Fetch JWKS for that tenant
    3. Verify signature, expiry, audience, issuer
    4. Extract user context
    """
    settings = get_settings()

    # Step 1: decode without verification to extract tenant_id from claims
    try:
        unverified = jwt.get_unverified_claims(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Malformed token: {exc}",
        )

    tenant_id: Optional[str] = unverified.get("tid")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing tenant identifier (tid)",
        )

    # Step 2: Check tenant is allowed
    allowed = settings.allowed_tenant_list
    if allowed and tenant_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not registered with FabricShield",
        )

    # Step 3: Get signing key
    signing_key = _get_signing_key(token, tenant_id)

    # Step 4: Verify signature + standard claims
    expected_issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
    audience = settings.jwt_audience or settings.azure_client_id

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=expected_issuer,
            options={"verify_exp": True, "verify_iat": True},
        )
    except JWTError as exc:
        logger.warning("Token validation failed for tenant %s: %s", tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        oid=claims["oid"],
        email=claims.get("preferred_username") or claims.get("email"),
        name=claims.get("name"),
        tenant_id=tenant_id,
        roles=_extract_roles(claims),
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    request: Request,
) -> UserContext:
    """FastAPI dependency — inject this to get the authenticated user."""
    user = validate_token(credentials.credentials)
    # Attach to request state for middleware/logging
    request.state.user = user
    return user


# ─── Role-Based Dependencies ──────────────────────────────────────────────────

def require_roles(*roles: UserRole):
    """
    Factory that returns a FastAPI dependency enforcing one of the given roles.

    Usage:
        @router.get("/scan", dependencies=[Depends(require_roles(UserRole.analyst, UserRole.admin))])
    """
    async def _dependency(user: Annotated[UserContext, Depends(get_current_user)]) -> UserContext:
        if not user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[r.value for r in roles]}",
            )
        return user
    return _dependency


# Convenience singletons
RequireViewer = Depends(require_roles(UserRole.viewer, UserRole.analyst, UserRole.approver, UserRole.admin))
RequireAnalyst = Depends(require_roles(UserRole.analyst, UserRole.approver, UserRole.admin))
RequireApprover = Depends(require_roles(UserRole.approver, UserRole.admin))
RequireAdmin = Depends(require_roles(UserRole.admin))
