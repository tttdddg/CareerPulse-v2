"""Mock FeedbackAgent with local in-state fallback."""

from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent, MissingDependencyError
from ..orchestrator.career_state import CareerState


class FeedbackAgent(BaseAgent):
    name = "FeedbackAgent"
    output_fields = ("feedback_result",)
    tool_name = "mock_save_growth_feedback"

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        ratings = (state.student_input or {}).get("ratings") or {}
        if not any(value is not None for value in ratings.values()):
            raise MissingDependencyError("at least one rating is required")
        satisfaction = int(ratings.get("satisfaction") or 3)
        return {
            "feedback_result": self._result(
                state, satisfaction, growth_archive_updated=True
            )
        }

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        return {
            "feedback_result": self._result(
                state, 3, growth_archive_updated=False
            )
        }

    @staticmethod
    def _result(
        state: CareerState, satisfaction: int, growth_archive_updated: bool
    ) -> dict[str, Any]:
        return {
            "session_id": state.session_id,
            "satisfaction": max(1, min(satisfaction, 5)),
            "path_rating": None,
            "training_rating": None,
            "resource_rating": None,
            "comments": None,
            "updated_priorities": [],
            "growth_archive_updated": growth_archive_updated,
        }
