# FabricShield AI — Azure ISV / Marketplace Readiness Checklist
**Owner:** Amritha tracks; Bishwesh signs off | **Target:** Azure Marketplace Transactable SaaS Offer

> This checklist is used **after** stakeholders give the green light. Nothing here needs to be done before the demo. Use it to plan the ISV submission sprint.

---

## PHASE 1: Microsoft Partner Enrollment

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1.1 | Create Microsoft Partner Center account (MPN ID) | Bishwesh | ⬜ | https://partner.microsoft.com |
| 1.2 | Enroll in the ISV Success Program (optional but valuable) | Bishwesh | ⬜ | Free support + Azure credits |
| 1.3 | Complete Publisher profile in Partner Center | Bishwesh | ⬜ | Company name, logo, legal name |
| 1.4 | Sign Microsoft Publisher Agreement | Bishwesh | ⬜ | Legal review needed |
| 1.5 | Set up banking / payout account | Bishwesh | ⬜ | Required for transactable offers |
| 1.6 | Complete company verification (5–7 business days) | Bishwesh | ⬜ | Microsoft manually verifies |

---

## PHASE 2: Technical Readiness

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 2.1 | Production deployment running on dedicated Azure subscription | Amritha | ⬜ | Separate from dev subscription |
| 2.2 | Custom domain: `app.fabricshield.io` + SSL cert | Amritha | ⬜ | Azure App Service custom domain |
| 2.3 | Landing page at `https://fabricshield.io` | Amritha/Bishwesh | ⬜ | Simple marketing page, no code needed — use Wix/Webflow |
| 2.4 | SaaS landing page at `https://app.fabricshield.io/activate` | Amritha | ⬜ | The post-purchase activation flow |
| 2.5 | Webhook URL registered in Partner Center | Amritha | ⬜ | `https://api.fabricshield.io/marketplace/webhook` |
| 2.6 | Marketplace landing page URL registered in Partner Center | Amritha | ⬜ | `https://app.fabricshield.io/activate` |
| 2.7 | Test SaaS fulfillment flow end-to-end with a test subscription | Amritha | ⬜ | Partner Center has a test subscription feature |
| 2.8 | Webhook HMAC secret configured in Key Vault + Partner Center | Amritha | ⬜ | `marketplace_webhook_secret` |
| 2.9 | All 3 plan IDs (`starter`, `growth`, `enterprise`) match Partner Center plan IDs | Amritha | ⬜ | Case-sensitive match in `fulfillment.py` |
| 2.10 | Metered billing integration (optional for initial launch) | Amritha | ⬜ | Use Azure Marketplace Metered API for overage |
| 2.11 | Automated tenant provisioning tested | Amritha | ⬜ | Buy → activate → tenant appears in Cosmos in < 5 min |
| 2.12 | Tenant de-provisioning tested | Amritha | ⬜ | Cancel → tenant marked inactive |
| 2.13 | Plan upgrade/downgrade tested | Amritha | ⬜ | ChangePlan webhook changes Cosmos limits |

---

## PHASE 3: Security & Compliance

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 3.1 | Penetration test (external) | Bishwesh to procure | ⬜ | Required for healthcare customers. Use a vendor like Bishweshop Fox or NCC Group |
| 3.2 | Vulnerability scan of Docker/App Service | Amritha | ⬜ | Use Microsoft Defender for Cloud |
| 3.3 | OWASP Top 10 manual review | Amritha | ⬜ | SQL injection (we use parameterized queries ✅), XSS (CSP headers ✅), CSRF, etc. |
| 3.4 | Dependency audit | Amritha | ⬜ | `pip-audit -r backend/requirements.txt` — fix any HIGH/CRITICAL CVEs |
| 3.5 | Secrets rotation procedure documented | Amritha | ⬜ | How to rotate client secret without downtime |
| 3.6 | Disaster recovery plan | Bishwesh | ⬜ | Cosmos DB continuous backup, RTO/RPO defined |
| 3.7 | Data residency documentation | Bishwesh | ⬜ | Which regions data is stored in (important for EU customers/GDPR) |
| 3.8 | Privacy policy published | Bishwesh (legal) | ⬜ | Required for Marketplace listing |
| 3.9 | Terms of service published | Bishwesh (legal) | ⬜ | Required for Marketplace listing |
| 3.10 | HIPAA BAA template prepared | Bishwesh (legal) | ⬜ | Customers in healthcare will request this |

---

## PHASE 4: Product Quality Gates

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 4.1 | All P0 + P1 items from `done_vs_pending.md` complete | Amritha | ⬜ | |
| 4.2 | 100% of TC-1 through TC-7 test cases passing | Amritha | ⬜ | See `05_Testing_Guide.md` |
| 4.3 | TC-8 performance baseline met | Amritha | ⬜ | Dashboard < 2s, scan < 90s |
| 4.4 | Zero P0/P1 bugs open | Amritha | ⬜ | |
| 4.5 | Browser compatibility: Chrome, Edge, Firefox | Amritha | ⬜ | |
| 4.6 | Microsoft Fabric scan tested against real Fabric workspace | Amritha | ⬜ | |
| 4.7 | Load test: 10 concurrent tenants scanning simultaneously | Amritha | ⬜ | Use k6 or Locust |
| 4.8 | 99.9% uptime SLA achievable — App Service autoscale configured | Amritha | ⬜ | Set min instances = 2 in Bicep for prod |

---

## PHASE 5: Marketplace Listing

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 5.1 | Offer name: "FabricShield AI — PII/PHI Governance" | Bishwesh | ⬜ | Check for trademark conflicts |
| 5.2 | Offer description (short: 256 chars) | Bishwesh/Amritha | ⬜ | |
| 5.3 | Offer description (long: 3000 chars, HTML) | Bishwesh/Amritha | ⬜ | |
| 5.4 | Screenshots (minimum 3, 1280x720 PNG) | Amritha | ⬜ | Dashboard, Scan page, Approvals page |
| 5.5 | Product logo (216x216, 90x90, 48x48 PNG) | Bishwesh | ⬜ | |
| 5.6 | Demo video (optional but strongly recommended, 60-90s) | Amritha | ⬜ | Record with OBS or Loom |
| 5.7 | Pricing plans created in Partner Center | Bishwesh | ⬜ | Starter $499, Growth $1,499, Enterprise $4,999 |
| 5.8 | Free trial configured (optional: 14-day trial) | Bishwesh | ⬜ | Reduces barrier to purchase |
| 5.9 | Support URL: `https://fabricshield.io/support` | Bishwesh | ⬜ | Can be email initially |
| 5.10 | Privacy policy URL | Bishwesh | ⬜ | |
| 5.11 | CSP (Cloud Solution Provider) eligibility | Bishwesh | ⬜ | Allows Microsoft partners to resell |

---

## PHASE 6: Go-Live

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 6.1 | Submit offer for Microsoft review | Bishwesh | ⬜ | Review takes 3–5 business days |
| 6.2 | Complete Marketplace Certification testing | Bishwesh/Amritha | ⬜ | Microsoft tests your fulfillment APIs |
| 6.3 | Fix any Certification issues | Amritha | ⬜ | Common: webhook response time, HTTPS cert |
| 6.4 | Soft launch: private preview (invite 2–3 beta customers) | Bishwesh | ⬜ | Partner Center supports limited audience |
| 6.5 | Collect and address beta feedback | Amritha | ⬜ | |
| 6.6 | Public launch | Bishwesh | ⬜ | 🚀 |

---

## Timeline Estimate (Post Green-Light)

```
Week 1-2:   Phase 1 (Partner Center enrollment) runs in parallel with dev
Week 3-4:   Phase 2 + Phase 3 (technical + security hardening)
Week 5-6:   Phase 4 (quality gates + load testing)
Week 7:     Phase 5 (listing content + assets)
Week 8:     Phase 6 — Submit, review, fix, launch
```

Total: approximately **8 weeks** from green light to public Marketplace listing.

---

## Useful Resources

| Resource | URL |
|----------|-----|
| Partner Center | https://partner.microsoft.com/dashboard |
| SaaS Fulfillment API v2 docs | https://aka.ms/saasapiv2 |
| Marketplace certification policies | https://aka.ms/marketplacecertificationpolicies |
| Azure Marketplace offer types | https://aka.ms/azuremarketplaceoffertypes |
| ISV Success Program | https://www.microsoft.com/isv |
| Metered billing docs | https://aka.ms/marketplacemeteringservice |
| SaaS offer checklist (Microsoft) | https://aka.ms/saaschecklist |
