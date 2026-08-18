"""Strict schemas for deterministic job matching and ability-gap results."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from .job_schema import Importance, JobProfile
from .profile_schema import StudentProfile, active_ability_tags


MatchLevel = Literal["high", "good", "fair", "weak", "low", "insufficient_data"]
DimensionStatus = Literal["matched", "gap", "unknown", "excluded"]
ConstraintStatus = Literal["passed", "failed", "unknown"]
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def _validate_private_evidence(value: str) -> str:
    if any(
        pattern.search(value)
        for pattern in (_EMAIL_PATTERN, _PHONE_PATTERN, _IDENTITY_PATTERN)
    ):
        raise ValueError("student evidence must not contain email, phone, or identity numbers")
    return value


PrivacySafeEvidence = Annotated[
    str,
    Field(min_length=1, max_length=500),
    AfterValidator(_validate_private_evidence),
]


class MatchSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MatchRequest(MatchSchemaModel):
    student_profile: StudentProfile
    job_profile: JobProfile


class DimensionMatch(MatchSchemaModel):
    dimension: str = Field(min_length=1, max_length=64)
    student_level: int | None = Field(default=None, ge=1, le=5)
    required_level: int = Field(ge=1, le=5)
    gap: int | None = Field(default=None, ge=0, le=4)
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    student_evidence: PrivacySafeEvidence | None = None
    job_evidence: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: Importance
    status: DimensionStatus

    @model_validator(mode="after")
    def validate_unknown_and_known_states(self) -> "DimensionMatch":
        if self.dimension not in active_ability_tags():
            raise ValueError("dimension must use an active standard ability tag")
        if self.student_level is None:
            if any(value is not None for value in (self.gap, self.score, self.confidence)):
                raise ValueError("unknown student level cannot have gap, score, or confidence")
            if self.student_evidence is not None or self.status not in {"unknown", "excluded"}:
                raise ValueError("unknown student level must use unknown/excluded status and no evidence")
        elif self.status == "unknown":
            raise ValueError("known student level cannot use unknown status")
        if self.weight == 0.0 and self.status not in {"unknown", "excluded"}:
            raise ValueError("zero-weight known dimensions must use excluded status")
        return self


class SkillGap(MatchSchemaModel):
    dimension: str = Field(min_length=1, max_length=64)
    student_level: int = Field(ge=1, le=5)
    required_level: int = Field(ge=1, le=5)
    gap: int = Field(ge=1, le=4)
    score: float = Field(ge=0.0, lt=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    priority: int = Field(ge=1)
    importance: Importance
    difficulty: float = Field(ge=1.0, le=3.0)
    student_evidence: PrivacySafeEvidence | None = None
    job_evidence: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class HardConstraintResult(MatchSchemaModel):
    constraint: str = Field(min_length=1, max_length=64)
    required_level: int = Field(ge=1, le=5)
    student_level: int | None = Field(default=None, ge=1, le=5)
    status: ConstraintStatus
    passed: bool | None
    reason: str = Field(min_length=1, max_length=300)


class MatchEvidence(MatchSchemaModel):
    dimension: str = Field(min_length=1, max_length=64)
    student_evidence: PrivacySafeEvidence | None = None
    job_evidence: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class LegacyDimension(MatchSchemaModel):
    name: str
    student_score: float = Field(ge=0.0, le=100.0)
    job_required: float = Field(ge=0.0, le=100.0)
    gap: float = Field(ge=-100.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)


class LegacyAbilityGap(MatchSchemaModel):
    tag: str
    current_level: int = Field(ge=0, le=5)
    required_level: int = Field(ge=1, le=5)
    gap: int = Field(ge=1, le=5)
    priority: int = Field(ge=1)


class LegacyGapAnalysis(MatchSchemaModel):
    item: str
    status: Literal["missing", "insufficient", "adequate"]
    suggestion: str


class MatchResult(MatchSchemaModel):
    overall_score: float = Field(ge=0.0, le=100.0)
    match_level: MatchLevel
    dimension_matches: list[DimensionMatch]
    matched_skills: list[str]
    missing_skills: list[str]
    skill_gaps: list[SkillGap]
    strengths: list[str]
    hard_constraint_results: list[HardConstraintResult]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[MatchEvidence]
    calculation_version: Literal["deterministic-match-v2"]
    data_quality_flags: list[str]

    # Frozen D2 fields retained as a compatibility projection.
    dimensions: list[LegacyDimension]
    ability_gaps: list[LegacyAbilityGap]
    gap_analysis: list[LegacyGapAnalysis]
    matching_algorithm_version: Literal["deterministic-v1"]

    @model_validator(mode="after")
    def validate_consistent_dimensions(self) -> "MatchResult":
        dimensions = [item.dimension for item in self.dimension_matches]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("dimension_matches must contain unique dimensions")
        if [item.dimension for item in self.evidence] != dimensions:
            raise ValueError("evidence must align with dimension_matches order")
        if set(self.matched_skills) & set(self.missing_skills):
            raise ValueError("matched_skills and missing_skills must be disjoint")
        return self


__all__ = [
    "DimensionMatch",
    "HardConstraintResult",
    "MatchEvidence",
    "MatchRequest",
    "MatchResult",
    "SkillGap",
]
