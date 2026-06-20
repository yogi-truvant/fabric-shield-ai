# FabricShield AI — Done vs Pending Tracker
**Last updated:** June 2026 | **Owner:** Amritha (SDE Intern Engineer)

> **Legend:** ✅ Done & tested | 🟡 Built but untested | 🔴 Not built | 🔵 Stretch goal

---

## PART 1: WHAT'S DONE (Built)

### Backend — Core Engine

| Feature | Status | File | Notes |
|---------|--------|------|-------|
| FastAPI app structure + middleware | 🟡 | `backend/main.py` | Security headers, CORS, request tracing all wired up. Needs live test. |
| Pydantic settings (env-based config) | 🟡 | `backend/config.py` | All settings defined. Needs `.env` populated to test. |
| Entra ID multi-tenant JWT validation | 🟡 | `backend/auth/entra.py` | JWKS fetching with TTL cache. Needs real tokens to verify. |
| RBAC role extraction from JWT | 🟡 | `backend/auth/entra.py` | 4 roles: viewer/analyst/approver/admin. |
| All Pydantic schemas | ✅ | `backend/models/schemas.py` | Fully typed request/response models. |
| Azure SQL + Fabric DB connector (MSI) | 🟡 | `backend/core/db_connector.py` | MSI token struct built. Needs real Azure SQL to test. |
| PII rule-based detection (13 patterns) | ✅ | `backend/core/pii_engine.py` | Unit tested. Covers SSN, email, phone, DOB, MRN, NPI, DEA, credit card, IBAN, IP, address, PHI. |
| PII Presidio ML detection | 🟡 | `backend/core/pii_engine.py` | Code written. Needs spaCy model downloaded + integration test. |
| Confidence score merging (rule + ML) | ✅ | `backend/core/pii_engine.py` | Unit tested. Boost logic when both agree. |
| DDM SQL builder (masking engine) | ✅ | `backend/core/masking_engine.py` | Unit tested. `default()`, `email()`, `partial()`, `random()`. |
| DDM apply + verify + drop | 🟡 | `backend/core/masking_engine.py` | Needs live Azure SQL to test. |
| Audit logger (dual-sink) | 🟡 | `backend/core/audit.py` | Cosmos + App Insights. Needs Cosmos to test. |
| Cosmos DB storage layer (all containers) | 🟡 | `backend/storage/cosmos_store.py` | Full CRUD for scans, approvals, audit, tenants. Needs real Cosmos. |

### Backend — API Layer

| Feature | Status | File | Notes |
|---------|--------|------|-------|
| `POST /scan` — trigger scan | 🟡 | `backend/api/scan.py` | Background task + polling. Needs DB connection. |
| `GET /scan/{id}` — poll scan status | 🟡 | `backend/api/scan.py` | Tenant-isolated. |
| `GET /scans` — list recent scans | 🟡 | `backend/api/scan.py` | |
| `GET /approvals` — list + filter | 🟡 | `backend/api/approvals.py` | Status filter, pagination. |
| `POST /approvals/bulk` — bulk approve/reject | 🟡 | `backend/api/approvals.py` | |
| `POST /approvals/{id}/mask` — apply DDM | 🟡 | `backend/api/approvals.py` | Triggers masking + Purview push. |
| `GET /approvals/stats` — KPI counts | 🟡 | `backend/api/approvals.py` | Used by dashboard. |
| `GET /audit` — audit log | 🟡 | `backend/api/audit.py` | |
| `GET /powerbi/token` — embed token | 🟡 | `backend/api/powerbi.py` | Needs Power BI workspace configured. |
| `GET /health` — health check | 🟡 | `backend/main.py` | |
| Marketplace: `/resolve` | 🟡 | `backend/marketplace/fulfillment.py` | Needs Marketplace listing. |
| Marketplace: `/activate` | 🟡 | `backend/marketplace/fulfillment.py` | |
| Marketplace: `/webhook` | 🟡 | `backend/marketplace/fulfillment.py` | |
| Purview classification push | 🟡 | `backend/governance/purview.py` | Needs Purview account. |

### Frontend

| Feature | Status | File | Notes |
|---------|--------|------|-------|
| MSAL multi-tenant login | 🟡 | `frontend/src/auth/msalConfig.js` | Needs App Registration redirect URIs set. |
| Login page UI | 🟡 | `frontend/src/App.jsx` | |
| App shell (nav + sidebar + user chip) | 🟡 | `frontend/src/components/Layout.jsx` | |
| RBAC role hook (`useRole`) | 🟡 | `frontend/src/hooks/useRole.js` | |
| Role guard component | 🟡 | `frontend/src/components/RoleGuard.jsx` | |
| API client (Axios + token injection) | 🟡 | `frontend/src/services/api.js` | |
| Dashboard — KPI cards | 🟡 | `frontend/src/pages/Dashboard.jsx` | |
| Dashboard — Power BI embed | 🟡 | `frontend/src/pages/Dashboard.jsx` | Needs Power BI config. Falls back gracefully. |
| Dashboard — masking coverage bar | 🟡 | `frontend/src/pages/Dashboard.jsx` | |
| Scan page — form + submit | 🟡 | `frontend/src/pages/Scan.jsx` | |
| Scan page — live polling | 🟡 | `frontend/src/pages/Scan.jsx` | |
| Scan page — recent scans list | 🟡 | `frontend/src/pages/Scan.jsx` | |
| Approvals — data grid | 🟡 | `frontend/src/pages/Approvals.jsx` | |
| Approvals — bulk approve/reject | 🟡 | `frontend/src/pages/Approvals.jsx` | |
| Approvals — status tabs | 🟡 | `frontend/src/pages/Approvals.jsx` | |
| Audit page — log viewer | 🟡 | `frontend/src/pages/Audit.jsx` | |
| Audit page — CSV export | 🟡 | `frontend/src/pages/Audit.jsx` | |
| Material UI enterprise theme | ✅ | `frontend/src/theme.js` | |

### Infrastructure & DevOps

| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Bicep template (all 13 resources) | 🟡 | `infra/main.bicep` | Written. Needs first deploy to validate. |
| One-click bash deploy script | 🟡 | `deploy/deploy.sh` | Needs testing against real subscription. |
| GitHub Actions CI/CD (7 stages) | 🟡 | `.github/workflows/ci-cd.yml` | Needs GitHub secrets configured. |
| Unit tests — PII engine | ✅ | `backend/tests/test_pii_engine.py` | 9 test cases, all pass. |
| Unit tests — masking DDL | ✅ | `backend/tests/test_masking_engine.py` | 7 test cases, all pass. |

---

## PART 2: WHAT'S PENDING (Amritha's Work)

### 🔴 P0 — Must Have Before Demo (Week 1-3)

| # | Task | Effort | Depends On | File(s) to Change |
|---|------|--------|-----------|-------------------|
| P0-1 | **Azure App Registration setup** — create multi-tenant app reg, configure redirect URIs, set API scopes, assign roles | 1 day | Azure Portal access | — (Azure config) |
| P0-2 | **Populate Key Vault secrets** — client secret, per-tenant SQL connstrings | 0.5 day | App Reg done | — (Azure KV) |
| P0-3 | **Deploy infra via Bicep** — first successful `deploy.sh` run | 1 day | KV secrets | `deploy/deploy.sh` |
| P0-4 | **Connect a real test Azure SQL database** — create test DB with dummy PII data | 1 day | Infra deployed | `backend/core/db_connector.py` |
| P0-5 | **Install spaCy model** — `python -m spacy download en_core_web_lg` in App Service | 0.5 day | Deploy done | `deploy/deploy.sh` (already has this, verify it runs) |
| P0-6 | **End-to-end scan test** — trigger scan via UI against test DB, see results | 1 day | P0-4 done | — |
| P0-7 | **Approval + masking flow** — approve a flagged column, apply DDM, verify on DB | 1 day | P0-6 done | — |
| P0-8 | **Fix `connection_name` gap in approvals** — when masking is triggered, the `connection_name` must be stored on the approval record so masking knows which DB to connect to | 0.5 day | — | `backend/models/schemas.py`, `backend/api/scan.py`, `backend/api/approvals.py` |
| P0-9 | **GitHub Actions secrets setup** — add all secrets to repo for CI/CD | 0.5 day | App Reg done | `.github/workflows/ci-cd.yml` |

### 🔴 P1 — Must Have Before Demo (Week 3-4)

| # | Task | Effort | Notes |
|---|------|--------|-------|
| P1-1 | **Power BI dashboard** — create the actual .pbix report with PII distribution, risk trends, compliance metrics; publish to Power BI Service; set up RLS role "TenantViewer" | 2 days | Needs Power BI Desktop + workspace |
| P1-2 | **Integration tests** — pytest tests that test the full API flow with a real Cosmos DB (use Cosmos Emulator locally) | 2 days | `backend/tests/test_integration.py` |
| P1-3 | **Vite config + index.html** — the frontend is missing `vite.config.js` and `index.html` entrypoints | 0.5 day | `frontend/vite.config.js`, `frontend/index.html` |
| P1-4 | **Frontend `.env` for local dev** — create `.env.development` with local API URL pointing to `localhost:8000` | 0.5 day | `frontend/.env.development` |
| P1-5 | **Backend `.env` for local dev** — create `.env` with test values (Cosmos emulator, dummy secrets) | 0.5 day | `backend/.env` |
| P1-6 | **Dummy PII test dataset** — SQL script to create a realistic test schema with patients, employees, transactions tables containing obvious PII | 1 day | `deploy/seed_test_data.sql` |
| P1-7 | **Store `data_type` on approval records** — masking engine needs the column's SQL data type to build correct DDM; currently hardcoded to "varchar" | 0.5 day | `backend/models/schemas.py`, `backend/api/scan.py` |
| P1-8 | **Error boundary in React** — wrap routes in error boundary to prevent full white-screen on JS error | 0.5 day | `frontend/src/components/ErrorBoundary.jsx` |
| P1-9 | **Loading + empty states** — all 4 pages need proper skeleton loaders and empty state illustrations | 1 day | All `frontend/src/pages/*.jsx` |

### 🟡 P2 — Nice to Have Before Demo (Week 4-5)

| # | Task | Effort | Notes |
|---|------|--------|-------|
| P2-1 | **Microsoft Fabric integration test** — test the scan + masking flow against an actual Fabric SQL Endpoint (not just Azure SQL) | 2 days | Needs Fabric workspace |
| P2-2 | **Purview integration test** — verify classification push actually appears in a real Purview account | 1 day | Needs Purview account |
| P2-3 | **Approval stats — fix COUNT query** — `list_audit` in cosmos_store currently returns `total=len(logs)` instead of true count from Cosmos | 0.5 day | `backend/storage/cosmos_store.py` |
| P2-4 | **Pagination on approvals page** — currently loads up to 500 records; add proper server-side pagination | 1 day | `frontend/src/pages/Approvals.jsx` |
| P2-5 | **Scan progress websocket** — instead of polling every 3s, use WebSocket for real-time scan progress | 1.5 days | Optional — polling works fine for demo |
| P2-6 | **Dark mode toggle** | 0.5 day | `frontend/src/theme.js` |
| P2-7 | **Mobile responsive fixes** — sidebar and data grid need responsive adjustments for smaller screens | 1 day | Layout.jsx, all pages |

### 🔵 Post-Stakeholder-Approval (ISV Track)

| # | Task | Effort | Notes |
|---|------|--------|-------|
| ISV-1 | **Azure Marketplace offer creation** — Partner Center registration, offer listing, pricing plans, screenshots | 1 week | Needs Microsoft Partner account |
| ISV-2 | **Marketplace landing page** — production landing page at app.fabricshield.io | 1 week | |
| ISV-3 | **Metered billing** — integrate Azure Marketplace metered billing API for overage charges | 3 days | |
| ISV-4 | **Automated tenant provisioning** — when a new customer buys, auto-create their Key Vault secrets + test connection | 2 days | |
| ISV-5 | **Custom Presidio recognizers** — enterprise plan feature: let customers define custom regex patterns | 2 days | |
| ISV-6 | **Scheduled scans** — cron-based recurring scans per tenant | 1 day | |
| ISV-7 | **Email notifications** — alert approvers when new PII is found | 1 day | Azure Communication Services |
| ISV-8 | **SOC2 audit report export** — one-click PDF compliance report | 2 days | |
| ISV-9 | **Admin tenant management UI** — page for our team to manage all tenants | 2 days | |
| ISV-10 | **Performance test** — load test with k6 or Locust, verify 100 concurrent scans | 2 days | |

---

## PART 3: SPRINT PLAN FOR AMRITHA

### Sprint 1 (Week 1-2): "Get It Running"
**Goal:** Local + Azure environment fully working, backend health check green, can trigger a scan via API.

- [ ] P0-1: Azure App Registration
- [ ] P0-2: Key Vault secrets
- [ ] P0-3: Deploy infra
- [ ] P0-4: Test Azure SQL DB with dummy data
- [ ] P0-5: Verify spaCy model install
- [ ] P1-3: Create `vite.config.js` + `index.html`
- [ ] P1-4: Frontend `.env.development`
- [ ] P1-5: Backend `.env`
- [ ] P0-9: GitHub Actions secrets

### Sprint 2 (Week 3-4): "Make It Work End-to-End"
**Goal:** Full scan → approve → mask flow working in the UI.

- [ ] P0-6: End-to-end scan test
- [ ] P0-7: Approval + masking flow
- [ ] P0-8: Fix `connection_name` on approval records
- [ ] P1-6: Dummy PII test dataset
- [ ] P1-7: Store `data_type` on approvals
- [ ] P1-1: Build Power BI dashboard
- [ ] P1-2: Integration tests
- [ ] P1-8: Error boundary
- [ ] P1-9: Loading/empty states

### Sprint 3 (Week 5): "Polish for Demo"
**Goal:** Demo-ready product. No crashes, good UX, convincing data.

- [ ] P2-3: Fix Cosmos COUNT query
- [ ] P2-4: Pagination on approvals
- [ ] Full test run against testing checklist (see `05_Testing_Guide.md`)
- [ ] Rehearse demo script (see `06_Demo_Script.md`)
- [ ] Fix any bugs found during testing

### Sprint 4 (Week 6): "Stakeholder Demo"
**Goal:** Present to US stakeholders. Collect feedback.

- [ ] Demo Day (Bish to schedule with stakeholders)
- [ ] Document feedback in a new `docs/stakeholder_feedback.md`
- [ ] Triage feedback into Must Fix / Should Fix / Won't Fix

### Sprint 5+ (Week 7+): "Iterate Until Green Light"
- Implement stakeholder feedback
- Re-demo until green light
- Then begin ISV track

---

## PART 4: KEY KNOWN GAPS & GOTCHAS

1. **`vite.config.js` and `index.html` are missing** — the frontend won't build without them. This is P1-3 and is your very first frontend fix.

2. **`connection_name` not stored on approval records** — when a scan creates approval records, it needs to also store which database connection name was used, so that masking can later connect to the right DB. See P0-8.

3. **`data_type` hardcoded in masking** — `approvals.py` line 115 has `data_type="varchar"` hardcoded. Real masking requires the actual column type (e.g., `int` vs `varchar` affects which DDM function works). See P1-7.

4. **Cosmos DB async client** — the `CosmosStore` uses `azure.cosmos.aio` (async). Make sure you always `await` its methods and you're inside an async function. Non-async callers will silently fail.

5. **`en_core_web_lg` is 700MB** — the large spaCy model is required for production Presidio accuracy. In CI we use `en_core_web_sm` for speed. On App Service, this model is downloaded at deploy time — first deploy will take ~5 extra minutes.

6. **Power BI RLS setup** — the Power BI dataset must have a Row Level Security role named exactly `"TenantViewer"` with a DAX filter on `tenant_id`. This is configured in Power BI Desktop before publishing. See P1-1.

7. **Marketplace webhook signature** — the `marketplace_webhook_secret` in Key Vault must match what's configured in Partner Center. Until you have a Partner Center account, this endpoint can't be fully tested.

8. **Multi-tenant JWT issuer** — Entra ID multi-tenant apps see tokens with issuer `https://login.microsoftonline.com/{customer_tenant_id}/v2.0`. The `validate_token()` function handles this correctly, but you need a second test tenant (or a personal Entra ID account) to verify it works with multiple tenants.
