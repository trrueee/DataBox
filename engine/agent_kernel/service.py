from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, Literal, cast

from sqlalchemy.orm import Session

from engine.agent import persistence as agent_persistence
from engine.agent.artifact_emitter import ArtifactEmitter
from engine.agent.artifacts import AgentArtifactIdentity
from engine.agent.events import EventEmitter
from engine.agent.runtime import DataBoxAgentRuntime
from engine.agent.state import AgentState
from engine.agent.types import (
    AgentApprovalRecord,
    AgentAnswer,
    AgentArtifact,
    AgentRunRequest,
    AgentRunResponse,
    AgentRuntimeEvent,
    AgentRuntimeEventType,
    ToolObservation,
)
from engine.agent_kernel.controller import decide_next_action
from engine.agent_kernel.databinding import apply_tool_result_to_state, merge_state
from engine.agent_kernel.databox_tools import register_databox_tools
from engine.agent_kernel.policy import PolicyGate
from engine.agent_kernel.state import KernelState, latest_user_message
from engine.agent_kernel.tool_registry import ToolContext, ToolRegistry

logger = logging.getLogger("databox.agent_kernel.service")


class AgentKernelService:
    def __init__(self, db: Session, registry: ToolRegistry | None = None):
        self.db = db
        self.registry = registry or register_databox_tools()
        self.policy_gate = PolicyGate(self.registry)
        self.artifact_emitter = ArtifactEmitter()

    def run(self, req: AgentRunRequest) -> AgentRunResponse:
        final_response: AgentRunResponse | None = None
        for event in self.run_iter(req):
            if event.response is not None:
                final_response = event.response
        if final_response is None:
            raise RuntimeError("Agent kernel completed without a final response.")
        return final_response

    def send_message(
        self,
        *,
        datasource_id: str,
        message: str,
        thread_id: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        model_name: str | None = None,
        workspace_context: Any | None = None,
        follow_up_context: Any | None = None,
        execute: bool = True,
        max_steps: int = 20,
    ) -> dict[str, Any]:
        req = AgentRunRequest(
            datasource_id=datasource_id,
            question=message,
            session_id=thread_id,
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
            workspace_context=workspace_context,
            follow_up_context=follow_up_context,
            execute=execute,
            max_steps=max_steps,
        )
        response = self.run(req)
        return {
            "thread_id": response.session_id,
            "status": response.status,
            "response": response.model_dump(mode="json"),
        }

    def run_iter(self, req: AgentRunRequest) -> Iterator[AgentRuntimeEvent]:
        run_id = str(uuid.uuid4())
        session_id = self._session_id(req)
        artifact_identity = AgentArtifactIdentity(run_id)
        agent_state = AgentState(
            run_id=run_id,
            session_id=session_id,
            parent_run_id=req.parent_run_id,
            question=req.question,
            datasource_id=req.datasource_id,
        )
        state: dict[str, Any] = dict(self._initial_state(req, run_id, session_id))
        emitted_artifact_ids: set[str] = set()

        def _save_event(event: AgentRuntimeEvent) -> None:
            try:
                agent_persistence.record_runtime_event(self.db, session_id, event)
            except Exception:
                logger.warning("Agent kernel persistence: failed to save event %s", event.event_id)
                self._rollback_quietly()

        emitter = EventEmitter(run_id, _save_event)

        def emit(
            event_type: AgentRuntimeEventType,
            *,
            step: dict[str, Any] | None = None,
            artifact: AgentArtifact | None = None,
            answer_payload: AgentAnswer | None = None,
            response: AgentRunResponse | None = None,
            approval: AgentApprovalRecord | None = None,
            error: str | None = None,
        ) -> AgentRuntimeEvent:
            return emitter.emit(
                event_type,
                step=step,
                artifact=artifact,
                answer_payload=answer_payload,
                response=response,
                approval=approval,
                error=error,
            )

        yield emit(
            "agent.run.started",
            step={"datasource_id": req.datasource_id, "question": req.question, "execute": req.execute},
        )
        self._start_persistence(req, run_id, session_id)

        while True:
            if int(state.get("step_count", 0)) >= int(state.get("max_steps", 20)):
                merge_state(
                    state,
                    {
                        "status": "failed",
                        "error": "Max agent steps reached.",
                    },
                )
                response = self._response(req, state, agent_state, run_id, session_id, artifact_identity, success=False)
                yield from self._final_events(emit, response, agent_state, emitted_artifact_ids)
                return

            decision = decide_next_action(
                state=cast(KernelState, state),
                available_tools=[spec.model_dump(mode="json") for spec in self.registry.list_specs()],
            )
            merge_state(
                state,
                {
                    "pending_decision": decision.model_dump(mode="json"),
                    "step_count": int(state.get("step_count", 0)) + 1,
                    "trace_events": [{"type": "controller.decision", "payload": decision.model_dump(mode="json")}],
                },
            )

            if decision.action == "final_answer":
                merge_state(state, {"status": "completed"})
                response = self._response(req, state, agent_state, run_id, session_id, artifact_identity, success=True)
                yield from self._final_events(emit, response, agent_state, emitted_artifact_ids)
                return

            if decision.action in {"ask_user", "pause", "wait_approval"}:
                status = "waiting_user" if decision.action == "ask_user" else "paused"
                if decision.action == "wait_approval":
                    status = "waiting_approval"
                merge_state(state, {"status": status})
                response = self._response(req, state, agent_state, run_id, session_id, artifact_identity, success=False)
                yield from self._final_events(emit, response, agent_state, emitted_artifact_ids)
                return

            if decision.action != "call_tool" or decision.tool_call is None:
                merge_state(state, {"status": "failed", "error": f"Unsupported controller action: {decision.action}"})
                response = self._response(req, state, agent_state, run_id, session_id, artifact_identity, success=False)
                yield from self._final_events(emit, response, agent_state, emitted_artifact_ids)
                return

            tool_name = decision.tool_call.tool_name
            policy = self.policy_gate.check(state, tool_name, decision.tool_call.args)
            if policy.status == "blocked":
                merge_state(state, {"error": policy.reason, "trace_events": [{"type": "policy.blocked", "payload": policy.model_dump(mode="json")}]})
                continue

            if policy.status == "approval_required":
                approval = self._approval_record(run_id, session_id, tool_name, policy.reason, policy.risk_level, policy.safe_args)
                merge_state(
                    state,
                    {
                        "status": "waiting_approval",
                        "pending_approval": approval.model_dump(mode="json"),
                        "trace_events": [{"type": "policy.approval_required", "payload": approval.model_dump(mode="json")}],
                    },
                )
                yield emit("agent.approval.required", step={"name": tool_name, "status": "waiting_approval"}, approval=approval)
                response = self._response(req, state, agent_state, run_id, session_id, artifact_identity, success=False, approval=approval)
                yield from self._final_events(emit, response, agent_state, emitted_artifact_ids, waiting_approval=True)
                return

            yield emit("agent.step.started", step={"name": self._step_name(tool_name), "tool_name": tool_name})
            observation = self._execute_tool(req, state, tool_name, policy.safe_args)
            agent_state.apply_observation(observation.name or self._step_name(tool_name), observation)
            yield emit(
                "agent.step.completed",
                step={
                    "name": observation.name or self._step_name(tool_name),
                    "tool_name": tool_name,
                    "status": observation.status,
                    "error": observation.error,
                    "latency_ms": observation.latency_ms,
                },
            )
            merge_state(state, apply_tool_result_to_state(state=state, tool_name=tool_name, observation=observation))
            yield from self._artifact_events(emit, observation, agent_state, artifact_identity, emitted_artifact_ids)

    def _execute_tool(
        self,
        req: AgentRunRequest,
        state: dict[str, Any],
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolObservation:
        tool = self.registry.require(tool_name)
        ctx = ToolContext(db=self.db, request=req, state=dict(state))
        return tool.handler(ctx, args)

    def _artifact_events(
        self,
        emit: Any,
        observation: ToolObservation,
        agent_state: AgentState,
        artifact_identity: AgentArtifactIdentity,
        emitted_artifact_ids: set[str],
    ) -> Iterator[AgentRuntimeEvent]:
        for artifact in self.artifact_emitter.from_observation(observation.name, observation, agent_state, artifact_identity):
            bound = self.artifact_emitter.bind_dependencies(agent_state.artifacts, artifact)
            agent_state.artifacts.append(bound)
            if bound.id in emitted_artifact_ids:
                continue
            emitted_artifact_ids.add(bound.id)
            event = emit("agent.artifact.created", step={"name": observation.name}, artifact=bound)
            yield event
            try:
                agent_persistence.record_artifact(self.db, agent_state.session_id or "", agent_state.run_id, bound, len(agent_state.artifacts))
            except Exception:
                logger.warning("Agent kernel persistence: failed to save artifact %s", bound.id)
                self._rollback_quietly()

    def _final_events(
        self,
        emit: Any,
        response: AgentRunResponse,
        agent_state: AgentState,
        emitted_artifact_ids: set[str],
        *,
        waiting_approval: bool = False,
    ) -> Iterator[AgentRuntimeEvent]:
        for artifact in response.artifacts:
            if artifact.id in emitted_artifact_ids:
                continue
            emitted_artifact_ids.add(artifact.id)
            event = emit("agent.artifact.created", artifact=artifact)
            yield event
            try:
                agent_persistence.record_artifact(self.db, response.session_id, response.run_id, artifact, len(agent_state.artifacts))
            except Exception:
                logger.warning("Agent kernel persistence: failed to save final artifact %s", artifact.id)
                self._rollback_quietly()

        if response.answer is not None:
            event = emit("agent.answer.completed", answer_payload=response.answer)
            yield event

        if waiting_approval:
            yield emit("agent.run.waiting_approval", response=response, approval=response.approval)
        else:
            final_type: AgentRuntimeEventType = "agent.run.completed" if response.success else "agent.run.failed"
            yield emit(final_type, response=response, error=response.error)

        try:
            if response.success:
                agent_persistence.complete_run(self.db, response)
            else:
                agent_persistence.fail_run(self.db, response.run_id, response.session_id, response.error or response.status or "Agent kernel stopped.", response)
            self.db.commit()
        except Exception:
            logger.warning("Agent kernel persistence: failed to persist final response for run %s", response.run_id)
            self._rollback_quietly()

    def _response(
        self,
        req: AgentRunRequest,
        state: dict[str, Any],
        agent_state: AgentState,
        run_id: str,
        session_id: str,
        artifact_identity: AgentArtifactIdentity,
        *,
        success: bool,
        approval: AgentApprovalRecord | None = None,
    ) -> AgentRunResponse:
        runtime = DataBoxAgentRuntime(self.db)
        error = state.get("error")
        return runtime._response(
            req=req,
            success=success and not error,
            steps=agent_state.steps,
            query_plan=agent_state.query_plan,
            sql=agent_state.sql,
            safety=agent_state.safety,
            execution=agent_state.execution,
            explanation=str((agent_state.answer or {}).get("answer") or "") or None,
            chart_suggestion=agent_state.chart_suggestion,
            result_profile=agent_state.result_profile,
            answer=agent_state.answer,
            suggestions=agent_state.suggestions,
            error=error,
            run_id=run_id,
            session_id=session_id,
            artifacts=agent_state.artifacts,
            artifact_identity=artifact_identity,
            status=state.get("status"),
            approval=approval,
        )

    def _initial_state(self, req: AgentRunRequest, run_id: str, session_id: str) -> KernelState:
        return KernelState(
            thread_id=session_id,
            run_id=run_id,
            datasource_id=req.datasource_id,
            execute=req.execute,
            status="running",
            messages=[{"role": "user", "content": req.question}],
            workspace_context=req.workspace_context,
            follow_up_context=req.follow_up_context,
            goal=req.question,
            plan=None,
            plan_events=[],
            pending_decision=None,
            pending_tool_call=None,
            pending_approval=None,
            tool_results=[],
            artifacts=[],
            trace_events=[],
            followup_context=None,
            schema_context=None,
            query_plan=None,
            sql_candidate=None,
            sql=None,
            safety=None,
            execution=None,
            result_profile=None,
            chart_suggestion=None,
            suggestions=[],
            answer=None,
            final_answer=None,
            error=None,
            revision_attempted=False,
            step_count=0,
            max_steps=req.max_steps,
            api_key=req.api_key,
            api_base=req.api_base,
            model_name=req.model_name,
        )

    def _start_persistence(self, req: AgentRunRequest, run_id: str, session_id: str) -> None:
        try:
            agent_persistence.create_or_get_session(self.db, req, run_id)
            agent_persistence.start_run(self.db, req, run_id, session_id)
        except Exception:
            logger.warning("Agent kernel persistence: failed to start run %s", run_id)
            self._rollback_quietly()

    def _approval_record(
        self,
        run_id: str,
        session_id: str,
        tool_name: str,
        reason: str,
        risk_level: str,
        requested_action: dict[str, Any],
    ) -> AgentApprovalRecord:
        now = datetime.now(timezone.utc)
        normalized_risk: Literal["safe", "warning", "danger"] = (
            cast(Literal["safe", "warning", "danger"], risk_level)
            if risk_level in {"safe", "warning", "danger"}
            else "warning"
        )
        return AgentApprovalRecord(
            id=f"approval_{uuid.uuid4().hex}",
            run_id=run_id,
            session_id=session_id,
            step_name=tool_name,
            tool_name=tool_name,
            status="pending",
            risk_level=normalized_risk,
            reason=reason,
            policy_decision={"reason": reason, "risk_level": risk_level},
            requested_action=requested_action,
            created_at=now,
        )

    def _session_id(self, req: AgentRunRequest) -> str:
        if req.session_id:
            return req.session_id
        if req.follow_up_context and req.follow_up_context.session_id:
            return req.follow_up_context.session_id
        return str(uuid.uuid4())

    def _step_name(self, tool_name: str) -> str:
        return {
            "followup.load_context": "load_follow_up_context",
            "schema.build_context": "build_schema_context",
            "query_plan.build": "build_query_plan",
            "sql.generate": "generate_sql_candidate",
            "sql.validate": "validate_sql",
            "sql.execute_readonly": "execute_sql",
            "sql.skip_execution": "execute_sql",
            "sql.revise": "revise_sql",
            "result.profile": "profile_result",
            "chart.suggest": "suggest_chart",
            "followup.suggest": "suggest_followups",
            "answer.synthesize": "answer_synthesizer",
        }.get(tool_name, tool_name)

    def _rollback_quietly(self) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass


def latest_message_for_debug(state: KernelState) -> str:
    return latest_user_message(state)
