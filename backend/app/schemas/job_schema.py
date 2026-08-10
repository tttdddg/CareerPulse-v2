"""Pydantic schemas for the frozen A02 JobAgent output contracts."""

from __future__ import annotations

from math import isclose
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .profile_schema import active_ability_tags


ShortText = Annotated[str, Field(min_length=1, max_length=200)]
EvidenceText = Annotated[str, Field(min_length=1, max_length=1000)]
SummaryText = Annotated[str, Field(min_length=1, max_length=5000)]
Importance = Literal["critical", "important", "nice_to_have"]
AIRiskAssessment = Literal["low", "medium", "high"]


class JobSchemaModel(BaseModel):
    """Strict base model for JobAgent structured output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequiredJobAbility(JobSchemaModel):
    """One normalized ability required by a job description."""

    tag: str = Field(min_length=1, max_length=64)
    required_level: int = Field(ge=1, le=5)
    weight: float = Field(ge=0.0, le=1.0)
    importance: Importance
    evidence: EvidenceText | None = Field(
        default=None,
        description=(
            "An anonymized JD fact supporting this requirement; null only when "
            "the source JD is unavailable and fallback data is used."
        ),
    )

    @field_validator("tag")
    @classmethod
    def validate_standard_tag(cls, value: str) -> str:
        if value not in active_ability_tags():
            raise ValueError("ability tag must exist and be active in ability_tags.json")
        return value


class JobProfile(JobSchemaModel):
    """Normalized job requirements written to ``CareerState.job_profile``.

    The frozen contract uses ``normalized_title`` for the normalized job type and
    ``job_description`` for the natural-language job summary.
    """

    job_id: int | None = Field(default=None, ge=1)
    title: ShortText
    normalized_title: ShortText
    industry: ShortText
    required_abilities: list[RequiredJobAbility] = Field(min_length=1, max_length=30)
    soft_skills: list[str] = Field(default_factory=list, max_length=30)
    salary_range: ShortText | None = None
    job_description: SummaryText

    @field_validator("soft_skills")
    @classmethod
    def validate_soft_skills(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("soft_skills must not contain blank values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("soft_skills must not contain duplicates")
        invalid = set(normalized) - active_ability_tags()
        if invalid:
            raise ValueError("soft_skills must use active standard ability tags")
        return normalized

    @model_validator(mode="after")
    def validate_ability_vector(self) -> "JobProfile":
        tags = [ability.tag for ability in self.required_abilities]
        if len(tags) != len(set(tags)):
            raise ValueError("required_abilities must not contain duplicate tags")
        total_weight = sum(ability.weight for ability in self.required_abilities)
        if not isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("required_abilities weights must sum to 1.0")
        return self


class TrendResult(JobSchemaModel):
    """Explainable job and skill trends written to ``CareerState.trend_result``."""

    job_title: ShortText
    industry: ShortText
    trend_summary: SummaryText
    hot_skills: list[str] = Field(default_factory=list, max_length=30)
    rising_skills: list[str] = Field(default_factory=list, max_length=30)
    declining_skills: list[str] = Field(default_factory=list, max_length=30)
    ai_risk_assessment: AIRiskAssessment
    ai_risk_detail: SummaryText
    development_opportunities: list[ShortText] = Field(
        default_factory=list, max_length=30
    )
    development_risks: list[ShortText] = Field(default_factory=list, max_length=30)
    data_source: SummaryText

    @field_validator("hot_skills", "rising_skills", "declining_skills")
    @classmethod
    def validate_trend_skills(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("trend skill lists must not contain blank values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("each trend skill list must contain unique tags")
        invalid = set(normalized) - active_ability_tags()
        if invalid:
            raise ValueError("trend skills must use active standard ability tags")
        return normalized


class JobAgentOutput(JobSchemaModel):
    """One validated LLM response that maps to two independent state fields."""

    job_profile: JobProfile
    trend_result: TrendResult

    @model_validator(mode="after")
    def job_and_trend_must_refer_to_same_target(self) -> "JobAgentOutput":
        if self.job_profile.title != self.trend_result.job_title:
            raise ValueError("job_profile.title must equal trend_result.job_title")
        if self.job_profile.industry != self.trend_result.industry:
            raise ValueError("job_profile.industry must equal trend_result.industry")
        return self


__all__ = [
    "JobAgentOutput",
    "JobProfile",
    "RequiredJobAbility",
    "TrendResult",
]
