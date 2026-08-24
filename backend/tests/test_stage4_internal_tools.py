"""Offline integration tests for the unregistered Stage 4 internal tools."""

from __future__ import annotations

import json
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agents.feedback_agent import FeedbackAgent
from app.agents.training_agent import TrainingAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator, CareerState
from app.schemas.internal_tool_schema import (
    GenerateAndScoreTrainingRequest,
    RecommendLearningAndJobResourcesRequest,
    SaveGrowthFeedbackRequest,
)
from app.services.feedback_service import FeedbackService
from app.services.resource_service import ResourceService
from app.services.training_service import TrainingService
from app.tools.mock_tools import call_mock_tool


LONG_ANSWER = (
    "我会先同步当前进展和已经确认的事实，再说明风险、下一步与负责人，"
    "并使用异步文档记录决策和反馈期限，确保所有参与者都能追踪。"
)


class OfflineLLMClient:
    """Fail every model call while recording that no network is required."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": deepcopy(args), "kwargs": deepcopy(kwargs)})
        raise RuntimeError("simulated offline LLM")


class RecordingResourceService:
    def __init__(self) -> None:
        self.inner = ResourceService()
        self.calls: list[dict[str, Any]] = []

    def recommend_resources(
        self,
        ability_gaps: list[str],
        target_job: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "ability_gaps": deepcopy(ability_gaps),
                "target_job": target_job,
            }
        )
        return self.inner.recommend_resources(ability_gaps, target_job)


class ErrorResourceService(RecordingResourceService):
    def recommend_resources(
        self,
        ability_gaps: list[str],
        target_job: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "ability_gaps": deepcopy(ability_gaps),
                "target_job": target_job,
            }
        )
        return {"error": "forced_resource_error:private detail omitted"}


class RecordingFeedbackService:
    def __init__(self) -> None:
        self.inner = FeedbackService()
        self.calls: list[dict[str, Any]] = []

    def save_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        return self.inner.save_feedback(**kwargs)


class StageFourInternalToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"stage4-tools-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.llm = OfflineLLMClient()
        self.resource_service = RecordingResourceService()
        self.feedback_service = RecordingFeedbackService()
        self.orchestrator = CareerOrchestrator(
            agents=[
                TrainingAgent(
                    client=self.llm,
                    service=TrainingService(),
                    resource_service=self.resource_service,
                ),
                FeedbackAgent(
                    client=self.llm,
                    service=self.feedback_service,
                ),
            ],
            repository=self.repository,
        )
        self.tools = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=2,
            resource_service=self.resource_service,
        )

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)
        Path(f"{self.db_path}-shm").unlink(missing_ok=True)
        Path(f"{self.db_path}-wal").unlink(missing_ok=True)

    def _seed_state(
        self,
        session_id: str,
        *,
        include_match: bool = True,
        user_id: str = "user-stage4",
    ) -> CareerState:
        state = CareerState(
            session_id=session_id,
            user_id=user_id,
            status="PATH_COMPLETED",
            student_input={"profile_marker": "preserve-me"},
            student_profile={
                "abilities": [
                    {"tag": "数据分析", "level": 2},
                    {"tag": "Python", "level": 2},
                ]
            },
            job_profile={"title": "数据分析师"},
            match_result=(
                {
                    "overall_score": 66.5,
                    "skill_gaps": [
                        {"dimension": "数据分析", "priority": 1},
                        {"dimension": "Python", "priority": 2},
                    ],
                }
                if include_match
                else None
            ),
        )
        self.orchestrator.persist(state)
        return state

    async def _generate(
        self,
        session_id: str,
        *,
        trace_id: str,
    ):
        return await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id=session_id,
                user_id="user-stage4",
                trace_id=trace_id,
                training_type="remote_collaboration",
            )
        )

    async def test_generate_training_uses_state_gaps_and_persists_task(self) -> None:
        self._seed_state("generate-training")

        result = await self._generate(
            "generate-training",
            trace_id="trace-generate-training",
        )

        self.assertTrue(result.success)
        self.assertEqual("generate", result.data.mode)
        self.assertEqual(
            "remote_collaboration",
            result.data.training_task.type,
        )
        state = self.orchestrator.get_session("generate-training")
        self.assertEqual(
            result.data.training_task.training_id,
            state.get_training_task()["training_id"],
        )
        self.assertEqual({"profile_marker": "preserve-me"}, state.student_input)
        self.assertEqual([], self.llm.calls)

    async def test_score_training_uses_stored_task_and_service_numbers(self) -> None:
        self._seed_state("score-training")
        generated = await self._generate(
            "score-training",
            trace_id="trace-score-generate",
        )
        training_id = generated.data.training_task.training_id

        result = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id="score-training",
                user_id="user-stage4",
                trace_id="trace-score-answer",
                training_id=training_id,
                user_answer=LONG_ANSWER,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual("score", result.data.mode)
        expected = TrainingService().score(training_id, LONG_ANSWER, None)
        self.assertEqual(expected["total_score"], result.data.training_score.total_score)
        state = self.orchestrator.get_session("score-training")
        self.assertEqual(
            result.data.training_score.model_dump(mode="json"),
            state.get_latest_training_score(),
        )
        self.assertEqual({"profile_marker": "preserve-me"}, state.student_input)
        self.assertNotIn(LONG_ANSWER, json.dumps(state.model_dump(), ensure_ascii=False))

    async def test_recommend_resources_uses_ordered_state_gaps_without_llm(self) -> None:
        self._seed_state("recommend-resources")

        result = await self.tools.recommend_learning_and_job_resources(
            RecommendLearningAndJobResourcesRequest(
                session_id="recommend-resources",
                user_id="user-stage4",
                trace_id="trace-recommend-resources",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(
            ["数据分析", "Python"],
            self.resource_service.calls[-1]["ability_gaps"],
        )
        self.assertEqual("数据分析师", self.resource_service.calls[-1]["target_job"])
        self.assertEqual([], self.llm.calls)
        state = self.orchestrator.get_session("recommend-resources")
        self.assertEqual(
            result.data.resource_result.model_dump(mode="json"),
            state.resource_result,
        )

    async def test_save_feedback_returns_growth_snapshot_and_state_context(self) -> None:
        self._seed_state("save-feedback")
        await self._generate("save-feedback", trace_id="trace-feedback-generate")

        result = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id="save-feedback",
                user_id="user-stage4",
                trace_id="trace-save-feedback",
                satisfaction=4,
                training_rating=2,
                comments="希望训练建议更简洁",
            )
        )

        self.assertTrue(result.success)
        self.assertTrue(result.data.feedback_result.feedback_saved)
        self.assertEqual("stable", result.data.feedback_result.growth_snapshot.growth_trend)
        call = self.feedback_service.calls[-1]
        self.assertEqual(
            ["数据分析", "Python"],
            [item["dimension"] for item in call["skill_gaps"]],
        )
        self.assertEqual(66.5, call["overall_score"])
        self.assertIsNotNone(call["training_target_abilities"])
        state = self.orchestrator.get_session("save-feedback")
        self.assertEqual({"profile_marker": "preserve-me"}, state.student_input)
        self.assertNotIn(
            "希望训练建议更简洁",
            json.dumps(state.model_dump(), ensure_ascii=False),
        )

    async def test_missing_match_result_is_a_safe_resource_failure(self) -> None:
        self._seed_state("missing-match", include_match=False)

        result = await self.tools.recommend_learning_and_job_resources(
            RecommendLearningAndJobResourcesRequest(
                session_id="missing-match",
                user_id="user-stage4",
                trace_id="trace-missing-match",
            )
        )

        self.assertFalse(result.success)
        self.assertEqual("MATCH_RESULT_NOT_FOUND", result.error_code)
        self.assertEqual(["match_result"], result.missing_fields)
        self.assertEqual([], self.resource_service.calls)

    async def test_missing_or_invalid_training_id_does_not_run_agent(self) -> None:
        self._seed_state("missing-training")

        result = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id="missing-training",
                user_id="user-stage4",
                trace_id="trace-missing-training",
                training_id="unknown-training",
                user_answer=LONG_ANSWER,
            )
        )

        self.assertFalse(result.success)
        self.assertEqual("TRAINING_NOT_FOUND", result.error_code)
        state = self.orchestrator.get_session("missing-training")
        self.assertIsNone(state.training_plan)
        self.assertEqual([], state.agent_logs)

    async def test_invalid_user_parameters_are_rejected_before_orchestrator(self) -> None:
        self._seed_state("invalid-boundary")

        with self.assertRaises(ValidationError):
            GenerateAndScoreTrainingRequest(
                session_id="invalid-boundary",
                user_id="user-stage4",
                training_type="unsupported",
            )
        with self.assertRaises(ValidationError):
            SaveGrowthFeedbackRequest(
                session_id="invalid-boundary",
                user_id="user-stage4",
                satisfaction=6,
            )
        with self.assertRaises(ValidationError):
            RecommendLearningAndJobResourcesRequest.model_validate(
                {
                    "session_id": "invalid-boundary",
                    "user_id": "user-stage4",
                    "ability_gaps": ["caller override forbidden"],
                }
            )

        self.assertEqual(
            [],
            self.orchestrator.get_session("invalid-boundary").agent_logs,
        )

    async def test_private_user_answer_fails_without_persisting_content(self) -> None:
        self._seed_state("private-answer")
        generated = await self._generate(
            "private-answer",
            trace_id="trace-private-generate",
        )
        private_answer = "请联系 private@example.com 获取完整答案"

        result = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id="private-answer",
                user_id="user-stage4",
                trace_id="trace-private-answer",
                training_id=generated.data.training_task.training_id,
                user_answer=private_answer,
            )
        )

        self.assertFalse(result.success)
        self.assertEqual("TRAINING_FAILED", result.error_code)
        state = self.orchestrator.get_session("private-answer")
        self.assertNotIn(
            "private@example.com",
            json.dumps(state.model_dump(), ensure_ascii=False),
        )
        self.assertNotIn("private@example.com", result.message)

    async def test_private_comments_fail_without_persisting_content(self) -> None:
        self._seed_state("private-comments")

        result = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id="private-comments",
                user_id="user-stage4",
                trace_id="trace-private-comments",
                satisfaction=4,
                comments="请联系 private@example.com",
            )
        )

        self.assertFalse(result.success)
        self.assertEqual("FEEDBACK_FAILED", result.error_code)
        state = self.orchestrator.get_session("private-comments")
        self.assertIsNone(state.feedback_result)
        self.assertNotIn(
            "private@example.com",
            json.dumps(state.model_dump(), ensure_ascii=False),
        )

    async def test_llm_failures_do_not_block_score_or_feedback(self) -> None:
        self._seed_state("offline-llm")
        generated = await self._generate(
            "offline-llm",
            trace_id="trace-offline-generate",
        )
        score = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id="offline-llm",
                user_id="user-stage4",
                trace_id="trace-offline-score",
                training_id=generated.data.training_task.training_id,
                user_answer=LONG_ANSWER,
            )
        )
        feedback = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id="offline-llm",
                user_id="user-stage4",
                trace_id="trace-offline-feedback",
                satisfaction=5,
            )
        )

        self.assertTrue(score.success)
        self.assertTrue(feedback.success)
        self.assertGreaterEqual(len(self.llm.calls), 3)

    async def test_resource_service_error_returns_safe_envelope(self) -> None:
        self._seed_state("resource-error")
        failing_tools = CareerMCPToolService(
            self.orchestrator,
            timeout_seconds=2,
            resource_service=ErrorResourceService(),
        )

        result = await failing_tools.recommend_learning_and_job_resources(
            RecommendLearningAndJobResourcesRequest(
                session_id="resource-error",
                user_id="user-stage4",
                trace_id="trace-resource-error",
            )
        )

        self.assertFalse(result.success)
        self.assertEqual("RESOURCE_SERVICE_ERROR", result.error_code)
        self.assertIsNone(self.orchestrator.get_session("resource-error").resource_result)
        self.assertNotIn("private detail", result.message)

    async def test_sessions_do_not_share_training_or_feedback(self) -> None:
        self._seed_state("session-a")
        self._seed_state("session-b")
        generated = await self._generate("session-a", trace_id="trace-session-a")

        cross_score = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id="session-b",
                user_id="user-stage4",
                trace_id="trace-session-b-score",
                training_id=generated.data.training_task.training_id,
                user_answer=LONG_ANSWER,
            )
        )
        feedback = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id="session-a",
                user_id="user-stage4",
                trace_id="trace-session-a-feedback",
                satisfaction=4,
            )
        )

        self.assertFalse(cross_score.success)
        self.assertTrue(feedback.success)
        self.assertIsNone(self.orchestrator.get_session("session-b").training_plan)
        self.assertIsNone(self.orchestrator.get_session("session-b").feedback_result)

    async def test_real_internal_feedback_is_distinct_from_explicit_mock(self) -> None:
        self._seed_state("real-vs-mock")
        mock_result = call_mock_tool(
            "save_growth_feedback",
            {
                "session_id": "mock-session",
                "user_id": "mock-user",
                "satisfaction": 4,
            },
        )

        real_result = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id="real-vs-mock",
                user_id="user-stage4",
                trace_id="trace-real-feedback",
                satisfaction=4,
            )
        )

        self.assertTrue(mock_result["data"]["demo_mode"])
        self.assertFalse(mock_result["data"]["feedback_saved"])
        self.assertTrue(real_result.success)
        self.assertTrue(real_result.data.feedback_result.feedback_saved)

    async def test_trace_replay_is_idempotent_and_does_not_rerun_agent(self) -> None:
        self._seed_state("training-replay")
        request = GenerateAndScoreTrainingRequest(
            session_id="training-replay",
            user_id="user-stage4",
            trace_id="trace-training-replay",
            training_type="remote_collaboration",
        )

        first = await self.tools.generate_and_score_training(request)
        replay = await self.tools.generate_and_score_training(request)

        self.assertTrue(first.success)
        self.assertTrue(replay.success)
        self.assertEqual(first.data, replay.data)
        state = self.orchestrator.get_session("training-replay")
        self.assertEqual(1, len(state.agent_logs))
        record = self.repository.get_tool_call("trace-training-replay")
        self.assertEqual("succeeded", record["status"])
        self.assertEqual(
            "generate_and_score_training",
            record["tool_name"],
        )


if __name__ == "__main__":
    unittest.main()
