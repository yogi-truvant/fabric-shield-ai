# FabricShield AI — End-to-End Testing Guide
**For:** Amritha | **Goal:** Achieve full test coverage before stakeholder demo

---

## Test Environment Requirements

Before running these tests, ensure:
- [ ] Backend running (local or Azure App Service)
- [ ] Frontend running (local or App Service)
- [ ] Test Azure SQL DB seeded with `deploy/seed_test_data.sql`
- [ ] Cosmos DB Emulator running (local) OR real Cosmos DB (Azure)
- [ ] You are signed in as a user with **Admin** role
- [ ] A second test user with **Analyst** role (create one in Azure Entra ID)
- [ ] A third test user with **Viewer** role

---

## TC-1: Authentication & RBAC

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-1.1 Sign in | Open app, click "Sign in with Microsoft", sign in with Admin account | Redirected to Dashboard, user chip shows role "admin" | |
| TC-1.2 Role display | Check sidebar | All 4 nav items visible (Dashboard, Scan, Approvals, Audit) | |
| TC-1.3 Viewer restriction | Sign in as Viewer user | Only Dashboard visible in nav; Scan/Approvals/Audit links absent | |
| TC-1.4 Analyst restriction | Sign in as Analyst user | Dashboard + Scan + Approvals + Audit visible; bulk approve buttons absent | |
| TC-1.5 Token expiry | Leave app open for 1hr 10min | App silently refreshes token without logout | |
| TC-1.6 Logout | Click logout icon in top bar | Redirected to login page; session cleared | |
| TC-1.7 Deep link | Navigate directly to `/approvals` while logged out | Redirected to login, then back to `/approvals` after login | |

---

## TC-2: Scan

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-2.1 Basic scan | Sign in as Analyst. Go to Scan. Enter `testdb` as connection name, `dbo` as schema. Click Start Scan. | Scan appears in "Running" state with scan ID | |
| TC-2.2 Scan polling | Wait after starting scan | Status transitions to "Completed" within 60s. PII column count shown. | |
| TC-2.3 PII detected | After scan completes | PII columns found in the `patients`, `employees`, `transactions` tables (at minimum SSN, email, DOB, credit card) | |
| TC-2.4 Schema filter | Run scan with only `hr` as schema | Only columns from `hr` schema appear in approvals | |
| TC-2.5 Large scan | Scan a schema with 200+ columns | Completes without timeout; all columns processed | |
| TC-2.6 Invalid connection | Enter `nonexistent-db` as connection name | Scan transitions to "failed" with clear error message | |
| TC-2.7 Recent scans list | Run 3 scans | All 3 appear in "Recent Scans" list, newest first | |
| TC-2.8 Viewer blocked | Sign in as Viewer, navigate to `/scan` | "Access Restricted" message shown, form not accessible | |

**Expected PII columns in test DB** (verify these are detected):

| Table | Column | Expected Entity | Min Confidence |
|-------|--------|----------------|---------------|
| patients | ssn | SSN | 0.90 |
| patients | email | EMAIL | 0.90 |
| patients | date_of_birth | DATE_OF_BIRTH | 0.85 |
| patients | medical_record_number | MEDICAL_RECORD | 0.85 |
| patients | phone_number | PHONE | 0.80 |
| employees | email_address | EMAIL | 0.90 |
| employees | ssn | SSN | 0.90 |
| employees | home_address | LOCATION | 0.70 |
| transactions | credit_card_number | CREDIT_CARD | 0.90 |
| transactions | account_number | IBAN | 0.80 |

---

## TC-3: Approvals

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-3.1 View pending | Go to Approvals after a completed scan | All flagged columns shown with status PENDING | |
| TC-3.2 Filter by status | Click PENDING / APPROVED / MASKED tabs | Grid filters correctly | |
| TC-3.3 Grid search | Type "email" in search box | Only email-related columns shown | |
| TC-3.4 Single approve | Sign in as Approver. Select one row, click Approve 1. | Success snackbar. Row status changes to APPROVED. | |
| TC-3.5 Bulk approve | Select 5 rows, click Approve 5. | All 5 change to APPROVED. Success message shows "5 succeeded, 0 failed". | |
| TC-3.6 Reject with reason | Select 2 rows, click Reject, enter reason "Not actually PII — product codes". | Rows change to REJECTED. Reason stored. | |
| TC-3.7 Analyst cannot approve | Sign in as Analyst. Go to Approvals. | Checkboxes not visible; bulk action toolbar absent. | |
| TC-3.8 Double approve | Try to approve an already-APPROVED record | Response shows "Already in status APPROVED". Count: 1 failed. | |
| TC-3.9 Stats accuracy | After approving 10 and masking 5 | Dashboard KPIs: pending reduced, masking_coverage_pct updated | |

---

## TC-4: Masking

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-4.1 Apply email mask | Approve `patients.email`. Click Mask button. | Success. Column status → MASKED. `email()` DDM applied on DB. |  |
| TC-4.2 Apply partial mask (SSN) | Approve + mask `patients.ssn` | `partial(0,"XXX-XX-",4)` applied. DB shows `XXX-XX-6789` for users without UNMASK permission. | |
| TC-4.3 Apply default mask | Approve + mask `patients.date_of_birth` | `default()` applied. DB shows `01-01-1900` (SQL Server default for date). | |
| TC-4.4 Verify mask on DB | After masking, query the DB as a regular user (non-admin) | Masked values returned — not raw SSN/email | |
| TC-4.5 Verify admin still sees data | Query DB as admin | Raw data still visible to privileged users (DDM only masks non-privileged) | |
| TC-4.6 Mask unapproved column | Try to call `POST /approvals/{id}/mask` on a PENDING record directly via API | HTTP 400: "Cannot mask — approval is in status PENDING" | |
| TC-4.7 Audit trail | After masking, check Audit page | `masking.applied` entry visible with correct schema/table/column | |
| TC-4.8 Masking failure | Simulate DB error (revoke DDL permission temporarily) | Status → MASKING_FAILED. Error recorded in audit. Snackbar shows error. | |

---

## TC-5: Audit Log

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-5.1 Scan events appear | Run a scan | `scan.started` and `scan.completed` entries appear in audit | |
| TC-5.2 Approval events appear | Approve/reject records | `approval.submitted` entries appear with actor email | |
| TC-5.3 Masking events appear | Apply masking | `masking.applied` entry appears with DDL | |
| TC-5.4 Filter by action | Select "masking.applied" from dropdown | Only masking records shown | |
| TC-5.5 Export CSV | Click Export CSV | Downloads CSV file with correct columns | |
| TC-5.6 Immutability | Try to DELETE or PUT to `/audit/{id}` via API | HTTP 404 / 405 — no edit/delete endpoints exposed | |
| TC-5.7 Tenant isolation | Sign in as a different tenant's user | Cannot see audit logs from other tenant | |

---

## TC-6: Dashboard

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-6.1 KPI cards load | After running scans and approvals | All 4 KPI cards show non-zero values | |
| TC-6.2 Coverage bar | After masking some columns | Coverage % bar updates correctly | |
| TC-6.3 Power BI embed | With PBI configured | Embedded report renders without error | |
| TC-6.4 PBI fallback | Without PBI configured | Alert shown: "Power BI is not configured" — no crash | |
| TC-6.5 Viewer access | Sign in as Viewer | Dashboard loads correctly; no scan/approval features shown | |

---

## TC-7: Security Tests

| Test Case | Steps | Expected Result | Pass/Fail |
|-----------|-------|----------------|-----------|
| TC-7.1 No token | Call `GET /api/v1/approvals` without Authorization header | HTTP 403 | |
| TC-7.2 Invalid JWT | Call with `Authorization: Bearer garbage` | HTTP 401 | |
| TC-7.3 Wrong tenant | Generate a valid JWT for Tenant A, call `/approvals` as Tenant B's admin | HTTP 403 — tenant mismatch | |
| TC-7.4 HTTPS enforced | Try `http://` URL to App Service | Redirected to `https://` | |
| TC-7.5 Security headers | Inspect response headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `HSTS` present | |
| TC-7.6 Cross-tenant isolation | Scan data from Tenant A; sign in as Tenant B | Tenant B sees zero records | |
| TC-7.7 Secrets not in response | Inspect any API response | No connection strings, passwords, or client secrets in any response body | |

---

## TC-8: Performance Baseline

Run before stakeholder demo to establish baseline numbers.

| Test | Target | Tool | Result |
|------|--------|------|--------|
| Scan 500-column schema | < 90 seconds | Manual + timer | |
| Dashboard load | < 2 seconds | Browser DevTools | |
| Approvals page (200 rows) | < 1 second | Browser DevTools | |
| Bulk approve 100 records | < 5 seconds | Manual + timer | |
| API response (auth'd) | < 500ms p95 | Browser DevTools Network tab | |

---

## TC-9: Browser Compatibility

| Browser | Version | Dashboard | Scan | Approvals | Audit |
|---------|---------|-----------|------|-----------|-------|
| Chrome | Latest | | | | |
| Edge | Latest | | | | |
| Firefox | Latest | | | | |
| Safari | Latest | | | | |

---

## Bug Reporting Template

When you find a bug, log it with this format:

```
**Bug #XX — [Short Title]**
- Severity: P0 (crash) / P1 (broken feature) / P2 (cosmetic)
- Steps to reproduce:
  1. ...
  2. ...
- Expected: ...
- Actual: ...
- Screenshot/log: (attach)
- File likely affected: backend/... or frontend/...
```

Track bugs in a `docs/bugs.md` file and share with Bish weekly.

---

## Test Data SQL Script

Create this as `deploy/seed_test_data.sql`:

```sql
-- FabricShield AI Test Data
-- Run this on your test Azure SQL DB

CREATE TABLE [dbo].[patients] (
    patient_id INT IDENTITY PRIMARY KEY,
    first_name NVARCHAR(100),
    last_name NVARCHAR(100),
    ssn VARCHAR(11),
    email NVARCHAR(200),
    date_of_birth DATE,
    phone_number VARCHAR(20),
    home_address NVARCHAR(300),
    medical_record_number VARCHAR(20),
    diagnosis NVARCHAR(500),
    created_at DATETIME DEFAULT GETDATE()
);

CREATE TABLE [dbo].[employees] (
    employee_id INT IDENTITY PRIMARY KEY,
    full_name NVARCHAR(200),
    email_address NVARCHAR(200),
    ssn VARCHAR(11),
    date_of_birth DATE,
    salary DECIMAL(10,2),
    department NVARCHAR(100),
    manager_id INT,
    hire_date DATE
);

CREATE TABLE [dbo].[transactions] (
    transaction_id INT IDENTITY PRIMARY KEY,
    customer_name NVARCHAR(200),
    credit_card_number VARCHAR(20),
    account_number VARCHAR(30),
    amount DECIMAL(12,2),
    transaction_date DATETIME,
    merchant_name NVARCHAR(200),
    ip_address VARCHAR(45)
);

CREATE TABLE [dbo].[products] (
    product_id INT IDENTITY PRIMARY KEY,
    product_name NVARCHAR(200),
    description NVARCHAR(500),
    price DECIMAL(10,2),
    category NVARCHAR(100),
    sku VARCHAR(50)
);

-- Insert test data (obviously fake PII for testing only)
INSERT INTO [dbo].[patients] (first_name, last_name, ssn, email, date_of_birth, phone_number, home_address, medical_record_number, diagnosis)
VALUES
    ('John', 'Smith', '123-45-6789', 'john.smith@testpatient.com', '1980-03-15', '555-867-5309', '123 Main St, Springfield IL 62701', 'MRN-00123456', 'Hypertension'),
    ('Jane', 'Doe', '987-65-4321', 'jane.doe@testpatient.com', '1975-07-22', '555-555-1212', '456 Oak Ave, Chicago IL 60601', 'MRN-00234567', 'Type 2 Diabetes'),
    ('Bob', 'Johnson', '555-12-3456', 'bob.j@testmail.com', '1990-11-08', '312-555-0100', '789 Elm St, Naperville IL 60540', 'MRN-00345678', 'Asthma');

INSERT INTO [dbo].[employees] (full_name, email_address, ssn, date_of_birth, salary, department, hire_date)
VALUES
    ('Alice Brown', 'alice.brown@company.com', '444-55-6666', '1985-05-20', 85000.00, 'Engineering', '2020-01-15'),
    ('Carlos Rivera', 'carlos.r@company.com', '777-88-9999', '1992-09-14', 72000.00, 'Marketing', '2021-06-01');

INSERT INTO [dbo].[transactions] (customer_name, credit_card_number, account_number, amount, transaction_date, merchant_name, ip_address)
VALUES
    ('John Smith', '4532-1234-5678-9012', 'ACC-0001234567890', 299.99, GETDATE(), 'Amazon', '192.168.1.100'),
    ('Jane Doe', '5412-7534-1234-5678', 'ACC-0009876543210', 1250.00, GETDATE(), 'Best Buy', '10.0.0.55');

INSERT INTO [dbo].[products] (product_name, description, price, category, sku)
VALUES
    ('Widget Pro', 'Industrial grade widget', 49.99, 'Hardware', 'WGT-001'),
    ('Gadget X', 'Smart gadget with connectivity', 199.99, 'Electronics', 'GDG-X01');

PRINT 'Test data seeded successfully.'
PRINT 'Tables: patients (3 rows), employees (2 rows), transactions (2 rows), products (2 rows)'
PRINT 'Expected PII columns: 10 (SSN x2, email x2, DOB x2, phone, address, MRN, credit card, account, IP)'
```
