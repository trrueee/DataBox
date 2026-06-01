from __future__ import annotations

from engine.agent import AgentRunRequest, DataBoxAgentRuntime
from engine.schema_sync import sync_schema


def test_agent_runtime_execute_false_generates_full_review_response(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="查询所有用户", execute=False)

    res = DataBoxAgentRuntime(db_session).run(req)

    assert res.success is True, res.model_dump()
    assert res.query_plan is not None
    assert res.sql is not None
    assert res.sql.upper().startswith("SELECT")
    assert "SELECT *" not in res.sql.upper()
    assert res.safety is not None
    assert res.safety["can_execute"] is True
    assert res.execution == {"reason": "Request execute=false; SQL was not executed."}
    assert res.explanation
    assert res.chart_suggestion is not None
    assert [step.name for step in res.steps] == [
        "build_schema_context",
        "build_query_plan",
        "generate_sql_candidate",
        "validate_sql",
        "execute_sql",
        "explain_result",
        "suggest_chart",
    ]
    assert res.steps[4].status == "skipped"


def test_agent_runtime_blocks_guardrail_failure_without_execution(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fake_generate_sql(*_args, **_kwargs):
        return {
            "sql": "DELETE FROM users",
            "model": "test",
            "mode": "offline",
            "latencyMs": 1,
            "schemaValidationWarnings": [],
        }

    monkeypatch.setattr("engine.agent.tools.generate_sql", fake_generate_sql)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="删除所有用户", execute=True)

    res = DataBoxAgentRuntime(db_session).run(req)

    assert res.success is False
    assert res.safety is not None
    assert res.safety["can_execute"] is False
    assert "execute_sql" not in [step.name for step in res.steps]
    assert [step.name for step in res.steps] == [
        "build_schema_context",
        "build_query_plan",
        "generate_sql_candidate",
        "validate_sql",
        "revise_sql",
    ]
    assert res.steps[-1].name == "revise_sql"
    assert res.steps[-1].output is not None
    assert {"can_fix", "fixed_sql", "reason", "changes", "remaining_risks"}.issubset(res.steps[-1].output.keys())


def test_agent_runtime_execution_failure_returns_revise_suggestion(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fake_generate_sql(*_args, **_kwargs):
        return {
            "sql": "SELECT id FROM users LIMIT 1",
            "model": "test",
            "mode": "offline",
            "latencyMs": 1,
            "schemaValidationWarnings": [],
        }

    def fail_execute(*_args, **_kwargs):
        raise RuntimeError("database is busy")

    monkeypatch.setattr("engine.agent.tools.generate_sql", fake_generate_sql)
    monkeypatch.setattr("engine.agent.tools.execute_query", fail_execute)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="查询用户", execute=True)

    res = DataBoxAgentRuntime(db_session).run(req)

    assert res.success is False
    assert res.execution is not None
    assert res.execution["success"] is False
    assert res.execution["revise_suggestion"]
    assert res.steps[-1].name == "revise_sql"


def test_agent_runtime_respects_max_steps_before_validation(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="list products", execute=False, max_steps=3)

    res = DataBoxAgentRuntime(db_session).run(req)

    assert res.success is False
    assert res.error == "Agent stopped before SQL validation because max_steps was reached."
    assert [step.name for step in res.steps] == [
        "build_schema_context",
        "build_query_plan",
        "generate_sql_candidate",
    ]


def test_agent_runtime_stops_on_schema_hallucination_without_execution(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fake_generate_sql(*_args, **_kwargs):
        return {
            "sql": "SELECT imaginary_column FROM users LIMIT 10",
            "model": "test",
            "mode": "offline",
            "latencyMs": 1,
            "schemaValidationWarnings": [],
        }

    def fail_execute(*_args, **_kwargs):
        raise AssertionError("hallucinated SQL must not execute")

    monkeypatch.setattr("engine.agent.tools._render_sql_from_query_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("engine.agent.tools.generate_sql", fake_generate_sql)
    monkeypatch.setattr("engine.agent.tools.execute_query", fail_execute)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="list users", execute=True)

    res = DataBoxAgentRuntime(db_session).run(req)

    assert res.success is False
    assert res.safety is not None
    assert res.safety["schema_warnings"]
    assert "execute_sql" not in [step.name for step in res.steps]
    assert res.steps[-1].name == "revise_sql"
