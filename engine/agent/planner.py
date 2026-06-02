from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy.orm import Session

from engine.agent.registry import ToolRegistry
from engine.agent.types import AgentIntentPlan, AgentPlanDraft, AgentPlanStep, AgentRunRequest


WORKSPACE_TOOL_BY_INTENT = {
    "explain_sql": "workspace.explain_sql",
    "fix_sql": "workspace.fix_sql",
    "optimize_sql": "workspace.optimize_sql",
    "rewrite_sql": "workspace.rewrite_sql",
    "explain_result": "workspace.explain_result",
    "continue_from_artifact": "workspace.continue_from_artifact",
    "explain_schema": "workspace.explain_schema",
}

ANALYSIS_TOOL_SEQUENCE = [
    "schema.build_context",
    "query_plan.build",
    "sql.generate_candidate",
    "sql.validate",
    "sql.execute_readonly",
    "answer.synthesize",
]


class AgentPlanner:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def plan(
        self,
        db: Session,
        req: AgentRunRequest,
        context_bundle: dict[str, Any],
    ) -> AgentPlanDraft:
        del db
        if req.api_key:
            online = self._online_plan(req, context_bundle)
            if online is not None:
                return online
        return self._fallback_plan(req, context_bundle)

    def _online_plan(
        self,
        req: AgentRunRequest,
        context_bundle: dict[str, Any],
    ) -> AgentPlanDraft | None:
        api_key = str(req.api_key or "").strip()
        if not api_key:
            return None
        api_base = str(req.api_base or "https://api.openai.com/v1").rstrip("/")
        model_name = str(req.model_name or "gpt-4o-mini")
        tool_specs = [
            {
                "name": spec.name,
                "description": spec.description,
                "risk_level": spec.risk_level,
                "requires_approval": spec.requires_approval,
            }
            for spec in self.registry.list_specs()
        ]
        prompt = _planner_prompt(req, context_bundle, tool_specs)
        try:
            response = httpx.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "Return only one valid JSON object for AgentPlanDraft v1."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=25,
            )
            response.raise_for_status()
            payload = response.json()
            text = str(payload["choices"][0]["message"]["content"])
        except Exception:
            return None

        plan = self._parse_plan(text, model_name=model_name, raw_response={"source": "llm"})
        if plan is not None:
            return plan
        try:
            repaired = _repair_json_text(text)
        except ValueError:
            return None
        if repaired != text:
            return self._parse_plan(repaired, model_name=model_name, raw_response={"source": "llm_repaired"})
        return None

    def _parse_plan(
        self,
        text: str,
        *,
        model_name: str,
        raw_response: dict[str, Any],
    ) -> AgentPlanDraft | None:
        try:
            data = json.loads(_extract_json_object(text))
            plan = AgentPlanDraft.model_validate(data)
            return plan.model_copy(update={"model": model_name, "raw_response": raw_response})
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
            return None

    def _fallback_plan(
        self,
        req: AgentRunRequest,
        context_bundle: dict[str, Any],
    ) -> AgentPlanDraft:
        intent = _infer_intent(req, context_bundle)
        context_summary = str(context_bundle.get("context_summary") or "")
        if intent in WORKSPACE_TOOL_BY_INTENT:
            tool_name = WORKSPACE_TOOL_BY_INTENT[intent]
            return AgentPlanDraft(
                intent=AgentIntentPlan(
                    intent=intent,  # type: ignore[arg-type]
                    confidence="medium",
                    rationale="Deterministic workspace-assist fallback selected from supplied editor context.",
                    requires_context=_required_context(intent),
                ),
                steps=[
                    AgentPlanStep(
                        id="workspace_assist",
                        tool_name=tool_name,
                        title=tool_name.replace(".", " "),
                        args={"intent": intent},
                    )
                ],
                should_execute_sql=False,
                context_summary=context_summary,
                safety_notes=[
                    "Workspace assistance may propose editor SQL, but it must not execute SQL automatically.",
                    "Annotations beginning with @ remain editor directives, not Agent tools.",
                ],
                model="databox-deterministic-planner",
                raw_response={"source": "fallback"},
            )

        steps = [
            AgentPlanStep(
                id=f"analysis_{index + 1}",
                tool_name=tool_name,
                title=tool_name.replace(".", " "),
                args={},
                required=tool_name != "sql.execute_readonly" or req.execute,
            )
            for index, tool_name in enumerate(ANALYSIS_TOOL_SEQUENCE)
        ]
        if not req.execute:
            for step in steps:
                if step.tool_name == "sql.execute_readonly":
                    step.required = False
        return AgentPlanDraft(
            intent=AgentIntentPlan(
                intent="analysis",
                confidence="medium",
                rationale="Deterministic analysis fallback keeps the existing schema-query-SQL-validation pipeline.",
                requires_context=[],
            ),
            steps=steps,
            should_execute_sql=bool(req.execute),
            context_summary=context_summary,
            safety_notes=[
                "SQL generation, validation, and optional execution remain bound to registered runtime tools.",
            ],
            model="databox-deterministic-planner",
            raw_response={"source": "fallback"},
        )


def _planner_prompt(
    req: AgentRunRequest,
    context_bundle: dict[str, Any],
    tool_specs: list[dict[str, Any]],
) -> str:
    contract = {
        "version": "agent-plan-draft/v1",
        "intent": {
            "intent": "analysis | explain_sql | fix_sql | optimize_sql | rewrite_sql | explain_result | continue_from_artifact | explain_schema",
            "confidence": "low | medium | high",
            "rationale": "short reason",
            "requires_context": ["active_sql | result_preview | selected_artifact | selected_table"],
        },
        "steps": [
            {
                "id": "stable step id",
                "tool_name": "registered tool name only",
                "title": "short title",
                "args": {},
                "depends_on": [],
                "required": True,
            }
        ],
        "should_execute_sql": False,
        "context_summary": "short summary",
        "safety_notes": [],
    }
    return json.dumps(
        {
            "task": "Create a schema-constrained DataBox Agent plan draft.",
            "question": req.question,
            "execute_requested": req.execute,
            "registered_tools": tool_specs,
            "context_bundle": _compact_for_prompt(context_bundle),
            "output_schema": contract,
            "hard_rules": [
                "Use only registered tool names. Do not invent tools.",
                "Do not represent @ annotations as tools.",
                "Do not plan DDL, DML, backup, restore, export, shell, file, or network operations.",
                "Do not plan automatic SQL execution for workspace explanation/fix/optimize/rewrite/result/schema assistance.",
                "If execution is planned for analysis, include sql.validate before sql.execute_readonly.",
                "Return JSON only.",
            ],
        },
        ensure_ascii=False,
    )


def _infer_intent(req: AgentRunRequest, context_bundle: dict[str, Any]) -> str:
    question = req.question.lower()
    workspace_value = context_bundle.get("workspace")
    workspace: dict[str, Any] = workspace_value if isinstance(workspace_value, dict) else {}
    has_sql = bool(workspace.get("selected_sql") or workspace.get("active_sql"))
    has_result = bool(workspace.get("last_query_result_preview"))
    has_error = bool(workspace.get("last_error"))
    has_artifact = bool(workspace.get("selected_artifact_id") or context_bundle.get("selected_artifact"))
    selected_tables = workspace.get("selected_table_names") or []

    if has_error and has_sql and _contains_any(question, ["fix", "repair", "error", "报错", "修复", "纠错"]):
        return "fix_sql"
    if has_sql and _contains_any(question, ["optimize", "优化", "performance", "性能", "slow", "慢"]):
        return "optimize_sql"
    if has_sql and _contains_any(question, ["rewrite", "改写", "重写", "refactor", "简化"]):
        return "rewrite_sql"
    if has_sql and _contains_any(question, ["explain sql", "explain this sql", "解释 sql", "解释当前 sql", "看懂"]):
        return "explain_sql"
    if has_result and _contains_any(question, ["result", "结果", "why", "为什么", "解释结果", "explain"]):
        return "explain_result"
    if has_artifact and _contains_any(question, ["continue", "artifact", "继续", "基于这个", "接着"]):
        return "continue_from_artifact"
    if selected_tables and _contains_any(question, ["schema", "table", "columns", "结构", "表", "字段"]):
        return "explain_schema"
    if has_sql and _contains_any(question, ["explain", "解释"]):
        return "explain_sql"
    return "analysis"


def _required_context(intent: str) -> list[str]:
    return {
        "explain_sql": ["active_sql"],
        "fix_sql": ["active_sql", "last_error"],
        "optimize_sql": ["active_sql"],
        "rewrite_sql": ["active_sql"],
        "explain_result": ["result_preview"],
        "continue_from_artifact": ["selected_artifact"],
        "explain_schema": ["selected_table"],
    }.get(intent, [])


def _contains_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", stripped, flags=re.IGNORECASE)
    if fence:
        return fence.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in planner response.")
    return stripped[start : end + 1]


def _repair_json_text(text: str) -> str:
    raw = _extract_json_object(text)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return raw


def _compact_for_prompt(value: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= 8000:
        return value
    compact = dict(value)
    if isinstance(compact.get("schema_linking"), dict):
        schema_linking = dict(compact["schema_linking"])
        schema_linking["schema_context"] = str(schema_linking.get("schema_context") or "")[:2000]
        compact["schema_linking"] = schema_linking
    if isinstance(compact.get("selected_table_schema"), list):
        compact["selected_table_schema"] = compact["selected_table_schema"][:4]
    return compact
