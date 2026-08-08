"""Mock TrainingAgent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base_agent import BaseAgent
from ..orchestrator.career_state import CareerState


class TrainingAgent(BaseAgent):
    name = "TrainingAgent"
    required_fields = ("student_profile", "job_profile")
    output_fields = ("training_plan", "resource_result")
    tool_name = "mock_generate_training"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        return self._build(state)

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        return self._build(state)

    @staticmethod
    def _build(state: CareerState) -> dict[str, Any]:
        gaps = [
            item.get("tag")
            for item in (state.match_result or {}).get("ability_gaps", [])
            if item.get("tag")
        ]
        targets = gaps[:2] or ["沟通表达"]
        return {
            "training_plan": {
                "trainings": [
                    {
                        "training_id": "mock-training-001",
                        "type": "cross_role_communication",
                        "title": "跨角色需求澄清 Mock 训练",
                        "scenario": "向协作方说明目标、约束和验收标准。",
                        "task_description": "输出一份结构化沟通方案。",
                        "evaluation_criteria": [
                            {
                                "dimension": "结构完整性",
                                "max_score": 100.0,
                                "weight": 1.0,
                                "description": "目标、约束和验收标准是否完整。",
                            }
                        ],
                        "target_abilities": targets,
                        "reference_answer": None,
                    }
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "resource_result": {
                "learning_resources": [
                    {
                        "title": "A02 Demo 学习任务",
                        "type": "practice",
                        "url": "",
                        "target_ability": targets[0],
                        "description": "Mock 资源，不代表真实平台资源。",
                    }
                ],
                "job_resources": [],
                "certificate_suggestions": [],
            },
        }
