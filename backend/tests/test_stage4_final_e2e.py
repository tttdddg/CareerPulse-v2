"""Final offline end-to-end acceptance for the Stage 4 internal chain."""

from __future__ import annotations

import json
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.agents.feedback_agent import FeedbackAgent
from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent
from app.agents.training_agent import TrainingAgent
from app.db_state import StateRepository
from app.mcp.tool_service import CareerMCPToolService
from app.orchestrator import CareerOrchestrator, CareerState
from app.schemas.career_profile_schema import StudentProfile
from app.schemas.internal_tool_schema import (
    GenerateAndScoreTrainingRequest,
    RecommendLearningAndJobResourcesRequest,
    SaveGrowthFeedbackRequest,
)
from app.services.feedback_service import (
    FLAG_FIRST_GROWTH_SNAPSHOT,
    FeedbackService,
)
from app.services.match_service import MatchService
from app.services.path_service import PathService
from app.services.resource_service import ResourceService
from app.services.training_service import TrainingService

from .stage3_fixtures import OfflineLLMClient, job_profile, student_profile


LONG_ANSWER = (
    "我会先明确事实、限制和证据口径，再列出需要协作确认的分歧。"
    "随后提出可验证的方案、负责人、截止时间和记录方式，确保结论可追踪。"
)


class StructuredStageFourLLM:
    """Offline LLM double for valid and intentionally invalid training signals."""

    def __init__(self) -> None:
        self.signal_mode = "valid"
        self.calls: list[str] = []
        self.last_analysis: dict[str, Any] | None = None

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        **kwargs: Any,
    ) -> Any:
        del kwargs
        model_name = response_model.__name__
        self.calls.append(model_name)
        if model_name == "TrainingAnalysis":
            payload = self._training_payload(messages)
            dimensions = [
                {
                    "dimension": item["dimension"],
                    "coverage": coverage,
                    "reason": "回答已覆盖该维度的关键要点。",
                }
                for item, coverage in zip(
                    payload["training_task"]["evaluation_criteria"],
                    ("fully", "mostly", "partial", "barely", "missing"),
                )
            ]
            if self.signal_mode == "invalid_coverage":
                dimensions[0]["coverage"] = "complete"
            signal: dict[str, Any] = {"dimensions": dimensions}
            if self.signal_mode == "numeric_field":
                signal["total_score"] = 99
            self.last_analysis = deepcopy(signal)
            if self.signal_mode == "valid":
                return response_model.model_validate(signal)
            return signal
        if model_name == "TrainingNaturalLanguageFeedback":
            return response_model.model_validate(
                {
                    "commentary": "评分已由确定性服务完成。",
                    "strengths": ["回答结构清晰"],
                    "next_steps": ["继续补充可验证证据"],
                }
            )
        if model_name == "FeedbackNaturalLanguageExplanation":
            return response_model.model_validate(
                {"message": "反馈已保存，成长快照已更新。"}
            )
        raise RuntimeError(f"unexpected response model: {model_name}")

    @staticmethod
    def _training_payload(messages: list[dict[str, str]]) -> dict[str, Any]:
        content = messages[-1]["content"]
        prefix = "<training_material>"
        suffix = "</training_material>"
        if not content.startswith(prefix) or not content.endswith(suffix):
            raise AssertionError("training payload wrapper is missing")
        return json.loads(content[len(prefix) : -len(suffix)])


class RecordingTrainingService:
    def __init__(self) -> None:
        self.inner = TrainingService()
        self.generate_calls: list[dict[str, Any]] = []
        self.score_calls: list[dict[str, Any]] = []

    def generate(self, training_type: str, ability_gaps: list[str]) -> dict[str, Any]:
        self.generate_calls.append(
            {"training_type": training_type, "ability_gaps": deepcopy(ability_gaps)}
        )
        return self.inner.generate(training_type, ability_gaps)

    def score(
        self,
        training_id: str,
        user_answer: str,
        agent_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.score_calls.append(
            {
                "training_id": training_id,
                "user_answer": user_answer,
                "agent_analysis": deepcopy(agent_analysis),
            }
        )
        return self.inner.score(training_id, user_answer, agent_analysis)


class RecordingResourceService:
    def __init__(self) -> None:
        self.inner = ResourceService()
        self.calls: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

    def recommend_resources(
        self,
        ability_gaps: list[str],
        target_job: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {"ability_gaps": deepcopy(ability_gaps), "target_job": target_job}
        )
        result = self.inner.recommend_resources(ability_gaps, target_job)
        self.results.append(deepcopy(result))
        return result


class RecordingFeedbackService:
    def __init__(self) -> None:
        self.inner = FeedbackService()
        self.calls: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

    def save_feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        result = self.inner.save_feedback(**kwargs)
        self.results.append(deepcopy(result))
        return result


class StageFourFinalEndToEndTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime_dir = Path(__file__).resolve().parents[1] / ".runtime" / "tests"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = runtime_dir / f"stage4-final-{uuid.uuid4().hex}.sqlite3"
        self.repository = StateRepository(sqlite_path=self.db_path)
        self.stage3_llm = OfflineLLMClient()
        self.stage4_llm = StructuredStageFourLLM()
        self.training_service = RecordingTrainingService()
        self.resource_service = RecordingResourceService()
        self.feedback_service = RecordingFeedbackService()
        self.orchestrator = CareerOrchestrator(
            agents=[
                MatchAgent(client=self.stage3_llm, service=MatchService()),
                PathAgent(client=self.stage3_llm, service=PathService()),
                TrainingAgent(
                    client=self.stage4_llm,
                    service=self.training_service,
                    resource_service=self.resource_service,
                ),
                FeedbackAgent(
                    client=self.stage4_llm,
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

    def _seed_profile_context(self, session_id: str) -> CareerState:
        profile = StudentProfile.model_validate(student_profile()).model_dump(mode="json")
        state = CareerState(
            session_id=session_id,
            user_id="user-final-e2e",
            status="PROFILE_COMPLETED",
            student_input={"profile_marker": "stage3-profile-accepted"},
            student_profile=profile,
            job_profile=job_profile(),
        )
        self.orchestrator.persist(state)
        return state

    async def _seed_real_match(self, session_id: str) -> CareerState:
        state = self._seed_profile_context(session_id)
        await self.orchestrator.run_stage(state, "MatchAgent")
        return state

    async def _generate(self, session_id: str, trace_id: str):
        return await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id=trace_id,
                training_type="ai_office_task",
            )
        )

    async def test_profile_match_path_training_resource_feedback_chain(self) -> None:
        session_id = "stage4-final-complete"
        state = self._seed_profile_context(session_id)

        await self.orchestrator.run_stage(state, "MatchAgent")
        expected_match = MatchService().calculate(
            MatchAgent._flatten_profile(student_profile()), job_profile()
        )
        self.assertEqual(expected_match, state.match_result)

        await self.orchestrator.run_stage(state, "PathAgent")
        expected_path = PathService().calculate(
            student_profile=PathAgent._flatten_profile(student_profile()),
            target_job_profile=job_profile(),
            match_result=expected_match,
            user_preferences=PathAgent._extract_preferences(student_profile()),
            horizon_years=3,
        )
        self.assertEqual(expected_path, state.career_roadmap)

        gaps = [item["dimension"] for item in expected_match["skill_gaps"]]
        generated = await self._generate(session_id, "trace-final-generate")
        self.assertTrue(generated.success)
        task = generated.data.training_task.model_dump(mode="json")
        expected_task = TrainingService().generate("ai_office_task", gaps)
        self.assertEqual(expected_task, task)
        self.assertEqual(gaps, self.training_service.generate_calls[-1]["ability_gaps"])
        self.assertTrue(set(task["target_abilities"]) & set(gaps))
        persisted = self.orchestrator.get_session(session_id)
        self.assertEqual(task, persisted.get_training_task(task["training_id"]))

        scored = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-final-score",
                training_id=task["training_id"],
                user_answer=LONG_ANSWER,
            )
        )
        self.assertTrue(scored.success)
        service_analysis = self.training_service.score_calls[-1]["agent_analysis"]
        expected_score = TrainingService().score(
            task["training_id"], LONG_ANSWER, service_analysis
        )
        actual_score = scored.data.training_score.model_dump(mode="json")
        self.assertEqual(expected_score, actual_score)
        self.assertEqual(
            expected_score["dimension_scores"], actual_score["dimension_scores"]
        )
        self.assertEqual(expected_score["total_score"], actual_score["total_score"])
        self.assertEqual(
            expected_score["ability_updates"], actual_score["ability_updates"]
        )
        persisted = self.orchestrator.get_session(session_id)
        self.assertEqual(actual_score, persisted.get_latest_training_score())

        resources = await self.tools.recommend_learning_and_job_resources(
            RecommendLearningAndJobResourcesRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-final-resources",
            )
        )
        self.assertTrue(resources.success)
        resource_result = resources.data.resource_result.model_dump(mode="json")
        expected_resources = ResourceService().recommend_resources(
            gaps, job_profile()["title"]
        )
        self.assertEqual(expected_resources, resource_result)
        self.assertEqual(gaps, self.resource_service.calls[-1]["ability_gaps"])
        self.assertTrue(resource_result["learning_resources"])
        self.assertIn("certificate_suggestions", resource_result)
        self.assertIn("job_resources_unavailable", resource_result["data_quality_flags"])

        profile_before_feedback = deepcopy(state.student_profile)
        feedback = await self.tools.save_growth_feedback(
            SaveGrowthFeedbackRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-final-feedback",
                satisfaction=4,
                training_rating=2,
                comments="希望增加更多结构化训练。",
            )
        )
        self.assertTrue(feedback.success)
        feedback_result = feedback.data.feedback_result.model_dump(mode="json")
        service_result = self.feedback_service.results[-1]
        for field in (
            "feedback_saved",
            "growth_archive_updated",
            "updated_priorities",
            "growth_snapshot",
            "data_quality_flags",
        ):
            self.assertEqual(service_result[field], feedback_result[field])
        feedback_call = self.feedback_service.calls[-1]
        self.assertEqual(session_id, feedback_call["session_id"])
        self.assertEqual("user-final-e2e", feedback_call["user_id"])
        self.assertEqual(expected_match["skill_gaps"], feedback_call["skill_gaps"])
        self.assertEqual(task["target_abilities"], feedback_call["training_target_abilities"])
        self.assertEqual(expected_match["overall_score"], feedback_call["overall_score"])
        self.assertTrue(feedback_result["updated_priorities"])
        self.assertEqual("stable", feedback_result["growth_snapshot"]["growth_trend"])
        self.assertIn(FLAG_FIRST_GROWTH_SNAPSHOT, feedback_result["data_quality_flags"])

        final_state = self.orchestrator.get_session(session_id)
        self.assertEqual(profile_before_feedback, final_state.student_profile)
        self.assertEqual(
            student_profile()["career_competitiveness_score"],
            final_state.student_profile["career_competitiveness_score"],
        )
        self.assertEqual(resource_result, final_state.resource_result)
        self.assertEqual(feedback_result, final_state.feedback_result)
        serialized = json.dumps(final_state.model_dump(), ensure_ascii=False)
        self.assertNotIn(LONG_ANSWER, serialized)
        self.assertNotIn("希望增加更多结构化训练。", serialized)
        self.assertEqual(
            {"profile_marker": "stage3-profile-accepted"},
            final_state.student_input,
        )

    async def test_invalid_coverage_falls_back_without_uncaught_error(self) -> None:
        session_id = "stage4-final-invalid-coverage"
        await self._seed_real_match(session_id)
        generated = await self._generate(session_id, "trace-invalid-generate")
        task = generated.data.training_task
        self.stage4_llm.signal_mode = "invalid_coverage"

        scored = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-invalid-score",
                training_id=task.training_id,
                user_answer=LONG_ANSWER,
            )
        )

        self.assertTrue(scored.success)
        expected = TrainingService().score(task.training_id, LONG_ANSWER, None)
        self.assertEqual(expected, scored.data.training_score.model_dump(mode="json"))
        self.assertIsNone(self.training_service.score_calls[-1]["agent_analysis"])

    async def test_numeric_llm_signal_is_rejected_by_service_and_falls_back(self) -> None:
        session_id = "stage4-final-numeric-signal"
        await self._seed_real_match(session_id)
        generated = await self._generate(session_id, "trace-numeric-generate")
        task = generated.data.training_task
        self.stage4_llm.signal_mode = "numeric_field"

        scored = await self.tools.generate_and_score_training(
            GenerateAndScoreTrainingRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-numeric-score",
                training_id=task.training_id,
                user_answer=LONG_ANSWER,
            )
        )

        self.assertTrue(scored.success)
        service_analysis = self.training_service.score_calls[-1]["agent_analysis"]
        self.assertEqual(99, service_analysis["total_score"])
        actual = scored.data.training_score.model_dump(mode="json")
        expected = TrainingService().score(task.training_id, LONG_ANSWER, service_analysis)
        self.assertEqual(expected, actual)
        self.assertIn(
            "agent_analysis_rejected:numeric_field",
            actual["data_quality_flags"],
        )

    async def test_unknown_resource_tag_is_a_deterministic_safe_result(self) -> None:
        session_id = "stage4-final-unknown-resource"
        state = self._seed_profile_context(session_id)
        state.match_result = {
            "overall_score": 0.0,
            "skill_gaps": [{"dimension": "完全未知能力标签", "priority": 1}],
        }
        self.orchestrator.persist(state)

        result = await self.tools.recommend_learning_and_job_resources(
            RecommendLearningAndJobResourcesRequest(
                session_id=session_id,
                user_id="user-final-e2e",
                trace_id="trace-unknown-resource",
            )
        )

        self.assertTrue(result.success)
        resource_result = result.data.resource_result.model_dump(mode="json")
        self.assertEqual([], resource_result["learning_resources"])
        self.assertIn(
            "unknown_tag:完全未知能力标签",
            resource_result["data_quality_flags"],
        )
        self.assertEqual([], self.stage4_llm.calls)


if __name__ == "__main__":
    unittest.main()
