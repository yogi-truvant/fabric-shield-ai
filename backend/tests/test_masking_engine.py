"""
Unit tests for the masking DDL builder.
These tests don't require a live DB — they validate SQL generation.
"""

from backend.core.masking_engine import _build_ddm_sql, _build_drop_mask_sql
from backend.models.schemas import MaskType


class TestDDLBuilder:
    def test_email_mask(self):
        sql = _build_ddm_sql("dbo", "patients", "email", "varchar", MaskType.email)
        assert "email()" in sql
        assert "[dbo].[patients]" in sql
        assert "[email]" in sql
        assert "ADD MASKED" in sql

    def test_partial_mask_varchar(self):
        sql = _build_ddm_sql("hr", "employees", "ssn", "varchar", MaskType.partial, 0, "XXXX", 4)
        assert "partial(0" in sql
        assert "[hr].[employees]" in sql

    def test_default_mask(self):
        sql = _build_ddm_sql("dbo", "users", "full_name", "varchar", MaskType.default)
        assert "default()" in sql

    def test_partial_mask_on_int_falls_back_to_default(self):
        # DDM doesn't support partial() on integer columns
        sql = _build_ddm_sql("dbo", "t", "age", "int", MaskType.partial)
        assert "default()" in sql
        assert "partial" not in sql

    def test_random_mask_on_int(self):
        sql = _build_ddm_sql("dbo", "t", "score", "int", MaskType.random)
        assert "random(" in sql

    def test_drop_mask_sql(self):
        sql = _build_drop_mask_sql("dbo", "patients", "ssn")
        assert "DROP MASKED" in sql
        assert "[dbo].[patients]" in sql
        assert "[ssn]" in sql

    def test_sql_injection_safe_brackets(self):
        # Column names with spaces are handled by brackets
        sql = _build_ddm_sql("My Schema", "My Table", "My Column", "varchar", MaskType.default)
        assert "[My Schema]" in sql
        assert "[My Table]" in sql
        assert "[My Column]" in sql
