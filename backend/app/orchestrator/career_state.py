"""Shared in-memory state for the A02 mock agent workflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolCallLog(BaseModel):
    """Privacy-safe summary of one mock tool invocation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    input_summary: str
    output_summary: str
    duration_ms: int = Field(ge=0)
    status: str = Field(pattern="^(success|error)$")


class AgentLog(BaseModel):
    """Agent execution log defined by the frozen A02 API contract."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    agent_name: str
    status: str = Field(pattern="^(success|partial|failed)$")
    summary: str
    duration_ms: int = Field(ge=0)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    fallback_used: bool = False
    error: str | None = None
    timestamp: str


class CareerState(BaseModel):
    """Conversation-scoped state passed through all six mock agents."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    platform_session_id: str | None = None
    user_id: str | None = None
    student_input: dict[str, Any] | None = None
    target_job_input: dict[str, Any] | None = None
    student_profile: dict[str, Any] | None = None
    job_profile: dict[str, Any] | None = None
    trend_result: dict[str, Any] | None = None
    match_result: dict[str, Any] | None = None
    path_plan: dict[str, Any] | None = None
    learning_plan: dict[str, Any] | None = None
    career_roadmap: dict[str, Any] | None = None
    career_preferences: dict[str, Any] | None = None
    desired_city: str | None = None
    training_plan: dict[str, Any] | None = None
    resource_result: dict[str, Any] | None = None
    feedback_result: dict[str, Any] | None = None
    final_report: dict[str, Any] | None = None
    agent_logs: list[AgentLog] = Field(default_factory=list)

    def apply_agent_data(self, data: dict[str, Any]) -> None:
        """Apply only declared state fields from an Agent result."""
        for field_name, value in data.items():
            if field_name not in type(self).model_fields or field_name in {
                "session_id",
                "agent_logs",
            }:
                raise ValueError(f"Agent attempted to update unsupported field: {field_name}")
            setattr(self, field_name, value)
