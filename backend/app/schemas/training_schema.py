"""Strict Agent-boundary schemas for deterministic career training."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TrainingType = Literal[
    "remote_collaboration",
    "ai_office_task",
    "cross_role_communication",
]
CoverageLevel = Literal["fully", "mostly", "partial", "barely", "missing"]

_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")


def _privacy_safe(value: str) -> str:
    if any(
        pattern.search(value)
        for pattern in (_EMAIL_PATTERN, _PHONE_PATTERN, _IDENTITY_PATTERN)
    ):
        raise ValueError("training text must not contain private identity information")
    return value


class TrainingSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TrainingAgentInput(TrainingSchemaModel):
    """Transient generate/score parameters read by TrainingAgent."""

    training_type: TrainingType
    ability_gaps: list[str] = Field(default_factory=list, max_length=100)
    training_id: str | None = Field(default=None, min_length=1, max_length=128)
    user_answer: str | None = Field(default=None, max_length=100_000)

    @field_validator("ability_gaps")
    @classmethod
    def validate_gaps(cls, values: list[str]) -> list[str]:
        if any(not value for value in values):
            raise ValueError("ability_gaps must not contain blank values")
        return values

    @model_validator(mode="after")
    def score_requires_training_id(self) -> "TrainingAgentInput":
        if self.user_answer is not None and self.training_id is None:
            raise ValueError("training_id is required when user_answer is supplied")
        if self.user_answer is None and self.training_id is not None:
            raise ValueError("training_id is only accepted in score mode")
        return self

    @property
    def mode(self) -> Literal["generate", "score"]:
        return "score" if self.user_answer is not None else "generate"


class EvaluationCriterion(TrainingSchemaModel):
    dimension: str = Field(min_length=1, max_length=64)
    max_score: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    description: str = Field(min_length=1, max_length=1000)


class TrainingTask(TrainingSchemaModel):
    mode: Literal["generate"] = "generate"
    training_id: str = Field(min_length=1, max_length=128)
    type: TrainingType
    title: str = Field(min_length=1, max_length=200)
    scenario: str = Field(min_length=1, max_length=2000)
    task_description: str = Field(min_length=1, max_length=2000)
    evaluation_criteria: list[EvaluationCriterion] = Field(min_length=1, max_length=30)
    target_abilities: list[str] = Field(min_length=1, max_length=30)
    reference_answer: str | None = Field(default=None, max_length=5000)


class TrainingCoverage(TrainingSchemaModel):
    """One LLM semantic judgment. It intentionally contains no numeric field."""

    dimension: str = Field(min_length=1, max_length=64)
    coverage: CoverageLevel
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def validate_reason_privacy(cls, value: str) -> str:
        return _privacy_safe(value)


class TrainingAnalysis(TrainingSchemaModel):
    dimensions: list[TrainingCoverage] = Field(max_length=30)

    @model_validator(mode="after")
    def dimensions_are_unique(self) -> "TrainingAnalysis":
        names = [item.dimension for item in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError("training analysis dimensions must be unique")
        return self


class TrainingDimensionScore(TrainingSchemaModel):
    dimension: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0.0, le=100.0)
    comment: str = Field(min_length=1, max_length=1000)


class TrainingAbilityUpdate(TrainingSchemaModel):
    tag: str = Field(min_length=1, max_length=64)
    level_change: int = Field(ge=-1, le=1)


class TrainingScore(TrainingSchemaModel):
    mode: Literal["score"] = "score"
    training_id: str = Field(min_length=1, max_length=128)
    total_score: float = Field(ge=0.0, le=100.0)
    dimension_scores: list[TrainingDimensionScore] = Field(min_length=1, max_length=30)
    overall_comment: str = Field(min_length=1, max_length=2000)
    improvement_suggestions: list[str] = Field(max_length=30)
    ability_updates: list[TrainingAbilityUpdate] = Field(max_length=30)
    data_quality_flags: list[str] = Field(default_factory=list, max_length=100)


class TrainingNaturalLanguageFeedback(TrainingSchemaModel):
    """Optional LLM explanation of immutable TrainingService results."""

    commentary: str = Field(min_length=1, max_length=1000)
    strengths: list[str] = Field(default_factory=list, max_length=10)
    next_steps: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("commentary")
    @classmethod
    def validate_commentary_privacy(cls, value: str) -> str:
        return _privacy_safe(value)

    @field_validator("strengths", "next_steps")
    @classmethod
    def validate_feedback_items(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in normalized):
            raise ValueError("training feedback items must contain 1-500 characters")
        return [_privacy_safe(value) for value in normalized]


class TrainingPlan(TrainingSchemaModel):
    trainings: list[TrainingTask] = Field(min_length=1, max_length=10)
    generated_at: str = Field(min_length=1, max_length=64)
    latest_score: TrainingScore | None = None
    natural_language_feedback: TrainingNaturalLanguageFeedback | None = None


__all__ = [
    "CoverageLevel",
    "EvaluationCriterion",
    "TrainingAbilityUpdate",
    "TrainingAgentInput",
    "TrainingAnalysis",
    "TrainingCoverage",
    "TrainingDimensionScore",
    "TrainingNaturalLanguageFeedback",
    "TrainingPlan",
    "TrainingScore",
    "TrainingTask",
    "TrainingType",
]
