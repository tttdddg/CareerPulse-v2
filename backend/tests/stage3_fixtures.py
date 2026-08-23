"""Shared anonymous fixtures and test doubles for stage-3 acceptance tests."""

from __future__ import annotations

from typing import Any


class OfflineLLMClient:
    """Stable failure double proving stage 3 never needs a paid LLM."""

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated offline LLM")


def student_profile() -> dict[str, Any]:
    return {
        "user_id": "student-003",
        "basic_info": {
            "name": "演示学生C",
            "education_level": "硕士",
            "major": "统计学（演示）",
            "graduation_year": 2026,
            "target_job": "AI产品经理",
            "target_industry": "人工智能",
            "city": "上海",
            "years_of_experience": 0.5,
        },
        "ability_dimensions": [
            {
                "dimension": "专业知识",
                "tags": ["产品规划", "需求分析"],
                "level": 3,
                "confidence": 0.85,
                "evidence": ["完成匿名AI产品方案和需求拆解项目"],
                "evidence_source": "project",
            },
            {
                "dimension": "技术与工具",
                "tags": ["数据驱动决策", "大模型应用"],
                "level": 3,
                "confidence": 0.82,
                "evidence": ["完成匿名数据决策和大模型应用原型"],
                "evidence_source": "project",
            },
            {
                "dimension": "项目实践",
                "tags": ["用户研究", "项目管理"],
                "level": 2,
                "confidence": 0.75,
                "evidence": ["完成模拟用户访谈并参与项目排期"],
                "evidence_source": "project",
            },
            {
                "dimension": "沟通协作",
                "tags": ["沟通表达"],
                "level": 3,
                "confidence": 0.78,
                "evidence": ["完成匿名跨角色项目汇报"],
                "evidence_source": "project",
            },
        ],
        "ability_tags": [
            "产品规划",
            "需求分析",
            "数据驱动决策",
            "大模型应用",
            "用户研究",
            "项目管理",
            "沟通表达",
        ],
        "profile_completeness": 0.8,
        "career_competitiveness_score": 66.0,
        "missing_fields": [],
        "follow_up_questions": [],
        "summary": "匿名阶段2学生画像",
        "created_at": "2026-08-20T10:00:00+00:00",
        "updated_at": "2026-08-20T10:00:00+00:00",
    }


def job_profile(title: str = "AI产品经理") -> dict[str, Any]:
    return {
        "job_id": 91002,
        "title": title,
        "normalized_title": title,
        "industry": "人工智能",
        "required_abilities": [
            {
                "tag": "产品规划",
                "required_level": 4,
                "weight": 0.25,
                "importance": "critical",
                "evidence": "匿名JD要求独立完成产品规划",
            },
            {
                "tag": "需求分析",
                "required_level": 4,
                "weight": 0.20,
                "importance": "critical",
                "evidence": "匿名JD要求完成需求分析",
            },
            {
                "tag": "数据驱动决策",
                "required_level": 3,
                "weight": 0.15,
                "importance": "important",
                "evidence": "匿名JD要求数据驱动决策",
            },
            {
                "tag": "大模型应用",
                "required_level": 3,
                "weight": 0.15,
                "importance": "important",
                "evidence": "匿名JD要求大模型应用经验",
            },
            {
                "tag": "用户研究",
                "required_level": 3,
                "weight": 0.10,
                "importance": "important",
                "evidence": "匿名JD要求用户研究",
            },
            {
                "tag": "沟通表达",
                "required_level": 4,
                "weight": 0.10,
                "importance": "nice_to_have",
                "evidence": "匿名JD要求跨团队沟通",
            },
            {
                "tag": "项目管理",
                "required_level": 2,
                "weight": 0.05,
                "importance": "nice_to_have",
                "evidence": "匿名JD要求项目管理",
            },
        ],
        "soft_skills": ["沟通表达", "团队协作"],
        "salary_range": None,
        "job_description": "匿名演示岗位画像",
    }
