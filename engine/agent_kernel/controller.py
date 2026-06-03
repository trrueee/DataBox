from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from engine.agent_kernel.schemas import AgentDecision, ToolCallDecision
from engine.agent_kernel.state import KernelState, latest_user_message


CONTROLLER_SYSTEM_PROMPT = (
    "You are the DataBox Agent Kernel controller. Choose exactly one next action.\n"
    "Use tools as capabilities, not as a fixed workflow. Respect policy and never request execution "
    "before SQL has been validated. Return only JSON matching AgentDecision."
)


def decide_next_action(
    *,
    state: KernelState,
    available_tools: list[dict[str, Any]],
) -> AgentDecision:
    if state.get("api_key"):
        decision = _try_llm_decision(state=state, available_tools=available_tools)
        if decision is not None:
            return decision
    return _fallback_decision(state)


def _try_llm_decision(
    *,
    state: KernelState,
    available_tools: list[dict[str, Any]],
) -> AgentDecision | None:
    api_key = str(state.get("api_key") or "").strip()
    if not api_key:
        return None

    api_base = str(state.get("api_base") or "https://api.openai.com/v1").rstrip("/")
    model_name = str(state.get("model_name") or "gpt-4o-mini")
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": CONTROLLER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "state": _controller_state_view(state),
                        "available_tools": available_tools,
                        "agent_decision_schema": {
                            "action": "call_tool | update_plan | ask_user | final_answer | pause | wait_approval",
                            "tool_call": {"tool_name": "string", "args": {}, "reason": "string"},
                            "plan_patches": [],
                            "user_message": "string | null",
                            "final_answer": "string | null",
                            "confidence": "low | medium | high",
                            "reasoning_summary": "short explanation",
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            f"{api_base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        raw = json.loads(content)
        return AgentDecision.model_validate(raw)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError):
        return None


def _controller_state_view(state: KernelState) -> dict[str, Any]:
    return {
        "goal": state.get("goal") or latest_user_message(state),
        "status": state.get("status"),
        "execute": state.get("execute"),
        "has_follow_up_context": bool(state.get("follow_up_context")),
        "has_loaded_followup": bool(state.get("followup_context")),
        "has_schema_context": bool(state.get("schema_context")),
        "has_query_plan": bool(state.get("query_plan")),
        "has_sql": bool(state.get("sql")),
        "has_safety": bool(state.get("safety")),
        "safety_can_execute": bool((state.get("safety") or {}).get("can_execute")) if isinstance(state.get("safety"), dict) else False,
        "safety_requires_confirmation": bool((state.get("safety") or {}).get("requires_confirmation")) if isinstance(state.get("safety"), dict) else False,
        "has_execution": bool(state.get("execution")),
        "has_result_profile": bool(state.get("result_profile")),
        "has_chart_suggestion": bool(state.get("chart_suggestion")),
        "suggestion_count": len(state.get("suggestions", [])),
        "has_answer": bool(state.get("answer")),
        "error": state.get("error"),
        "step_count": state.get("step_count", 0),
        "max_steps": state.get("max_steps", 20),
    }


def _fallback_decision(state: KernelState) -> AgentDecision:
    if state.get("error") and not state.get("revision_attempted") and state.get("sql"):
        return _call("sql.revise", {"sql": state.get("sql"), "error": state.get("error")}, "Revise SQL after the current error.")

    if state.get("answer"):
        answer = state.get("answer") or {}
        return AgentDecision(
            action="final_answer",
            final_answer=str(answer.get("answer") or ""),
            confidence="high",
            reasoning_summary="The answer artifact is ready.",
        )

    if state.get("follow_up_context") and not state.get("followup_context"):
        return _call("followup.load_context", {}, "Normalize prior artifacts for this thread.")

    if not state.get("schema_context"):
        return _call("schema.build_context", {"question": latest_user_message(state)}, "Build schema context before data work.")

    if not state.get("query_plan"):
        return _call("query_plan.build", {}, "Build a query plan from the current schema context.")

    if not state.get("sql"):
        return _call("sql.generate", {}, "Generate a SQL candidate.")

    if not state.get("safety"):
        return _call("sql.validate", {"sql": state.get("sql")}, "Validate SQL before any execution.")

    raw_safety = state.get("safety")
    safety: dict[str, Any] = raw_safety if isinstance(raw_safety, dict) else {}
    if not safety.get("can_execute"):
        if not state.get("revision_attempted"):
            return _call(
                "sql.revise",
                {"sql": state.get("sql"), "error": safety.get("revise_suggestion") or "SQL did not pass TrustGate."},
                "Ask the revision tool for deterministic recovery guidance.",
            )
        return _call("answer.synthesize", {}, "Explain why the agent cannot continue safely.")

    if not state.get("execution"):
        if not state.get("execute", True):
            return _call("sql.skip_execution", {}, "The request is review-only, so execution is skipped.")
        return _call("sql.execute_readonly", {}, "Execute the validated read-only SQL.")

    raw_execution = state.get("execution")
    execution: dict[str, Any] = raw_execution if isinstance(raw_execution, dict) else {}
    if execution.get("success") is False and not state.get("revision_attempted"):
        return _call(
            "sql.revise",
            {"sql": state.get("sql"), "error": execution.get("revise_suggestion") or state.get("error") or "SQL execution failed."},
            "Revise after execution failure.",
        )

    if not state.get("result_profile"):
        return _call("result.profile", {}, "Profile the result for answer synthesis.")

    if not state.get("chart_suggestion"):
        return _call("chart.suggest", {}, "Suggest a chart when the result supports one.")

    if not state.get("suggestions"):
        return _call("followup.suggest", {}, "Suggest useful follow-up questions.")

    return _call("answer.synthesize", {}, "Synthesize the final answer from artifacts.")


def _call(tool_name: str, args: dict[str, Any], reason: str) -> AgentDecision:
    return AgentDecision(
        action="call_tool",
        tool_call=ToolCallDecision(tool_name=tool_name, args=args, reason=reason),
        confidence="medium",
        reasoning_summary=reason,
    )
