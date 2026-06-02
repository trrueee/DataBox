from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from engine.agent.planner import WORKSPACE_TOOL_BY_INTENT
from engine.agent.registry import ToolRegistry
from engine.agent.types import AgentPlanDraft, AgentRunRequest
from engine.guardrail import guardrail_check


FORBIDDEN_OPERATION_RE = re.compile(
    r"\b("
    r"insert|update|delete|drop|create|alter|truncate|merge|replace|grant|revoke|"
    r"backup|restore|dump|export|outfile|load_file"
    r")\b",
    flags=re.IGNORECASE,
)
PROPOSED_SQL_KEYS = {"sql", "proposed_sql", "safe_sql", "fixed_sql", "rewritten_sql"}


class PlanValidationResult(BaseModel):
    valid: bool
    reasons: list[str] = Field(default_factory=list)
    normalized_plan: AgentPlanDraft | None = None


class AgentPlanValidator:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def validate(
        self,
        req: AgentRunRequest,
        plan: AgentPlanDraft,
        context_bundle: dict[str, Any],
    ) -> PlanValidationResult:
        reasons: list[str] = []
        tool_names = {spec.name for spec in self.registry.list_specs()}
        planned_tools = [step.tool_name for step in plan.steps]

        if len(plan.steps) > 6:
            reasons.append("Plan contains more than 6 steps.")
        if not plan.steps:
            reasons.append("Plan contains no executable steps.")

        for step in plan.steps:
            if step.tool_name.startswith("@"):
                reasons.append(f"Annotations are not tools: {step.tool_name}.")
            if step.tool_name not in tool_names:
                reasons.append(f"Unknown tool: {step.tool_name}.")
            if FORBIDDEN_OPERATION_RE.search(_json_text(step.args)):
                reasons.append(f"Step {step.id} contains a forbidden operation.")
            for sql in _proposed_sql_values(step.args):
                reasons.extend(_validate_proposed_sql(sql, step.id))

        intent = plan.intent.intent
        compatible_tool = WORKSPACE_TOOL_BY_INTENT.get(intent)
        if compatible_tool and compatible_tool not in planned_tools:
            reasons.append(f"Intent {intent} must use {compatible_tool}.")
        if intent == "analysis" and any(tool.startswith("workspace.") for tool in planned_tools):
            reasons.append("Analysis intent cannot use workspace assist tools.")
        if intent != "analysis" and any(tool == "sql.execute_readonly" for tool in planned_tools):
            reasons.append("Workspace assistance cannot execute SQL.")

        if plan.should_execute_sql or (req.execute and intent == "analysis"):
            if "sql.validate" not in planned_tools:
                reasons.append("Execution plans must include sql.validate.")
            if "sql.execute_readonly" not in planned_tools:
                reasons.append("Execution plans must include sql.execute_readonly.")
        if not req.execute and plan.should_execute_sql:
            reasons.append("Plan requested SQL execution when the request is review-only.")

        reasons.extend(_context_reasons(intent, context_bundle))

        if FORBIDDEN_OPERATION_RE.search(_json_text(plan.model_dump(mode="json", exclude={"raw_response"}))):
            # Natural-language questions can contain words like "delete"; the concrete plan must not.
            plan_text_without_question = _json_text(
                {
                    "intent": plan.intent.model_dump(mode="json"),
                    "steps": [step.model_dump(mode="json") for step in plan.steps],
                    "safety_notes": plan.safety_notes,
                }
            )
            if FORBIDDEN_OPERATION_RE.search(plan_text_without_question):
                reasons.append("Plan contains forbidden DDL/DML/backup/restore/export language.")

        return PlanValidationResult(valid=not reasons, reasons=reasons, normalized_plan=plan if not reasons else None)


def _context_reasons(intent: str, context_bundle: dict[str, Any]) -> list[str]:
    workspace_value = context_bundle.get("workspace")
    workspace: dict[str, Any] = workspace_value if isinstance(workspace_value, dict) else {}
    reasons: list[str] = []
    active_sql = bool(workspace.get("selected_sql") or workspace.get("active_sql"))
    if intent in {"explain_sql", "optimize_sql", "rewrite_sql"} and not active_sql:
        reasons.append(f"Intent {intent} requires active SQL context.")
    if intent == "fix_sql":
        if not active_sql:
            reasons.append("Intent fix_sql requires active SQL context.")
        if not workspace.get("last_error"):
            reasons.append("Intent fix_sql requires last_error context.")
    if intent == "explain_result" and not workspace.get("last_query_result_preview"):
        reasons.append("Intent explain_result requires a result preview.")
    if intent == "continue_from_artifact" and not (workspace.get("selected_artifact_id") or context_bundle.get("selected_artifact")):
        reasons.append("Intent continue_from_artifact requires a selected artifact.")
    if intent == "explain_schema":
        linking_value = context_bundle.get("schema_linking")
        linking: dict[str, Any] = linking_value if isinstance(linking_value, dict) else {}
        selected_tables = workspace.get("selected_table_names") or workspace.get("selected_table_ids") or linking.get("selected_tables")
        if not selected_tables:
            reasons.append("Intent explain_schema requires selected table or linked schema context.")
    return reasons


def _validate_proposed_sql(sql: str, step_id: str) -> list[str]:
    stripped = sql.strip()
    if not stripped:
        return []
    result = guardrail_check(stripped)
    reasons = []
    if result["result"] == "reject":
        reasons.append(f"Step {step_id} proposed SQL failed guardrail: {result['message']}")
    rules = {str(item.get("rule")) for item in result.get("checks", [])}
    if "multi_statement" in rules:
        reasons.append(f"Step {step_id} proposed SQL contains multiple statements.")
    if "select_only" in rules or "blocked_command_type" in rules:
        reasons.append(f"Step {step_id} proposed SQL is not read-only SELECT.")
    return reasons


def _proposed_sql_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PROPOSED_SQL_KEYS and isinstance(item, str):
                found.append(item)
            else:
                found.extend(_proposed_sql_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_proposed_sql_values(item))
    return found


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)
