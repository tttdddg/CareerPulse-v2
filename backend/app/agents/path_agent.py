"""Deterministic Mock PathAgent."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent
from ..orchestrator.career_state import CareerState


class PathAgent(BaseAgent):
    name = "PathAgent"
    required_fields = ("student_profile", "job_profile", "match_result")
    output_fields = ("path_plan", "learning_plan")
    tool_name = "mock_recommend_career_path"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        return self._build(state)

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        return self._build(state)

    @staticmethod
    def _build(state: CareerState) -> dict[str, Any]:
        target = (state.job_profile or {}).get("title") or "目标岗位"
        gaps = [
            item.get("tag")
            for item in (state.match_result or {}).get("ability_gaps", [])
            if item.get("tag")
        ]
        score = float((state.match_result or {}).get("overall_score", 0.0))
        phases = [
            {
                "phase": 1,
                "duration_months": 6,
                "target_role": "基础能力准备",
                "required_abilities": gaps[:2],
                "tasks": ["完成基础课程", "完成一个可展示项目"],
                "milestone": "形成基础作品集",
            },
            {
                "phase": 2,
                "duration_months": 12,
                "target_role": "岗位实践",
                "required_abilities": gaps,
                "tasks": ["参加真实项目", "复盘能力差距"],
                "milestone": "能够独立完成核心任务",
            },
            {
                "phase": 3,
                "duration_months": 18,
                "target_role": target,
                "required_abilities": gaps,
                "tasks": ["完善作品集", "准备岗位面试"],
                "milestone": f"达到{target}岗位要求",
            },
        ]
        return {
            "path_plan": {
                "target_job": target,
                "plan_3year": {"phases": phases, "total_score": round(score, 2)},
                "plan_5year": {"phases": phases, "total_score": round(score, 2)},
                "alternative_paths": [],
                "path_algorithm_version": "graph-search-v1",
            },
            "learning_plan": {
                "phases": [
                    {
                        "phase": index,
                        "title": phase["target_role"],
                        "tasks": [
                            {
                                "task_id": f"mock-task-{index}",
                                "description": phase["tasks"][0],
                                "target_ability": (phase["required_abilities"] or ["通用能力"])[0],
                                "estimated_hours": 20,
                                "resources": [],
                            }
                        ],
                    }
                    for index, phase in enumerate(phases, start=1)
                ],
                "certificate_suggestions": [],
                "project_suggestions": ["完成一个可展示的岗位项目"],
            },
        }
