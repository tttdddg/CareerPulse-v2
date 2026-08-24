"""Real FeedbackAgent backed by deterministic FeedbackService outputs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent
from ..core.llm_client import llm_client
from ..orchestrator.career_state import CareerState
from ..schemas.feedback_schema import (
    FeedbackAgentInput,
    FeedbackAgentResult,
    FeedbackNaturalLanguageExplanation,
    FeedbackServiceResult,
)
from ..services.feedback_service import FeedbackService


_PROMPT_FILE = (
    Path(__file__).resolve().parents[3]
    / "prompts"
    / "feedback_agent"
    / "explain.txt"
)
_FEEDBACK_INPUT_FIELDS = (
    "satisfaction",
    "path_rating",
    "training_rating",
    "resource_rating",
    "comments",
)


class FeedbackServiceError(RuntimeError):
    """A fail-safe error returned by the frozen FeedbackService."""


class FeedbackAgent(BaseAgent):
    """Project real state context into FeedbackService without recalculation."""

    name = "FeedbackAgent"
    service_name = "FeedbackService"
    output_fields = ("feedback_result",)
    tool_name = "save_growth_feedback"

    def __init__(
        self,
        client: Any | None = None,
        service: FeedbackService | None = None,
    ) -> None:
        self._llm_client = client if client is not None else llm_client
        self._service = service or FeedbackService()

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        request = self._request_from_state(state)
        raw_result = self._service.save_feedback(
            session_id=state.session_id,
            user_id=state.user_id,
            satisfaction=request.satisfaction,
            path_rating=request.path_rating,
            training_rating=request.training_rating,
            resource_rating=request.resource_rating,
            comments=request.comments,
            skill_gaps=self._state_skill_gaps(state),
            abilities=self._state_abilities(state),
            completed_trainings=0,
            completed_phases=0,
            training_target_abilities=self._latest_training_target_abilities(state),
            overall_score=self._state_overall_score(state),
        )
        result = self._validated_service_result(raw_result)
        explanation = await self._explain_result(result)
        enriched = {
            **result,
            "natural_language_summary": explanation.message,
        }
        validated = FeedbackAgentResult.model_validate(enriched)
        return {"feedback_result": validated.model_dump(mode="json")}

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        # Never claim that feedback was saved or invent neutral ratings after an
        # input/Service failure.
        return {}

    async def _explain_result(
        self,
        result: dict[str, Any],
    ) -> FeedbackNaturalLanguageExplanation:
        try:
            response = await self._llm_client.generate_structured(
                self._explanation_messages(result),
                FeedbackNaturalLanguageExplanation,
                temperature=0.1,
            )
            return (
                response
                if isinstance(response, FeedbackNaturalLanguageExplanation)
                else FeedbackNaturalLanguageExplanation.model_validate(response)
            )
        except Exception:
            return FeedbackNaturalLanguageExplanation(
                message="反馈已保存，成长档案已更新。"
            )

    def _explanation_messages(
        self,
        result: dict[str, Any],
    ) -> list[dict[str, str]]:
        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        safe_payload = payload.replace("<", "&lt;").replace(">", "&gt;")
        return [
            {"role": "system", "content": self._explanation_prompt()},
            {
                "role": "user",
                "content": f"<feedback_service_result>{safe_payload}</feedback_service_result>",
            },
        ]

    @staticmethod
    @lru_cache(maxsize=1)
    def _explanation_prompt() -> str:
        try:
            prompt = _PROMPT_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("FeedbackAgent prompt could not be loaded") from exc
        if not prompt.strip():
            raise RuntimeError("FeedbackAgent prompt must not be empty")
        return prompt

    @staticmethod
    def _request_from_state(state: CareerState) -> FeedbackAgentInput:
        source = state.student_input or {}
        nested = source.get("feedback")
        if nested is None:
            nested = source.get("ratings")
        if nested is not None and not isinstance(nested, Mapping):
            raise ValueError("student_input feedback must be an object")
        candidate = (
            dict(nested)
            if isinstance(nested, Mapping)
            else {
                name: source[name]
                for name in _FEEDBACK_INPUT_FIELDS
                if name in source
            }
        )
        return FeedbackAgentInput.model_validate(candidate)

    @staticmethod
    def _state_skill_gaps(state: CareerState) -> list[dict[str, Any]] | None:
        return state.get_skill_gaps()

    @staticmethod
    def _state_abilities(state: CareerState) -> list[dict[str, Any]] | None:
        profile = state.student_profile or {}
        abilities = profile.get("abilities")
        if isinstance(abilities, list) and abilities:
            return deepcopy(abilities)
        dimensions = profile.get("ability_dimensions")
        if isinstance(dimensions, list) and dimensions:
            return deepcopy(dimensions)
        return None

    @staticmethod
    def _latest_training_target_abilities(
        state: CareerState,
    ) -> list[str] | None:
        return state.get_latest_training_target_abilities()

    @staticmethod
    def _state_overall_score(state: CareerState) -> float | None:
        return state.get_match_overall_score()

    @staticmethod
    def _validated_service_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, Mapping):
            raise FeedbackServiceError("invalid_feedback_result")
        if isinstance(result.get("error"), str):
            code = result["error"].split(":", 1)[0]
            raise FeedbackServiceError(code)
        FeedbackServiceResult.model_validate(result)
        return deepcopy(dict(result))

    def _input_summary(self, state: CareerState) -> str:
        try:
            request = self._request_from_state(state)
        except Exception:
            return "反馈请求=无效; comments内容已省略"
        return (
            f"用户ID={'已提供' if state.user_id else '未提供'}; "
            f"满意度=已提供; 路径评分={'已提供' if request.path_rating is not None else '未提供'}; "
            f"训练评分={'已提供' if request.training_rating is not None else '未提供'}; "
            f"资源评分={'已提供' if request.resource_rating is not None else '未提供'}; "
            f"comments={'已提供' if request.comments is not None else '未提供'}; "
            f"能力缺口数={len(self._state_skill_gaps(state) or [])}"
        )


__all__ = ["FeedbackAgent", "FeedbackServiceError"]
