"""Mock HTTP tool adapter for Ant TBox Enterprise integration testing."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field

from ..orchestrator import CareerOrchestrator, CareerState


class MockCareerToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    platform_session_id: str | None = None
    user_id: str | None = None
    student_input: dict[str, Any] | None = None
    target_job_input: dict[str, Any] | None = None


class ToolError(BaseModel):
    type: str
    detail: str


class MockToolResponse(BaseModel):
    code: int
    message: str
    request_id: str
    data: dict[str, Any] | None = None
    error: ToolError | None = None


router = APIRouter(prefix="/api/tbox", tags=["tbox-mock"])
orchestrator = CareerOrchestrator()


async def run_mock_career_tool(payload: MockCareerToolRequest) -> MockToolResponse:
    """Run the full Mock Agent chain using the frozen platform envelope."""
    request_id = str(uuid4())
    try:
        state = await orchestrator.run(CareerState(**payload.model_dump()))
        has_fallback = any(log.fallback_used for log in state.agent_logs)
        return MockToolResponse(
            code=-4 if has_fallback else 0,
            message="Mock workflow completed with fallback" if has_fallback else "success",
            request_id=request_id,
            data=state.model_dump(mode="json"),
            error=None,
        )
    except Exception as exc:
        return MockToolResponse(
            code=-1,
            message="Mock workflow failed",
            request_id=request_id,
            data=None,
            error=ToolError(
                type=type(exc).__name__,
                detail="Mock platform adapter failed; request content was omitted",
            ),
        )


@router.post("/mock-career-analysis", response_model=MockToolResponse)
async def mock_career_analysis(payload: MockCareerToolRequest) -> MockToolResponse:
    return await run_mock_career_tool(payload)


# Standalone TBox Mock endpoint; run with app.platform.tbox_adapter:app.
app = FastAPI(title="CareerPulse A02 TBox Mock Tool")
app.include_router(router)
