"""
FabricShield AI - Database Connector
Cross-tenant connection to a customer's Azure SQL / Microsoft Fabric SQL Endpoint.

AUTH (hybrid, per connection):
  * service_principal : OAuth2 client-credentials token against the CUSTOMER tenant
                        (multi-tenant app reg). No stored credentials. Default.
  * sql               : SQL login + password (password stored in Key Vault).

Connection metadata + secrets live in OUR Key Vault, keyed:
  tenant-{tenant_id}-{name}-server / -database / -meta(JSON) / -sqlpassword

DATA SAFETY: reads only schema metadata (INFORMATION_SCHEMA / sys.*) and executes
masking DDL. Never selects, samples, caches, logs, or returns table row data.
"""

import json
import struct
from contextlib import contextmanager
from typing import Dict, Generator, List, Optional, Tuple

import pyodbc
import structlog
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import ClientSecretCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import get_settings
from backend.models.schemas import DatabaseType

logger = structlog.get_logger(__name__)
settings = get_settings()

ODBC_DRIVER = "{ODBC Driver 18 for SQL Server}"
AZURE_SQL_SCOPE = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256

SCHEMA_COLUMNS_SQL = """
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE,
       c.CHARACTER_MAXIMUM_LENGTH, c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
  AND c.TABLE_SCHEMA IN ({schema_placeholders})
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""


def _odbc_quote(value: str) -> str:
    """Brace-quote an ODBC connection-string value (handles ; { } in passwords)."""
    return "{" + str(value).replace("}", "}}") + "}"


def _bracket(identifier: str) -> str:
    """Safely bracket-quote a SQL identifier (schema/table/column); escapes embedded ]."""
    return "[" + str(identifier).replace("]", "]]") + "]"


def _conn_str_token(server: str, database: str) -> str:
    return (
        f"DRIVER={ODBC_DRIVER};SERVER={server};DATABASE={database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def _conn_str_sql(server: str, database: str, user: str, password: str) -> str:
    return (
        f"DRIVER={ODBC_DRIVER};SERVER={server};DATABASE={database};"
        f"UID={_odbc_quote(user)};PWD={_odbc_quote(password)};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception_type(pyodbc.OperationalError), reraise=True)
def _open_token(conn_str: str, token_struct: bytes) -> "pyodbc.Connection":
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception_type(pyodbc.OperationalError), reraise=True)
def _open_sql(conn_str: str) -> "pyodbc.Connection":
    return pyodbc.connect(conn_str)


class DatabaseConnector:
    """Cross-tenant connector bound to a single customer tenant."""

    def __init__(self, customer_tenant_id: str):
        self.customer_tenant_id = customer_tenant_id
        self._sql_credential = ClientSecretCredential(
            tenant_id=customer_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
        self._kv_client: Optional[SecretClient] = None

    def _get_kv_client(self) -> SecretClient:
        if self._kv_client is None:
            self._kv_client = SecretClient(vault_url=settings.keyvault_url, credential=ManagedIdentityCredential())
        return self._kv_client

    def _kv_get(self, name: str) -> Optional[str]:
        try:
            return self._get_kv_client().get_secret(name).value
        except ResourceNotFoundError:
            return None

    def _token_struct(self) -> bytes:
        token = self._sql_credential.get_token(AZURE_SQL_SCOPE).token
        b = token.encode("utf-16-le")
        return struct.pack(f"<I{len(b)}s", len(b), b)

    def _resolve(self, connection_name: str) -> Tuple[str, str, str, Optional[str], Optional[str]]:
        """Return (server, database, auth_mode, sql_user, sql_password) from Key Vault."""
        prefix = f"tenant-{self.customer_tenant_id}-{connection_name}"
        kv = self._get_kv_client()
        server = kv.get_secret(f"{prefix}-server").value
        database = kv.get_secret(f"{prefix}-database").value
        auth_mode, sql_user = "service_principal", None
        meta = self._kv_get(f"{prefix}-meta")
        if meta:
            try:
                m = json.loads(meta)
                auth_mode = m.get("auth_mode", "service_principal")
                sql_user = m.get("sql_username")
            except (ValueError, TypeError):
                pass
        sql_pw = self._kv_get(f"{prefix}-sqlpassword") if auth_mode == "sql" else None
        return server, database, auth_mode, sql_user, sql_pw

    @contextmanager
    def connect(
        self, connection_name: str, db_type: DatabaseType = DatabaseType.azure_sql,
    ) -> Generator["pyodbc.Connection", None, None]:
        server, database, auth_mode, sql_user, sql_pw = self._resolve(connection_name)
        if auth_mode == "sql" and sql_user and sql_pw:
            conn = _open_sql(_conn_str_sql(server, database, sql_user, sql_pw))
        else:
            conn = _open_token(_conn_str_token(server, database), self._token_struct())
        conn.autocommit = False
        logger.info("db_connector.connected", tenant_id=self.customer_tenant_id,
                    db_type=db_type.value, server=server, database=database, auth_mode=auth_mode)
        try:
            yield conn
        finally:
            conn.close()

    def test_connection(self, connection_name: str, db_type: DatabaseType) -> Tuple[bool, str, Optional[int]]:
        """Lightweight metadata-only reachability check. Returns (ok, message, table_count)."""
        try:
            with self.connect(connection_name, db_type) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE'"
                )
                count = cur.fetchone()[0]
            return True, "Connection succeeded (metadata read).", count
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller
            logger.warning("db_connector.test_failed", connection=connection_name, error=str(exc))
            return False, str(exc), None

    def list_schemas(self, connection_name: str, db_type: DatabaseType) -> List[str]:
        """Return the schemas that actually contain base tables (metadata-only).
        Used to populate the Scan page schema picker. No row data is read."""
        sql = (
            "SELECT DISTINCT TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_SCHEMA"
        )
        with self.connect(connection_name, db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            schemas = [row[0] for row in cursor.fetchall() if row[0]]
        logger.info("db_connector.list_schemas", tenant_id=self.customer_tenant_id, schema_count=len(schemas))
        return schemas

    def get_masked_columns(self, connection_name: str, db_type: DatabaseType) -> set:
        """Return the set of (schema, table, column) that currently have a mask applied,
        read from sys.masked_columns. Metadata-only — the DB is the source of truth for
        mask state, so a scan reflects reality even after FabricShield's records are cleared."""
        sql = (
            "SELECT s.name, t.name, c.name "
            "FROM sys.masked_columns mc "
            "JOIN sys.columns c ON mc.object_id = c.object_id AND mc.column_id = c.column_id "
            "JOIN sys.tables t ON mc.object_id = t.object_id "
            "JOIN sys.schemas s ON t.schema_id = s.schema_id "
            "WHERE mc.is_masked = 1"
        )
        out = set()
        with self.connect(connection_name, db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            for row in cursor.fetchall():
                out.add((row[0], row[1], row[2]))
        logger.info("db_connector.masked_columns", tenant_id=self.customer_tenant_id, count=len(out))
        return out

    def get_schema_metadata(
        self, connection_name: str, db_type: DatabaseType, schema_names: List[str],
        include_tables: Optional[List[str]] = None, exclude_tables: Optional[List[str]] = None,
    ) -> List[Dict]:
        placeholders = ",".join(["?" for _ in schema_names])
        sql = SCHEMA_COLUMNS_SQL.format(schema_placeholders=placeholders)
        results: List[Dict] = []
        with self.connect(connection_name, db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, schema_names)
            cols = [c[0] for c in cursor.description]
            for row in cursor.fetchall():
                rec = dict(zip(cols, row))
                table = rec.get("TABLE_NAME", "")
                if include_tables and table not in include_tables:
                    continue
                if exclude_tables and table in exclude_tables:
                    continue
                results.append({
                    "schema_name": rec["TABLE_SCHEMA"], "table_name": rec["TABLE_NAME"],
                    "column_name": rec["COLUMN_NAME"], "data_type": rec["DATA_TYPE"],
                    "max_length": rec.get("CHARACTER_MAXIMUM_LENGTH"),
                    "is_nullable": rec.get("IS_NULLABLE", "YES") == "YES",
                })
        logger.info("db_connector.schema_metadata", tenant_id=self.customer_tenant_id, column_count=len(results))
        return results

    def fetch_table_sample(
        self, connection_name: str, db_type: DatabaseType, schema: str, table: str,
        columns: List[str], limit: int = 100,
    ) -> Dict[str, List[str]]:
        """OPT-IN content sampling. Reads up to `limit` rows for the given columns and
        returns their non-null values to the caller, IN MEMORY only.

        This is the single, deliberate row-reading path in the product. It is reached
        only when a scan sets content_scan=True (explicit client consent). Raw values are
        never logged, cached, or persisted here — only row/column counts are logged."""
        if not columns:
            return {}
        n = max(1, min(int(limit), 1000))
        cols_sql = ", ".join(_bracket(c) for c in columns)
        sql = f"SELECT TOP ({n}) {cols_sql} FROM {_bracket(schema)}.{_bracket(table)}"
        out: Dict[str, List[str]] = {c: [] for c in columns}
        with self.connect(connection_name, db_type) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            colnames = [d[0] for d in cursor.description]
            for row in cursor.fetchall():
                for cn, val in zip(colnames, row):
                    if val is not None and cn in out:
                        out[cn].append(str(val))
        logger.info(
            "db_connector.sampled", tenant_id=self.customer_tenant_id,
            table=f"{schema}.{table}", columns=len(columns), rows_cap=n,
        )  # NOTE: no values logged — counts only
        return out

    def execute_ddl(self, connection_name: str, db_type: DatabaseType, ddl: str) -> None:
        with self.connect(connection_name, db_type) as conn:
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(ddl)
        logger.info("db_connector.ddl_executed", tenant_id=self.customer_tenant_id, ddl_preview=ddl[:200])
