from __future__ import annotations

import datetime
import decimal
import sqlite3
import time
from typing import Any

import pymysql
from sqlalchemy.orm import Session

from engine.datasource import get_mysql_connection_params, is_demo_db
from engine.demo_db_init import DEMO_DB_PATH, init_demo_database
from engine.errors import GuardrailValidationError, SQLExecutionError
from engine.guardrail import guardrail_check
from engine.models import DataSource, QueryHistory

MAX_ROWS = 1000
MAX_COLUMNS = 100
MAX_CELL_CHARS = 5000


def _serialize_value(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, decimal.Decimal):
        return str(val)
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    if isinstance(val, bytes):
        return "<binary>"
    return str(val)


def _process_rows(
    raw_rows: list[sqlite3.Row],
    columns: list[str],
    max_columns: int = MAX_COLUMNS,
    max_cell_chars: int = MAX_CELL_CHARS,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Process raw cursor rows into a list of serialized dicts with limits applied."""
    if len(columns) > max_columns:
        columns = columns[:max_columns]

    rows = []
    for r in raw_rows:
        row_dict = {}
        for col in columns:
            val = r[col]
            if isinstance(val, str) and len(val) > max_cell_chars:
                val = val[:max_cell_chars] + "..."
            row_dict[col] = _serialize_value(val)
        rows.append(row_dict)

    return rows, columns


def _execute_on_sqlite(safe_sql: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute a safe SQL query on the local SQLite demo database."""
    demo_path = init_demo_database()
    conn = sqlite3.connect(demo_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        cursor = conn.cursor()
        cursor.execute(safe_sql)

        columns = []
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            raw_rows = cursor.fetchmany(MAX_ROWS)
            return _process_rows(raw_rows, columns)
        return [], []
    finally:
        conn.close()


def _execute_on_mysql(params: dict[str, Any], safe_sql: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Execute a safe SQL query on a real MySQL database via PyMySQL."""
    conn = pymysql.connect(**params)
    try:
        with conn.cursor() as cursor:
            cursor.execute(safe_sql)

            columns = []
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                raw_rows = cursor.fetchmany(MAX_ROWS)
                return _process_rows(raw_rows, columns)
            return [], []
    finally:
        conn.close()


def execute_query(
    db: Session, datasource_id: str, sql_str: str, question: str | None = None
) -> dict[str, Any]:
    """
    Safely executes a SELECT query:
    1. Guardrail check
    2. Execute on demo SQLite or real MySQL
    3. Serialize results, log history
    """
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise ValueError("Data source not found")

    guard_res = guardrail_check(sql_str)
    guard_checks_json = str(guard_res["checks"])

    if guard_res["result"] == "reject":
        history = QueryHistory(
            data_source_id=datasource_id,
            question=question,
            submitted_sql=sql_str,
            generated_sql=sql_str,
            safe_sql="",
            executed_sql="",
            guardrail_result="reject",
            guardrail_checks=guard_checks_json,
            execution_status="failed",
            error_message=guard_res["message"],
        )
        db.add(history)
        db.commit()
        raise GuardrailValidationError(
            guard_res["message"], checks=guard_res["checks"]  # type: ignore[arg-type]
        )

    safe_sql = guard_res["safeSql"]
    start_time = time.time()
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    error_message: str | None = None
    execution_status = "success"

    try:
        if is_demo_db(str(ds.host), str(ds.database_name)):
            rows, columns = _execute_on_sqlite(safe_sql)
        else:
            conn_params = get_mysql_connection_params({
                "host": ds.host,
                "port": ds.port,
                "username": ds.username,
                "database_name": ds.database_name,
                "password_ciphertext": ds.password_ciphertext,
                "password_nonce": ds.password_nonce,
            })
            rows, columns = _execute_on_mysql(conn_params, safe_sql)
    except Exception as e:
        execution_status = "failed"
        error_message = f"执行 SQL 遇到错误: {str(e)}"
        raise SQLExecutionError(error_message) from e

    finally:
        latency_ms = int((time.time() - start_time) * 1000)

        history = QueryHistory(
            data_source_id=datasource_id,
            question=question,
            submitted_sql=sql_str,
            generated_sql=sql_str,
            safe_sql=safe_sql,
            executed_sql=safe_sql if execution_status == "success" else "",
            guardrail_result=guard_res["result"],
            guardrail_checks=guard_checks_json,
            execution_status=execution_status,
            execution_time_ms=latency_ms,
            rows_returned=len(rows) if execution_status == "success" else 0,
            columns_returned=len(columns) if execution_status == "success" else 0,
            error_message=error_message,
        )
        db.add(history)
        db.commit()

    return {
        "success": True,
        "columns": columns,
        "rows": rows,
        "rowCount": len(rows),
        "latencyMs": latency_ms,
        "guardrail": guard_res,
        "historyId": history.id,
    }
