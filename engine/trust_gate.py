from __future__ import annotations

from typing import Callable, Literal, TypedDict

from sqlalchemy.orm import Session

from engine.guardrail import GuardrailResult, guardrail_check
from engine.models import DataSource


RiskLevel = Literal["safe", "warning", "danger"]
SchemaValidator = Callable[[str, Session, str], list[str]]


class TrustGateResult(TypedDict, total=False):
    sql: str
    schemaWarnings: list[str]
    guardrail: GuardrailResult
    riskLevel: RiskLevel
    requiresConfirmation: bool
    messages: list[str]
    canExecute: bool


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
