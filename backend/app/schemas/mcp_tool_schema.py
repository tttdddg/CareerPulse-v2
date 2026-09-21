"""Strict schemas for the CareerPulse remote MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..orchestrator.career_state import Status
from .career_profile_schema import StudentProfile
from .job_schema import JobProfile, TrendResult
from .match_schema import MatchResult
from .path_schema import PathResult


_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class MCPModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StudentProfileInput(MCPModel):
    """Raw evidence accepted by the existing ProfileAgent."""

    resume_text: str | None = Field(default=None, max_length=100_000)
    form_fields: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None
    parsed_data: dict[str, Any] | None = None
    skills: list[str] | str | None = None
    education: list[Any] | dict[str, Any] | str | None = None
    projects: list[Any] | str | None = None
    internships: list[Any] | str | None = None
    work_experience: list[Any] | str | None = None
    competitions: list[Any] | str | None = None
    certificates: list[Any] | str | None = None
    supplementary_info: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def require_evidence(self) -> "StudentProfileInput":
        if not any(value not in (None, "", [], {}) for value in self.model_dump().values()):
            raise ValueError("student_input must contain profile evidence")
        return self


class TargetJobInput(MCPModel):
    """Target evidence accepted by the existing JobAgent."""

    job_id: int | None = Field(default=None, ge=1)
    type_key: str | None = Field(default=None, min_length=1, max_length=300)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    job_description: str | None = Field(default=None, max_length=100_000)
    trend_context: str | dict[str, Any] | list[Any] | None = None

    @model_validator(mode="after")
    def require_database_reference_or_job_evidence(self) -> "TargetJobInput":
        if not any(
            value not in (None, "", [], {})
            for value in (
                self.job_id,
                self.type_key,
                self.job_title,
                self.job_description,
            )
        ):
            raise ValueError(
                "target job requires job_id, type_key, title, or job description"
            )
        return self


class MCPToolRequest(MCPModel):
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    trace_id: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN
    )


class BuildStudentProfileRequest(MCPToolRequest):
    student_input: StudentProfileInput


class AnalyzeTargetJobRequest(MCPToolRequest):
    target_job_input: TargetJobInput


class AnalyzeJobMatchMCPRequest(MCPToolRequest):
    pass


class GenerateCareerPathMCPRequest(MCPToolRequest):
    pass


class BuildStudentProfileData(MCPModel):
    agent_run_id: str = Field(min_length=1, max_length=256)
    fallback_used: bool
    student_id: int | None = Field(default=None, ge=1)
    data_source: Literal["session", "postgresql", "demo_json"] = "session"
    demo_mode: bool = False
    student_profile: StudentProfile


class AnalyzeTargetJobData(MCPModel):
    agent_run_id: str = Field(min_length=1, max_length=256)
    fallback_used: bool
    job_id: int | None = Field(default=None, ge=1)
    type_key: str | None = Field(default=None, max_length=300)
    data_source: Literal["session", "postgresql", "demo_json"] = "session"
    demo_mode: bool = False
    job_profile: JobProfile
    trend_result: TrendResult


class AnalyzeJobMatchMCPData(MCPModel):
    agent_run_id: str = Field(min_length=1, max_length=256)
    match_result: MatchResult


class GenerateCareerPathMCPData(MCPModel):
    agent_run_id: str = Field(min_length=1, max_length=256)
    career_roadmap: PathResult


class MCPToolResult(MCPModel):
    success: bool
    error_code: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=500)
    missing_fields: list[str] = Field(default_factory=list, max_length=30)
    retryable: bool = False
    trace_id: str = Field(
        min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN
    )
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    status: Status
    data: Any | None = None

    @model_validator(mode="after")
    def outcome_is_consistent(self) -> "MCPToolResult":
        if self.success:
            if self.error_code is not None or self.missing_fields or self.retryable:
                raise ValueError("successful MCP result cannot contain error fields")
            if self.data is None:
                raise ValueError("successful MCP result must contain data")
        elif self.error_code is None or self.data is not None:
            raise ValueError("failed MCP result requires error_code and no data")
        return self


class BuildStudentProfileResult(MCPToolResult):
    data: BuildStudentProfileData | None = None


class AnalyzeTargetJobResult(MCPToolResult):
    data: AnalyzeTargetJobData | None = None


class AnalyzeJobMatchMCPResult(MCPToolResult):
    data: AnalyzeJobMatchMCPData | None = None


class GenerateCareerPathMCPResult(MCPToolResult):
    data: GenerateCareerPathMCPData | None = None


__all__ = [
    "AnalyzeJobMatchMCPData",
    "AnalyzeJobMatchMCPRequest",
    "AnalyzeJobMatchMCPResult",
    "AnalyzeTargetJobData",
    "AnalyzeTargetJobRequest",
    "AnalyzeTargetJobResult",
    "BuildStudentProfileData",
    "BuildStudentProfileRequest",
    "BuildStudentProfileResult",
    "GenerateCareerPathMCPData",
    "GenerateCareerPathMCPRequest",
    "GenerateCareerPathMCPResult",
    "MCPToolResult",
    "StudentProfileInput",
    "TargetJobInput",
]
