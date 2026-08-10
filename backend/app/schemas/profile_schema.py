"""Pydantic schemas for the frozen A02 ProfileAgent output contract."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NonEmptyText = Annotated[str, Field(min_length=1, max_length=200)]
EducationLevel = Literal["专科", "本科", "硕士", "博士"]

_ABILITY_TAGS_FILE = Path(__file__).resolve().parents[1] / "data" / "ability_tags.json"
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


class ProfileSchemaModel(BaseModel):
    """Strict base model shared by the nested profile contract models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@lru_cache(maxsize=1)
def active_ability_tags() -> frozenset[str]:
    """Load the authoritative, add-only ability tag dictionary."""

    with _ABILITY_TAGS_FILE.open(encoding="utf-8") as tag_file:
        records = json.load(tag_file)
    return frozenset(
        record["tag"] for record in records if not record.get("deprecated", False)
    )


class StudentBasicInfo(ProfileSchemaModel):
    """Basic information in a student career profile."""

    education_level: EducationLevel
    major: NonEmptyText
    graduation_year: int | None = Field(ge=1900, le=2200)
    target_job: NonEmptyText
    target_industry: NonEmptyText | None
    years_of_experience: float | None = Field(ge=0, le=80)


class StudentAbility(ProfileSchemaModel):
    """One evidence-backed ability from the controlled tag dictionary."""

    tag: str = Field(min_length=1, max_length=64)
    level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=500)

    @field_validator("tag")
    @classmethod
    def validate_tag(cls, value: str) -> str:
        if value not in active_ability_tags():
            raise ValueError(
                "ability tag must exist and be active in ability_tags.json"
            )
        return value

    @field_validator("evidence")
    @classmethod
    def protect_evidence_privacy(cls, value: str) -> str:
        if any(
            pattern.search(value)
            for pattern in (_EMAIL_PATTERN, _PHONE_PATTERN, _IDENTITY_PATTERN)
        ):
            raise ValueError(
                "evidence must not contain email, phone, or identity numbers"
            )
        return value


class StudentProfile(ProfileSchemaModel):
    """ProfileAgent output compatible with CareerState.student_profile.

    ``competitiveness_score`` remains required for the frozen public contract, but
    callers must populate it using deterministic weighted calculation rather than
    accepting an unconstrained score invented by an LLM.
    """

    student_id: int | None = Field(ge=1)
    name: str = Field(min_length=1, max_length=64, description="匿名化姓名")
    basic_info: StudentBasicInfo
    abilities: list[StudentAbility] = Field(min_length=3, max_length=30)
    competitiveness_score: float = Field(
        ge=0.0,
        le=100.0,
        description="综合竞争力评分；必须由确定性能力等级加权计算提供",
    )
    completeness: float = Field(ge=0.0, le=1.0)
    missing_fields: list[NonEmptyText] = Field(max_length=50)

    @model_validator(mode="after")
    def abilities_must_be_unique(self) -> "StudentProfile":
        tags = [ability.tag for ability in self.abilities]
        if len(tags) != len(set(tags)):
            raise ValueError("abilities must not contain duplicate tags")
        return self


__all__ = [
    "StudentAbility",
    "StudentBasicInfo",
    "StudentProfile",
    "active_ability_tags",
]
