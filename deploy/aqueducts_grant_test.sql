/* ============================================================================
   FabricShield AI — Least-Privilege Grant (Aqueducts TEST database)
   Run by an AQUEDUCTS admin, connected to the `test` database on aqctest,
   AUTHENTICATED AS THE MICROSOFT ENTRA ADMIN (not SQL auth) — external-provider
   users can only be created from an Entra-authenticated session.

   Prereqs: (1) admin consent granted to the FabricShield app in Aqueducts,
            (2) an Entra admin set on the aqctest server.
   Works in the Portal Query Editor (no GO batches needed).
   ============================================================================ */

SELECT DB_NAME() AS current_database;   -- must be 'test'

-- 1) Map the FabricShield service principal to a contained DB user.
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'FabricShield AI')
    EXEC('CREATE USER [FabricShield AI] FROM EXTERNAL PROVIDER');
/*  If the name is ambiguous, use the SP Object ID from
    Entra ID > Enterprise applications > FabricShield AI > Object ID:
    EXEC('CREATE USER [FabricShield AI] FROM EXTERNAL PROVIDER WITH OBJECT_ID = ''<sp-object-id>'''); */

-- 2) Connect.
GRANT CONNECT TO [FabricShield AI];

-- 3) METADATA-ONLY read (DB-wide: covers dbo, clinical, billing). No row access.
GRANT VIEW DEFINITION TO [FabricShield AI];

-- 4) Apply/alter masks on the schemas that actually hold the seeded tables.
GRANT ALTER ANY MASK TO [FabricShield AI];
GRANT ALTER ON SCHEMA::[clinical] TO [FabricShield AI];
GRANT ALTER ON SCHEMA::[billing]  TO [FabricShield AI];

-- 5) Defense in depth — forbid row reads + unmasking (schema-scoped, NOT db-wide,
--    so catalog/metadata stay readable for the scan).
DENY SELECT ON SCHEMA::[clinical] TO [FabricShield AI];
DENY SELECT ON SCHEMA::[billing]  TO [FabricShield AI];
DENY SELECT ON SCHEMA::[dbo]      TO [FabricShield AI];
DENY UNMASK TO [FabricShield AI];

-- 6) Verify effective permissions.
SELECT pr.name AS principal, pe.permission_name, pe.state_desc,
       COALESCE(s.name, pe.class_desc) AS scope
FROM sys.database_permissions pe
JOIN sys.database_principals pr ON pe.grantee_principal_id = pr.principal_id
LEFT JOIN sys.schemas s ON pe.class = 3 AND pe.major_id = s.schema_id
WHERE pr.name = N'FabricShield AI'
ORDER BY pe.permission_name;

/* EXPECTED:
   ALTER            GRANT  clinical
   ALTER            GRANT  billing
   ALTER ANY MASK   GRANT  DATABASE
   CONNECT          GRANT  DATABASE
   SELECT           DENY   clinical / billing / dbo
   UNMASK           DENY   DATABASE
   VIEW DEFINITION  GRANT  DATABASE
   NEGATIVE TEST (should FAIL):  EXECUTE AS USER='FabricShield AI'; SELECT TOP 1 * FROM clinical.Patients; REVERT; */
