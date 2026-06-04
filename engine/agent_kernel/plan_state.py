from __future__ import annotations

from typing import Any

from engine.agent_kernel.schemas import PlanPatch, PlanState, PlanStep


def apply_plan_patches(
    plan: dict[str, Any] | PlanState | None,
    patches: list[PlanPatch],
) -> dict[str, Any]:
    state = _plan_state(plan)
    steps_by_id = {step.id: step for step in state.steps}
    ordered_ids = [step.id for step in state.steps]

    for patch in patches:
        if patch.operation == "clear_plan":
            steps_by_id.clear()
            ordered_ids.clear()
            continue

        if patch.operation == "create_plan":
            steps_by_id.clear()
            ordered_ids.clear()
            if patch.step is not None:
                _upsert_step(steps_by_id, ordered_ids, patch.step)
            continue

        if patch.operation == "add_step" and patch.step is not None:
            _upsert_step(steps_by_id, ordered_ids, patch.step)
            continue

        if patch.operation == "update_step" and patch.step is not None:
            current = steps_by_id.get(patch.step.id)
            merged = _merge_step(current, patch.step)
            _upsert_step(steps_by_id, ordered_ids, merged)
            continue

        step_id = patch.step_id or (patch.step.id if patch.step is not None else None)
        if not step_id or step_id not in steps_by_id:
            continue

        if patch.operation == "mark_running":
            steps_by_id[step_id] = steps_by_id[step_id].model_copy(update={"status": "running"})
        elif patch.operation in {"mark_completed", "complete_step"}:
            steps_by_id[step_id] = steps_by_id[step_id].model_copy(update={"status": "completed"})
        elif patch.operation in {"mark_failed", "fail_step"}:
            steps_by_id[step_id] = steps_by_id[step_id].model_copy(update={"status": "failed"})
        elif patch.operation == "skip_step":
            steps_by_id[step_id] = steps_by_id[step_id].model_copy(update={"status": "skipped"})

    return PlanState(steps=[steps_by_id[step_id] for step_id in ordered_ids]).model_dump(mode="json")


def _plan_state(plan: dict[str, Any] | PlanState | None) -> PlanState:
    if isinstance(plan, PlanState):
        return plan
    if isinstance(plan, dict):
        return PlanState.model_validate(plan)
    return PlanState()


def _upsert_step(steps_by_id: dict[str, PlanStep], ordered_ids: list[str], step: PlanStep) -> None:
    if step.id not in steps_by_id:
        ordered_ids.append(step.id)
    steps_by_id[step.id] = step


def _merge_step(current: PlanStep | None, patch: PlanStep) -> PlanStep:
    if current is None:
        return patch
    update = patch.model_dump(exclude_unset=True)
    return current.model_copy(update=update)
