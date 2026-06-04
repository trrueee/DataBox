from __future__ import annotations

from engine.agent import AgentRunRequest
from engine.agent_kernel.schemas import AgentDecision, PlanPatch, PlanStep
from engine.agent_kernel.service import AgentKernelService


def test_agent_kernel_plan_events_reduce_to_plan_state() -> None:
    from engine.agent_kernel.plan_state import apply_plan_patches

    plan = apply_plan_patches(
        None,
        [
            PlanPatch(
                operation="add_step",
                step=PlanStep(
                    id="schema",
                    title="Inspect schema",
                    tool_name="schema.build_context",
                    depends_on=[],
                ),
            ),
            PlanPatch(operation="mark_running", step_id="schema"),
            PlanPatch(operation="mark_completed", step_id="schema"),
            PlanPatch(
                operation="add_step",
                step=PlanStep(
                    id="answer",
                    title="Answer from evidence",
                    tool_name="answer.synthesize",
                    depends_on=["schema"],
                ),
            ),
            PlanPatch(operation="skip_step", step_id="answer", reason="No execution evidence is needed."),
        ],
    )

    assert plan["version"] == "agent-plan/v1"
    assert plan["steps"][0]["id"] == "schema"
    assert plan["steps"][0]["status"] == "completed"
    assert plan["steps"][0]["tool_name"] == "schema.build_context"
    assert plan["steps"][1]["id"] == "answer"
    assert plan["steps"][1]["status"] == "skipped"
    assert plan["steps"][1]["depends_on"] == ["schema"]


def test_agent_kernel_update_plan_continues_and_returns_agent_plan_artifact(
    db_session,
    demo_datasource,
    monkeypatch,
) -> None:
    decisions = iter(
        [
            AgentDecision(
                action="update_plan",
                plan_patches=[
                    PlanPatch(
                        operation="add_step",
                        step=PlanStep(
                            id="draft_sql",
                            title="Draft SQL candidate",
                            tool_name="sql.generate",
                            depends_on=[],
                        ),
                    )
                ],
                confidence="high",
                reasoning_summary="Expose the visible plan before choosing the next action.",
            ),
            AgentDecision(
                action="final_answer",
                final_answer="Plan is ready for review.",
                confidence="high",
                reasoning_summary="Stop after proving update_plan can continue.",
            ),
        ]
    )

    monkeypatch.setattr("engine.agent_kernel.service.decide_next_action", lambda **_kwargs: next(decisions))

    response = AgentKernelService(db_session).run(
        AgentRunRequest(
            datasource_id=demo_datasource.id,
            question="Plan a query",
            execute=False,
            session_id="kernel-plan-update",
        )
    )

    plan_artifacts = [artifact for artifact in response.artifacts if artifact.type == "agent_plan"]

    assert response.status == "completed"
    assert response.answer is not None
    assert response.answer.answer == "Plan is ready for review."
    assert plan_artifacts
    assert plan_artifacts[0].semantic_id == "agent_plan_draft"
    assert plan_artifacts[0].payload["steps"][0]["id"] == "draft_sql"
    assert plan_artifacts[0].payload["steps"][0]["status"] == "pending"
