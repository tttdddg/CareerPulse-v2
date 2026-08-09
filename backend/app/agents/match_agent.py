"""Deterministic Mock MatchAgent; no LLM produces scores."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..orchestrator.career_state import CareerState


class MatchAgent(BaseAgent):
    name = "MatchAgent"
    required_fields = ("student_profile", "job_profile")
    output_fields = ("match_result",)
    tool_name = "mock_calculate_job_match"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        return {"match_result": self._calculate(state)}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        return {"match_result": self._default_result()}

    @staticmethod
    def _calculate(state: CareerState) -> dict[str, Any]:
        student = state.student_profile or {}
        job = state.job_profile or {}
        levels = {
            item["tag"]: int(item.get("level", 1))
            for item in student.get("abilities", [])
            if item.get("tag")
        }
        requirements = job.get("required_abilities") or []
        if not requirements:
            raise ValueError("job_profile.required_abilities is empty")

        weighted_score = 0.0
        ability_gaps: list[dict[str, Any]] = []
        strengths: list[str] = []
        for item in requirements:
            tag = str(item["tag"])
            current = levels.get(tag, 0)
            required = max(1, int(item.get("required_level", 1)))
            weight = float(item.get("weight", 0))
            weighted_score += min(current / required, 1.0) * weight * 100
            gap = max(required - current, 0)
            if gap:
                ability_gaps.append(
                    {
                        "tag": tag,
                        "current_level": current,
                        "required_level": required,
                        "gap": gap,
                        "priority": 0,
                    }
                )
            else:
                strengths.append(tag)

        ability_gaps.sort(key=lambda item: (-item["gap"], item["tag"]))
        for priority, item in enumerate(ability_gaps, start=1):
            item["priority"] = priority

        overall = round(max(0.0, min(weighted_score, 100.0)), 2)
        dimension = {
            "name": "岗位核心能力",
            "student_score": overall,
            "job_required": 100.0,
            "gap": round(overall - 100.0, 2),
            "weight": 1.0,
        }
        gap_analysis = [
            {
                "item": item["tag"],
                "status": "missing" if item["current_level"] == 0 else "insufficient",
                "suggestion": f"建议补充{item['tag']}的实践项目",
            }
            for item in ability_gaps
        ]
        return {
            "overall_score": overall,
            "dimensions": [dimension],
            "ability_gaps": ability_gaps,
            "gap_analysis": gap_analysis,
            "strengths": strengths,
            "matching_algorithm_version": "deterministic-v1",
        }

    @staticmethod
    def _default_result() -> dict[str, Any]:
        return {
            "overall_score": 0.0,
            "dimensions": [],
            "ability_gaps": [],
            "gap_analysis": [],
            "strengths": [],
            "matching_algorithm_version": "deterministic-v1",
        }
