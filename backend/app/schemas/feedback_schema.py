"""Strict Agent and tool boundaries for deterministic growth feedback."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
Rating = Annotated[int, Field(strict=True, ge=1, le=5)]
GrowthTrend = Literal["improving", "stable", "declining"]


class FeedbackSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FeedbackAgentInput(FeedbackSchemaModel):
    """Transient user feedback read by FeedbackAgent from CareerState input."""

    satisfaction: Rating
    path_rating: Rating | None = None
    training_rating: Rating | None = None
    resource_rating: Rating | None = None
    comments: str | None = Field(default=None, max_length=10_000)


class FeedbackToolInput(FeedbackAgentInput):
    """Strict future internal/platform tool parameter boundary; not registered here."""

    session_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_IDENTIFIER_PATTERN,
    )
    user_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=_IDENTIFIER_PATTERN,
    )


class PriorityUpdate(FeedbackSchemaModel):
    tag: str = Field(min_length=1, max_length=64)
    old_priority: int = Field(ge=1)
    new_priority: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class GrowthSnapshot(FeedbackSchemaModel):
    competitiveness_score: float = Field(ge=0.0, le=100.0)
    completed_trainings: int = Field(ge=0)
    completed_phases: int = Field(ge=0)
    growth_trend: GrowthTrend


class FeedbackServiceResult(FeedbackSchemaModel):
    """Validation view of the frozen Service's raw dict output."""

    feedback_saved: bool
    growth_archive_updated: bool
    updated_priorities: list[PriorityUpdate] = Field(max_length=100)
    growth_snapshot: GrowthSnapshot
    data_quality_flags: list[str] = Field(max_length=100)


class FeedbackNaturalLanguageExplanation(FeedbackSchemaModel):
    """Optional LLM wording; it cannot carry or replace business fields."""

    message: str = Field(min_length=1, max_length=300)


class FeedbackAgentResult(FeedbackServiceResult):
    natural_language_summary: str = Field(min_length=1, max_length=300)


__all__ = [
    "FeedbackAgentInput",
    "FeedbackAgentResult",
    "FeedbackNaturalLanguageExplanation",
    "FeedbackServiceResult",
    "FeedbackToolInput",
    "GrowthSnapshot",
    "GrowthTrend",
    "PriorityUpdate",
    "Rating",
]
