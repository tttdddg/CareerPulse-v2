"""Frozen HTTP tool schemas for the Ant TBox stage-3 integration."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .career_profile_schema import StudentProfile
from .job_schema import JobProfile
from .match_schema import MatchResult
from .path_schema import PathResult


_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
ToolName = Literal["analyze_job_match", "generate_career_path"]
ToolCallStatus = Literal["running", "succeeded", "failed", "timed_out"]
ToolCallId = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=_IDENTIFIER_PATTERN),
]
AgentRunId = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=_IDENTIFIER_PATTERN),
]


class PlatformSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnalyzeJobMatchRequest(PlatformSchemaModel):
    """The platform supplies validated profiles, never calculated scores."""

    schema_version: Literal["stage3-tool-v1"]
    idempotency_key: str = Field(
        min_length=8, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    platform_session_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    student_profile: StudentProfile
    job_profile: JobProfile


class GenerateCareerPathRequest(PlatformSchemaModel):
    """Reference a completed backend match; no client score is accepted."""

    schema_version: Literal["stage3-tool-v1"]
    idempotency_key: str = Field(
        min_length=8, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    session_id: str = Field(
        min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    platform_session_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )
    user_id: str | None = Field(
        default=None, max_length=128, pattern=_IDENTIFIER_PATTERN
    )


class ToolErrorDetail(PlatformSchemaModel):
    type: str = Field(min_length=1, max_length=128)
    detail: str = Field(min_length=1, max_length=500)
    retryable: bool


class AnalyzeJobMatchData(PlatformSchemaModel):
    tool_call_id: ToolCallId
    tool_name: Literal["analyze_job_match"] = "analyze_job_match"
    session_id: str
    status: Literal["succeeded"] = "succeeded"
    idempotent_replay: bool
    agent_run_id: AgentRunId
    match_result: MatchResult


class GenerateCareerPathData(PlatformSchemaModel):
    tool_call_id: ToolCallId
    tool_name: Literal["generate_career_path"] = "generate_career_path"
    session_id: str
    status: Literal["succeeded"] = "succeeded"
    idempotent_replay: bool
    agent_run_id: AgentRunId
    career_roadmap: PathResult


class AnalyzeJobMatchResponse(PlatformSchemaModel):
    code: Literal[0] = 0
    message: Literal["success"] = "success"
    request_id: ToolCallId
    data: AnalyzeJobMatchData
    error: None = None


class GenerateCareerPathResponse(PlatformSchemaModel):
    code: Literal[0] = 0
    message: Literal["success"] = "success"
    request_id: ToolCallId
    data: GenerateCareerPathData
    error: None = None


class ToolStatusData(PlatformSchemaModel):
    tool_call_id: ToolCallId
    tool_name: ToolName
    session_id: str
    status: ToolCallStatus
    result_available: bool
    agent_run_id: AgentRunId | None
    updated_at: datetime


class ToolStatusResponse(PlatformSchemaModel):
    code: Literal[0] = 0
    message: Literal["success"] = "success"
    request_id: ToolCallId
    data: ToolStatusData
    error: None = None


class ToolResultData(PlatformSchemaModel):
    tool_call_id: ToolCallId
    tool_name: ToolName
    session_id: str
    status: Literal["succeeded"] = "succeeded"
    agent_run_id: AgentRunId
    match_result: MatchResult | None = None
    career_roadmap: PathResult | None = None

    @model_validator(mode="after")
    def result_matches_tool(self) -> "ToolResultData":
        if self.tool_name == "analyze_job_match":
            if self.match_result is None or self.career_roadmap is not None:
                raise ValueError("match tool result must contain only match_result")
        elif self.career_roadmap is None or self.match_result is not None:
            raise ValueError("path tool result must contain only career_roadmap")
        return self


class ToolResultResponse(PlatformSchemaModel):
    code: Literal[0] = 0
    message: Literal["success"] = "success"
    request_id: ToolCallId
    data: ToolResultData
    error: None = None


class ToolErrorResponse(PlatformSchemaModel):
    code: int = Field(le=-1)
    message: str = Field(min_length=1, max_length=200)
    request_id: ToolCallId
    data: None = None
    error: ToolErrorDetail


__all__ = [
    "AnalyzeJobMatchData",
    "AnalyzeJobMatchRequest",
    "AnalyzeJobMatchResponse",
    "GenerateCareerPathData",
    "GenerateCareerPathRequest",
    "GenerateCareerPathResponse",
    "ToolCallStatus",
    "ToolCallId",
    "ToolErrorDetail",
    "ToolErrorResponse",
    "ToolName",
    "ToolResultData",
    "ToolResultResponse",
    "ToolStatusData",
    "ToolStatusResponse",
]
