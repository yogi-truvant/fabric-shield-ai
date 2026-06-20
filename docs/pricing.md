# FabricShield AI — SaaS Pricing Model

## Tiers

| | **Starter** | **Growth** | **Enterprise** |
|---|---|---|---|
| **Price** | $499/mo | $1,499/mo | $4,999/mo |
| **Setup Fee** | $0 | $0 | $2,500 one-time |
| **Databases** | 2 | 10 | Unlimited |
| **Scans/month** | 30 | 200 | 5,000 |
| **Columns scanned/scan** | 500 | 5,000 | Unlimited |
| **Azure SQL** | ✅ | ✅ | ✅ |
| **Microsoft Fabric** | ❌ | ✅ | ✅ |
| **Bulk approvals** | ❌ | ✅ | ✅ |
| **Purview integration** | ❌ | ✅ | ✅ |
| **Power BI embedded** | Basic | Full | Full + custom |
| **Audit log retention** | 30 days | 90 days | 365 days |
| **SLA** | 99.5% | 99.9% | 99.95% |
| **Support** | Community | Email (48hr) | Dedicated CSM |
| **Custom recognizers** | ❌ | ❌ | ✅ |
| **Azure Marketplace** | ✅ | ✅ | ✅ |

---

## Metered Billing (Usage-Based Add-On)

Available on Growth and Enterprise for overage:

| Metric | Price |
|--------|-------|
| Extra scan (above plan limit) | $2.50/scan |
| Extra database connection | $50/database/month |
| Purview classification push | $0.01/column classified |

Metered billing is implemented via **Azure Marketplace Custom Meter APIs** — usage events are submitted after each scan completion.

---

## Marketplace SKU Mapping

| Plan ID (Marketplace) | Internal Plan | Description |
|---|---|---|
| `starter` | Starter | Entry-level PII governance |
| `growth` | Growth | Mid-market, Fabric + Purview |
| `enterprise` | Enterprise | Full platform, unlimited scale |

---

## Revenue Projections (Indicative)

| Scenario | Customers | MRR | ARR |
|---|---|---|---|
| Early (Y1) | 20 Starter + 5 Growth | $17,480/mo | ~$210K |
| Growth (Y2) | 50 Growth + 10 Enterprise | $124,940/mo | ~$1.5M |
| Scale (Y3) | 100 Growth + 30 Enterprise | $299,850/mo | ~$3.6M |

---

## Competitive Positioning

| Product | Price Point | Scope |
|---|---|---|
| **FabricShield AI** | $499–$4,999/mo | Azure-native, Fabric-first |
| Microsoft Purview | $0.01/GB scanned + DPU | Full catalog, complex to deploy |
| Collibra | $50K–$200K/year | Enterprise data governance suite |
| BigID | $30K–$150K/year | Broad data discovery |

**FabricShield's moat**: Deep Azure/Fabric-native integration, SaaS simplicity, Azure Marketplace distribution, affordable entry price for SMB healthcare/finance.
