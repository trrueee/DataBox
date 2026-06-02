from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from engine.agent.runtime import DataBoxAgentRuntime
from engine.agent.types import AgentRunRequest, AgentWorkspaceContext
from engine.evaluation.agent_case_evaluator import AgentCaseEvaluator
from engine.models import AgentEvalCaseResult, AgentEvalRun, AgentGoldenTask
from engine.schemas.agent_eval import AgentEvalRunRequest, AgentEvalRunResponse, AgentEvalCaseResultResponse

logger = logging.getLogger("databox.agent_eval")


class AgentEvalRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.evaluator = AgentCaseEvaluator()

    def run(self, req: AgentEvalRunRequest) -> AgentEvalRunResponse:
        query = self.db.query(AgentGoldenTask).filter(
            AgentGoldenTask.datasource_id == req.datasource_id
        )
        if req.project_id:
            query = query.filter(AgentGoldenTask.project_id == req.project_id)
        if req.task_ids:
            query = query.filter(AgentGoldenTask.id.in_(req.task_ids))
        if req.tags:
            for tag in req.tags:
                query = query.filter(AgentGoldenTask.tags_json.contains(tag))
        if req.source:
            query = query.filter(AgentGoldenTask.source == req.source)

        tasks = query.all()
        if not tasks:
            return AgentEvalRunResponse(
                id="",
                datasource_id=req.datasource_id,
                project_id=req.project_id,
                status="completed",
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                pass_rate=None,
                avg_latency_ms=None,
                summary_json="{}",
                created_at="",
                completed_at="",
                case_results=[],
            )

        eval_run = AgentEvalRun(
            datasource_id=req.datasource_id,
            project_id=req.project_id,
            source_filter_json=json.dumps({"source": req.source, "tags": req.tags}),
            status="running",
            total_cases=len(tasks),
            passed_cases=0,
            failed_cases=0,
            created_at=datetime.now(UTC),
        )
        self.db.add(eval_run)
        self.db.flush()

        passed = 0
        failed = 0
        total_latency = 0
        case_responses: list[AgentEvalCaseResultResponse] = []
        runtime = DataBoxAgentRuntime(self.db)

        for task in tasks:
            try:
                start = time.monotonic()
                workspace_ctx = _build_workspace_context(task)
                agent_req = AgentRunRequest(
                    datasource_id=str(task.datasource_id),
                    question=str(task.question),
                    session_id=None,
                    execute=req.execute,
                    api_key=req.api_key,
                    api_base=req.api_base,
                    model_name=req.model_name,
                    workspace_context=workspace_ctx,
                )
                response = runtime.run(agent_req)
                latency_ms = int((time.monotonic() - start) * 1000)
                total_latency += latency_ms

                evaluation = self.evaluator.evaluate(task, response, events=None, trace=None)

                case_result = AgentEvalCaseResult(
                    eval_run_id=str(eval_run.id),
                    task_id=str(task.id),
                    run_id=response.run_id,
                    status="passed" if evaluation.passed else "failed",
                    score=evaluation.score,
                    latency_ms=latency_ms,
                    actual_intent=evaluation.actual.get("actual_intent"),
                    actual_tools_json=json.dumps(evaluation.actual.get("actual_tools", [])),
                    actual_artifact_types_json=json.dumps(evaluation.actual.get("actual_artifact_types", [])),
                    actual_approval_state=evaluation.actual.get("actual_approval_state"),
                    actual_sql_json="[]",
                    failure_reasons_json=json.dumps(evaluation.failure_reasons),
                    response_json=_safe_response_json(response),
                    created_at=datetime.now(UTC),
                )
                self.db.add(case_result)
                self.db.flush()

                if evaluation.passed:
                    passed += 1
                else:
                    failed += 1

                case_responses.append(AgentEvalCaseResultResponse(
                    id=str(case_result.id),
                    eval_run_id=str(case_result.eval_run_id),
                    task_id=str(case_result.task_id),
                    run_id=str(case_result.run_id) if case_result.run_id else None,
                    status=str(case_result.status),
                    score=float(case_result.score),
                    latency_ms=int(case_result.latency_ms) if case_result.latency_ms else None,
                    actual_intent=str(case_result.actual_intent) if case_result.actual_intent else None,
                    actual_tools_json=str(case_result.actual_tools_json),
                    actual_artifact_types_json=str(case_result.actual_artifact_types_json),
                    actual_approval_state=str(case_result.actual_approval_state) if case_result.actual_approval_state else None,
                    actual_sql_json=str(case_result.actual_sql_json),
                    failure_reasons_json=str(case_result.failure_reasons_json),
                    response_json=str(case_result.response_json),
                    created_at=case_result.created_at.isoformat() if case_result.created_at else None,
                ))

            except Exception as exc:
                logger.exception("Eval case failed for task %s: %s", task.id, exc)
                failed += 1
                case_result = AgentEvalCaseResult(
                    eval_run_id=str(eval_run.id),
                    task_id=str(task.id),
                    run_id=None,
                    status="error",
                    score=0.0,
                    latency_ms=None,
                    actual_intent=None,
                    actual_tools_json="[]",
                    actual_artifact_types_json="[]",
                    actual_approval_state=None,
                    actual_sql_json="[]",
                    failure_reasons_json=json.dumps([str(exc)]),
                    response_json="{}",
                    created_at=datetime.now(UTC),
                )
                self.db.add(case_result)
                self.db.flush()
                case_responses.append(AgentEvalCaseResultResponse(
                    id=str(case_result.id),
                    eval_run_id=str(case_result.eval_run_id),
                    task_id=str(case_result.task_id),
                    run_id=None,
                    status="error",
                    score=0.0,
                    latency_ms=None,
                    failure_reasons_json=str(case_result.failure_reasons_json),
                    actual_intent=None,
                    actual_tools_json="[]",
                    actual_artifact_types_json="[]",
                    actual_approval_state=None,
                    actual_sql_json="[]",
                    response_json="{}",
                    created_at=case_result.created_at.isoformat() if case_result.created_at else None,
                ))

        pass_rate_value = round(passed / max(len(tasks), 1), 4)
        avg_latency_value = round(total_latency / max(len(tasks), 1), 2) if total_latency > 0 else None

        eval_run.status = "completed"  # type: ignore[assignment]
        eval_run.passed_cases = passed  # type: ignore[assignment]
        eval_run.failed_cases = failed  # type: ignore[assignment]
        eval_run.pass_rate = pass_rate_value  # type: ignore[assignment]
        eval_run.avg_latency_ms = avg_latency_value  # type: ignore[assignment]
        eval_run.summary_json = json.dumps({  # type: ignore[assignment]
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate_value,
            "avg_latency_ms": avg_latency_value,
        })
        eval_run.completed_at = datetime.now(UTC)  # type: ignore[assignment]

        self.db.commit()

        return AgentEvalRunResponse(
            id=str(eval_run.id),
            datasource_id=str(eval_run.datasource_id),
            project_id=str(eval_run.project_id) if eval_run.project_id else None,
            status=str(eval_run.status),
            total_cases=int(eval_run.total_cases),
            passed_cases=int(eval_run.passed_cases),
            failed_cases=int(eval_run.failed_cases),
            pass_rate=float(eval_run.pass_rate) if eval_run.pass_rate is not None else None,
            avg_latency_ms=float(eval_run.avg_latency_ms) if eval_run.avg_latency_ms is not None else None,
            summary_json=str(eval_run.summary_json),
            created_at=eval_run.created_at.isoformat() if eval_run.created_at else None,
            completed_at=eval_run.completed_at.isoformat() if eval_run.completed_at else None,
            case_results=case_responses,
        )


def _build_workspace_context(task: AgentGoldenTask) -> AgentWorkspaceContext | None:
    try:
        data = json.loads(str(task.workspace_context_json))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not data:
        return None
    selected = data.get("selected_table_names")
    return AgentWorkspaceContext(
        datasource_id=str(task.datasource_id),
        active_sql=data.get("active_sql"),
        last_error=data.get("last_error"),
        last_query_result_preview=data.get("last_query_result_preview"),
        selected_table_names=list(selected) if isinstance(selected, list) else [],
        selected_artifact_id=data.get("selected_artifact_id"),
        recent_agent_run_id=data.get("recent_agent_run_id"),
    )


def _safe_response_json(response: Any) -> str:
    try:
        data = response.model_dump()
        data.pop("api_key", None)
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return "{}"
