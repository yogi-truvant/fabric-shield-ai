#!/usr/bin/env bash
# ============================================================================
# FabricShield AI — One-Click Azure Deployment Script
# ============================================================================
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh \
#     --subscription "your-subscription-id" \
#     --tenant "your-tenant-id" \
#     --resource-group "rg-fabricshield-prod" \
#     --location "eastus2" \
#     --client-id "your-app-reg-client-id" \
#     --client-secret "your-app-reg-client-secret"
# ============================================================================
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
SUBSCRIPTION=""
TENANT_ID=""
RESOURCE_GROUP="rg-fabricshield-prod"
LOCATION="eastus2"
CLIENT_ID=""
CLIENT_SECRET=""
ENVIRONMENT="prod"
DEPLOY_BACKEND=true
DEPLOY_FRONTEND=true
DEPLOY_INFRA=true
WORKERS=2          # uvicorn workers — sized for Basic/B1 (1 vCPU, 1.75GB). Each worker
                   # lazily loads the spaCy model (~250MB), so keep low on small SKUs.
                   # Raise (e.g. --workers 4) on PremiumV3 / multi-core plans.

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --subscription)     SUBSCRIPTION="$2"; shift 2 ;;
    --tenant)           TENANT_ID="$2"; shift 2 ;;
    --resource-group)   RESOURCE_GROUP="$2"; shift 2 ;;
    --location)         LOCATION="$2"; shift 2 ;;
    --client-id)        CLIENT_ID="$2"; shift 2 ;;
    --client-secret)    CLIENT_SECRET="$2"; shift 2 ;;
    --environment)      ENVIRONMENT="$2"; shift 2 ;;
    --skip-infra)       DEPLOY_INFRA=false; shift ;;
    --skip-backend)     DEPLOY_BACKEND=false; shift ;;
    --skip-frontend)    DEPLOY_FRONTEND=false; shift ;;
    --workers)          WORKERS="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Validate required ────────────────────────────────────────────────────────
for var in SUBSCRIPTION TENANT_ID CLIENT_ID CLIENT_SECRET; do
  if [[ -z "${!var}" ]]; then
    echo "ERROR: --${var//_/-} is required"
    exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo " FabricShield AI — Deployment"
echo " Environment : $ENVIRONMENT"
echo " Subscription: $SUBSCRIPTION"
echo " Resource Grp: $RESOURCE_GROUP"
echo " Location    : $LOCATION"
echo "============================================"

# ── 1. Check Azure CLI ────────────────────────────────────────────────────────
echo ""
echo "[ 1/7 ] Checking Azure CLI..."
if ! command -v az &>/dev/null; then
  echo "ERROR: Azure CLI not found. Install from https://aka.ms/installazurecli"
  exit 1
fi

az account set --subscription "$SUBSCRIPTION"
echo "      Using subscription: $(az account show --query name -o tsv)"

# ── 2. Create Resource Group ──────────────────────────────────────────────────
echo ""
echo "[ 2/7 ] Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags "app=fabricshield" "environment=$ENVIRONMENT" \
  --output none
echo "      Resource group ready."

# ── 3. Deploy Infrastructure (Bicep) ─────────────────────────────────────────
if $DEPLOY_INFRA; then
  echo ""
  echo "[ 3/7 ] Deploying infrastructure (Bicep)..."
  DEPLOY_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$ROOT_DIR/infra/main.bicep" \
    --parameters \
      environment="$ENVIRONMENT" \
      location="$LOCATION" \
      serviceTenantId="$TENANT_ID" \
      clientId="$CLIENT_ID" \
      clientSecret="$CLIENT_SECRET" \
    --output json)

  # Parse all Bicep outputs in a single python pass (one process, not five).
  eval "$(echo "$DEPLOY_OUTPUT" | python3 -c '
import sys, json
o = json.load(sys.stdin)["properties"]["outputs"]
b = o["backendUrl"]["value"]
f = o["frontendUrl"]["value"]
kv = o["keyVaultName"]["value"]
host = lambda u: u.split("//")[-1].split(".")[0]
print("BACKEND_URL=" + b)
print("FRONTEND_URL=" + f)
print("BACKEND_APP_NAME=" + host(b))
print("FRONTEND_APP_NAME=" + host(f))
print("KV_NAME=" + kv)
')"

  echo "      Backend:  $BACKEND_URL"
  echo "      Frontend: $FRONTEND_URL"
else
  echo ""
  echo "[ 3/7 ] Skipping infrastructure deployment."
  # Try to infer from existing deployment
  BACKEND_APP_NAME=$(az webapp list -g "$RESOURCE_GROUP" --query "[?contains(name,'api')].name" -o tsv | head -1)
  FRONTEND_APP_NAME=$(az webapp list -g "$RESOURCE_GROUP" --query "[?contains(name,'ui')].name" -o tsv | head -1)
fi

# ── 4. Store secrets in Key Vault (RBAC vault — grant deployer data-plane first) ─
if $DEPLOY_INFRA; then
  echo ""
  echo "[ 4/7 ] Granting Key Vault access + storing secrets in '$KV_NAME'..."
  ME=$(az ad signed-in-user show --query id -o tsv)
  KV_ID="/subscriptions/$SUBSCRIPTION/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KV_NAME"
  az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
    --role "Key Vault Secrets Officer" --scope "$KV_ID" --output none 2>/dev/null || true
  echo "      Waiting for RBAC propagation (can take a minute)..."
  STORED=false
  for i in $(seq 1 12); do
    if az keyvault secret set --vault-name "$KV_NAME" --name "azure-client-secret" \
         --value "$CLIENT_SECRET" --output none 2>/dev/null; then STORED=true; break; fi
    echo "      retry $i/12 (RBAC not propagated yet)..."; sleep 20
  done
  if ! $STORED; then
    echo "ERROR: could not write to Key Vault. You likely lack Owner/User Access Administrator"
    echo "       on the resource group (needed to grant yourself Key Vault Secrets Officer)."
    exit 1
  fi
  az keyvault secret set --vault-name "$KV_NAME" --name "marketplace-webhook-secret" \
    --value "$(openssl rand -hex 32)" --output none
  echo "      Secrets stored."
fi

# ── 5. Build & Deploy Backend ─────────────────────────────────────────────────
if $DEPLOY_BACKEND; then
  echo ""
  echo "[ 5/7 ] Building and deploying backend..."
  cd "$ROOT_DIR"

  # No local pip install: App Service builds deps server-side (Oryx, SCM_DO_BUILD_DURING_DEPLOYMENT).
  # Package from repo root so `backend` is an importable package + Oryx finds requirements.txt
  zip -r /tmp/app.zip backend requirements.txt -x "*.pyc" "**/__pycache__/*" "backend/tests/*" "**/.venv/*"

  az webapp deploy \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BACKEND_APP_NAME" \
    --src-path /tmp/app.zip \
    --type zip \
    --async false

  # Set startup command
  az webapp config set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BACKEND_APP_NAME" \
    --startup-file "uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers $WORKERS" \
    --output none

  echo "      Backend deployed to: https://$BACKEND_APP_NAME.azurewebsites.net"
fi

# ── 6. Build & Deploy Frontend ────────────────────────────────────────────────
if $DEPLOY_FRONTEND; then
  echo ""
  echo "[ 6/7 ] Building and deploying frontend..."
  cd "$ROOT_DIR/frontend"

  # Create .env for build
  cat > .env.production << EOF
VITE_AZURE_CLIENT_ID=$CLIENT_ID
VITE_API_BASE_URL=https://$BACKEND_APP_NAME.azurewebsites.net/api/v1
VITE_REDIRECT_URI=https://$FRONTEND_APP_NAME.azurewebsites.net
EOF

  # Reproducible install when a lockfile exists; fall back to install otherwise.
  if [[ -f package-lock.json ]]; then npm ci --silent; else npm install --silent; fi
  npm run build

  # Deploy dist/ as static site
  cd dist
  zip -r /tmp/frontend.zip .

  az webapp deploy \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FRONTEND_APP_NAME" \
    --src-path /tmp/frontend.zip \
    --type zip \
    --async false

  # Serve the built SPA with history-API fallback
  az webapp config set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FRONTEND_APP_NAME" \
    --startup-file "pm2 serve /home/site/wwwroot 8080 --no-daemon --spa" \
    --output none

  echo "      Frontend deployed to: https://$FRONTEND_APP_NAME.azurewebsites.net"
  cd "$ROOT_DIR"
fi

# ── 7. Post-deployment ────────────────────────────────────────────────────────
echo ""
echo "[ 7/7 ] Post-deployment checks..."
# Cold start (incl. server-side pip build + first spaCy load) can take a minute+,
# so poll instead of a single early check.
HEALTH_URL="https://$BACKEND_APP_NAME.azurewebsites.net/health"
HEALTH_OK=false
for i in $(seq 1 10); do
  HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || echo "000")
  if [[ "$HEALTH_STATUS" == "200" ]]; then HEALTH_OK=true; break; fi
  echo "      health attempt $i/10: HTTP $HEALTH_STATUS (warming up)..."; sleep 15
done
if $HEALTH_OK; then
  echo "      ✅ Backend health check: PASSED"
else
  echo "      ⚠️  Backend still not healthy after ~2.5 min — check the log stream:"
  echo "         az webapp log tail -g $RESOURCE_GROUP -n $BACKEND_APP_NAME"
fi

echo ""
echo "============================================"
echo " 🎉 Deployment Complete!"
echo "============================================"
echo " Frontend : https://$FRONTEND_APP_NAME.azurewebsites.net"
echo " Backend  : https://$BACKEND_APP_NAME.azurewebsites.net"
echo " API Docs : https://$BACKEND_APP_NAME.azurewebsites.net/api/docs"
echo "            (only in dev/staging environments)"
echo ""
echo " Next steps:"
echo "   1. Configure Entra ID App Registration redirect URIs"
echo "   2. Add customer tenant connection strings to Key Vault"
echo "   3. Register Azure Marketplace offer (Partner Center)"
echo "   4. Configure Power BI workspace + report IDs"
echo "============================================"
