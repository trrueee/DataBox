from __future__ import annotations

import uuid

import pytest

from engine.agent import AgentRunRequest
from engine.agent.tools import (
    build_query_plan_tool,
    generate_sql_tool,
    revise_sql_tool,
    suggest_chart_tool,
    validate_sql_tool,
)
from engine.models import SchemaColumn, SchemaTable
from engine.schema_sync import sync_schema


def test_build_query_plan_tool_for_chinese_question(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="统计每天订单量")

    obs = build_query_plan_tool(db_session, req, {"schema_context": "", "selected_tables": ["orders"]})

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["analysis_goal"]
    assert "orders" in obs.output["candidate_tables"]


def test_generate_sql_tool_rewrites_select_star(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fake_generate_sql(*_args, **_kwargs):
        return {
            "sql": "SELECT * FROM users",
            "model": "test",
            "mode": "offline",
            "latencyMs": 1,
            "schemaValidationWarnings": [],
        }

    monkeypatch.setattr("engine.agent.tools.generate_sql", fake_generate_sql)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="查询所有用户")

    obs = generate_sql_tool(db_session, req)

    assert obs.status == "success"
    assert obs.output is not None
    assert "SELECT *" not in obs.output["sql"].upper()
    assert "users.id" in obs.output["sql"]
    assert "LIMIT" in obs.output["sql"].upper()
    assert "select_star_rewritten_to_explicit_columns" in obs.output["rewrite_notes"]
    assert obs.output["metadata"]["rewrite"]["select_star_column_limit"] == 12


def test_generate_sql_tool_uses_query_plan_before_fallback(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)

    def fail_generate_sql(*_args, **_kwargs):
        raise AssertionError("generate_sql fallback should not run for a renderable plan")

    monkeypatch.setattr("engine.agent.tools.generate_sql", fail_generate_sql)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="count users")
    metric = {"name": "total_users", "expression": "COUNT(*)"}
    query_plan = {
        "analysis_goal": "count users",
        "metrics": [metric],
        "dimensions": [],
        "filters": [],
        "candidate_tables": ["users"],
        "raw_plan": {
            "intent": "aggregate",
            "tables": ["users"],
            "metrics": [metric],
            "dimensions": [],
            "filters": [],
            "joins": [],
            "limit": 100,
        },
    }

    obs = generate_sql_tool(db_session, req, schema_context={"schema_context_size": 1}, query_plan=query_plan)

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["metadata"]["generation_source"] == "query_plan_rendered"
    assert "COUNT(*) AS total_users" in obs.output["sql"]
    assert "FROM users" in obs.output["sql"]


def test_generate_sql_tool_no_key_uses_offline_fallback(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="list products", api_key=None)

    obs = generate_sql_tool(db_session, req)

    assert obs.status == "success"
    assert obs.input is not None
    assert obs.input["has_api_key"] is False
    assert obs.output is not None
    assert obs.output["model"] == "databox-local-heuristic"
    assert obs.output["mode"] == "offline"


def test_generate_sql_tool_reports_select_star_truncation_limit(db_session, demo_datasource, monkeypatch) -> None:
    sync_schema(db_session, demo_datasource.id)
    table = SchemaTable(
        id=str(uuid.uuid4()),
        data_source_id=demo_datasource.id,
        table_schema=demo_datasource.database_name,
        table_name="wide_table",
        table_comment="wide table",
        table_type="BASE TABLE",
        row_count_estimate=1,
        engine_name="InnoDB",
    )
    db_session.add(table)
    db_session.flush()
    db_session.add_all(
        [
            SchemaColumn(
                id=str(uuid.uuid4()),
                table_id=table.id,
                column_name=f"col_{index}",
                data_type="varchar",
                column_type="varchar(50)",
                ordinal_position=index,
            )
            for index in range(1, 14)
        ]
    )
    db_session.commit()

    def fake_generate_sql(*_args, **_kwargs):
        return {
            "sql": "SELECT * FROM wide_table",
            "model": "test",
            "mode": "offline",
            "latencyMs": 1,
            "schemaValidationWarnings": [],
        }

    monkeypatch.setattr("engine.agent.tools.generate_sql", fake_generate_sql)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="wide table")

    obs = generate_sql_tool(db_session, req)

    assert obs.status == "success"
    assert obs.output is not None
    rewrite = obs.output["metadata"]["rewrite"]
    assert rewrite["select_star_column_limit"] == 12
    assert rewrite["truncated_tables"] == ["wide_table"]
    assert "first 12 columns" in rewrite["message"]
    assert "col_13" not in obs.output["sql"]


@pytest.mark.parametrize("sql", ["DELETE FROM users", "UPDATE users SET role = 'admin'", "DROP TABLE users"])
def test_validate_sql_tool_blocks_write_operations(db_session, demo_datasource, sql: str) -> None:
    sync_schema(db_session, demo_datasource.id)

    obs = validate_sql_tool(db_session, demo_datasource.id, sql)

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["can_execute"] is False
    assert obs.output["guardrail"]["result"] == "reject"


def test_validate_sql_tool_blocks_unrewritten_select_star(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    obs = validate_sql_tool(db_session, demo_datasource.id, "SELECT * FROM users")

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["can_execute"] is False
    assert obs.output["execution_safety_decision"]["policy"] == "agent_readonly"
    assert "select_star" in obs.output["execution_safety_decision"]["blocked_reasons"]
    assert "explicit column" in obs.output["revise_suggestion"]


def test_validate_sql_tool_blocks_schema_hallucination(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)

    obs = validate_sql_tool(db_session, demo_datasource.id, "SELECT imaginary_column FROM users LIMIT 10")

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["can_execute"] is False
    assert obs.output["schema_warnings"]


def test_validate_sql_tool_requires_confirmation_for_prod(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    demo_datasource.env = "prod"
    db_session.commit()

    obs = validate_sql_tool(db_session, demo_datasource.id, "SELECT id, username FROM users LIMIT 10")

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["requires_confirmation"] is True
    assert obs.output["can_execute"] is False
    assert any("Production datasource" in message for message in obs.output["messages"])


def test_revise_sql_tool_returns_structured_fix_fields(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    safety = validate_sql_tool(db_session, demo_datasource.id, "SELECT * FROM users").output

    obs = revise_sql_tool(
        "SELECT * FROM users",
        "SELECT * is blocked",
        safety,
        db=db_session,
        datasource_id=demo_datasource.id,
    )

    assert obs.status == "success"
    assert obs.output is not None
    assert obs.output["can_fix"] is True
    assert obs.output["fixed_sql"]
    assert "SELECT *" not in obs.output["fixed_sql"].upper()
    assert "select_star_rewritten_to_explicit_columns" in obs.output["changes"]
    assert isinstance(obs.output["remaining_risks"], list)


def test_suggest_chart_category_numeric_returns_bar() -> None:
    obs = suggest_chart_tool(
        {
            "success": True,
            "columns": ["category", "count"],
            "rows": [{"category": "A", "count": "2"}, {"category": "B", "count": "5"}],
            "rowCount": 2,
        }
    )

    assert obs.status == "success"
    assert obs.output == {
        "type": "bar",
        "x": "category",
        "y": "count",
        "reason": "A category field plus a numeric measure is best compared by category.",
    }
