"""Strict persistence and context schemas for PostgreSQL job data."""

from __future__ import annotations

import json
from datetime import datetime
from math import isclose
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .job_schema import JobProfile
from .profile_schema import active_ability_tags


class JobContextModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )


class JobSkillRequirement(JobContextModel):
    tag: str = Field(min_length=1, max_length=64)
    required_level: int = Field(ge=1, le=5)
    weight: float = Field(gt=0.0, le=1.0)
    importance: Literal["critical", "important", "nice_to_have"]

    @field_validator("tag")
    @classmethod
    def validate_active_tag(cls, value: str) -> str:
        if value not in active_ability_tags():
            raise ValueError("job skill tag is not active")
        return value


class JobCleanRecord(JobContextModel):
    job_id: int = Field(ge=1)
    job_title: str = Field(min_length=1, max_length=255)
    normalized_job_title: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=64)
    salary_range: str | None = Field(default=None, max_length=128)
    company_name: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    job_description: str | None = None
    updated_at: datetime | None = None


class JobTypeProfileRecord(JobContextModel):
    type_key: str = Field(min_length=1, max_length=300)
    industry: str | None = Field(default=None, max_length=255)
    sample_size: int = Field(ge=0)
    salary_desc_p50: str | None = Field(default=None, max_length=128)
    exemplar_job_id: int | None = Field(default=None, ge=1)
    profile_summary: str | None = None
    level_range: Literal["entry", "junior", "mid", "senior", "lead"] | None = None
    updated_at: datetime | None = None
    skill_requirements: list[JobSkillRequirement] = Field(min_length=1, max_length=30)

    @field_validator("skill_requirements", mode="before")
    @classmethod
    def decode_skill_requirements(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                raise ValueError("invalid persisted skill requirements") from None
        return value

    @model_validator(mode="after")
    def validate_skill_vector(self) -> "JobTypeProfileRecord":
        tags = [item.tag for item in self.skill_requirements]
        if len(tags) != len(set(tags)):
            raise ValueError("job skill requirements must use unique tags")
        total = sum(item.weight for item in self.skill_requirements)
        if not isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("job skill requirement weights must sum to 1")
        return self


class JobSearchFilters(JobContextModel):
    keyword: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=64)
    industry: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=50)

    @field_validator("keyword", "city", "industry", mode="before")
    @classmethod
    def blank_filters_are_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class JobSearchPage(JobContextModel):
    items: list[JobCleanRecord]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    has_more: bool


class JobContext(JobContextModel):
    job: JobCleanRecord
    job_type: JobTypeProfileRecord
    profile: JobProfile


__all__ = [
    "JobCleanRecord",
    "JobContext",
    "JobSearchFilters",
    "JobSearchPage",
    "JobSkillRequirement",
    "JobTypeProfileRecord",
]
