from __future__ import annotations

from engine.agent import AgentIntentPlan, AgentPlanDraft, AgentPlanStep, AgentRunRequest, AgentWorkspaceContext
from engine.agent.default_tools import build_default_tool_registry
from engine.agent.plan_validator import AgentPlanValidator


def _validator() -> AgentPlanValidator:
    return AgentPlanValidator(build_default_tool_registry())


def _req(datasource_id: str = "ds-test") -> AgentRunRequest:
    return AgentRunRequest(datasource_id=datasource_id, question="Explain this SQL")


def _context(**workspace):
    return {"workspace": workspace, "schema_linking": {"selected_tables": workspace.get("selected_table_names", [])}}


def test_validator_rejects_unknown_tool() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="analysis"),
        steps=[AgentPlanStep(id="s1", tool_name="made.up.tool")],
    )

    result = _validator().validate(_req(), plan, _context())

    assert result.valid is False
    assert any("Unknown tool" in reason for reason in result.reasons)


def test_validator_rejects_annotation_tool() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="analysis"),
        steps=[AgentPlanStep(id="s1", tool_name="@export")],
    )

    result = _validator().validate(_req(), plan, _context())

    assert result.valid is False
    assert any("Annotations are not tools" in reason for reason in result.reasons)


def test_validator_rejects_forbidden_operations_and_proposed_sql() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="rewrite_sql"),
        steps=[
            AgentPlanStep(
                id="s1",
                tool_name="workspace.rewrite_sql",
                args={"proposed_sql": "DROP TABLE users"},
            )
        ],
    )

    result = _validator().validate(
        _req(),
        plan,
        _context(active_sql="SELECT id FROM users LIMIT 10"),
    )

    assert result.valid is False
    assert any("forbidden" in reason.lower() for reason in result.reasons)
    assert any("guardrail" in reason.lower() for reason in result.reasons)


def test_validator_requires_context_for_workspace_intent() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="fix_sql"),
        steps=[AgentPlanStep(id="s1", tool_name="workspace.fix_sql")],
    )

    result = _validator().validate(_req(), plan, _context(active_sql="SELECT id FROM users LIMIT 10"))

    assert result.valid is False
    assert any("last_error" in reason for reason in result.reasons)


def test_validator_requires_validate_and_execute_for_execution_plan() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="analysis"),
        steps=[
            AgentPlanStep(id="s1", tool_name="schema.build_context"),
            AgentPlanStep(id="s2", tool_name="query_plan.build"),
        ],
        should_execute_sql=True,
    )

    result = _validator().validate(
        AgentRunRequest(datasource_id="ds-test", question="list users", execute=True),
        plan,
        _context(),
    )

    assert result.valid is False
    assert any("sql.validate" in reason for reason in result.reasons)
    assert any("sql.execute_readonly" in reason for reason in result.reasons)


def test_validator_accepts_valid_workspace_explain_sql_plan() -> None:
    plan = AgentPlanDraft(
        intent=AgentIntentPlan(intent="explain_sql"),
        steps=[AgentPlanStep(id="s1", tool_name="workspace.explain_sql")],
    )

    result = _validator().validate(
        AgentRunRequest(
            datasource_id="ds-test",
            question="Explain this SQL",
            workspace_context=AgentWorkspaceContext(
                datasource_id="ds-test",
                active_sql="SELECT id FROM users LIMIT 10",
            ),
        ),
        plan,
        _context(active_sql="SELECT id FROM users LIMIT 10"),
    )

    assert result.valid is True
