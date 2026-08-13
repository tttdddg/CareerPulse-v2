"""Shared ability dimensions used by student and job profiles."""

from __future__ import annotations

from enum import Enum


class AbilityDimension(str, Enum):
    """The seven fixed A02 capability dimensions."""

    PROFESSIONAL_KNOWLEDGE = "专业知识"
    TECHNOLOGY_AND_TOOLS = "技术与工具"
    PROJECT_PRACTICE = "项目实践"
    COMMUNICATION_AND_COLLABORATION = "沟通协作"
    PROBLEM_SOLVING = "问题解决"
    LEARNING_AND_GROWTH = "学习成长"
    INDUSTRY_AWARENESS = "行业认知"


ABILITY_DIMENSIONS: tuple[AbilityDimension, ...] = tuple(AbilityDimension)

__all__ = ["ABILITY_DIMENSIONS", "AbilityDimension"]
