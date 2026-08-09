"""Mock JobAgent."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..orchestrator.career_state import CareerState


class JobAgent(BaseAgent):
    name = "JobAgent"
    required_fields = ("target_job_input",)
    output_fields = ("job_profile", "trend_result")
    tool_name = "mock_analyze_job_and_trend"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        target = state.target_job_input or {}
        return self._build(
            title=target.get("job_title") or "数据分析师",
            industry=target.get("industry") or "数字技术",
            job_id=target.get("job_id"),
        )

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        return self._build(title="数据分析师", industry="数字技术", job_id=None)

    @staticmethod
    def _build(title: str, industry: str, job_id: Any) -> dict[str, Any]:
        return {
            "job_profile": {
                "job_id": job_id,
                "title": title,
                "normalized_title": title,
                "industry": industry,
                "required_abilities": [
                    {"tag": "Python", "required_level": 3, "weight": 0.4, "importance": "critical"},
                    {"tag": "数据分析", "required_level": 3, "weight": 0.4, "importance": "critical"},
                    {"tag": "沟通表达", "required_level": 2, "weight": 0.2, "importance": "important"},
                ],
                "soft_skills": ["沟通表达"],
                "salary_range": None,
                "job_description": "A02 Demo Mode 固定岗位画像",
            },
            "trend_result": {
                "job_title": title,
                "industry": industry,
                "trend_summary": "Mock 趋势数据，仅用于平台联调。",
                "hot_skills": ["数据分析", "Python"],
                "rising_skills": ["大模型应用"],
                "declining_skills": [],
                "ai_risk_assessment": "medium",
                "ai_risk_detail": "重复性任务可能自动化，业务判断仍需人工完成。",
                "development_opportunities": ["AI 辅助分析"],
                "development_risks": ["工具迭代较快"],
                "data_source": "A02 Demo Mode 固定数据",
            },
        }
