"""Strict public schemas for parameterized read-only database tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import CareerGraphEdge
from .job_context_schema import JobContext
from .mcp_tool_schema import MCPToolRequest, MCPToolResult
from .student_persistence_schema import StudentProfilePersistenceResult


DataSource = Literal["postgresql", "demo_json"]


class DatabaseToolRequest(MCPToolRequest):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )


class ReadStudentProfileRequest(DatabaseToolRequest):
    student_id: int = Field(ge=1)


class SearchJobsRequest(DatabaseToolRequest):
    keyword: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=64)
    industry: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=50)


class ReadJobContextRequest(DatabaseToolRequest):
    job_id: int | None = Field(default=None, ge=1)
    normalized_title: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def require_one_reference(self) -> "ReadJobContextRequest":
        if (self.job_id is None) == (self.normalized_title is None):
            raise ValueError("provide exactly one job reference")
        return self


class ReadCareerGraphEdgesRequest(DatabaseToolRequest):
    source_type_key: str | None = Field(default=None, min_length=1, max_length=300)
    relation_type: Literal["vertical", "lateral"] | None = None
    limit: int = Field(default=100, ge=1, le=500)


class DatabaseToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DatabaseToolData(DatabaseToolModel):
    """Shared source metadata without accepting undeclared response fields."""

    model_config = ConfigDict(extra="forbid")

    data_source: DataSource
    fallback_used: bool


class ReadStudentProfileData(DatabaseToolData):
    student_profile: StudentProfilePersistenceResult


class JobSearchItem(DatabaseToolModel):
    job_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    normalized_title: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=64)
    salary_range: str | None = Field(default=None, max_length=128)
    industry: str | None = Field(default=None, max_length=255)


class SearchJobsData(DatabaseToolData):
    items: list[JobSearchItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    has_more: bool


class ReadJobContextData(DatabaseToolData):
    context: JobContext


class ReadCareerGraphEdgesData(DatabaseToolData):
    edges: list[CareerGraphEdge] = Field(max_length=500)


class ReadStudentProfileResult(MCPToolResult):
    data: ReadStudentProfileData | None = None


class SearchJobsResult(MCPToolResult):
    data: SearchJobsData | None = None


class ReadJobContextResult(MCPToolResult):
    data: ReadJobContextData | None = None


class ReadCareerGraphEdgesResult(MCPToolResult):
    data: ReadCareerGraphEdgesData | None = None


__all__ = [
    "DatabaseToolData",
    "DataSource",
    "JobSearchItem",
    "ReadCareerGraphEdgesData",
    "ReadCareerGraphEdgesRequest",
    "ReadCareerGraphEdgesResult",
    "ReadJobContextData",
    "ReadJobContextRequest",
    "ReadJobContextResult",
    "ReadStudentProfileData",
    "ReadStudentProfileRequest",
    "ReadStudentProfileResult",
    "SearchJobsData",
    "SearchJobsRequest",
    "SearchJobsResult",
]
