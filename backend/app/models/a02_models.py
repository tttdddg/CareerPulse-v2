"""Pydantic models for validating frozen A02 seed-data contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AbilityTag(StrictModel):
    tag: str = Field(min_length=1, max_length=64)
    category: Literal[
        "hard_skill",
        "product_business",
        "soft_skill",
        "domain_knowledge",
        "certification",
    ]
    difficulty: float = Field(ge=1.0, le=3.0)
    description: str = Field(min_length=1)
    deprecated: bool = False


class StudentAbility(StrictModel):
    tag: str
    level: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1)


class StudentBasicInfo(StrictModel):
    education_level: Literal["专科", "本科", "硕士", "博士"]
    major: str
    graduation_year: int | None = None
    target_job: str
    target_industry: str | None = None
    years_of_experience: float | None = Field(default=None, ge=0)


class StudentDemo(StrictModel):
    student_id: int = Field(gt=0)
    name: str = Field(pattern=r"^演示学生[A-Z]$")
    basic_info: StudentBasicInfo
    abilities: list[StudentAbility] = Field(min_length=3, max_length=30)
    competitiveness_score: float = Field(ge=0.0, le=100.0)
    completeness: float = Field(ge=0.0, le=1.0)
    missing_fields: list[str]


class JobAbilityWeight(StrictModel):
    tag: str
    required_level: int = Field(ge=1, le=5)
    weight: float = Field(gt=0.0, le=1.0)
    importance: Literal["critical", "important", "nice_to_have"]


class JobDemo(StrictModel):
    job_id: int = Field(gt=0)
    title: str
    normalized_title: str
    industry: str
    required_abilities: list[JobAbilityWeight] = Field(min_length=1)
    soft_skills: list[str]
    salary_range: str | None = None
    job_description: str

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "JobDemo":
        total = sum(item.weight for item in self.required_abilities)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"job ability weights must sum to 1.0, got {total}")
        return self


class CareerGraphNode(StrictModel):
    node_key: str = Field(min_length=1, max_length=128)
    job_title: str
    level_range: Literal["entry", "junior", "mid", "senior", "lead"]
    industry: str | None = None
    description: str


class CareerGraphEdge(StrictModel):
    source_key: str
    target_key: str
    relation_type: Literal["vertical", "lateral"]
    reason: str
    transfer_cost: float = Field(ge=0.0)
    growth_value: float = Field(ge=0.0)
    source_industry: str | None = None
    target_industry: str | None = None


class CareerGraph(StrictModel):
    nodes: list[CareerGraphNode] = Field(min_length=10)
    edges: list[CareerGraphEdge] = Field(min_length=15)


class EvaluationCriterion(StrictModel):
    dimension: str
    max_score: float = Field(gt=0.0, le=100.0)
    weight: float = Field(gt=0.0, le=1.0)
    description: str


class TrainingTask(StrictModel):
    training_id: str
    type: Literal[
        "remote_collaboration", "ai_office_task", "cross_role_communication"
    ]
    title: str
    scenario: str
    task_description: str
    evaluation_criteria: list[EvaluationCriterion] = Field(min_length=1)
    reference_answer: str | None = None
    target_abilities: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def criteria_totals_are_valid(self) -> "TrainingTask":
        max_score = sum(item.max_score for item in self.evaluation_criteria)
        weight = sum(item.weight for item in self.evaluation_criteria)
        if abs(max_score - 100.0) > 1e-9:
            raise ValueError(f"criterion max scores must sum to 100, got {max_score}")
        if abs(weight - 1.0) > 1e-9:
            raise ValueError(f"criterion weights must sum to 1.0, got {weight}")
        return self


class LearningResource(StrictModel):
    resource_id: str
    title: str
    type: Literal["course", "book", "practice", "certificate"]
    url: str
    target_ability: str
    description: str
    demo_only: Literal[True] = True
