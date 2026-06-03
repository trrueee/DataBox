from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from engine.agent.types import AgentRunRequest, AgentRunResponse
from engine.agent_kernel.service import AgentKernelService
from engine.db import get_db
from engine.errors import DataBoxError


router = APIRouter(prefix="/agent-kernel", tags=["agent-kernel"])


class SendMessageRequest(BaseModel):
    datasource_id: str
    message: str
    thread_id: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    model_name: str | None = None
    workspace_context: Any | None = None
    follow_up_context: Any | None = None
    execute: bool = True
    max_steps: int = Field(default=20, ge=1, le=20)


@router.post("/run", response_model=AgentRunResponse)
def run_agent_kernel(req: AgentRunRequest, db: Session = Depends(get_db)) -> AgentRunResponse:
    try:
        return AgentKernelService(db).run(req)
    except DataBoxError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "AGENT_KERNEL_ERROR", "message": f"Agent kernel failed: {str(exc)}"},
        )


@router.post("/messages")
def send_agent_kernel_message(payload: SendMessageRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return AgentKernelService(db).send_message(
            datasource_id=payload.datasource_id,
            message=payload.message,
            thread_id=payload.thread_id,
            api_key=payload.api_key,
            api_base=payload.api_base,
            model_name=payload.model_name,
            workspace_context=payload.workspace_context,
            follow_up_context=payload.follow_up_context,
            execute=payload.execute,
            max_steps=payload.max_steps,
        )
    except DataBoxError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "AGENT_KERNEL_ERROR", "message": f"Agent kernel failed: {str(exc)}"},
        )
