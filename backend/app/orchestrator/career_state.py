"""Shared state model for the A02 Agent workflow."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Status = Literal[
    "INITIALIZED",
    "PROFILE_STARTED",
    "PROFILE_COMPLETED",
    "JOB_STARTED",
    "JOB_COMPLETED",
    "MATCH_STARTED",
    "MATCH_COMPLETED",
    "PATH_STARTED",
    "PATH_COMPLETED",
    "TRAINING_STARTED",
    "TRAINING_COMPLETED",
    "FEEDBACK_STARTED",
    "FEEDBACK_COMPLETED",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
]

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class ToolCallLog(BaseModel):
    """Privacy-safe summary of one tool invocation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    service_name: str | None = Field(default=None, max_length=64)
    input_summary: str
    output_summary: str
    duration_ms: int = Field(ge=0)
    status: str = Field(pattern="^(success|error)$")


class AgentLog(BaseModel):
    """Agent execution log defined by the frozen A02 API contract."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN)
    agent_name: str
    service_name: str | None = Field(default=None, max_length=64)
    status: str = Field(pattern="^(success|partial|failed)$")
    summary: str
    duration_ms: int = Field(ge=0)
    tool_calls: list[ToolCallLog] = Field(default_factory=list)
    fallback_used: bool = False
    error: str | None = None
    timestamp: str


class CareerState(BaseModel):
    """Conversation-scoped state passed through all A02 agents."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    platform_session_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    status: Status = "INITIALIZED"
    error_type: str | None = Field(default=None, max_length=128)
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
                "status",
                "error_type",
            }:
                raise ValueError(f"Agent attempted to update unsupported field: {field_name}")
            setattr(self, field_name, value)

    def set_status(self, status: Status, error_type: str | None = None) -> None:
        """Transition the career state machine."""
        self.status = status
        self.error_type = error_type
