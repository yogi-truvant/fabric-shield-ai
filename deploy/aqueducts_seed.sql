/* ============================================================================
   FabricShield AI — Aqueducts Test Seed (run against EACH database: dev, then test)
   Creates schemas [clinical] and [billing], 3 tables each, with synthetic PII/PHI.
   Synthetic only: 900-series SSNs, 4111 test card, example.com. No real data.
   Works in sqlcmd AND the Azure Portal Query Editor (no GO batches required).
   ============================================================================ */
SET NOCOUNT ON;
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='clinical') EXEC('CREATE SCHEMA [clinical]');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='billing')  EXEC('CREATE SCHEMA [billing]');

DROP TABLE IF EXISTS [clinical].[Patients];
CREATE TABLE [clinical].[Patients] (
    [PatientID] INT IDENTITY(1,1) PRIMARY KEY,
    [MRN] NVARCHAR(20) NULL,
    [DateOfBirth] DATE NULL,
    [PhoneNumber] NVARCHAR(20) NULL,
    [Email] NVARCHAR(120) NULL,
    [RecordStatus] NVARCHAR(20) NULL,
    [CreatedDate] DATETIME2 NULL
);
INSERT INTO [clinical].[Patients] ([MRN], [DateOfBirth], [PhoneNumber], [Email], [RecordStatus], [CreatedDate]) VALUES
('MRN777568', '1963-10-30', '+1-555-1076', 'jane.doe@example.com', 'pending', '2025-03-30 03:58:42'),
('MRN360735', '1972-03-10', '+1-555-1248', 'john.smith@example.com', 'closed', '2023-05-24 15:21:36'),
('MRN292401', '1979-12-28', '+1-555-1593', 'maria.garcia@example.com', 'active', '2024-03-29 20:02:12'),
('MRN202664', '1959-07-16', '+1-555-1838', 'wei.chen@example.com', 'active', '2025-09-19 03:23:44'),
('MRN890170', '1976-03-16', '+1-555-1216', 'aisha.khan@example.com', 'closed', '2024-05-07 07:46:56'),
('MRN520521', '1960-04-05', '+1-555-1216', 'carlos.lopez@example.com', 'active', '2024-02-04 09:39:20'),
('MRN922157', '1995-10-27', '+1-555-1366', 'priya.patel@example.com', 'closed', '2023-06-08 06:54:50'),
('MRN411120', '1974-07-13', '+1-555-1079', 'tom.brown@example.com', 'active', '2025-02-04 11:25:04'),
('MRN159942', '1959-07-02', '+1-555-1747', 'lena.mueller@example.com', 'inactive', '2023-02-28 18:29:22'),
('MRN184002', '1971-09-03', '+1-555-1089', 'omar.hassan@example.com', 'active', '2024-11-22 08:33:48');

DROP TABLE IF EXISTS [clinical].[Encounters];
CREATE TABLE [clinical].[Encounters] (
    [EncounterID] INT IDENTITY(1,1) PRIMARY KEY,
    [MRN] NVARCHAR(20) NULL,
    [DateOfBirth] DATE NULL,
    [Quantity] INT NULL,
    [RecordStatus] NVARCHAR(20) NULL,
    [CreatedDate] DATETIME2 NULL
);
INSERT INTO [clinical].[Encounters] ([MRN], [DateOfBirth], [Quantity], [RecordStatus], [CreatedDate]) VALUES
('MRN523389', '1965-10-03', 73, 'inactive', '2024-08-15 21:38:44'),
('MRN141672', '1962-05-10', 54, 'pending', '2025-08-15 09:29:39'),
('MRN314181', '1983-03-10', 31, 'pending', '2024-02-10 04:45:54'),
('MRN804318', '1981-11-30', 59, 'pending', '2025-08-09 02:38:28'),
('MRN109767', '1996-02-12', 80, 'active', '2023-03-17 19:34:28'),
('MRN323508', '2000-05-20', 34, 'inactive', '2025-08-13 12:42:25'),
('MRN172132', '1976-11-30', 48, 'pending', '2023-06-11 15:57:13'),
('MRN974244', '2003-09-26', 91, 'pending', '2024-09-18 23:48:37'),
('MRN654634', '1955-09-14', 86, 'pending', '2025-08-12 03:46:17'),
('MRN240814', '1978-09-23', 15, 'active', '2025-01-30 20:08:32');

DROP TABLE IF EXISTS [clinical].[Demographics];
CREATE TABLE [clinical].[Demographics] (
    [DemographicID] INT IDENTITY(1,1) PRIMARY KEY,
    [SSN] NVARCHAR(11) NULL,
    [Email] NVARCHAR(120) NULL,
    [PhoneNumber] NVARCHAR(20) NULL,
    [DateOfBirth] DATE NULL,
    [RecordStatus] NVARCHAR(20) NULL
);
INSERT INTO [clinical].[Demographics] ([SSN], [Email], [PhoneNumber], [DateOfBirth], [RecordStatus]) VALUES
('900-29-5462', 'jane.doe@example.com', '+1-555-1369', '1973-11-23', 'pending'),
('900-36-5325', 'john.smith@example.com', '+1-555-1647', '1977-07-12', 'active'),
('900-21-7939', 'maria.garcia@example.com', '+1-555-1350', '1955-04-27', 'pending'),
('900-26-5291', 'wei.chen@example.com', '+1-555-1207', '1993-05-15', 'active'),
('900-24-2232', 'aisha.khan@example.com', '+1-555-1882', '2003-12-12', 'active'),
('900-57-3426', 'carlos.lopez@example.com', '+1-555-1552', '1958-10-02', 'pending'),
('900-56-1653', 'priya.patel@example.com', '+1-555-1453', '1977-05-21', 'active'),
('900-55-7658', 'tom.brown@example.com', '+1-555-1792', '1976-03-28', 'inactive'),
('900-32-7755', 'lena.mueller@example.com', '+1-555-1032', '1984-10-20', 'closed'),
('900-95-5065', 'omar.hassan@example.com', '+1-555-1342', '1964-09-12', 'closed');

DROP TABLE IF EXISTS [billing].[Invoices];
CREATE TABLE [billing].[Invoices] (
    [InvoiceID] INT IDENTITY(1,1) PRIMARY KEY,
    [Email] NVARCHAR(120) NULL,
    [CreditCardNumber] NVARCHAR(19) NULL,
    [Amount] DECIMAL(12,2) NULL,
    [RecordStatus] NVARCHAR(20) NULL,
    [CreatedDate] DATETIME2 NULL
);
INSERT INTO [billing].[Invoices] ([Email], [CreditCardNumber], [Amount], [RecordStatus], [CreatedDate]) VALUES
('jane.doe@example.com', '4111-1111-1111-1634', 8586.49, 'inactive', '2023-07-24 16:45:32'),
('john.smith@example.com', '4111-1111-1111-6728', 3058.55, 'inactive', '2023-08-17 00:51:41'),
('maria.garcia@example.com', '4111-1111-1111-4164', 3990.28, 'pending', '2025-06-04 02:31:39'),
('wei.chen@example.com', '4111-1111-1111-5573', 3517.6, 'closed', '2024-11-26 19:31:22'),
('aisha.khan@example.com', '4111-1111-1111-6425', 9392.04, 'active', '2025-06-17 09:30:37'),
('carlos.lopez@example.com', '4111-1111-1111-3925', 5809.51, 'pending', '2023-02-09 03:56:48'),
('priya.patel@example.com', '4111-1111-1111-8119', 3463.07, 'pending', '2024-03-22 22:04:17'),
('tom.brown@example.com', '4111-1111-1111-9379', 1165.19, 'inactive', '2023-09-18 01:36:57'),
('lena.mueller@example.com', '4111-1111-1111-8144', 26.89, 'inactive', '2024-01-08 15:42:11'),
('omar.hassan@example.com', '4111-1111-1111-2146', 9488.31, 'pending', '2024-09-30 11:25:45');

DROP TABLE IF EXISTS [billing].[Payments];
CREATE TABLE [billing].[Payments] (
    [PaymentID] INT IDENTITY(1,1) PRIMARY KEY,
    [CreditCardNumber] NVARCHAR(19) NULL,
    [Amount] DECIMAL(12,2) NULL,
    [Quantity] INT NULL,
    [CreatedDate] DATETIME2 NULL,
    [RecordStatus] NVARCHAR(20) NULL
);
INSERT INTO [billing].[Payments] ([CreditCardNumber], [Amount], [Quantity], [CreatedDate], [RecordStatus]) VALUES
('4111-1111-1111-3041', 7199.63, 39, '2024-06-03 11:15:38', 'closed'),
('4111-1111-1111-6344', 4029.58, 38, '2024-07-21 04:38:03', 'inactive'),
('4111-1111-1111-7888', 6651.98, 49, '2024-11-24 06:20:10', 'pending'),
('4111-1111-1111-7653', 5483.34, 1, '2023-11-08 10:26:46', 'inactive'),
('4111-1111-1111-8043', 7858.94, 78, '2024-11-01 11:43:57', 'closed'),
('4111-1111-1111-8238', 4426.73, 28, '2024-06-07 17:13:41', 'inactive'),
('4111-1111-1111-2389', 2844.74, 85, '2024-10-10 22:32:47', 'pending'),
('4111-1111-1111-2530', 8185.23, 97, '2023-08-29 11:18:07', 'inactive'),
('4111-1111-1111-4262', 1481.92, 6, '2023-09-08 17:17:57', 'active'),
('4111-1111-1111-8461', 4149.85, 81, '2024-08-12 07:04:45', 'closed');

DROP TABLE IF EXISTS [billing].[Accounts];
CREATE TABLE [billing].[Accounts] (
    [AccountID] INT IDENTITY(1,1) PRIMARY KEY,
    [SSN] NVARCHAR(11) NULL,
    [Email] NVARCHAR(120) NULL,
    [PhoneNumber] NVARCHAR(20) NULL,
    [Amount] DECIMAL(12,2) NULL,
    [RecordStatus] NVARCHAR(20) NULL
);
INSERT INTO [billing].[Accounts] ([SSN], [Email], [PhoneNumber], [Amount], [RecordStatus]) VALUES
('900-73-7547', 'jane.doe@example.com', '+1-555-1312', 6563.36, 'active'),
('900-23-7965', 'john.smith@example.com', '+1-555-1282', 8042.25, 'closed'),
('900-16-5082', 'maria.garcia@example.com', '+1-555-1157', 1341.92, 'closed'),
('900-95-9702', 'wei.chen@example.com', '+1-555-1719', 3179.49, 'closed'),
('900-88-9270', 'aisha.khan@example.com', '+1-555-1548', 4464.23, 'inactive'),
('900-70-8373', 'carlos.lopez@example.com', '+1-555-1333', 8399.39, 'pending'),
('900-76-8939', 'priya.patel@example.com', '+1-555-1803', 2752.95, 'active'),
('900-46-4841', 'tom.brown@example.com', '+1-555-1345', 3203.58, 'active'),
('900-27-3471', 'lena.mueller@example.com', '+1-555-1296', 6941.86, 'inactive'),
('900-18-7797', 'omar.hassan@example.com', '+1-555-1525', 5430.14, 'closed');

PRINT 'Seed complete for current database: 2 schemas (clinical, billing), 6 tables.';
