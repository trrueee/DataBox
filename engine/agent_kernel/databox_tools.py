from __future__ import annotations

from typing import Any

from engine.agent.tools import (
    answer_synthesizer_tool,
    build_query_plan_tool,
    build_schema_context_tool,
    execute_sql_tool,
    generate_sql_tool,
    load_followup_context_tool,
    profile_result_tool,
    revise_sql_tool,
    skipped_execute_observation,
    suggest_chart_tool,
    suggest_followups_tool,
    validate_sql_tool,
)
from engine.agent.types import AgentRunRequest, ToolObservation
from engine.agent_kernel.tool_registry import (
    RegisteredTool,
    ToolContext,
    ToolPolicy,
    ToolRegistry,
    ToolSpec,
)


def register_databox_tools() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(_tool("followup.load_context", "Load and normalize follow-up context.", _load_followup_context))
    registry.register(_tool("schema.build_context", "Build relevant schema context for a data question.", _schema_build_context))
    registry.register(_tool("query_plan.build", "Build a structured query plan from schema context.", _query_plan_build))
    registry.register(_tool("sql.generate", "Generate a SQL candidate without executing it.", _sql_generate))
    registry.register(_tool("sql.validate", "Validate SQL with TrustGate and guardrail checks.", _sql_validate))
    registry.register(
        _tool(
            "sql.execute_readonly",
            "Execute previously validated read-only SQL.",
            _sql_execute_readonly,
            policy=ToolPolicy(
                risk_level="warning",
                side_effect="read",
                requires_validated_sql=True,
            ),
        )
    )
    registry.register(_tool("sql.skip_execution", "Record that SQL execution was skipped.", _sql_skip_execution))
    registry.register(_tool("sql.revise", "Revise SQL after validation or execution error.", _sql_revise))
    registry.register(_tool("result.profile", "Profile query results and notable facts.", _result_profile))
    registry.register(_tool("chart.suggest", "Suggest a chart from query results.", _chart_suggest))
    registry.register(_tool("followup.suggest", "Suggest evidence-aware follow-up questions.", _followup_suggest))
    registry.register(_tool("answer.synthesize", "Synthesize the final evidence-grounded answer.", _answer_synthesize))

    return registry


def _tool(
    name: str,
    description: str,
    handler: Any,
    *,
    policy: ToolPolicy | None = None,
) -> RegisteredTool:
    return RegisteredTool(
        spec=ToolSpec(
            name=name,
            description=description,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            policy=policy or ToolPolicy(),
        ),
        handler=handler,
    )


def _request(ctx: ToolContext, args: dict[str, Any]) -> AgentRunRequest:
    if not args.get("question"):
        return ctx.request
    return ctx.request.model_copy(update={"question": str(args["question"])})


def _load_followup_context(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return load_followup_context_tool(_request(ctx, args))


def _schema_build_context(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return build_schema_context_tool(ctx.db, _request(ctx, args))


def _query_plan_build(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return build_query_plan_tool(ctx.db, _request(ctx, args), ctx.state.get("schema_context"))


def _sql_generate(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return generate_sql_tool(
        ctx.db,
        _request(ctx, args),
        schema_context=ctx.state.get("schema_context"),
        query_plan=ctx.state.get("query_plan"),
    )


def _sql_validate(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    sql = args.get("sql") or ctx.state.get("sql")
    return validate_sql_tool(ctx.db, ctx.request.datasource_id, str(sql or ""))


def _sql_execute_readonly(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    raw_safety = ctx.state.get("safety")
    safety: dict[str, Any] = raw_safety if isinstance(raw_safety, dict) else {}
    safe_sql = args.get("sql") or safety.get("safe_sql") or ctx.state.get("sql")
    return execute_sql_tool(ctx.db, _request(ctx, args), str(safe_sql or ""), safety=safety)


def _sql_skip_execution(_ctx: ToolContext, _args: dict[str, Any]) -> ToolObservation:
    return skipped_execute_observation()


def _sql_revise(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return revise_sql_tool(
        sql=str(args.get("sql") or ctx.state.get("sql") or ""),
        error=str(args.get("error") or ctx.state.get("error") or "SQL needs revision."),
        safety=ctx.state.get("safety") if isinstance(ctx.state.get("safety"), dict) else None,
        db=ctx.db,
        datasource_id=ctx.request.datasource_id,
    )


def _result_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return profile_result_tool(_request(ctx, args), ctx.state.get("query_plan"), ctx.state.get("execution"))


def _chart_suggest(ctx: ToolContext, _args: dict[str, Any]) -> ToolObservation:
    return suggest_chart_tool(ctx.state.get("execution"))


def _followup_suggest(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return suggest_followups_tool(
        _request(ctx, args),
        ctx.state.get("sql"),
        ctx.state.get("safety"),
        ctx.state.get("execution"),
        ctx.state.get("result_profile"),
        ctx.state.get("chart_suggestion"),
    )


def _answer_synthesize(ctx: ToolContext, args: dict[str, Any]) -> ToolObservation:
    return answer_synthesizer_tool(
        req=_request(ctx, args),
        query_plan=ctx.state.get("query_plan"),
        sql=ctx.state.get("sql"),
        safety=ctx.state.get("safety"),
        execution=ctx.state.get("execution"),
        result_profile=ctx.state.get("result_profile"),
        suggestions=ctx.state.get("suggestions"),
        error=ctx.state.get("error"),
    )
