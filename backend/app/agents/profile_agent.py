"""Mock ProfileAgent."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..orchestrator.career_state import CareerState


class ProfileAgent(BaseAgent):
    name = "ProfileAgent"
    required_fields = ("student_input",)
    output_fields = ("student_profile",)
    tool_name = "mock_analyze_student_profile"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        source = state.student_input or {}
        form = source.get("form_fields") or {}
        target = state.target_job_input or {}
        target_job = target.get("job_title") or form.get("target_job") or "待确认岗位"
        profile = self._profile(target_job=target_job, form=form)
        return {"student_profile": profile}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        target = state.target_job_input or {}
        return {
            "student_profile": self._profile(
                target_job=target.get("job_title") or "待确认岗位", form={}
            )
        }

    @staticmethod
    def _profile(target_job: str, form: dict[str, Any]) -> dict[str, Any]:
        return {
            "student_id": None,
            "name": "匿名用户",
            "basic_info": {
                "education_level": form.get("education_level") or "本科",
                "major": form.get("major") or "待补充",
                "graduation_year": form.get("graduation_year"),
                "target_job": target_job,
                "target_industry": form.get("target_industry"),
                "years_of_experience": None,
            },
            "abilities": [
                {"tag": "Python", "level": 2, "confidence": 0.5, "evidence": "Mock 规则标签"},
                {"tag": "数据分析", "level": 2, "confidence": 0.5, "evidence": "Mock 规则标签"},
                {"tag": "沟通表达", "level": 2, "confidence": 0.5, "evidence": "Mock 规则标签"},
            ],
            "competitiveness_score": 50.0,
            "completeness": 0.6,
            "missing_fields": [],
        }
