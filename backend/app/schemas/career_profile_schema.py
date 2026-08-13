"""Stage 3 unified request, domain, and response schemas.

These models contain validation only. Scores and other business values must be
calculated by Services before constructing the domain models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ability_dimension import AbilityDimension


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceSource(str, Enum):
    RESUME = "resume"
    FORM = "form"
    PROJECT = "project"
    ASSESSMENT = "assessment"
    JOB_DESCRIPTION = "job_description"
    KNOWLEDGE_BASE = "knowledge_base"
    USER_SUPPLEMENT = "user_supplement"
    HISTORY = "history"
    DEMO = "demo"


class StudentBasicInfo(SchemaModel):
    name: str | None = Field(default=None, max_length=64)
    education_level: str | None = Field(default=None, max_length=32)
    major: str | None = Field(default=None, max_length=200)
    graduation_year: int | None = Field(default=None, ge=1900, le=2200)
    city: str | None = Field(default=None, max_length=100)
    target_job: str | None = Field(default=None, max_length=200)
    target_industry: str | None = Field(default=None, max_length=200)
    years_of_experience: float | None = Field(default=None, ge=0, le=80)


class AbilityDimensionProfile(SchemaModel):
    dimension: AbilityDimension
    tags: list[str] = Field(default_factory=list, max_length=50)
    level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=50)
    evidence_source: EvidenceSource

    @field_validator("tags", "evidence")
    @classmethod
    def reject_blank_or_duplicate_items(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("list items must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("list items must not contain duplicates")
        return normalized


class StudentProfile(SchemaModel):
    """Unified student profile domain schema."""

    user_id: str = Field(min_length=1, max_length=128)
    basic_info: StudentBasicInfo
    ability_dimensions: list[AbilityDimensionProfile] = Field(
        default_factory=list, max_length=7
    )
    ability_tags: list[str] = Field(default_factory=list, max_length=100)
    profile_completeness: float = Field(ge=0.0, le=1.0)
    career_competitiveness_score: float = Field(ge=0.0, le=100.0)
    missing_fields: list[str] = Field(default_factory=list, max_length=100)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=30)
    summary: str = Field(min_length=1, max_length=5000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_dimensions_and_timestamps(self) -> "StudentProfile":
        dimensions = [item.dimension for item in self.ability_dimensions]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("ability_dimensions must not repeat a dimension")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        return self


class JobProfile(SchemaModel):
    """Unified job profile domain schema."""

    job_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    core_skills: list[str] = Field(default_factory=list, max_length=100)
    bonus_skills: list[str] = Field(default_factory=list, max_length=100)
    education_requirements: list[str] = Field(default_factory=list, max_length=30)
    experience_requirements: list[str] = Field(default_factory=list, max_length=30)
    key_tasks: list[str] = Field(default_factory=list, max_length=100)
    ability_dimensions: list[AbilityDimensionProfile] = Field(
        default_factory=list, max_length=7
    )
    trend_keywords: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def dimensions_must_be_unique(self) -> "JobProfile":
        dimensions = [item.dimension for item in self.ability_dimensions]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("ability_dimensions must not repeat a dimension")
        return self


class KnowledgeSource(SchemaModel):
    name: str = Field(min_length=1, max_length=200)
    reference: str | None = Field(default=None, max_length=2000)
    observed_at: datetime | None = None


class CareerTrend(SchemaModel):
    """Career trend domain schema; it records claims but does not derive them."""

    job_name: str = Field(min_length=1, max_length=200)
    trend_summary: str = Field(min_length=1, max_length=5000)
    growing_skills: list[str] = Field(default_factory=list, max_length=100)
    stable_skills: list[str] = Field(default_factory=list, max_length=100)
    declining_skills: list[str] = Field(default_factory=list, max_length=100)
    entry_opportunities: list[str] = Field(default_factory=list, max_length=100)
    risks: list[str] = Field(default_factory=list, max_length=100)
    knowledge_sources: list[KnowledgeSource] = Field(default_factory=list, max_length=50)


# Request schemas are deliberately separate from persisted/returned domain models.
class StudentProfileRequest(SchemaModel):
    user_id: str = Field(min_length=1, max_length=128)
    resume_text: str | None = Field(default=None, max_length=100_000)
    form_fields: dict[str, Any] = Field(default_factory=dict)
    target_job: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_profile_input(self) -> "StudentProfileRequest":
        if not self.resume_text and not self.form_fields:
            raise ValueError("resume_text or form_fields must be provided")
        return self


class JobProfileRequest(SchemaModel):
    job_name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    job_description: str | None = Field(default=None, max_length=100_000)


class CareerTrendRequest(SchemaModel):
    job_name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)


ResponseData = TypeVar("ResponseData")


class AgentResponse(SchemaModel, Generic[ResponseData]):
    """Unified response envelope for Agent-facing application endpoints."""

    agent_name: str = Field(min_length=1, max_length=100)
    status: str = Field(pattern="^(success|partial|failed)$")
    data: ResponseData | None = None
    summary: str = Field(min_length=1, max_length=5000)
    fallback_used: bool = False
    error: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)


__all__ = [
    "AbilityDimensionProfile",
    "AgentResponse",
    "CareerTrend",
    "CareerTrendRequest",
    "EvidenceSource",
    "JobProfile",
    "JobProfileRequest",
    "KnowledgeSource",
    "StudentBasicInfo",
    "StudentProfile",
    "StudentProfileRequest",
]
