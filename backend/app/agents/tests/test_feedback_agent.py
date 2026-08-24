"""FeedbackAgent tests for real FeedbackService and offline LLM boundaries."""

from __future__ import annotations

import inspect
import json
import unittest
from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from app.agents.feedback_agent import FeedbackAgent, FeedbackServiceError
from app.core.llm_client import LLMValidationError
from app.orchestrator.career_state import CareerState
from app.schemas.feedback_schema import (
    FeedbackAgentInput,
    FeedbackNaturalLanguageExplanation,
    FeedbackToolInput,
)
from app.services.feedback_service import FeedbackService
from app.services.training_service import TrainingService


class QueueClient:
    """Offline structured-output client with deterministic queued responses."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_schema: type[Any],
        **kwargs: Any,
    ) -> Any:
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "response_schema": response_schema,
                "kwargs": deepcopy(kwargs),
            }
        )
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response_schema.model_validate(response)


class RecordingFeedbackService:
    """Record exact Agent parameters while executing frozen Service logic."""

    def __init__(self) -> None:
        self.inner = FeedbackService()
        self.calls: list[dict[str, Any]] = []

    def save_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return self.inner.save_feedback(**kwargs)


class ErrorFeedbackService(RecordingFeedbackService):
    def save_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return {"error": "forced_feedback_error:test"}


class FixedFeedbackService(RecordingFeedbackService):
    FIXED_RESULT = {
        "feedback_saved": True,
        "growth_archive_updated": True,
        "updated_priorities": [
            {
                "tag": "远程协作",
                "old_priority": 7,
                "new_priority": 4,
                "reason": "固定 Service 返回，Agent 不得重算。",
            }
        ],
        "growth_snapshot": {
            "competitiveness_score": 88.75,
            "completed_trainings": 6,
            "completed_phases": 4,
            "growth_trend": "declining",
        },
        "data_quality_flags": ["fixed_feedback_service"],
    }

    def save_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return deepcopy(self.FIXED_RESULT)


def explanation(message: str = "反馈已保存，后续建议已按真实结果更新。") -> dict[str, str]:
    return {"message": message}


def build_state(
    feedback: dict[str, Any] | None,
    *,
    session_id: str = "feedback-agent-test",
    user_id: str | None = "user-001",
    skill_gaps: list[dict[str, Any]] | None = None,
    include_training: bool = True,
) -> CareerState:
    latest_task = TrainingService().generate(
        "remote_collaboration",
        ["远程协作"],
    )
    later_task = TrainingService().generate(
        "ai_office_task",
        ["数据分析"],
    )
    training_plan = None
    if include_training:
        training_plan = {
            "trainings": [latest_task, later_task],
            "generated_at": "2026-08-24T00:00:00+00:00",
            "latest_score": {
                "training_id": latest_task["training_id"],
                "total_score": 80.0,
            },
        }
    student_input: dict[str, Any] = {}
    if feedback is not None:
        student_input["feedback"] = feedback
    return CareerState(
        session_id=session_id,
        user_id=user_id,
        student_input=student_input,
        student_profile={
            "abilities": [
                {"tag": "远程协作", "level": 2},
                {"tag": "沟通表达", "level": 3},
            ]
        },
        match_result={
            "overall_score": 62.5,
            "skill_gaps": skill_gaps
            if skill_gaps is not None
            else [
                {"dimension": "沟通表达", "priority": 1},
                {"dimension": "远程协作", "priority": 2},
                {"dimension": "数据分析", "priority": 3},
            ],
        },
        training_plan=training_plan,
        path_plan={"plan_3year": {"phases": [{"phase": 1}, {"phase": 2}]}},
    )


class FeedbackAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_calls_real_service_and_never_returns_mock_false(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4, "comments": "整体体验良好"})

        result = await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual("FeedbackService", result.service_name)
        self.assertEqual("save_growth_feedback", result.tool_calls[0].tool_name)
        self.assertTrue(state.feedback_result["feedback_saved"])
        self.assertTrue(state.feedback_result["growth_archive_updated"])
        self.assertIsNotNone(service.inner.get_feedback(state.session_id))
        self.assertNotIn(
            '"feedback_saved": False',
            inspect.getsource(FeedbackAgent),
        )

    async def test_all_context_parameters_come_from_current_state(self) -> None:
        service = RecordingFeedbackService()
        state = build_state(
            {
                "satisfaction": 4,
                "path_rating": 5,
                "training_rating": 2,
                "resource_rating": 3,
                "comments": "希望后续保持简洁",
            }
        )
        expected_gaps = deepcopy(state.match_result["skill_gaps"])
        expected_abilities = deepcopy(state.student_profile["abilities"])
        scored_id = state.training_plan["latest_score"]["training_id"]
        expected_targets = next(
            item["target_abilities"]
            for item in state.training_plan["trainings"]
            if item["training_id"] == scored_id
        )

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        call = service.calls[0]
        self.assertEqual(state.session_id, call["session_id"])
        self.assertEqual(state.user_id, call["user_id"])
        self.assertEqual(expected_gaps, call["skill_gaps"])
        self.assertEqual(expected_abilities, call["abilities"])
        self.assertEqual(expected_targets, call["training_target_abilities"])
        self.assertEqual(62.5, call["overall_score"])
        self.assertEqual(0, call["completed_trainings"])
        self.assertEqual(0, call["completed_phases"])

    async def test_latest_scored_task_wins_over_last_generated_task(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4})
        first, last = state.training_plan["trainings"]
        self.assertNotEqual(first["target_abilities"], last["target_abilities"])

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertEqual(
            first["target_abilities"],
            service.calls[0]["training_target_abilities"],
        )

    async def test_low_training_rating_priority_update_comes_from_service(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4, "training_rating": 2})

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        update = next(
            item
            for item in state.feedback_result["updated_priorities"]
            if item["tag"] == "远程协作"
        )
        self.assertEqual(2, update["old_priority"])
        self.assertEqual(1, update["new_priority"])
        self.assertIn("训练反馈低", update["reason"])

    async def test_high_training_rating_priority_falls_back_from_service(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 5, "training_rating": 5})

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        update = next(
            item
            for item in state.feedback_result["updated_priorities"]
            if item["tag"] == "远程协作"
        )
        self.assertEqual(2, update["old_priority"])
        self.assertEqual(3, update["new_priority"])
        self.assertIn("紧迫度下调", update["reason"])

    async def test_low_satisfaction_does_not_force_priority_change(self) -> None:
        state = build_state({"satisfaction": 2, "training_rating": 1})

        await FeedbackAgent(client=QueueClient(explanation())).run(state)

        self.assertEqual([], state.feedback_result["updated_priorities"])
        self.assertIn(
            "low_satisfaction_recorded",
            state.feedback_result["data_quality_flags"],
        )

    async def test_missing_training_rating_is_valid_and_does_not_adjust(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4})

        result = await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertEqual("success", result.status)
        self.assertIsNone(service.calls[0]["training_rating"])
        self.assertEqual([], state.feedback_result["updated_priorities"])

    async def test_no_skill_gaps_is_passed_as_none_without_invention(self) -> None:
        service = RecordingFeedbackService()
        state = build_state(
            {"satisfaction": 4, "training_rating": 2},
            skill_gaps=[],
        )

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertIsNone(service.calls[0]["skill_gaps"])
        self.assertEqual([], state.feedback_result["updated_priorities"])

    async def test_no_recent_training_is_passed_as_none_without_invention(self) -> None:
        service = RecordingFeedbackService()
        state = build_state(
            {"satisfaction": 4, "training_rating": 2},
            include_training=False,
        )

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertIsNone(service.calls[0]["training_target_abilities"])
        self.assertEqual([], state.feedback_result["updated_priorities"])

    async def test_growth_and_priority_values_are_copied_from_service(self) -> None:
        service = FixedFeedbackService()
        state = build_state({"satisfaction": 4, "training_rating": 2})

        await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        for key, value in service.FIXED_RESULT.items():
            self.assertEqual(value, state.feedback_result[key])
        source = inspect.getsource(FeedbackAgent)
        self.assertNotIn("_adjust_priorities", source)
        self.assertNotIn("TREND_IMPROVING", source)
        self.assertNotIn("PRIORITY_STEP", source)

    async def test_service_error_becomes_standard_failed_result(self) -> None:
        state = build_state({"satisfaction": 4})
        result = await FeedbackAgent(
            client=QueueClient(),
            service=ErrorFeedbackService(),
        ).run(state)

        self.assertEqual("failed", result.status)
        self.assertTrue(result.fallback_used)
        self.assertIsNone(state.feedback_result)
        self.assertIn("FeedbackServiceError", result.error)

    async def test_missing_user_id_reaches_service_error(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4}, user_id=None)

        result = await FeedbackAgent(
            client=QueueClient(),
            service=service,
        ).run(state)

        self.assertEqual("failed", result.status)
        self.assertIsNone(service.calls[0]["user_id"])
        self.assertIn("FeedbackServiceError", result.error)

    async def test_missing_session_id_reaches_service_error(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4})
        # CareerState normally prevents this invalid state. Bypass that public
        # boundary only to prove FeedbackAgent does not swallow the Service error.
        state.__dict__["session_id"] = None

        with self.assertRaises(FeedbackServiceError):
            await FeedbackAgent(
                client=QueueClient(),
                service=service,
            )._execute(state)

        self.assertIsNone(service.calls[0]["session_id"])

    async def test_privacy_violation_is_finally_rejected_by_service(self) -> None:
        service = RecordingFeedbackService()
        client = QueueClient()
        state = build_state(
            {"satisfaction": 4, "comments": "请联系 demo@example.com"}
        )

        result = await FeedbackAgent(client=client, service=service).run(state)

        self.assertEqual("failed", result.status)
        self.assertIn("demo@example.com", service.calls[0]["comments"])
        self.assertEqual([], client.calls)
        self.assertIsNone(state.feedback_result)

    async def test_invalid_or_missing_satisfaction_fails_before_service_call(self) -> None:
        for value in (None, 0, 6, True, "4"):
            with self.subTest(value=value):
                service = RecordingFeedbackService()
                feedback = {} if value is None else {"satisfaction": value}
                state = build_state(feedback, session_id=f"bad-rating-{value!s}")

                result = await FeedbackAgent(
                    client=QueueClient(),
                    service=service,
                ).run(state)

                self.assertEqual("failed", result.status)
                self.assertEqual([], service.calls)
                self.assertIsNone(state.feedback_result)

    def test_tool_schema_requires_session_user_and_valid_satisfaction(self) -> None:
        valid = {
            "session_id": "schema-session",
            "user_id": "schema-user",
            "satisfaction": 4,
        }
        FeedbackToolInput.model_validate(valid)
        for invalid in (
            {"user_id": "schema-user", "satisfaction": 4},
            {"session_id": "schema-session", "satisfaction": 4},
            {**valid, "satisfaction": 0},
            {**valid, "satisfaction": True},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    FeedbackToolInput.model_validate(invalid)

    async def test_llm_explanation_failure_does_not_affect_real_save(self) -> None:
        service = RecordingFeedbackService()
        state = build_state({"satisfaction": 4, "training_rating": 2})

        result = await FeedbackAgent(
            client=QueueClient(LLMValidationError("offline failure")),
            service=service,
        ).run(state)

        self.assertEqual("success", result.status)
        self.assertTrue(state.feedback_result["feedback_saved"])
        self.assertIsNotNone(service.inner.get_feedback(state.session_id))
        self.assertEqual(
            "反馈已保存，成长档案已更新。",
            state.feedback_result["natural_language_summary"],
        )

    async def test_comments_are_not_sent_to_llm_or_agent_logs(self) -> None:
        private_comment = "这是一段只应交给 Service 的匿名反馈正文"
        client = QueueClient(explanation())
        state = build_state({"satisfaction": 4, "comments": private_comment})

        await FeedbackAgent(client=client).run(state)

        llm_payload = json.dumps(client.calls, ensure_ascii=False, default=str)
        logs = json.dumps(
            [item.model_dump(mode="json") for item in state.agent_logs],
            ensure_ascii=False,
        )
        self.assertNotIn(private_comment, llm_payload)
        self.assertNotIn(private_comment, logs)
        self.assertIs(client.calls[0]["response_schema"], FeedbackNaturalLanguageExplanation)

    async def test_legacy_ratings_input_is_still_supported(self) -> None:
        service = RecordingFeedbackService()
        state = build_state(None)
        state.student_input = {"ratings": {"satisfaction": 5, "path_rating": 4}}

        result = await FeedbackAgent(
            client=QueueClient(explanation()),
            service=service,
        ).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(5, service.calls[0]["satisfaction"])
        self.assertEqual(4, service.calls[0]["path_rating"])

    def test_agent_input_schema_allows_missing_optional_ratings(self) -> None:
        parsed = FeedbackAgentInput.model_validate({"satisfaction": 3})
        self.assertIsNone(parsed.path_rating)
        self.assertIsNone(parsed.training_rating)
        self.assertIsNone(parsed.resource_rating)


if __name__ == "__main__":
    unittest.main()
