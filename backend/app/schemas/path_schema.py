"""Strict schemas for deterministic career-graph path planning."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import CareerGraphEdge, CareerGraphNode
from .job_schema import JobProfile
from .match_schema import MatchResult, SkillGap
from .profile_schema import StudentProfile


PathType = Literal["direct", "robust", "extension"]
PathStatus = Literal["success", "no_reachable_path", "insufficient_data"]


class PathSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserPreferences(PathSchemaModel):
    target_industry: str | None = Field(default=None, min_length=1, max_length=200)
    target_job: str | None = Field(default=None, min_length=1, max_length=200)
    desired_city: str | None = Field(default=None, min_length=1, max_length=100)
    preferred_path_type: PathType | None = None


# Stage-3 names are aliases of the validated seed/runtime graph models.  This
# preserves the existing CareerGraphNode/Edge imports while exposing the names
# used by the path-planning contract.
CareerNode = CareerGraphNode
CareerEdge = CareerGraphEdge


class PathRequest(PathSchemaModel):
    student_profile: StudentProfile
    target_job_profile: JobProfile
    match_result: MatchResult
    user_preferences: UserPreferences = Field(default_factory=UserPreferences)
    horizon_years: Literal[3, 5]


class PathScore(PathSchemaModel):
    current_match_score: float = Field(ge=0.0, le=100.0)
    growth_value: float = Field(ge=0.0)
    transfer_cost: float = Field(ge=0.0)
    ability_gap_cost: float = Field(ge=0.0)
    base_score: float
    preference_adjustment: float
    industry_continuity: float = Field(ge=0.0, le=1.0)
    region_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_penalty: float = Field(ge=0.0)
    target_consistency: float = Field(ge=0.0, le=1.0)
    data_confidence: float = Field(ge=0.0, le=1.0)
    total_score: float


class CandidatePath(PathSchemaModel):
    path_id: str = Field(min_length=1, max_length=64)
    path_type: PathType
    nodes: list[CareerGraphNode] = Field(min_length=1)
    edges: list[CareerGraphEdge]
    target_node_key: str = Field(min_length=1)
    fallback_target: bool = False
    time_estimate_months: int = Field(ge=1)
    score: PathScore
    data_quality_flags: list[str]

    @model_validator(mode="after")
    def path_shape_is_consistent(self) -> "CandidatePath":
        if len(self.edges) != len(self.nodes) - 1:
            raise ValueError("candidate path edges must connect each adjacent node")
        for index, edge in enumerate(self.edges):
            if edge.source_key != self.nodes[index].node_key:
                raise ValueError("candidate edge source does not match node order")
            if edge.target_key != self.nodes[index + 1].node_key:
                raise ValueError("candidate edge target does not match node order")
        if self.target_node_key != self.nodes[-1].node_key:
            raise ValueError("target_node_key must equal the final path node")
        node_keys = [node.node_key for node in self.nodes]
        if len(node_keys) != len(set(node_keys)):
            raise ValueError("candidate path must be simple and contain no repeated nodes")
        return self


class CareerStage(PathSchemaModel):
    stage_index: int = Field(ge=1, le=5)
    year_label: str = Field(min_length=1, max_length=20)
    duration_months: Literal[12] = 12
    target_role: str = Field(min_length=1, max_length=200)
    target_node_key: str = Field(min_length=1, max_length=128)
    objectives: list[str] = Field(min_length=1)
    key_abilities: list[str]
    current_gaps: list[SkillGap]
    suggested_actions: list[str] = Field(min_length=1)
    completion_criteria: str = Field(min_length=1, max_length=500)
    risks: list[str]
    next_stage_condition: str = Field(min_length=1, max_length=500)


class CareerRoadmap(PathSchemaModel):
    target_job: str = Field(min_length=1, max_length=200)
    horizon_years: Literal[3, 5]
    stages: list[CareerStage]
    selected_path_id: str | None
    total_score: float | None
    path_algorithm_version: Literal["graph-search-v1"] = "graph-search-v1"

    @model_validator(mode="after")
    def stage_count_matches_horizon(self) -> "CareerRoadmap":
        if self.selected_path_id is None:
            if self.stages or self.total_score is not None:
                raise ValueError("roadmap without selected path must be empty")
        elif len(self.stages) != self.horizon_years:
            raise ValueError("roadmap must contain one stage per horizon year")
        return self


class PathResult(PathSchemaModel):
    status: PathStatus
    requested_horizon_years: Literal[3, 5]
    candidate_paths: list[CandidatePath]
    recommended_path: CandidatePath | None
    alternative_paths: list[CandidatePath]
    path_scores: dict[str, PathScore]
    three_year_roadmap: CareerRoadmap
    five_year_roadmap: CareerRoadmap
    assumptions: list[str]
    risks: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality_flags: list[str]
    calculation_version: Literal["deterministic-path-v1"]

    @model_validator(mode="after")
    def output_references_are_consistent(self) -> "PathResult":
        ids = [item.path_id for item in self.candidate_paths]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_paths must have unique path ids")
        if set(self.path_scores) != set(ids):
            raise ValueError("path_scores keys must equal candidate path ids")
        if self.recommended_path is None:
            if self.status == "success" or self.alternative_paths:
                raise ValueError("result without recommendation cannot be successful")
        else:
            if not ids or self.recommended_path.path_id != ids[0]:
                raise ValueError("recommended_path must be the first ranked candidate")
            if [item.path_id for item in self.alternative_paths] != ids[1:]:
                raise ValueError("alternative_paths must contain remaining ranked candidates")
        return self


def validate_path_result(value: dict[str, Any]) -> PathResult:
    """Small public boundary helper for callers holding plain dictionaries."""

    return PathResult.model_validate(value)


__all__ = [
    "CandidatePath",
    "CareerEdge",
    "CareerNode",
    "CareerRoadmap",
    "CareerStage",
    "PathRequest",
    "PathResult",
    "PathScore",
    "UserPreferences",
    "validate_path_result",
]
