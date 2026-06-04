from engine.ai import validate_sql_schema
from engine.schema_sync import sync_schema
from engine.trust_gate import TrustGate


def test_trust_gate_safe_select(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    result = TrustGate(db_session, validate_sql_schema).evaluate(
        demo_datasource.id,
        "SELECT id, username FROM users LIMIT 10",
    )

    assert result["riskLevel"] == "safe"
    assert result["requiresConfirmation"] is False
    assert result["canExecute"] is True
    assert result["schemaWarnings"] == []
    assert result["guardrail"]["result"] == "pass"


def test_trust_gate_schema_warning_requires_confirmation(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    result = TrustGate(db_session, validate_sql_schema).evaluate(
        demo_datasource.id,
        "SELECT imaginary_column FROM users LIMIT 10",
    )

    assert result["riskLevel"] == "warning"
    assert result["requiresConfirmation"] is True
    assert result["canExecute"] is True
    assert any("imaginary_column" in warning for warning in result["schemaWarnings"])


def test_trust_gate_rejects_dangerous_sql(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    result = TrustGate(db_session, validate_sql_schema).evaluate(
        demo_datasource.id,
        "DROP TABLE users",
    )

    assert result["riskLevel"] == "danger"
    assert result["requiresConfirmation"] is False
    assert result["canExecute"] is False
    assert result["guardrail"]["result"] == "reject"


def test_trust_gate_prod_datasource_requires_confirmation(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    demo_datasource.env = "prod"
    db_session.commit()

    result = TrustGate(db_session, validate_sql_schema).evaluate(
        demo_datasource.id,
        "SELECT id, username FROM users LIMIT 10",
    )

    assert result["riskLevel"] == "safe"
    assert result["requiresConfirmation"] is True
    assert result["canExecute"] is True
    assert any("Production datasource" in message for message in result["messages"])


def test_trust_gate_execution_decision_blocks_invalid_order_by_syntax(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    decision = TrustGate(db_session, validate_sql_schema).execution_decision(
        demo_datasource.id,
        "SELECT id FROM users ORDER BY ARRAY() LIMIT 10",
        policy="agent_readonly",
    )

    assert decision.can_execute is False
    assert decision.passed is False
    assert decision.safe_sql is None
    assert "syntax_error" in decision.blocked_reasons


def test_trust_gate_execution_decision_blocks_missing_table_schema_error(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    decision = TrustGate(db_session, validate_sql_schema).execution_decision(
        demo_datasource.id,
        "SELECT id FROM missing_table LIMIT 10",
        policy="agent_readonly",
    )

    assert decision.can_execute is False
    assert decision.passed is False
    assert decision.safe_sql is None
    assert "schema_error" in decision.blocked_reasons


def test_trust_gate_execution_decision_blocks_when_dry_run_unavailable(
    db_session,
    demo_datasource,
    monkeypatch,
) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fail_dry_run(*_args, **_kwargs):
        raise RuntimeError("dry run connection unavailable")

    monkeypatch.setattr("engine.trust_gate.dry_run_query", fail_dry_run)

    decision = TrustGate(db_session, validate_sql_schema).execution_decision(
        demo_datasource.id,
        "SELECT id FROM users LIMIT 10",
        policy="agent_readonly",
    )

    assert decision.can_execute is False
    assert decision.passed is False
    assert decision.safe_sql is None
    assert "explain_unavailable" in decision.blocked_reasons
    assert any("dry run connection unavailable" in message for message in decision.messages)
