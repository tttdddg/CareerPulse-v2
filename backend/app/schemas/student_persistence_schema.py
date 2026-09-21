"""Strict schemas for PostgreSQL student-profile persistence boundaries."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .career_profile_schema import StudentProfile as UnifiedStudentProfile
from .profile_schema import active_ability_tags


_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


class StudentPersistenceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )


class StoredStudentBasicInfo(StudentPersistenceModel):
    education_level: Literal["专科", "本科", "硕士", "博士"]
    major: str = Field(min_length=1, max_length=200)
    graduation_year: int | None = Field(default=None, ge=1900, le=2200)
    target_job: str = Field(min_length=1, max_length=200)
    target_industry: str | None = Field(default=None, max_length=200)
    years_of_experience: float | None = Field(default=None, ge=0, le=80)


class StoredStudentAbility(StudentPersistenceModel):
    tag: str = Field(min_length=1, max_length=64)
    level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=500)

    @field_validator("tag")
    @classmethod
    def validate_active_tag(cls, value: str) -> str:
        if value not in active_ability_tags():
            raise ValueError("ability tag is not active")
        return value

    @field_validator("evidence")
    @classmethod
    def reject_private_evidence(cls, value: str) -> str:
        if any(
            pattern.search(value)
            for pattern in (_EMAIL_PATTERN, _PHONE_PATTERN, _IDENTITY_PATTERN)
        ):
            raise ValueError("ability evidence contains private information")
        return value


class StudentProfileWrite(StudentPersistenceModel):
    name: str = Field(min_length=1, max_length=64)
    basic_info: StoredStudentBasicInfo
    abilities: list[StoredStudentAbility] = Field(min_length=3, max_length=30)
    competitiveness_score: float = Field(ge=0.0, le=100.0)
    completeness: float = Field(ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("missing_fields")
    @classmethod
    def validate_missing_fields(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 200 for value in normalized):
            raise ValueError("missing fields must contain 1-200 characters")
        return normalized

    @model_validator(mode="after")
    def abilities_are_unique(self) -> "StudentProfileWrite":
        tags = [ability.tag for ability in self.abilities]
        if len(tags) != len(set(tags)):
            raise ValueError("stored abilities must use unique tags")
        return self


class StudentProfileRecord(StudentProfileWrite):
    student_id: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("basic_info", "abilities", "missing_fields", mode="before")
    @classmethod
    def decode_json_columns(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                raise ValueError("invalid persisted JSON") from None
        return value

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> "StudentProfileRecord":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        return self


class StudentProfilePersistenceResult(StudentPersistenceModel):
    """Keep the display name outside the Agent-facing unified profile."""

    student_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=64)
    profile: UnifiedStudentProfile


__all__ = [
    "StoredStudentAbility",
    "StoredStudentBasicInfo",
    "StudentProfilePersistenceResult",
    "StudentProfileRecord",
    "StudentProfileWrite",
]
