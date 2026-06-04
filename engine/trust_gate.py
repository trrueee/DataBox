from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from engine.guardrail import GuardrailResult, guardrail_check
from engine.models import DataSource
from engine.datasource import get_mysql_connection_params
import pymysql


RiskLevel = Literal["safe", "warning", "danger"]
ExecutionPolicy = Literal["readonly", "agent_readonly", "explain"]
SchemaValidator = Callable[[str, Session, str], list[str]]


class TrustGateResult(TypedDict, total=False):
    sql: str
    schemaWarnings: list[str]
    guardrail: GuardrailResult
    riskLevel: RiskLevel
    requiresConfirmation: bool
    messages: list[str]
    canExecute: bool


class ExecutionSafetyDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: f"safety-{uuid4()}")
    datasource_id: str
    policy: ExecutionPolicy = "readonly"
    original_sql: str
    safe_sql: str | None
    passed: bool
    can_execute: bool
    requires_confirmation: bool
    guardrail: GuardrailResult
    schema_warnings: list[str] = Field(default_factory=list)
    scope_state: dict[str, Any] = Field(default_factory=dict)
    blocked_reasons: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrustGate:
    """Schema and safety gate for AI-generated SQL."""

    def __init__(self, db: Session, schema_validator: SchemaValidator) -> None:
        self.db = db
        self.schema_validator = schema_validator

    def evaluate(self, datasource_id: str, sql: str) -> TrustGateResult:
        datasource = self.db.query(DataSource).filter(DataSource.id == datasource_id).first()
        dialect = str(datasource.db_type or "mysql") if datasource else "mysql"
        env = str(datasource.env or "dev").lower() if datasource else "dev"

        schema_warnings = self.schema_validator(sql, self.db, datasource_id)
        guardrail = guardrail_check(sql, dialect=dialect)
        messages: list[str] = []

        guardrail_result = guardrail["result"]
        if guardrail_result == "reject":
            risk_level: RiskLevel = "danger"
            messages.append("Guardrail rejected this SQL. Execution is blocked.")
        elif schema_warnings or guardrail_result == "warn":
            risk_level = "warning"
            if schema_warnings:
                messages.append("Schema validation found unknown tables or columns.")
            if guardrail_result == "warn":
                messages.append(guardrail["message"])
        else:
            risk_level = "safe"
            messages.append("SQL passed schema validation and guardrail checks.")

        requires_confirmation = risk_level == "warning"
        if env == "prod":
            requires_confirmation = True
            messages.append("Production datasource requires manual confirmation.")

        can_execute = guardrail_result != "reject"

        return {
            "sql": sql,
            "schemaWarnings": schema_warnings,
            "guardrail": guardrail,
            "riskLevel": risk_level,
            "requiresConfirmation": requires_confirmation,
            "messages": messages,
            "canExecute": can_execute,
        }

    def execution_decision(
        self,
        datasource_id: str,
        sql: str,
        policy: ExecutionPolicy = "readonly",
    ) -> ExecutionSafetyDecision:
        datasource = self.db.query(DataSource).filter(DataSource.id == datasource_id).first()
        trust_gate = self.evaluate(datasource_id, sql)
        guardrail = trust_gate["guardrail"]
        schema_warnings = list(trust_gate.get("schemaWarnings", []))
        messages = list(trust_gate.get("messages", []))
        env = str(datasource.env or "dev").lower() if datasource else "unknown"
        guardrail_rejected = guardrail.get("result") == "reject"
        guardrail_checks = list(guardrail.get("checks", []))
        select_star_blocked = (
            policy == "agent_readonly"
            and any(check.get("rule") == "select_star" for check in guardrail_checks)
        )
        requires_confirmation = env == "prod"
        blocked_reasons: list[str] = []

        # Extra safety: attempt a MySQL EXPLAIN dry-run to catch syntax/schema errors
        dialect = str(datasource.db_type or "mysql") if datasource else "mysql"
        if datasource and "mysql" in dialect.lower():
            try:
                conn_params = get_mysql_connection_params({
                    "id": datasource.id,
                    "host": datasource.host,
                    "port": datasource.port,
                    "username": datasource.username,
                    "database_name": datasource.database_name,
                    "password_ciphertext": datasource.password_ciphertext,
                    "password_nonce": datasource.password_nonce,
                    "ssh_enabled": datasource.ssh_enabled,
                    "ssh_host": datasource.ssh_host,
                    "ssh_port": datasource.ssh_port,
                    "ssh_username": datasource.ssh_username,
                    "ssh_password_ciphertext": datasource.ssh_password_ciphertext,
                    "ssh_password_nonce": datasource.ssh_password_nonce,
                    "ssl_enabled": datasource.ssl_enabled,
                    "ssl_ca_path": datasource.ssl_ca_path,
                    "ssl_cert_path": datasource.ssl_cert_path,
                    "ssl_key_path": datasource.ssl_key_path,
                    "ssl_verify_identity": datasource.ssl_verify_identity,
                })
                # If SQL contains clearly-broken ORDER BY patterns, mark as syntax_error
                up = sql.upper()
                if "ORDER BY" in up and ("ARRAY(" in up or "STRUCT(" in up or "[]" in up):
                    blocked_reasons.append("syntax_error")
                    messages.append("ORDER BY contains unsupported ARRAY/STRUCT literal")
                else:
                    # Try EXPLAIN to detect syntax or schema issues
                    try:
                        conn = pymysql.connect(**conn_params)
                        try:
                            with conn.cursor() as cur:
                                cur.execute(f"EXPLAIN {sql}")
                        finally:
                            conn.close()
                    except Exception as exc:
                        msg = str(exc)
                        messages.append(f"EXPLAIN failed: {msg}")
                        # Heuristic: classify as syntax vs schema
                        if "You have an error in your SQL syntax" in msg or "syntax" in msg.lower():
                            blocked_reasons.append("syntax_error")
                        elif "unknown column" in msg.lower() or "unknown table" in msg.lower() or "doesn't exist" in msg.lower():
                            blocked_reasons.append("schema_error")
                        else:
                            blocked_reasons.append("syntax_error")
            except Exception:
                # If EXPLAIN helper itself fails, don't block here — keep prior reasons
                pass

        if not datasource:
            blocked_reasons.append("datasource_scope")
            messages.append("Datasource scope could not be resolved.")
        if guardrail_rejected:
            blocked_reasons.append("guardrail_reject")
        if schema_warnings:
            blocked_reasons.append("schema_validation")
            messages.append("Execution blocked until schema validation warnings are resolved.")
        if requires_confirmation:
            blocked_reasons.append("requires_confirmation")
            messages.append("Execution blocked until production datasource confirmation is handled.")
        if select_star_blocked:
            blocked_reasons.append("select_star")
            messages.append("Agent execution requires explicit projected columns instead of SELECT *.")

        can_execute = not blocked_reasons
        safe_sql = str(guardrail.get("safeSql") or "").strip() if can_execute else None

        return ExecutionSafetyDecision(
            datasource_id=datasource_id,
            policy=policy,
            original_sql=sql,
            safe_sql=safe_sql,
            passed=can_execute,
            can_execute=can_execute,
            requires_confirmation=requires_confirmation,
            guardrail=guardrail,
            schema_warnings=schema_warnings,
            scope_state={
                "datasource_exists": bool(datasource),
                "datasource_id": datasource_id,
                "db_type": str(datasource.db_type or "mysql") if datasource else None,
                "env": env,
                "is_read_only": bool(datasource.is_read_only) if datasource else None,
                "project_id": str(datasource.project_id) if datasource and datasource.project_id else None,
                "environment_id": str(datasource.environment_id) if datasource and datasource.environment_id else None,
            },
            blocked_reasons=blocked_reasons,
            messages=messages,
        )
