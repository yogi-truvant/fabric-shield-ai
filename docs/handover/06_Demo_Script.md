# FabricShield AI — US Stakeholder Demo Script
**Presenter:** Amritha | **Duration:** 25–30 minutes + Q&A

---

## Pre-Demo Checklist (Do the night before)

- [ ] Environment deployed and healthy — `GET /health` returns 200
- [ ] Test database seeded with `seed_test_data.sql`
- [ ] Previous scan results cleared from Cosmos DB (or start fresh tenant)
- [ ] Logged in as Admin user in the browser
- [ ] Browser zoom at 100%, full-screen mode ready
- [ ] Postman / REST Client open with API collection loaded (for technical audience)
- [ ] Power BI report refreshed and embedded
- [ ] Second browser tab ready as "non-admin user" (Viewer role)
- [ ] Presentation notes printed or on a second screen
- [ ] Demo on stable internet — if showing remotely, use screen share + Teams/Zoom

---

## Opening (3 min)

> *"Good morning / afternoon, everyone. My name is Amritha and I'm working with Bishwesh's team at Truvant Consulting on FabricShield AI — an enterprise governance platform we're building for the Azure Marketplace.*
>
> *In the next 25 minutes, I'm going to show you a working prototype that solves a very specific, very expensive problem that every hospital, insurance company, and financial firm on Azure faces today: how do you know where your sensitive data — patient records, SSNs, credit cards — actually lives inside your databases? And how do you automatically protect it?*
>
> *Let me start with 60 seconds of context, then I'll go straight to the demo."*

### The Problem (1 min, no slides needed — just talk)

> *"Imagine you're the data compliance officer at a regional hospital. You have 50 databases on Azure SQL, maintained by 10 different teams over 10 years. HIPAA requires you to know exactly where every piece of patient data lives and that it's protected. Today, you either pay a consultant $200K to manually audit those databases, or you rely on engineers to self-report — which never works.*
>
> *FabricShield AI automates this. It scans your databases, finds the sensitive columns using AI, routes them through a human review process, and then applies automatic masking — all within Azure, all without moving data anywhere, all in under an hour."*

---

## Demo Part 1: The Dashboard (3 min)

*[Open browser, show Dashboard page]*

> *"This is the FabricShield command center. Everything a compliance officer needs at a glance.*
>
> *These four KPIs — total PII columns detected, the percentage that are high-risk and pending review, masking coverage, and pending approvals — give you an instant compliance health score.*
>
> *The masking coverage bar tells you the percentage of detected sensitive columns that have been protected. Our goal is 100% — and it tracks in real time as your team works through approvals.*
>
> *And here — [point to Power BI embed] — is a live Power BI dashboard showing PII distribution by entity type, risk trends over time, and compliance metrics. This is updated automatically with every scan."*

**Key talking point:** *"Notice everything you see here belongs only to your organization — FabricShield is multi-tenant SaaS, so your data and your compliance dashboard are completely isolated from other customers."*

---

## Demo Part 2: Running a Scan (5 min)

*[Navigate to Scan page]*

> *"Let me show you how a scan works. I'll scan a test database that mimics a real hospital patient management system."*

*[Type `testdb` in Connection Name, `dbo` in Schemas]*

> *"We select the database type — Azure SQL or Microsoft Fabric — and choose which schemas to scan. The connection is authenticated via Managed Identity — no passwords, no connection strings stored anywhere in the application."*

*[Click Start Scan]*

> *"Scan is running. FabricShield is now doing two things simultaneously — first, a rule-based pass: it checks every column name against a catalog of 13 PII patterns. `ssn`, `email`, `date_of_birth`, `medical_record_number`, `credit_card`, and more.*
>
> *At the same time, for text columns, it samples up to 100 rows and runs them through Microsoft Presidio — an NLP engine that Microsoft built specifically for PII detection. It's the same engine that powers Microsoft Purview's data discovery.*
>
> *When both engines agree on a column, we boost the confidence score. When they disagree, we take the higher-confidence result."*

*[Wait for scan to complete — show "12 PII columns found" or similar]*

> *"Done in about [X] seconds. It found [N] PII columns across [M] tables. Let's go see what it found."*

---

## Demo Part 3: Human-in-the-Loop Approvals (7 min)

*[Navigate to Approvals page]*

> *"This is where governance becomes a collaborative process rather than a black box.*
>
> *Every detected column goes through human review before any action is taken. This is a fundamental design principle — AI suggests, humans decide.*
>
> *Let me walk you through what we're seeing. Each row is a flagged column. We can see the schema and table, the column name, what type of PII was detected, the confidence score, whether it was caught by rules, ML, or both — and the recommended masking type."*

*[Hover over a row with a red CREDIT_CARD chip]*

> *"This credit card column was detected with 95% confidence. Both the column name 'credit_card_number' triggered our rules, AND Presidio found actual credit card patterns in the sample data. That dual confirmation gives us very high confidence."*

*[Select 5–6 rows]*

> *"I can bulk-approve or bulk-reject. In a real scenario, a data steward would review each one and confirm whether the detection is correct. Let me approve these."*

*[Click Approve]*

> *"Approved. These are now queued for masking. The approver role is separate from the analyst role — you can require a manager sign-off before any masking is applied, which supports segregation of duties for SOX and HIPAA."*

*[Click Reject on one row, enter reason "Test column — not real PII"]*

> *"Rejected with a reason. This goes into the audit trail."*

---

## Demo Part 4: Automatic Data Masking (5 min)

*[Click Mask on an approved email column]*

> *"When I click Mask, FabricShield connects to the Azure SQL database using Managed Identity and executes a Dynamic Data Masking statement directly on the database.*
>
> *Dynamic Data Masking is an Azure SQL native feature. The data is never moved, never copied, never exposed. The mask is applied at the query engine level — users without UNMASK permission get obfuscated values, users with UNMASK permission see the real data.*
>
> *For this email column, the DDM function is `email()` — it shows the first letter and the domain, so `john.smith@hospital.com` becomes `jXXXX@XXXXX.com`. For an SSN, it would show the last four digits only."*

*[Show the green MASKED chip appear on the row]*

> *"The column is now protected. Let me show you what this looks like on the actual database."*

*[Switch to Azure Data Studio / SSMS, query the patients table as a regular user]*

> *"Here's what a non-privileged user sees — masked values. The actual data is still there, the application still works, but analysts who don't have a medical need to see raw SSNs will never see them."*

*[Query as admin to show real data still accessible]*

> *"And here's what a privileged admin sees — the real data. Masking is transparent to authorized users."*

---

## Demo Part 5: Audit Trail (3 min)

*[Navigate to Audit page]*

> *"Every single action in FabricShield is recorded in an immutable audit log. You can see the scan, the approval, the masking — all with timestamps, who did it, and what was done.*
>
> *This is stored in Cosmos DB with append-only access — the API has no DELETE or UPDATE endpoints for audit records. This satisfies HIPAA's requirement for audit trails that cannot be tampered with.*
>
> *You can filter by action type, search for specific resources, and export to CSV for your compliance officer or for external audit firms."*

*[Export CSV, show the downloaded file briefly]*

---

## Demo Part 6: Architecture in 60 Seconds (2 min)

*[Optional — show only if audience is technical]*

> *"Quick architectural callout for the engineers in the room. FabricShield runs entirely within your Azure tenant. The backend is a FastAPI service on App Service. Workflow state goes into Cosmos DB, partitioned by tenant ID for isolation. Authentication is Entra ID — no FabricShield passwords anywhere. All service connections use Managed Identity — no secrets stored in code or config. And everything emits structured telemetry to Application Insights."*

---

## Closing (2 min)

> *"So to summarize what you just saw: a compliance team can go from 'we don't know where our sensitive data is' to 'every PII column is detected, reviewed, masked, and audited' — in under an hour, with zero manual database work, and full audit trail compliance.*
>
> *We're targeting this at Azure-native healthcare and financial organizations as a SaaS product on the Azure Marketplace, with a Starter plan at $499/month.*
>
> *We're in the final testing and polish phase. Your feedback today will directly shape what we prioritize for production release. I'd love to know: does this solve the real problem you're seeing with your customers or your own data estate? And what's missing?"*

---

## Q&A Preparation

**Q: Does this support non-Azure databases (Snowflake, Databricks, on-prem SQL)?**
> *"Currently Azure SQL and Microsoft Fabric only. On-premise SQL and Databricks connectivity is on our roadmap based on demand. Azure SQL covers the largest share of our target market."*

**Q: What happens to the raw data that's sampled during scanning?**
> *"We sample up to 100 rows per column, run them through the detection engine in memory, and never store them. The only thing we persist is the column-level detection result — entity type, confidence score, and a truncated 4-character hint. No PII is stored in Cosmos DB."*

**Q: How does this compare to Microsoft Purview?**
> *"Purview is a full data catalog — it's designed to document and govern an entire data estate across hundreds of sources. It's powerful but complex to deploy, typically taking weeks and significant licensing cost. FabricShield is narrower and deeper — we focus specifically on Azure SQL and Fabric, and we go all the way to masking. You can use both together: FabricShield detects and masks, Purview catalogs the classifications we push to it."*

**Q: Is this HIPAA-compliant?**
> *"FabricShield is designed with HIPAA controls: audit log immutability, Managed Identity (no shared credentials), encryption at rest (TDE on SQL, Cosmos DB native), TLS 1.2+ in transit, and RBAC with least-privilege principles. For a formal HIPAA Business Associate Agreement, customers would work with their Azure account team."*

**Q: What's the pricing?**
> *"Starter at $499/month covers 2 databases and 30 scans per month — good for a team just starting their compliance journey. Growth at $1,499/month adds Microsoft Fabric support, Purview integration, and 10 databases. Enterprise at $4,999/month is unlimited databases with a dedicated customer success manager. All plans are on the Azure Marketplace — customers can use their Azure Commit to Pay credits to purchase."*

**Q: How long does a scan take on a large database?**
> *"For a schema with 500 columns, under 90 seconds. The bottleneck is the NLP inference on sampled data. We're exploring GPU-accelerated inference for the Enterprise tier for very large databases."*

**Q: Is multi-tenancy truly isolated?**
> *"Yes — Cosmos DB partitions by tenant_id at the storage level. JWT validation checks the tenant claim on every request. There's no code path that can return data across tenant boundaries — we enforce this at both the API layer and the Cosmos query layer."*

---

## Demo Recovery Playbook

| Problem | Recovery |
|---------|----------|
| Scan fails | Say "let me switch to a pre-recorded scan result" — have a screenshot/recording ready |
| Login fails | Have a second browser already logged in |
| Masking fails | Show the already-masked column from previous run — say "as you can see, this column was masked in our previous test run" |
| API is down | Switch to Postman to show API responses directly |
| Power BI doesn't load | Show screenshot, say "the Power BI integration requires workspace configuration — happy to walk through that separately" |
