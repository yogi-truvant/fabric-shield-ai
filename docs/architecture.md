# FabricShield AI — Architecture Deep Dive

## 1. Multi-Tenant Isolation Model

Each tenant (customer) is identified by a `tenant_id` (= their Entra ID tenant GUID).

```
Cosmos DB
└── Container: scan_results      (partition key: /tenant_id)
└── Container: approvals         (partition key: /tenant_id)
└── Container: audit_logs        (partition key: /tenant_id)
└── Container: tenant_config     (partition key: /tenant_id)
```

Azure SQL and Fabric connections are stored per-tenant in Key Vault as:
```
kv-fabricshield-prod
└── secret: tenant-{id}-sql-connstring
└── secret: tenant-{id}-fabric-endpoint
```

Entra ID multi-tenant app registration with `signInAudience: AzureADMultipleOrgs` ensures each
customer's users authenticate against their own tenant directory, while our app service validates
the JWT issuer against an allowed-tenants list stored in Cosmos DB `tenant_config`.

---

## 2. PII/PHI Detection Pipeline

```
Schema Metadata Pull
        │
        ▼
Rule-Based Triage  ──────────────────────────────────►  PII Candidates
(column name regex)                                          │
        │                                                    │
        ▼                                                    ▼
Sample Row Fetch (TOP 100)                       Merge + Deduplicate
        │                                                    │
        ▼                                                    ▼
Presidio AnalyzerEngine ──────────────────────►  Final Results (entity, confidence, source)
(NLP + recognizers)                                          │
                                                             ▼
                                                    Cosmos DB (scan_results)
                                                             │
                                                             ▼
                                                    Purview Classification Push
```

### Confidence Score Logic

| Source   | Raw Score    | Final Confidence |
|----------|-------------|-----------------|
| Rule-only (name match) | N/A | 0.75 |
| Presidio only | Presidio score | as-is |
| Both agree | max(rule, presidio) | +0.15 boost, cap 1.0 |

---

## 3. Human-in-the-Loop Workflow

```
Scan Complete ──► Cosmos approval record (status: PENDING)
                              │
                    UI shows in Approvals page
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
         APPROVE                          REJECT
               │                             │
               ▼                             ▼
    masking_engine.apply_mask()    Record in audit log
               │
               ▼
    Azure SQL DDM statement executed
               │
               ▼
    Purview classification pushed
               │
               ▼
    Cosmos record status: MASKED
    Audit log written
```

---

## 4. RBAC Model

```
Entra ID Group ──────────────────────► App Role Claim (JWT)
                                               │
                              ┌────────────────▼────────────────┐
                              │         Role Resolver           │
                              └────────────────┬────────────────┘
                                               │
              ┌────────────┬──────────┬────────┴────────┬──────────────┐
              ▼            ▼          ▼                  ▼              ▼
           viewer       analyst    approver            admin          system
              │            │          │                  │
         Dashboard     Scan +      Approve +          Full
          only         View        Mask               access
```

Roles are checked at two layers:
1. **FastAPI dependency** (`require_role(["approver","admin"])`) — server-side enforcement
2. **React `<RoleGuard>`** — client-side UI gating (cosmetic, not a security boundary)

---

## 5. Data Flow for Masking

Azure SQL Dynamic Data Masking is applied at the database layer — the application never touches
the raw data. The masking engine constructs and executes:

```sql
-- Example: Email masking
ALTER TABLE [schema].[table]
ALTER COLUMN [email_col] ADD MASKED WITH (FUNCTION = 'email()');

-- Example: SSN partial masking
ALTER TABLE [dbo].[patients]
ALTER COLUMN [ssn] ADD MASKED WITH (FUNCTION = 'partial(0,"XXX-XX-",4)');
```

For Microsoft Fabric (SQL Endpoint), the same T-SQL syntax is used via pyodbc with the Fabric
connection string using Entra ID token-based auth (no password, MSI token).

---

## 6. Power BI Embedded Architecture

```
Backend /powerbi/token endpoint
        │
        ├── Authenticate as Service Principal to Power BI REST API
        ├── Call GenerateTokenInGroup (RLS-aware, per-tenant dataset)
        └── Return { embedUrl, accessToken, tokenId, expiration }

Frontend Dashboard.jsx
        │
        └── powerbi-client-react <PowerBIEmbed>
            ├── embedUrl from backend
            ├── accessToken from backend
            └── RLS identity = { username: tenant_id, roles: ["tenant_viewer"] }
```

---

## 7. Observability

All significant operations emit structured telemetry to Application Insights:

| Event | Custom Dimensions |
|-------|-------------------|
| scan.started | tenant_id, db_type, schema_count |
| scan.completed | tenant_id, pii_columns_found, duration_ms |
| approval.submitted | tenant_id, column_id, approver_oid, action |
| masking.applied | tenant_id, column_id, mask_type, success |
| masking.failed | tenant_id, column_id, error_code |
| marketplace.activated | tenant_id, plan_id |

---

## 8. Azure Marketplace Integration

FabricShield AI uses the **SaaS Fulfillment API v2** (AMI pattern):

```
Customer clicks "Get It Now" on Marketplace
        │
        ▼
Azure sends POST /marketplace/webhook (OperationType: Activate)
        │
        ▼
Our /marketplace/resolve resolves the subscription token
        │
        ▼
Provision tenant in Cosmos DB (tenant_config)
        │
        ▼
Send welcome email / redirect to app
        │
        ▼
Background: provision isolated Key Vault secrets
```

---

## 9. Security Controls (HIPAA Alignment)

| Control | Implementation |
|---------|---------------|
| Encryption at rest | Azure SQL TDE, Cosmos DB built-in, Key Vault HSM |
| Encryption in transit | TLS 1.2+ enforced at App Service, SQL |
| Access control | Entra ID + RBAC, no shared passwords |
| Audit logging | Immutable Cosmos append-only audit container + App Insights |
| Secrets management | Key Vault, no secrets in env vars or code |
| Network isolation | App Service VNet integration (optional SKU) |
| Data minimization | Presidio samples only TOP N rows, never stores raw data |
| Managed Identity | Used for all service-to-service auth |
