"""Strict Stage 4 boundaries shared by internal and MCP tool adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from .feedback_schema import FeedbackAgentResult, Rating
from .mcp_tool_schema import MCPModel, MCPToolRequest, MCPToolResult
from .training_schema import TrainingScore, TrainingTask, TrainingType


class StageFourInternalModel(MCPModel):
    """Keep the same strict model behavior as the mature Stage 3 tools."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GenerateAndScoreTrainingRequest(MCPToolRequest):
    """User-supplied training parameters; State supplies every business context."""

    training_type: TrainingType | None = None
    training_id: str | None = Field(default=None, min_length=1, max_length=128)
    user_answer: str | None = Field(default=None, min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def validate_mode(self) -> "GenerateAndScoreTrainingRequest":
        if self.user_answer is None:
            if self.training_type is None:
                raise ValueError("training_type is required in generate mode")
            if self.training_id is not None:
                raise ValueError("training_id is only accepted in score mode")
        elif self.training_id is None:
            raise ValueError("training_id is required in score mode")
        return self

    @property
    def mode(self) -> Literal["generate", "score"]:
        return "score" if self.user_answer is not None else "generate"


class RecommendLearningAndJobResourcesRequest(MCPToolRequest):
    """State-only resource context; callers cannot override gaps or target job."""


class SaveGrowthFeedbackRequest(MCPToolRequest):
    """Only feedback authored by the user is exposed at the tool boundary."""

    satisfaction: Rating
    path_rating: Rating | None = None
    training_rating: Rating | None = None
    resource_rating: Rating | None = None
    comments: str | None = Field(default=None, max_length=10_000)


class ResourceRecommendation(StageFourInternalModel):
    """Validation view of the frozen ResourceService raw dict."""

    learning_resources: list[dict[str, Any]] = Field(max_length=10)
    job_resources: list[dict[str, Any]] = Field(max_length=100)
    certificate_suggestions: list[str] = Field(max_length=100)
    data_quality_flags: list[str] = Field(max_length=100)


class GenerateAndScoreTrainingData(StageFourInternalModel):
    tool_name: Literal["generate_and_score_training"] = (
        "generate_and_score_training"
    )
    agent_run_id: str = Field(min_length=1, max_length=256)
    mode: Literal["generate", "score"]
    training_task: TrainingTask | None = None
    training_score: TrainingScore | None = None

    @model_validator(mode="after")
    def payload_matches_mode(self) -> "GenerateAndScoreTrainingData":
        if self.mode == "generate":
            if self.training_task is None or self.training_score is not None:
                raise ValueError("generate mode must return only training_task")
        elif self.training_score is None or self.training_task is not None:
            raise ValueError("score mode must return only training_score")
        return self


class RecommendLearningAndJobResourcesData(StageFourInternalModel):
    tool_name: Literal["recommend_learning_and_job_resources"] = (
        "recommend_learning_and_job_resources"
    )
    service_name: Literal["ResourceService"] = "ResourceService"
    resource_result: ResourceRecommendation


class SaveGrowthFeedbackData(StageFourInternalModel):
    tool_name: Literal["save_growth_feedback"] = "save_growth_feedback"
    agent_run_id: str = Field(min_length=1, max_length=256)
    feedback_result: FeedbackAgentResult


class GenerateAndScoreTrainingResult(MCPToolResult):
    data: GenerateAndScoreTrainingData | None = None


class RecommendLearningAndJobResourcesResult(MCPToolResult):
    data: RecommendLearningAndJobResourcesData | None = None


class SaveGrowthFeedbackResult(MCPToolResult):
    data: SaveGrowthFeedbackData | None = None


__all__ = [
    "GenerateAndScoreTrainingData",
    "GenerateAndScoreTrainingRequest",
    "GenerateAndScoreTrainingResult",
    "RecommendLearningAndJobResourcesData",
    "RecommendLearningAndJobResourcesRequest",
    "RecommendLearningAndJobResourcesResult",
    "ResourceRecommendation",
    "SaveGrowthFeedbackData",
    "SaveGrowthFeedbackRequest",
    "SaveGrowthFeedbackResult",
]
