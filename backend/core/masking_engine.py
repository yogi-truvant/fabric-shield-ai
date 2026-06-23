"""
FabricShield AI — Dynamic Data Masking Engine
Applies Azure SQL / Microsoft Fabric Dynamic Data Masking (DDM) via T-SQL ALTER COLUMN.

Security: object identifiers are escaped (QUOTENAME-equivalent) before interpolation.
T-SQL cannot parameterize object names, so callers MUST also whitelist (schema, table,
column) against the scanned metadata before invoking apply_mask().
"""

from datetime import datetime, timezone

import structlog

from backend.core.db_connector import DatabaseConnector
from backend.models.schemas import DatabaseType, MaskType, MaskingResult

logger = structlog.get_logger(__name__)


# ─── Identifier safety ────────────────────────────────────────────────────────

def _q(ident: str) -> str:
    """QUOTENAME-equivalent: validate, escape ] -> ]] , and wrap in [].
    Prevents bracket-breakout SQL injection via crafted object names."""
    if ident is None or not isinstance(ident, str) or ident == "" or len(ident) > 128 or "\x00" in ident:
        raise ValueError(f"illegal SQL identifier: {ident!r}")
    return "[" + ident.replace("]", "]]") + "]"


# ─── DDM SQL Builders ─────────────────────────────────────────────────────────

_NUMERIC_HINTS = ("int", "numeric", "decimal", "money", "float", "real", "bigint", "smallint", "tinyint")


def _build_ddm_sql(
    schema: str,
    table: str,
    column: str,
    data_type: str,
    mask_type: MaskType,
    partial_prefix: int = 0,
    partial_suffix: str = "XXXX",
    partial_suffix_size: int = 4,
) -> str:
    """Build a T-SQL DDM statement for a column.

    DDM functions:
      default()       full mask, type default
      email()         aXXX@XXXX.com
      partial(p,m,s)  show p prefix chars, literal m, s suffix chars  (text types only)
      random(lo,hi)   random number in range  (numeric types only)
    """
    dt = data_type.lower()

    if mask_type == MaskType.email:
        mask_func = "email()"
    elif mask_type == MaskType.partial:
        if any(k in dt for k in _NUMERIC_HINTS):
            mask_func = "default()"  # partial() is unsupported on numeric types
        else:
            pad = str(partial_suffix).replace('"', "").replace("'", "")
            mask_func = f'partial({int(partial_prefix)},"{pad}",{int(partial_suffix_size)})'
    elif mask_type == MaskType.random:
        mask_func = "random(1, 9999)" if "int" in dt else "default()"
    else:
        mask_func = "default()"

    return (
        f"ALTER TABLE {_q(schema)}.{_q(table)} "
        f"ALTER COLUMN {_q(column)} ADD MASKED WITH (FUNCTION = '{mask_func}');"
    )


def _build_drop_mask_sql(schema: str, table: str, column: str) -> str:
    """Drop an existing DDM mask from a column."""
    return f"ALTER TABLE {_q(schema)}.{_q(table)} ALTER COLUMN {_q(column)} DROP MASKED;"


def _build_grant_unmask_sql(schema: str, table: str, principal: str) -> str:
    """Grant UNMASK to a privileged database principal (e.g. a data-steward role).
    NEVER granted to the FabricShield scanning principal."""
    return f"GRANT UNMASK ON {_q(schema)}.{_q(table)} TO {_q(principal)};"


# ─── Masking Engine ───────────────────────────────────────────────────────────

class MaskingEngine:
    """Applies DDM masks to approved PII columns. All operations are audited by callers."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._connector = DatabaseConnector(customer_tenant_id=tenant_id)

    def apply_mask(
        self,
        connection_name: str,
        db_type: DatabaseType,
        schema: str,
        table: str,
        column: str,
        data_type: str,
        mask_type: MaskType,
        partial_prefix: int = 0,
        partial_suffix: str = "XXXX",
        partial_suffix_size: int = 4,
    ) -> MaskingResult:
        """Apply DDM to a single column. Returns a MaskingResult with the executed DDL."""
        ddl = _build_ddm_sql(
            schema=schema,
            table=table,
            column=column,
            data_type=data_type,
            mask_type=mask_type,
            partial_prefix=partial_prefix,
            partial_suffix=partial_suffix,
            partial_suffix_size=partial_suffix_size,
        )

        try:
            self._connector.execute_ddl(connection_name=connection_name, db_type=db_type, ddl=ddl)
            logger.info(
                "masking_engine.mask_applied",
                tenant_id=self.tenant_id,
                schema=schema,
                table=table,
                column=column,
                mask_type=mask_type.value,
            )
            return MaskingResult(
                approval_id="",
                column_id="",
                success=True,
                ddl_executed=ddl,
                masked_at=datetime.now(timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to caller as a failed result
            logger.error(
                "masking_engine.mask_failed",
                tenant_id=self.tenant_id,
                schema=schema,
                table=table,
                column=column,
                error=str(exc),
            )
            return MaskingResult(
                approval_id="",
                column_id="",
                success=False,
                ddl_executed=ddl,
                error=str(exc),
            )

    def drop_mask(
        self,
        connection_name: str,
        db_type: DatabaseType,
        schema: str,
        table: str,
        column: str,
    ) -> "tuple[bool, str | None]":
        """Remove DDM from a column (admin operation).

        Returns (ok, error). On failure `error` carries the real SQL/connection
        message so it can be surfaced in the UI and audit log instead of a generic
        'failed'. If the column already has no mask, that is treated as success
        (idempotent) — the desired end state is 'not masked'."""
        ddl = _build_drop_mask_sql(schema, table, column)
        try:
            self._connector.execute_ddl(connection_name, db_type, ddl)
            logger.info(
                "masking_engine.mask_dropped",
                tenant_id=self.tenant_id,
                schema=schema,
                table=table,
                column=column,
            )
            return True, None
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            # "DROP MASKED" fails if the column isn't masked — our goal is already met.
            low = msg.lower()
            if "is not masked" in low or "not currently masked" in low or "no masking function" in low:
                logger.info("masking_engine.drop_noop", schema=schema, table=table, column=column)
                return True, None
            logger.error(
                "masking_engine.drop_failed",
                tenant_id=self.tenant_id, schema=schema, table=table, column=column, error=msg,
            )
            return False, msg

    def verify_mask_applied(
        self,
        connection_name: str,
        db_type: DatabaseType,
        schema: str,
        table: str,
        column: str,
    ) -> bool:
        """Verify DDM is active on a column via sys.masked_columns (metadata only)."""
        sql = """
        SELECT COUNT(*)
        FROM sys.masked_columns mc
        INNER JOIN sys.tables t  ON mc.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id  = s.schema_id
        INNER JOIN sys.columns c ON mc.object_id = c.object_id AND mc.column_id = c.column_id
        WHERE s.name = ? AND t.name = ? AND c.name = ? AND mc.is_masked = 1
        """
        try:
            with self._connector.connect(connection_name, db_type) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (schema, table, column))
                return cursor.fetchone()[0] > 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("masking_engine.verify_error", error=str(exc))
            return False
