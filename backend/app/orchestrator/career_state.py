"""Shared state model for the A02 Agent workflow."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    student_profile_id: int | None = Field(default=None, ge=1)
    student_profile_snapshot_id: int | None = Field(default=None, ge=1)
    student_profile_updated_at: datetime | None = None
    target_job_input: dict[str, Any] | None = None
    job_record_id: int | None = Field(default=None, ge=1)
    job_type_key: str | None = Field(default=None, max_length=300)
    job_profile_snapshot_id: int | None = Field(default=None, ge=1)
    job_profile_snapshot_type_key: str | None = Field(default=None, max_length=300)
    job_data_source: Literal["session", "postgresql", "demo_json"] | None = None
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

    @field_validator(
        "training_plan",
        "resource_result",
        "feedback_result",
        mode="before",
    )
    @classmethod
    def copy_stage4_state(cls, value: Any) -> Any:
        """Keep mutable Stage 4 results owned by one CareerState instance."""

        return deepcopy(value)

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
            setattr(self, field_name, deepcopy(value))

    def get_skill_gaps(self) -> list[dict[str, Any]] | None:
        """Return an isolated view of the latest deterministic match gaps."""

        gaps = (self.match_result or {}).get("skill_gaps")
        if not isinstance(gaps, list) or not gaps:
            return None
        return deepcopy(gaps)

    def get_training_task(
        self,
        training_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Resolve an exact task, or the task belonging to the latest context."""

        plan = self.training_plan or {}
        trainings = plan.get("trainings")
        if not isinstance(trainings, list) or not trainings:
            return None

        selected_id = training_id
        if selected_id is None:
            latest_score = plan.get("latest_score")
            if isinstance(latest_score, Mapping):
                candidate = latest_score.get("training_id")
                if isinstance(candidate, str) and candidate:
                    selected_id = candidate

        if selected_id is not None:
            for item in trainings:
                if isinstance(item, Mapping) and item.get("training_id") == selected_id:
                    return deepcopy(dict(item))
            if training_id is not None:
                return None

        for item in reversed(trainings):
            if isinstance(item, Mapping):
                return deepcopy(dict(item))
        return None

    def get_latest_training_score(self) -> dict[str, Any] | None:
        """Return the last deterministic TrainingService score, if available."""

        score = (self.training_plan or {}).get("latest_score")
        if not isinstance(score, Mapping):
            return None
        return deepcopy(dict(score))

    def get_latest_ability_updates(self) -> list[dict[str, Any]]:
        """Project ability updates from the latest score without storing a copy."""

        score = self.get_latest_training_score()
        updates = (score or {}).get("ability_updates")
        if not isinstance(updates, list):
            return []
        return deepcopy(updates)

    def get_latest_training_target_abilities(self) -> list[str] | None:
        """Return targets from the task associated with the latest context."""

        task = self.get_training_task()
        targets = (task or {}).get("target_abilities")
        if not isinstance(targets, list) or not targets:
            return None
        return deepcopy(targets)

    def get_match_overall_score(self) -> float | None:
        """Return the latest deterministic match score without recomputation."""

        score = (self.match_result or {}).get("overall_score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None
        return float(score)

    def get_growth_snapshot(self) -> dict[str, Any] | None:
        """Project the growth snapshot from the latest feedback result."""

        snapshot = (self.feedback_result or {}).get("growth_snapshot")
        if not isinstance(snapshot, Mapping):
            return None
        return deepcopy(dict(snapshot))

    def set_status(self, status: Status, error_type: str | None = None) -> None:
        """Transition the career state machine."""
        self.status = status
        self.error_type = error_type
