from __future__ import annotations

from engine.agent import AgentRunRequest
from engine.agent_kernel.databox_tools import register_databox_tools
from engine.agent_kernel.graph import build_agent_kernel_graph, langgraph_available
from engine.agent_kernel.policy import PolicyGate
from engine.agent_kernel.service import AgentKernelService
from engine.schema_sync import sync_schema


def test_agent_kernel_registry_exposes_domain_tools() -> None:
    registry = register_databox_tools()
    names = {spec.name for spec in registry.list_specs()}

    assert {
        "schema.build_context",
        "query_plan.build",
        "sql.generate",
        "sql.validate",
        "sql.execute_readonly",
        "sql.revise",
        "answer.synthesize",
    }.issubset(names)

    execute_spec = registry.require("sql.execute_readonly").spec
    assert execute_spec.policy.requires_validated_sql is True
    assert execute_spec.policy.side_effect == "read"


def test_agent_kernel_policy_blocks_execution_without_validated_sql() -> None:
    registry = register_databox_tools()
    decision = PolicyGate(registry).check({}, "sql.execute_readonly", {})

    assert decision.status == "blocked"
    assert "sql.validate" in decision.reason


def test_agent_kernel_graph_factory_builds_langgraph_shape() -> None:
    if not langgraph_available():
        return

    graph = build_agent_kernel_graph(
        controller_node=lambda _state: {"pending_decision": {"action": "final_answer"}},
        policy_node=lambda _state: {},
        execute_tool_node=lambda _state: {},
    )

    assert graph is not None


def test_agent_kernel_execute_false_returns_review_response(db_session, demo_datasource) -> None:
    sync_schema(db_session, demo_datasource.id)
    req = AgentRunRequest(datasource_id=demo_datasource.id, question="查询所有用户", execute=False)

    res = AgentKernelService(db_session).run(req)

    assert res.success is True, res.model_dump()
    assert res.status == "completed"
    assert res.sql is not None
    assert res.safety is not None
    assert res.safety["can_execute"] is True
    assert res.execution == {"reason": "Request execute=false; SQL was not executed."}
    assert res.answer is not None
    assert [step.name for step in res.steps] == [
        "build_schema_context",
        "build_query_plan",
        "generate_sql_candidate",
        "validate_sql",
        "execute_sql",
        "profile_result",
        "suggest_chart",
        "suggest_followups",
        "answer_synthesizer",
    ]
    assert res.steps[4].status == "skipped"
