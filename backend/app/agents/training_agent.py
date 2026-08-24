"""Real TrainingAgent backed by deterministic TrainingService outputs."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .base_agent import BaseAgent, MissingDependencyError
from ..core.llm_client import llm_client
from ..orchestrator.career_state import CareerState
from ..schemas.training_schema import (
    TrainingAgentInput,
    TrainingAnalysis,
    TrainingNaturalLanguageFeedback,
    TrainingPlan,
    TrainingScore,
    TrainingTask,
)
from ..services.resource_service import ResourceService
from ..services.training_service import TRAINING_TYPES, TrainingService


_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "training_agent"
_SERVICE_NUMERIC_KEY = re.compile(r"(score|total|level)", re.IGNORECASE)
_INPUT_FIELDS = ("training_type", "ability_gaps", "training_id", "user_answer")
_RESOURCE_RESULT_FIELDS = (
    "learning_resources",
    "job_resources",
    "certificate_suggestions",
    "data_quality_flags",
)


class TrainingServiceError(RuntimeError):
    """A fail-safe error returned by the frozen TrainingService."""


class ResourceServiceError(RuntimeError):
    """A fail-safe error returned by the frozen ResourceService."""


class TrainingAgent(BaseAgent):
    """Generate real tasks and delegate every training score to TrainingService."""

    name = "TrainingAgent"
    service_name = "TrainingService"
    required_fields = ("student_profile", "job_profile")
    output_fields = ("training_plan", "resource_result")
    tool_name = "generate_and_score_training"

    def __init__(
        self,
        client: Any | None = None,
        service: TrainingService | None = None,
        resource_service: ResourceService | None = None,
    ) -> None:
        self._llm_client = client if client is not None else llm_client
        self._service = service or TrainingService()
        self._resource_service = resource_service or ResourceService()

    async def _execute(self, state: CareerState) -> dict[str, Any]:
        request = self._request_from_state(state)
        if request is None:
            return {"training_plan": self._generate_all_types(state)}
        if request.mode == "generate":
            return {"training_plan": self._generate_one(request)}
        training_plan = await self._score(state, request)
        resource_result = self._recommend_resources(state)
        return {
            "training_plan": training_plan,
            "resource_result": resource_result,
        }

    async def _fallback(self, state: CareerState, error: Exception) -> dict[str, Any]:
        # TrainingService owns deterministic scoring fallback. Agent-level
        # failures must not invent a task, score, or replacement answer.
        return {}

    def _generate_one(self, request: TrainingAgentInput) -> dict[str, Any]:
        task = self._validated_task(
            self._service.generate(
                training_type=request.training_type,
                ability_gaps=request.ability_gaps,
            )
        )
        return TrainingPlan(
            trainings=[task],
            generated_at=self._timestamp(),
        ).model_dump(mode="json", exclude_none=True)

    def _generate_all_types(self, state: CareerState) -> dict[str, Any]:
        """Keep the legacy full-chain call useful without choosing a fake task."""

        ability_gaps = self._state_ability_gaps(state)
        tasks = [
            self._validated_task(
                self._service.generate(
                    training_type=training_type,
                    ability_gaps=ability_gaps,
                )
            )
            for training_type in TRAINING_TYPES
        ]
        return TrainingPlan(
            trainings=tasks,
            generated_at=self._timestamp(),
        ).model_dump(mode="json", exclude_none=True)

    def _recommend_resources(self, state: CareerState) -> dict[str, Any]:
        """Pass the real ordered match gaps to the frozen ResourceService."""

        result = self._resource_service.recommend_resources(
            ability_gaps=self._state_ability_gaps(state),
            target_job=self._state_target_job(state),
        )
        if not isinstance(result, Mapping):
            raise ResourceServiceError("invalid_resource_result")
        if isinstance(result.get("error"), str):
            code = result["error"].split(":", 1)[0]
            raise ResourceServiceError(code)
        missing = [name for name in _RESOURCE_RESULT_FIELDS if name not in result]
        if missing:
            raise ResourceServiceError("incomplete_resource_result")
        return deepcopy(dict(result))

    async def _score(
        self,
        state: CareerState,
        request: TrainingAgentInput,
    ) -> dict[str, Any]:
        task = self._find_current_task(state, request.training_id or "")
        if task is None:
            raise MissingDependencyError(
                "the requested training task is not present in training_plan"
            )

        analysis = await self._analyze_answer(task, request.user_answer or "")
        raw_score = self._service.score(
            training_id=request.training_id or "",
            user_answer=request.user_answer or "",
            agent_analysis=analysis,
        )
        self._raise_service_error(raw_score)
        score = TrainingScore.model_validate(raw_score)

        feedback = await self._explain_score(
            task,
            request.user_answer or "",
            score,
        )
        existing = TrainingPlan.model_validate(state.training_plan)
        updated = existing.model_copy(
            update={
                "latest_score": score,
                "natural_language_feedback": feedback,
            }
        )
        return TrainingPlan.model_validate(updated).model_dump(
            mode="json", exclude_none=True
        )

    async def _analyze_answer(
        self,
        task: TrainingTask,
        user_answer: str,
    ) -> dict[str, Any] | None:
        try:
            response = await self._llm_client.generate_structured(
                self._analysis_messages(task, user_answer),
                TrainingAnalysis,
                temperature=0.1,
            )
        except Exception:
            return None

        if isinstance(response, TrainingAnalysis):
            analysis = response
        else:
            try:
                analysis = TrainingAnalysis.model_validate(response)
            except (ValidationError, TypeError, ValueError):
                # A mocked or non-conforming client can bypass LLMClient schema
                # validation. Preserve numeric-contaminated signals so the frozen
                # Service rejects and flags them through its own fail-safe path.
                if isinstance(response, Mapping) and self._service_rejects_numeric(
                    response
                ):
                    return deepcopy(dict(response))
                return None

        allowed = {item.dimension for item in task.evaluation_criteria}
        if any(item.dimension not in allowed for item in analysis.dimensions):
            return None
        return analysis.model_dump(mode="json")

    async def _explain_score(
        self,
        task: TrainingTask,
        user_answer: str,
        score: TrainingScore,
    ) -> TrainingNaturalLanguageFeedback:
        try:
            response = await self._llm_client.generate_structured(
                self._feedback_messages(task, user_answer, score),
                TrainingNaturalLanguageFeedback,
                temperature=0.2,
            )
            return (
                response
                if isinstance(response, TrainingNaturalLanguageFeedback)
                else TrainingNaturalLanguageFeedback.model_validate(response)
            )
        except Exception:
            # Keep the exact Service result and reuse only its existing text.
            return TrainingNaturalLanguageFeedback(
                commentary=score.overall_comment,
                strengths=[],
                next_steps=list(score.improvement_suggestions),
            )

    def _analysis_messages(
        self,
        task: TrainingTask,
        user_answer: str,
    ) -> list[dict[str, str]]:
        score_prompt, _ = self._prompt_templates()
        payload = {
            "training_task": task.model_dump(
                mode="json", exclude={"reference_answer"}
            ),
            "user_answer": user_answer,
        }
        return self._messages(score_prompt, payload)

    def _feedback_messages(
        self,
        task: TrainingTask,
        user_answer: str,
        score: TrainingScore,
    ) -> list[dict[str, str]]:
        _, feedback_prompt = self._prompt_templates()
        payload = {
            "training_task": task.model_dump(
                mode="json", exclude={"reference_answer"}
            ),
            "user_answer": user_answer,
            "service_score": score.model_dump(mode="json"),
        }
        return self._messages(feedback_prompt, payload)

    @staticmethod
    def _messages(system_prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        safe_payload = serialized.replace("<", "&lt;").replace(">", "&gt;")
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"<training_material>{safe_payload}</training_material>",
            },
        ]

    @staticmethod
    @lru_cache(maxsize=1)
    def _prompt_templates() -> tuple[str, str]:
        try:
            score_prompt = (_PROMPT_DIR / "score.txt").read_text(encoding="utf-8")
            feedback_prompt = (_PROMPT_DIR / "feedback.txt").read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise RuntimeError("TrainingAgent prompt could not be loaded") from exc
        if not score_prompt.strip() or not feedback_prompt.strip():
            raise RuntimeError("TrainingAgent prompt must not be empty")
        return score_prompt, feedback_prompt

    def _request_from_state(self, state: CareerState) -> TrainingAgentInput | None:
        source = state.student_input or {}
        nested = source.get("training")
        if nested is not None and not isinstance(nested, Mapping):
            raise ValueError("student_input.training must be an object")
        candidate = (
            dict(nested)
            if isinstance(nested, Mapping)
            else {name: source[name] for name in _INPUT_FIELDS if name in source}
        )
        if "training_type" not in candidate:
            if candidate:
                raise ValueError("training_type is required for a training request")
            return None
        if candidate.get("ability_gaps") is None:
            candidate["ability_gaps"] = self._state_ability_gaps(state)
        return TrainingAgentInput.model_validate(candidate)

    @staticmethod
    def _state_ability_gaps(state: CareerState) -> list[str]:
        gaps: list[str] = []
        for item in state.get_skill_gaps() or []:
            if not isinstance(item, Mapping):
                continue
            dimension = item.get("dimension")
            if isinstance(dimension, str) and dimension.strip():
                gaps.append(dimension)
        return gaps

    @staticmethod
    def _state_target_job(state: CareerState) -> str | None:
        title = (state.job_profile or {}).get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        return title

    @staticmethod
    def _find_current_task(
        state: CareerState,
        training_id: str,
    ) -> TrainingTask | None:
        task = state.get_training_task(training_id)
        return TrainingTask.model_validate(task) if task is not None else None

    @staticmethod
    def _service_rejects_numeric(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, Mapping):
            return any(
                (isinstance(key, str) and _SERVICE_NUMERIC_KEY.search(key))
                or TrainingAgent._service_rejects_numeric(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(TrainingAgent._service_rejects_numeric(item) for item in value)
        if isinstance(value, str):
            return _SERVICE_NUMERIC_KEY.search(value) is not None
        return False

    @staticmethod
    def _raise_service_error(result: Any) -> None:
        if isinstance(result, Mapping) and isinstance(result.get("error"), str):
            code = result["error"].split(":", 1)[0]
            raise TrainingServiceError(code)

    def _validated_task(self, result: dict[str, Any]) -> TrainingTask:
        self._raise_service_error(result)
        return TrainingTask.model_validate(result)

    def _input_summary(self, state: CareerState) -> str:
        try:
            request = self._request_from_state(state)
        except Exception:
            return "训练请求=无效; 用户回答内容已省略"
        if request is None:
            return (
                "训练模式=兼容生成全部类型; "
                f"能力缺口数={len(self._state_ability_gaps(state))}"
            )
        return (
            f"训练模式={request.mode}; 训练类型={request.training_type}; "
            f"能力缺口数={len(request.ability_gaps)}; "
            f"训练ID={'已提供' if request.training_id else '未提供'}; "
            f"用户回答={'已提供' if request.user_answer is not None else '未提供'}"
        )


__all__ = ["ResourceServiceError", "TrainingAgent", "TrainingServiceError"]
