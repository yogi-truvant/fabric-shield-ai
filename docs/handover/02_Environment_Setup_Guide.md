# FabricShield AI — Environment Setup Guide
**For:** Amritha | **Time to complete:** ~4 hours (first time)

---

## Prerequisites

Install these on your VM before starting:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | https://python.org/downloads |
| Node.js | 20 LTS | https://nodejs.org |
| Azure CLI | Latest | `winget install Microsoft.AzureCLI` or https://aka.ms/installazurecli |
| Git | Latest | https://git-scm.com |
| VS Code | Latest | https://code.visualstudio.com |
| ODBC Driver 18 | — | https://aka.ms/downloadmsodbcsql (required for pyodbc) |

**VS Code Extensions to install:**
- Python (Microsoft)
- Pylance
- ES7+ React/Redux/React-Native snippets
- Bicep (Microsoft)
- Azure Tools (Microsoft)
- REST Client (Huachao Mao) — for testing APIs without Postman

---

## Step 1: Clone the Repo

```bash
git clone https://github.com/YOUR_ORG/fabricshield-ai.git
cd fabricshield-ai
```

---

## Step 2: Azure App Registration (One-time, ~30 min)

This is the most important setup step. FabricShield uses Entra ID for auth.

### 2a. Create the App Registration

1. Go to **Azure Portal** → **Entra ID** → **App registrations** → **New registration**
2. Name: `FabricShield AI`
3. Supported account types: **"Accounts in any organizational directory (Multi-tenant)"**
4. Redirect URI: `Single-page application (SPA)` → `http://localhost:5173` (Vite dev server)
5. Click **Register**

### 2b. Configure the App

After creation:

1. **Add another redirect URI** (for Azure App Service):
   - Go to **Authentication** → add `https://your-frontend-app.azurewebsites.net`

2. **Expose an API:**
   - Go to **Expose an API** → **Set Application ID URI** → Accept the default `api://{client_id}`
   - Add scope: Name = `access_as_user`, Who can consent = `Admins and users`, display name = `Access FabricShield`

3. **Add App Roles:**
   Go to **App roles** → **Create app role** for each:
   | Display Name | Value | Description | Allowed member types |
   |---|---|---|---|
   | Admin | Admin | Full access | Users/Groups |
   | Approver | Approver | Approve + mask | Users/Groups |
   | Analyst | Analyst | Scan + view | Users/Groups |
   | Viewer | Viewer | Dashboard only | Users/Groups |

4. **Create a Client Secret:**
   - Go to **Certificates & secrets** → **New client secret**
   - Description: `fabricshield-prod`, Expires: 24 months
   - **Copy the value immediately** — you can't see it again

5. Note down:
   - **Application (client) ID** → this is `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → this is `AZURE_TENANT_ID`
   - **Client secret value** → this is `AZURE_CLIENT_SECRET`

### 2c. Assign yourself a role

1. Go to **Enterprise applications** → find `FabricShield AI` → **Users and groups**
2. Add your user → assign **Admin** role

---

## Step 3: Set Up Azure Resources

### Option A: Full deploy with the script (recommended)

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh \
  --subscription "YOUR_SUBSCRIPTION_ID" \
  --tenant "YOUR_TENANT_ID" \
  --resource-group "rg-fabricshield-dev" \
  --location "eastus2" \
  --client-id "YOUR_CLIENT_ID" \
  --client-secret "YOUR_CLIENT_SECRET" \
  --environment dev
```

This creates: App Service plan, 2 App Services (backend + frontend), Cosmos DB, Key Vault, Storage Account, App Insights.

### Option B: Manual (if you want to understand each resource)

```bash
# Login
az login

# Create resource group
az group create --name rg-fabricshield-dev --location eastus2

# Deploy Bicep
az deployment group create \
  --resource-group rg-fabricshield-dev \
  --template-file infra/main.bicep \
  --parameters environment=dev serviceTenantId=YOUR_TENANT_ID clientId=YOUR_CLIENT_ID clientSecret=YOUR_CLIENT_SECRET
```

---

## Step 4: Create a Test Azure SQL Database

You need a test database with fake PII data to run scans against.

```bash
# Create SQL Server (Managed Identity auth)
az sql server create \
  --name fabricshield-test-sql \
  --resource-group rg-fabricshield-dev \
  --location eastus2 \
  --enable-ad-only-auth \
  --external-admin-principal-type User \
  --external-admin-name "YOUR_EMAIL" \
  --external-admin-sid "YOUR_USER_OBJECT_ID"

# Create test database
az sql db create \
  --resource-group rg-fabricshield-dev \
  --server fabricshield-test-sql \
  --name FabricShieldTestDB \
  --service-objective Basic
```

Then run the seed script to create PII test data:
```bash
# Connect with Azure Data Studio or sqlcmd and run:
sqlcmd -S fabricshield-test-sql.database.windows.net -d FabricShieldTestDB -G -Q "$(cat deploy/seed_test_data.sql)"
```

Store the connection info in Key Vault:
```bash
KV_NAME=$(az keyvault list -g rg-fabricshield-dev --query "[0].name" -o tsv)
az keyvault secret set --vault-name $KV_NAME --name "tenant-YOUR_TENANT_ID-testdb-server" --value "fabricshield-test-sql.database.windows.net"
az keyvault secret set --vault-name $KV_NAME --name "tenant-YOUR_TENANT_ID-testdb-database" --value "FabricShieldTestDB"
```

Grant the backend App Service MSI access to the SQL Server:
```bash
BACKEND_APP=$(az webapp list -g rg-fabricshield-dev --query "[?contains(name,'api')].name" -o tsv)
MSI_OID=$(az webapp identity show -g rg-fabricshield-dev -n $BACKEND_APP --query principalId -o tsv)

# In Azure Data Studio / SSMS, run as SQL Admin:
# CREATE USER [<backend-app-name>] FROM EXTERNAL PROVIDER;
# ALTER ROLE db_datareader ADD MEMBER [<backend-app-name>];
# ALTER ROLE db_ddladmin ADD MEMBER [<backend-app-name>]; -- needed for DDM
```

---

## Step 5: Local Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model (700MB — do this once)
python -m spacy download en_core_web_lg

# Create .env file for local dev
cp .env.example .env
# Edit .env with your values (see below)
```

**`.env` for local development:**
```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

AZURE_CLIENT_ID=your-client-id-here
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
JWT_AUDIENCE=api://your-client-id-here

# Cosmos DB — use Cosmos Emulator for local dev
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_USE_MANAGED_IDENTITY=false
COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMcZeThbBd9pLfTQ==

# Key Vault — not needed for local dev
KEYVAULT_URL=

# CORS — Vite dev server
CORS_ORIGINS=http://localhost:5173
```

**Start the Cosmos Emulator (for local dev):**
Download from: https://aka.ms/cosmosdb-emulator
Start it, then create the `fabricshield` database and 4 containers manually in the Emulator UI (Data Explorer at https://localhost:8081/_explorer).

**Run the backend:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Test it:
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"1.0.0","environment":"development"}
```

**Run unit tests:**
```bash
pytest tests/ -v
# Expected: 16 tests, all passing
```

---

## Step 6: Local Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create local .env
cp .env.example .env.development.local
```

**`.env.development.local`:**
```env
VITE_AZURE_CLIENT_ID=your-client-id-here
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_REDIRECT_URI=http://localhost:5173
```

**Create the missing files (P1-3 from done_vs_pending):**

Create `frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FabricShield AI</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/index.jsx"></script>
  </body>
</html>
```

Create `frontend/vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})
```

**Start the frontend:**
```bash
npm run dev
```

Open: http://localhost:5173

You should see the FabricShield login page. Click "Sign in with Microsoft" and sign in with your Azure account.

---

## Step 7: Configure GitHub Actions Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |
| `AZURE_TENANT_ID` | Your Entra ID tenant ID |
| `AZURE_CLIENT_ID` | App Registration client ID |
| `AZURE_CLIENT_SECRET` | App Registration client secret |
| `AZURE_RESOURCE_GROUP` | `rg-fabricshield-dev` (or prod) |
| `AZURE_CLIENT_ID_DEPLOYER` | Client ID of a service principal with Contributor role (for OIDC deploy) |

For OIDC deployments (recommended), configure federated credentials on the deployer service principal pointing to your GitHub repo.

---

## Step 8: Verify End-to-End

Once everything is running, do this quick smoke test:

1. ✅ Open `http://localhost:5173` — see login page
2. ✅ Sign in with Microsoft — reach Dashboard
3. ✅ Dashboard shows KPI cards (zeros are fine if no data)
4. ✅ Navigate to Scan page — form visible
5. ✅ Enter `testdb` as connection name, `dbo` as schema, click Scan
6. ✅ Scan appears in "Running" state, transitions to "Completed"
7. ✅ Navigate to Approvals — see flagged columns
8. ✅ Select columns, click Approve
9. ✅ Click Mask on an approved column
10. ✅ Navigate to Audit — see log entries for scan + approval + masking

If all 10 check out — congratulations, you have a working FabricShield instance! 🎉

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ODBC Driver not found` | ODBC Driver 18 not installed | Install from https://aka.ms/downloadmsodbcsql |
| `Token validation failed: Invalid issuer` | JWT_AUDIENCE doesn't match app reg | Set `JWT_AUDIENCE=api://YOUR_CLIENT_ID` |
| `CosmosHttpResponseError 401` | `COSMOS_USE_MANAGED_IDENTITY=true` but running locally | Set to `false` locally, use emulator key |
| `spacy.errors.E050: Can't find model 'en_core_web_lg'` | Model not downloaded | Run `python -m spacy download en_core_web_lg` |
| `MSAL login loop` | Redirect URI not registered | Add `http://localhost:5173` to App Registration redirect URIs |
| `CORS error in browser` | `CORS_ORIGINS` doesn't include frontend URL | Add `http://localhost:5173` to `CORS_ORIGINS` in `.env` |
| Vite `Cannot find module 'react'` | `npm install` not run | Run `npm install` in `frontend/` |
| `KeyVault access denied` | MSI not assigned KV Secrets User role | Check RBAC assignment in Azure Portal |
