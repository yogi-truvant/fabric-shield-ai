# FabricShield AI — Enterprise PII/PHI Governance Platform

> Production-ready, multi-tenant SaaS governance platform for Azure SQL & Microsoft Fabric.  
> Azure Marketplace–enabled · HIPAA-aligned · Powered by Microsoft Presidio + Azure Purview.

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TENANT (Browser)                                   │
│  React + MUI  ──MSAL──►  Azure AD (Entra ID multi-tenant)                   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │  JWT (Bearer)
                    ┌───────────▼────────────┐
                    │   Azure App Service     │
                    │   FastAPI Backend       │
                    │   (Managed Identity)    │
                    └──┬──────┬──────┬───────┘
                       │      │      │
           ┌───────────▼─┐  ┌─▼──────▼──────────┐  ┌──────────────────┐
           │  Azure SQL  │  │  Microsoft Fabric   │  │   Cosmos DB      │
           │  Database   │  │  (SQL Endpoint)     │  │  (workflow state)│
           └─────────────┘  └────────────────────┘  └──────────────────┘
                       │                                      │
           ┌───────────▼──────────────────────────────────────▼──────────┐
           │              Core Engine                                      │
           │  pii_engine.py   masking_engine.py   audit.py               │
           │  db_connector.py  (Presidio + rules)  (App Insights)        │
           └───────────────────────────┬──────────────────────────────────┘
                                       │
            ┌──────────────────────────▼──────────────────────────────┐
            │               Azure Services                             │
            │  Key Vault · Purview · Power BI · App Insights           │
            └─────────────────────────────────────────────────────────┘
```

## 🗂 Repository Structure

```
fabricshield-ai/
├── backend/
│   ├── main.py                    # FastAPI entrypoint
│   ├── config.py                  # Settings (Pydantic BaseSettings)
│   ├── requirements.txt
│   ├── auth/
│   │   ├── entra.py               # JWT validation, RBAC middleware
│   │   └── roles.py               # Role definitions + decorators
│   ├── api/
│   │   ├── scan.py                # POST /scan
│   │   ├── approvals.py           # GET/POST /approvals, /approve
│   │   ├── audit.py               # GET /audit
│   │   └── powerbi.py             # GET /powerbi/token
│   ├── core/
│   │   ├── pii_engine.py          # Hybrid PII detection (Presidio + rules)
│   │   ├── db_connector.py        # Azure SQL + Fabric connections
│   │   ├── masking_engine.py      # Dynamic Data Masking (DDM)
│   │   └── audit.py               # Audit log writer (Cosmos + App Insights)
│   ├── marketplace/
│   │   └── fulfillment.py         # Azure Marketplace SaaS Fulfillment v2
│   ├── governance/
│   │   └── purview.py             # Microsoft Purview classification push
│   ├── models/
│   │   └── schemas.py             # Pydantic request/response models
│   └── tests/
│       ├── test_pii_engine.py
│       └── test_masking_engine.py
├── frontend/
│   ├── package.json
│   ├── .env.example
│   └── src/
│       ├── App.jsx
│       ├── index.jsx
│       ├── theme.js               # Material UI enterprise theme
│       ├── auth/
│       │   └── msalConfig.js      # MSAL multi-tenant config
│       ├── components/
│       │   ├── Layout.jsx         # Nav + sidebar
│       │   └── RoleGuard.jsx      # RBAC component wrapper
│       ├── pages/
│       │   ├── Dashboard.jsx      # Power BI embed + KPIs
│       │   ├── Scan.jsx           # Scan trigger UI
│       │   ├── Approvals.jsx      # Data grid with bulk approve
│       │   └── Audit.jsx          # Audit log viewer
│       ├── services/
│       │   └── api.js             # Axios client with token injection
│       └── hooks/
│           └── useRole.js         # RBAC hook
├── infra/
│   ├── main.bicep                 # Root Bicep template
│   ├── parameters.json
│   └── modules/
│       ├── appservice.bicep
│       ├── cosmos.bicep
│       ├── keyvault.bicep
│       └── monitoring.bicep
├── deploy/
│   ├── deploy.sh                  # One-click bash deploy
│   └── azuredeploy.json           # ARM template for "Deploy to Azure" button
├── .github/
│   └── workflows/
│       └── ci-cd.yml              # GitHub Actions pipeline
└── docs/
    ├── architecture.md
    └── pricing.md
```

## 🚀 Quick Deploy

```bash
# One-click deploy
chmod +x deploy/deploy.sh
./deploy/deploy.sh \
  --subscription "your-subscription-id" \
  --tenant "your-tenant-id" \
  --resource-group "rg-fabricshield-prod" \
  --location "eastus2"
```

Or use the **Deploy to Azure** button:

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fyourorg%2Ffabricshield-ai%2Fmain%2Fdeploy%2Fazuredeploy.json)

## 🔐 Security

- All secrets in Azure Key Vault — never in code
- Managed Identity for all Azure service connections
- Entra ID multi-tenant authentication + group-based RBAC
- HTTPS enforced at App Service level
- Cosmos DB firewall restricted to App Service outbound IPs

## 📋 Requirements

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI |
| Frontend | Node 18+, React 18, MUI v5 |
| IaC | Azure Bicep / ARM |
| Auth | Entra ID (MSAL) |
| PII Detection | Microsoft Presidio 2.x |
| Storage | Azure Cosmos DB (NoSQL) |
| Monitoring | Azure Application Insights |

## 📄 License

MIT — See LICENSE for details.
