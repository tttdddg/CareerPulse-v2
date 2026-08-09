"""HTTP adapters for the in-memory A02 Mock orchestrator.

The routers are intentionally exported but not mounted into the legacy router
aggregator in this task, because existing public routing files are out of scope.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..orchestrator import CareerOrchestrator, CareerState


class CareerAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    platform_session_id: str | None = None
    user_id: str | None = None
    student_input: dict[str, Any] | None = None
    target_job_input: dict[str, Any] | None = None


orchestrator = CareerOrchestrator()
router = APIRouter(prefix="/api/career-agent", tags=["career-agent-mock"])
agent_log_router = APIRouter(prefix="/api/agent", tags=["career-agent-mock"])


@router.post("/run", response_model=CareerState)
async def run_career_agent(payload: CareerAgentRunRequest) -> CareerState:
    return await orchestrator.run(CareerState(**payload.model_dump()))


@router.get("/session/{session_id}", response_model=CareerState)
async def get_career_session(session_id: str) -> CareerState:
    state = orchestrator.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Career Agent session not found")
    return state


@agent_log_router.get("/logs/{session_id}")
async def get_agent_logs(session_id: str):
    state = orchestrator.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Career Agent session not found")
    return state.agent_logs


# Standalone Mock entry point. The legacy FastAPI application remains untouched.
app = FastAPI(title="CareerPulse A02 Mock Agent API")
app.include_router(router)
app.include_router(agent_log_router)
