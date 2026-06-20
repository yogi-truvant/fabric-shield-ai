/* =============================================================================
   FabricShield AI — Seed Test Schema (dummy PII)
   -----------------------------------------------------------------------------
   Run this on a NON-PRODUCTION test database to exercise the full
   scan -> approve -> mask -> verify loop. Do NOT run on a client's real DB.

   All values are synthetic: SSNs use the invalid 900-series, the card number is
   the well-known Visa test number, emails use example.com. No real PII.

   Column names are deliberately obvious so the metadata-only detector flags them;
   a few control columns (Amount, RecordStatus, HireDate, ...) must NOT be flagged.
   ============================================================================= */

SET NOCOUNT ON;
GO

-- ── Patients ────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dbo.Patients;
GO
CREATE TABLE dbo.Patients (
    PatientID       INT IDENTITY(1,1) PRIMARY KEY,   -- flagged: patient id (PHI identifier)
    MRN             NVARCHAR(20)  NOT NULL,           -- flagged: medical record number
    FirstName       NVARCHAR(60)  NOT NULL,           -- flagged: person name
    LastName        NVARCHAR(60)  NOT NULL,           -- flagged: person name
    DateOfBirth     DATE          NULL,               -- flagged: DOB
    SSN             NVARCHAR(11)  NULL,               -- flagged: SSN
    Email           NVARCHAR(120) NULL,               -- flagged: email
    PhoneNumber     NVARCHAR(20)  NULL,               -- flagged: phone
    StreetAddress   NVARCHAR(160) NULL,               -- flagged: location
    City            NVARCHAR(80)  NULL,               -- flagged: location
    State           NVARCHAR(40)  NULL,               -- flagged: location
    ZipCode         NVARCHAR(10)  NULL,               -- flagged: location
    Diagnosis       NVARCHAR(200) NULL,               -- flagged: PHI
    MedicationName  NVARCHAR(120) NULL,               -- flagged: PHI
    RecordStatus    NVARCHAR(20)  NULL,               -- CONTROL: must NOT flag
    CreatedAt       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()  -- CONTROL: must NOT flag
);
GO
INSERT INTO dbo.Patients (MRN, FirstName, LastName, DateOfBirth, SSN, Email, PhoneNumber, StreetAddress, City, State, ZipCode, Diagnosis, MedicationName, RecordStatus) VALUES
 (N'MRN000001', N'Jane',  N'Doe',     '1984-03-12', N'900-00-0001', N'jane.doe@example.com',   N'+1-555-0100', N'1 Test St',   N'Austin',  N'TX', N'73301', N'Type 2 Diabetes', N'Metformin',  N'active'),
 (N'MRN000002', N'John',  N'Smith',   '1979-11-02', N'900-00-0002', N'john.smith@example.com', N'+1-555-0101', N'2 Demo Ave',  N'Seattle', N'WA', N'98101', N'Hypertension',    N'Lisinopril', N'active'),
 (N'MRN000003', N'Maria', N'Garcia',  '1992-07-25', N'900-00-0003', N'maria.g@example.com',    N'+1-555-0102', N'3 Sample Rd', N'Miami',   N'FL', N'33101', N'Asthma',          N'Albuterol',  N'inactive'),
 (N'MRN000004', N'Wei',   N'Chen',    '1968-01-30', N'900-00-0004', N'wei.chen@example.com',   N'+1-555-0103', N'4 Mock Blvd', N'Boston',  N'MA', N'02101', N'Migraine',        N'Sumatriptan',N'active'),
 (N'MRN000005', N'Aisha', N'Khan',    '2001-09-09', N'900-00-0005', N'aisha.k@example.com',    N'+1-555-0104', N'5 Fake Ln',   N'Denver',  N'CO', N'80201', N'Anemia',          N'Ferrous',    N'active');
GO

-- ── Employees ───────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dbo.Employees;
GO
CREATE TABLE dbo.Employees (
    EmployeeID         INT IDENTITY(1,1) PRIMARY KEY,  -- CONTROL: must NOT flag
    FullName           NVARCHAR(120) NOT NULL,          -- flagged: person name
    SSN                NVARCHAR(11)  NULL,              -- flagged: SSN
    Email              NVARCHAR(120) NULL,              -- flagged: email
    BankAccountNumber  NVARCHAR(34)  NULL,              -- flagged: bank/IBAN
    RoutingNumber      NVARCHAR(20)  NULL,              -- flagged: routing
    AnnualSalary       DECIMAL(12,2) NULL,              -- CONTROL: must NOT flag
    HireDate           DATE          NULL               -- CONTROL: must NOT flag
);
GO
INSERT INTO dbo.Employees (FullName, SSN, Email, BankAccountNumber, RoutingNumber, AnnualSalary, HireDate) VALUES
 (N'Riley Adams',  N'900-10-0001', N'riley@example.com',  N'GB29NWBK60161331926819', N'021000021', 88000.00, '2020-02-01'),
 (N'Sam Patel',    N'900-10-0002', N'sam@example.com',    N'DE89370400440532013000', N'011000015', 102500.00,'2018-06-15'),
 (N'Toni Rossi',   N'900-10-0003', N'toni@example.com',   N'FR1420041010050500013M02606', N'026009593', 75000.00,'2021-09-20'),
 (N'Kim Lee',      N'900-10-0004', N'kim@example.com',    N'US64SVBKUS6S3300958879',  N'121000358', 96000.00, '2019-11-11');
GO

-- ── Transactions ──────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dbo.Transactions;
GO
CREATE TABLE dbo.Transactions (
    TransactionID        INT IDENTITY(1,1) PRIMARY KEY,  -- CONTROL: must NOT flag
    PatientID            INT NULL,                        -- flagged: patient id
    CreditCardNumber     NVARCHAR(19) NULL,               -- flagged: credit card
    CVV                  NVARCHAR(4)  NULL,               -- flagged: credit card
    IBAN                 NVARCHAR(34) NULL,               -- flagged: IBAN
    Amount               DECIMAL(12,2) NULL,              -- CONTROL: must NOT flag
    TransactionTimestamp DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()  -- CONTROL: must NOT flag
);
GO
INSERT INTO dbo.Transactions (PatientID, CreditCardNumber, CVV, IBAN, Amount) VALUES
 (1, N'4111111111111111', N'123', N'GB29NWBK60161331926819', 120.50),
 (2, N'4111111111111111', N'456', N'DE89370400440532013000', 75.00),
 (3, N'4111111111111111', N'789', N'FR1420041010050500013M02606', 250.25),
 (4, N'4111111111111111', N'234', N'US64SVBKUS6S3300958879', 999.99),
 (5, N'4111111111111111', N'567', N'GB29NWBK60161331926819', 42.00);
GO

-- ── Providers ─────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS dbo.Providers;
GO
CREATE TABLE dbo.Providers (
    ProviderID        INT IDENTITY(1,1) PRIMARY KEY,  -- flagged: provider id (NPI family)
    NPI               NVARCHAR(10) NULL,               -- flagged: NPI
    DEANumber         NVARCHAR(12) NULL,               -- flagged: DEA
    ProviderFullName  NVARCHAR(120) NULL,              -- flagged: person name
    Email             NVARCHAR(120) NULL,              -- flagged: email
    IsActive          BIT NOT NULL DEFAULT 1            -- CONTROL: must NOT flag
);
GO
INSERT INTO dbo.Providers (NPI, DEANumber, ProviderFullName, Email) VALUES
 (N'1234567890', N'AB1234567', N'Dr. Pat Morgan', N'pmorgan@example.com'),
 (N'1987654321', N'CD7654321', N'Dr. Lee Brooks', N'lbrooks@example.com'),
 (N'1555555555', N'EF1112223', N'Dr. Sky Nguyen', N'snguyen@example.com');
GO

PRINT 'Seed complete: dbo.Patients, dbo.Employees, dbo.Transactions, dbo.Providers';
GO
