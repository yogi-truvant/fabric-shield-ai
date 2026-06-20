/* =============================================================================
   FabricShield AI — Least-Privilege Grant Script
   Tenant : Aqueducts (the CLIENT)            Run by: Aqueducts DBA / Entra admin
   -----------------------------------------------------------------------------
   PURPOSE
     Authorize FabricShield's multi-tenant service principal to (a) READ schema
     METADATA and (b) ALTER columns to add/drop masks — while making it
     PHYSICALLY IMPOSSIBLE for it to read a single row of data.

   PREREQUISITES (must be done first — see runbook §5)
     1. Aqueducts Global Admin has admin-consented the FabricShield app, creating
        its service principal (Enterprise App) in the Aqueducts tenant.
     2. An *Microsoft Entra admin* is set on the Azure SQL logical server
        (Portal > SQL server > Microsoft Entra ID > Set admin).
     3. You are connected TO THE TARGET DATABASE (not master) AS that Entra admin.

   HOW TO RUN
     - SSMS / Azure Data Studio / sqlcmd: run as-is (GO batch separators included).
     - Azure Portal "Query editor": it does NOT support GO — delete the GO lines
       and run each numbered section one at a time.
   ============================================================================= */

-- 0) SAFETY: confirm you are in the TARGET database, not master.
SELECT DB_NAME() AS current_database;     -- must NOT return 'master'
GO

-- 1) Create the database user mapped to FabricShield's service principal.
--    NAME must equal the Enterprise App display name in Aqueducts (default below).
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'FabricShield AI')
BEGIN
    CREATE USER [FabricShield AI] FROM EXTERNAL PROVIDER;
END
GO
/*  ── If the name is ambiguous or the plain form errors, use the Object ID form ──
    Get it from: Entra ID > Enterprise applications > FabricShield AI > Object ID,
    then replace the GUID and run THIS block instead of the one above.

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'FabricShield AI')
BEGIN
    CREATE USER [FabricShield AI] FROM EXTERNAL PROVIDER
        WITH OBJECT_ID = '00000000-0000-0000-0000-000000000000';
END
GO
*/

-- 2) Allow the principal to connect to this database.
GRANT CONNECT TO [FabricShield AI];
GO

-- 3) METADATA-ONLY read.
--    VIEW DEFINITION exposes sys.schemas / sys.tables / sys.columns /
--    INFORMATION_SCHEMA / sys.masked_columns — names, types, mask state.
--    It does NOT grant access to any row data.
GRANT VIEW DEFINITION TO [FabricShield AI];
--    Tighter alternative (per-schema; hides proc/view bodies elsewhere):
--    GRANT VIEW DEFINITION ON SCHEMA::[dbo] TO [FabricShield AI];
GO

-- 4) APPLY / ALTER masks. Minimum needed for ALTER COLUMN ... ADD MASKED / DROP MASKED.
GRANT ALTER ANY MASK TO [FabricShield AI];
GRANT ALTER ON SCHEMA::[dbo] TO [FabricShield AI];   -- repeat per in-scope schema
GO

-- 5) DEFENSE IN DEPTH — explicitly forbid data reads + unmasking.
--    IMPORTANT: scope the SELECT deny to the user schema(s). Do NOT issue a
--    database-wide "DENY SELECT TO [user]" — that also blocks the system catalog
--    views and would break metadata scanning.
DENY SELECT ON SCHEMA::[dbo] TO [FabricShield AI];   -- repeat per in-scope schema
DENY UNMASK TO [FabricShield AI];                    -- never allowed to see clear data
GO
/*  NOTE: SELECT is never granted in this script, so even without the DENY the
    principal cannot read rows. The DENY makes the guarantee explicit & audit-ready,
    and prevents a future accidental GRANT SELECT from taking effect. */

-- 6) (Optional) Grant UNMASK to a privileged data-steward role for legitimate
--    clear-text access. NEVER grant UNMASK to [FabricShield AI].
--    CREATE ROLE [DataSteward];
--    GRANT UNMASK TO [DataSteward];
--    ALTER ROLE [DataSteward] ADD MEMBER [some-admin-user];
GO

-- 7) VERIFY effective permissions for the principal.
SELECT pr.name                              AS principal,
       pe.permission_name,
       pe.state_desc,
       pe.class_desc,
       COALESCE(s.name, OBJECT_SCHEMA_NAME(pe.major_id)) AS scope
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pe.grantee_principal_id = pr.principal_id
LEFT JOIN sys.schemas s ON pe.class = 3 AND pe.major_id = s.schema_id
WHERE pr.name = N'FabricShield AI'
ORDER BY pe.permission_name;
GO

/*  EXPECTED RESULT:
      ALTER            GRANT  (SCHEMA dbo)
      ALTER ANY MASK   GRANT  (DATABASE)
      CONNECT          GRANT  (DATABASE)
      SELECT           DENY   (SCHEMA dbo)
      UNMASK           DENY   (DATABASE)
      VIEW DEFINITION  GRANT  (DATABASE)

   NEGATIVE TEST (run from the app or impersonate; should FAIL with permission denied):
      EXECUTE AS USER = 'FabricShield AI';
      SELECT TOP 1 * FROM dbo.Patients;     -- expect: msg 229, SELECT denied
      REVERT;
*/
