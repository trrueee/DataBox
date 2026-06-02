from __future__ import annotations

from engine.agent import AgentRunRequest, AgentWorkspaceContext
from engine.agent.default_tools import build_default_tool_registry
from engine.agent.planner import AgentPlanner


def test_planner_fallback_returns_workspace_sql_explain_plan(db_session, demo_datasource) -> None:
    req = AgentRunRequest(
        datasource_id=demo_datasource.id,
        question="Explain this SQL",
        workspace_context=AgentWorkspaceContext(
            datasource_id=demo_datasource.id,
            active_sql="SELECT id FROM users LIMIT 10",
        ),
    )
    bundle = {
        "context_summary": "active SQL available",
        "workspace": {"active_sql": req.workspace_context.active_sql},
    }

    plan = AgentPlanner(build_default_tool_registry()).plan(db_session, req, bundle)

    assert plan.version == "agent-plan-draft/v1"
    assert plan.intent.intent == "explain_sql"
    assert plan.steps[0].tool_name == "workspace.explain_sql"
    assert plan.should_execute_sql is False


def test_planner_fallback_keeps_analysis_on_old_request(db_session, demo_datasource) -> None:
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="list users", execute=True)

    plan = AgentPlanner(build_default_tool_registry()).plan(db_session, req, {"context_summary": "database"})

    assert plan.intent.intent == "analysis"
    assert "sql.validate" in [step.tool_name for step in plan.steps]
    assert "sql.execute_readonly" in [step.tool_name for step in plan.steps]
    assert plan.should_execute_sql is True


def test_planner_repairs_invalid_json_once(db_session, demo_datasource, monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "version": "agent-plan-draft/v1",
                              "intent": {"intent": "explain_sql", "confidence": "high"},
                              "steps": [{"id": "s1", "tool_name": "workspace.explain_sql", "title": "Explain",}],
                              "should_execute_sql": false,
                            }
                            """,
                        }
                    }
                ]
            }

    monkeypatch.setattr("engine.agent.planner.httpx.post", lambda *_args, **_kwargs: FakeResponse())
    req = AgentRunRequest(
        datasource_id=demo_datasource.id,
        question="Explain this SQL",
        api_key="sk-test",
        model_name="gpt-test",
        workspace_context=AgentWorkspaceContext(
            datasource_id=demo_datasource.id,
            active_sql="SELECT id FROM users LIMIT 10",
        ),
    )

    plan = AgentPlanner(build_default_tool_registry()).plan(
        db_session,
        req,
        {"context_summary": "active SQL", "workspace": {"active_sql": "SELECT id FROM users LIMIT 10"}},
    )

    assert plan.intent.intent == "explain_sql"
    assert plan.model == "gpt-test"
    assert plan.raw_response == {"source": "llm_repaired"}


def test_planner_falls_back_when_online_json_is_unusable(db_session, demo_datasource, monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"choices": [{"message": {"content": "not json"}}]}

    monkeypatch.setattr("engine.agent.planner.httpx.post", lambda *_args, **_kwargs: FakeResponse())
    req = AgentRunRequest(
        datasource_id=demo_datasource.id,
        question="Explain this SQL",
        api_key="sk-test",
        workspace_context=AgentWorkspaceContext(
            datasource_id=demo_datasource.id,
            active_sql="SELECT id FROM users LIMIT 10",
        ),
    )

    plan = AgentPlanner(build_default_tool_registry()).plan(
        db_session,
        req,
        {"context_summary": "active SQL", "workspace": {"active_sql": "SELECT id FROM users LIMIT 10"}},
    )

    assert plan.model == "databox-deterministic-planner"
    assert plan.raw_response == {"source": "fallback"}
