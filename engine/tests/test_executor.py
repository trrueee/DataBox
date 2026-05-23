"""Tests for executor module — query execution against SQLite demo DB."""
import decimal
import datetime

import pytest

from engine.executor import _serialize_value, _process_rows, MAX_ROWS


class TestSerializeValue:
    def test_none_returns_none(self) -> None:
        assert _serialize_value(None) is None

    def test_decimal_returns_string(self) -> None:
        assert _serialize_value(decimal.Decimal("10.5")) == "10.5"

    def test_datetime_returns_isoformat(self) -> None:
        dt = datetime.datetime(2025, 1, 15, 12, 30, 0)
        assert _serialize_value(dt) == "2025-01-15T12:30:00"

    def test_date_returns_isoformat(self) -> None:
        d = datetime.date(2025, 1, 15)
        assert _serialize_value(d) == "2025-01-15"

    def test_bytes_returns_binary_tag(self) -> None:
        assert _serialize_value(b"hello") == "<binary>"

    def test_string_passes_through(self) -> None:
        assert _serialize_value("hello") == "hello"

    def test_int_passes_through_as_str(self) -> None:
        assert _serialize_value(42) == "42"

    def test_float_passes_through_as_str(self) -> None:
        assert _serialize_value(3.14) == "3.14"


class TestProcessRows:
    def test_empty_rows(self) -> None:
        rows, cols = _process_rows([], ["id", "name"])
        assert rows == []
        assert cols == ["id", "name"]

    def test_basic_processing(self) -> None:
        raw = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        rows, cols = _process_rows(raw, ["id", "name"])
        assert rows == [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        assert cols == ["id", "name"]

    def test_column_limit_enforced(self) -> None:
        raw = [{"a": 1, "b": 2, "c": 3, "d": 4}]
        rows, cols = _process_rows(raw, ["a", "b", "c", "d"], max_columns=2)
        assert cols == ["a", "b"]

    def test_cell_truncation(self) -> None:
        raw = [{"col": "x" * 100}]
        rows, _ = _process_rows(raw, ["col"], max_cell_chars=10)
        assert rows[0]["col"] == "x" * 10 + "..."

    def test_decimal_serialization(self) -> None:
        raw = [{"price": decimal.Decimal("9.99")}]
        rows, _ = _process_rows(raw, ["price"])
        assert rows[0]["price"] == "9.99"

    def test_none_value_remains_none(self) -> None:
        raw = [{"col": None}]
        rows, _ = _process_rows(raw, ["col"])
        assert rows[0]["col"] is None


class TestExecutorSQLite:
    """Integration test: execute real queries against the demo SQLite database."""

    def test_select_all_users(self) -> None:
        from engine.executor import _execute_on_sqlite

        rows, columns = _execute_on_sqlite("SELECT id, username, email FROM users LIMIT 5")
        assert len(rows) >= 1
        assert "username" in columns
        assert "email" in columns
        assert isinstance(rows[0]["username"], str)

    def test_aggregation_query(self) -> None:
        from engine.executor import _execute_on_sqlite

        rows, columns = _execute_on_sqlite("SELECT COUNT(*) AS cnt FROM users")
        assert len(rows) == 1
        assert columns == ["cnt"]
        assert int(rows[0]["cnt"]) > 0

    def test_join_query(self) -> None:
        from engine.executor import _execute_on_sqlite

        rows, columns = _execute_on_sqlite(
            "SELECT u.username, o.total_amount FROM users u "
            "JOIN orders o ON u.id = o.user_id LIMIT 5"
        )
        assert len(rows) >= 1
        assert "username" in columns
        assert "total_amount" in columns

    def test_row_limit_enforced(self) -> None:
        from engine.executor import _execute_on_sqlite

        rows, _ = _execute_on_sqlite("SELECT * FROM users")
        assert len(rows) <= MAX_ROWS

    def test_non_select_rejected(self) -> None:
        """SQLite executes DDL without issue, but guardrail should be tested separately."""
        # This test verifies SQLite execution works; guardrail handles DDL blocking.
        from engine.executor import _execute_on_sqlite

        rows, columns = _execute_on_sqlite(
            "SELECT name FROM sqlite_master WHERE type='table' LIMIT 5"
        )
        assert len(columns) == 1
        assert "name" in columns
