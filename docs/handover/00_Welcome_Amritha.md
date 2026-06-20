# Welcome to FabricShield AI, Amritha! 🎉

**Date:** 8th June 2026  
**Project:** FabricShield AI — Enterprise PII/PHI Governance Platform  
**Your Role:** SDE Intern Engineer (Completion, Testing & Stakeholder Demo)  
**Reporting To:** Yogi (yogi@truvantconsulting.com)
**Skip Level Reporting To:** Bishwesh Singh (bishwesh@truvantconsulting.com)

---

## Hey Amritha 👋

Welcome aboard! You're joining at a really exciting stage of this project. The foundation — the full backend, frontend, infrastructure, and cloud architecture — has already been built. Your mission is to take it from "built" to "shippable."

That means: get it running end-to-end, fill in the gaps, make it demoable, present it to our US stakeholders, and then iterate based on their feedback until we get the green light to publish it on the **Azure Marketplace as an ISV product**.

This is real, production-level work that will appear in Microsoft's cloud marketplace. It's not a toy project.

---

## What Is This Product?

**FabricShield AI** is a SaaS governance platform that helps enterprises — especially in healthcare and finance — automatically detect and protect sensitive data (PII/PHI) in their Azure SQL databases and Microsoft Fabric warehouses.

Think of it as a "Grammarly for sensitive data" — it scans your database columns, flags anything that looks like a Social Security Number, patient record, email address, or other personally identifiable information, lets a human review and approve, and then automatically applies data masking so that non-privileged users never see the raw sensitive values.

**Why does it matter?** Every hospital, insurance company, and financial institution that stores data on Azure has regulatory obligations under HIPAA, GDPR, and SOC2. FabricShield automates the most painful part of compliance — finding and protecting that data — and does it natively within Azure.

**Target customers:** Healthcare orgs, insurance companies, banks, any enterprise with Azure SQL or Microsoft Fabric.

---

## What You're Inheriting

The codebase is in your **FabricShield AI** folder. Here's what was built before you arrived:

| Layer | What's Built |
|-------|-------------|
| **Backend** | FastAPI app (Python) — all 6 API endpoints, PII engine, masking engine, Cosmos DB storage, audit logger |
| **Frontend** | React + Material UI — 4 pages: Dashboard, Scan, Approvals, Audit |
| **Auth** | Entra ID multi-tenant JWT validation + RBAC (4 roles) |
| **PII Engine** | 13 rule patterns + Microsoft Presidio NLP — detects SSN, email, DOB, MRN, NPI, PHI, etc. |
| **Masking** | Azure SQL Dynamic Data Masking via T-SQL DDM statements |
| **Cosmos DB** | Multi-tenant storage (partition key = tenant_id) for scans, approvals, audit logs |
| **Marketplace** | SaaS Fulfillment API v2 (resolve, activate, unsubscribe webhook) |
| **Purview** | Microsoft Purview classification push integration |
| **Infrastructure** | Bicep template for all 13 Azure resources |
| **CI/CD** | GitHub Actions 7-stage pipeline |
| **Tests** | Unit tests for PII engine and masking DDL builder |

---

## What You Need to Do

At a high level, your journey looks like this:

```
Week 1-2:  Get the environment running locally + on Azure
Week 3-4:  Complete the pending features (see done_vs_pending.md)
Week 5:    End-to-end testing — every feature, edge cases
Week 6:    Prepare and deliver stakeholder demo to US team
Week 7+:   Iterate based on feedback, repeat until green light
Then:      ISV submission to Azure Marketplace
```

Detailed tasks, setup steps, test cases, and the demo script are all in this `docs/handover/` folder.

---

## Your Tools & Access

You'll be given the following. If anything is missing, email Bish immediately — don't try to work around missing access.

| Tool | What For | Access Level |
|------|----------|-------------|
| **Azure Portal** | Deploy infrastructure, manage resources | Contributor on the FabricShield subscription |
| **Azure CLI** | Deploy via scripts, manage resources | Same subscription |
| **Claude (Anthropic)** | Your AI coding partner — use it heavily | Full access |
| **GitHub** | Source code, CI/CD | Write access to the repo |
| **VM (Windows/Linux)** | Dev machine, running local environment | Admin |
| **VS Code** | Code editor (recommended) | Your VM |
| **Postman or Bruno** | API testing | Free install |
| **Power BI Desktop** | Build/edit the embedded dashboard | Free |

---

## Important Contacts

| Name | Role | Contact |
|------|------|---------|
| **Yogi** | Project Lead | yogi@truvantconsulting.com |
| **Bishwesh Singh** |Architect | bishwesh@truvantconsulting.com |
| **US Stakeholders** | Feedback / Go/No-Go decision | TBD — Bishwesh will introduce |
| **You (Amritha)** | SDE Intern Engineer | amritha@truvantconsulting.com |

---

## Ground Rules

1. **Ask early, not late.** If you're stuck for more than 2 hours on something, reach out. Don't lose a day going in circles.
2. **Use Claude heavily.** You have a Claude license. Use it to understand code, debug, write tests, generate documentation. That's what it's there for.
3. **Commit daily.** Push your work to GitHub every evening, even if it's incomplete. Small commits with clear messages.
4. **Don't hardcode secrets.** Ever. Everything sensitive goes in Azure Key Vault. The architecture was built this way — don't break it.
5. **Document as you go.** When you figure something out that isn't documented, add it. Future-you will thank you.
6. **The demo is real.** US stakeholders are real decision-makers. The demo needs to be polished, reliable, and tell a clear story.

---

## Your First Week Plan

**Day 1**
- Read all 8 documents in this `docs/handover/` folder
- Set up your GitHub access and clone the repo
- Read `docs/architecture.md` carefully
- Set up VS Code + Python 3.11 + Node 20 on your VM

**Day 2**
- Follow `02_Environment_Setup_Guide.md` start to finish
- Get the backend running locally
- Run the unit tests: `pytest backend/tests/`
- Get the frontend running locally

**Day 3**
- Deploy to Azure using `deploy/deploy.sh`
- Verify health check passes
- Log in through the UI with your Entra ID credentials

**Day 4-5**
- Start working through `03_Done_vs_Pending.md`
- Pick up the first 3 pending items
- Begin connecting a real Azure SQL test database

---

## A Note on This Codebase

The code is well-structured and production-grade, but like any code, you'll find places that need refinement as you test it. That's expected and normal — your job is to find those places and fix them.

Every large codebase feels overwhelming at first. Start with one module, understand it fully, run it, break it, fix it. Then move to the next.

You've got this. Good luck — and make it ship! 🚀

— Bishwesh
