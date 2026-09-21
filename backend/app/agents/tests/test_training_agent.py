"""TrainingAgent tests for real TrainingService and offline LLM boundaries."""

from __future__ import annotations

import inspect
import json
import unittest
from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from app.agents.training_agent import TrainingAgent
from app.core.llm_client import LLMValidationError
from app.orchestrator.career_state import CareerState
from app.schemas.training_schema import TrainingAnalysis
from app.services.match_service import MatchService
from app.services.resource_service import ResourceService
from app.services.training_service import TRAINING_TYPES, TrainingService


LONG_ANSWER = (
    "我会先同步当前进展和已确认事实，再列出风险、下一步与负责人，"
    "并通过异步文档约定反馈期限，确保所有成员可以追踪决策。"
)


class RawResponse:
    """Return a raw value without applying the requested response schema."""

    def __init__(self, value: Any) -> None:
        self.value = value


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
                "kwargs": dict(kwargs),
            }
        )
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, RawResponse):
            return deepcopy(response.value)
        return response_schema.model_validate(response)


class RecordingTrainingService:
    """Record exact Agent-to-Service parameters while using the frozen logic."""

    def __init__(self) -> None:
        self.inner = TrainingService()
        self.generate_calls: list[dict[str, Any]] = []
        self.score_calls: list[dict[str, Any]] = []

    def generate(
        self,
        training_type: str,
        ability_gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        self.generate_calls.append(
            {
                "training_type": training_type,
                "ability_gaps": deepcopy(ability_gaps),
            }
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
    """Record exact Agent-to-ResourceService parameters and return real data."""

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


class ErrorTrainingService(RecordingTrainingService):
    def generate(
        self,
        training_type: str,
        ability_gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        self.generate_calls.append(
            {"training_type": training_type, "ability_gaps": deepcopy(ability_gaps)}
        )
        return {"error": "no_training_task_for_type:forced test error"}


class FixedScoreTrainingService(RecordingTrainingService):
    FIXED_SCORE = {
        "mode": "score",
        "training_id": "train-remote-001",
        "total_score": 73.25,
        "dimension_scores": [
            {
                "dimension": "信息完整",
                "score": 71.5,
                "comment": "确定性测试维度结果。",
            }
        ],
        "overall_comment": "确定性测试综合结果。",
        "improvement_suggestions": ["保持证据和行动项清晰。"],
        "ability_updates": [{"tag": "远程协作", "level_change": 0}],
        "data_quality_flags": ["fixed_service_test"],
    }

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
        return deepcopy(self.FIXED_SCORE)


class ScoreErrorTrainingService(RecordingTrainingService):
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
        return {"error": "privacy_violation:forced score error"}


def analysis_for_remote_001(*, omit_last: bool = False) -> dict[str, Any]:
    dimensions = [
        {
            "dimension": "信息完整",
            "coverage": "fully",
            "reason": "回答包含进展、风险和下一步。",
        },
        {
            "dimension": "异步友好",
            "coverage": "mostly",
            "reason": "回答说明异步文档和反馈期限。",
        },
        {
            "dimension": "责任清晰",
            "coverage": "partial",
            "reason": "回答提到负责人但细节较少。",
        },
    ]
    return {"dimensions": dimensions[:-1] if omit_last else dimensions}


def feedback() -> dict[str, Any]:
    return {
        "commentary": "回答结构清楚，可继续细化责任边界。",
        "strengths": ["能够说明进展和风险。"],
        "next_steps": ["补充每个行动项的负责人。"],
    }


def build_state(
    training: dict[str, Any] | None,
    *,
    session_id: str = "training-agent-test",
) -> CareerState:
    student_input: dict[str, Any] = {}
    if training is not None:
        student_input["training"] = training
    return CareerState(
        session_id=session_id,
        student_input=student_input,
        student_profile={"profile": "ready"},
        job_profile={"title": "测试岗位"},
        match_result={
            "skill_gaps": [
                {"dimension": "解决问题", "priority": 1},
                {"dimension": "远程协作", "priority": 2},
            ]
        },
    )


def real_match_result() -> dict[str, Any]:
    """Build a valid deterministic MatchService result for resource tests."""

    student = {
        "abilities": [
            {"tag": "数据分析", "level": 1, "confidence": 0.9, "evidence": "匿名项目"},
            {"tag": "Python", "level": 2, "confidence": 0.8, "evidence": "匿名练习"},
            {"tag": "数据库/SQL", "level": 3, "confidence": 0.7, "evidence": "匿名任务"},
        ],
        "completeness": 1.0,
        "missing_fields": [],
    }
    job = {
        "job_id": 92001,
        "title": "数据分析师",
        "normalized_title": "数据分析师",
        "industry": "电子商务",
        "required_abilities": [
            {
                "tag": "数据分析",
                "required_level": 4,
                "weight": 0.5,
                "importance": "critical",
                "evidence": "匿名岗位要求",
            },
            {
                "tag": "Python",
                "required_level": 4,
                "weight": 0.3,
                "importance": "important",
                "evidence": "匿名岗位要求",
            },
            {
                "tag": "数据库/SQL",
                "required_level": 4,
                "weight": 0.2,
                "importance": "important",
                "evidence": "匿名岗位要求",
            },
        ],
        "soft_skills": [],
        "salary_range": None,
        "job_description": "匿名岗位画像",
    }
    return MatchService().calculate(student, job)


class TrainingAgentTests(unittest.IsolatedAsyncioTestCase):
    async def _generate_remote(
        self,
        service: RecordingTrainingService,
        *,
        session_id: str = "generated-remote",
    ) -> CareerState:
        state = build_state(
            {
                "training_type": "remote_collaboration",
                "ability_gaps": [],
            },
            session_id=session_id,
        )
        result = await TrainingAgent(client=QueueClient(), service=service).run(state)
        self.assertEqual("success", result.status)
        self.assertEqual("train-remote-001", state.training_plan["trainings"][0]["training_id"])
        return state

    async def test_generate_calls_service_and_passes_ability_gaps(self) -> None:
        service = RecordingTrainingService()
        gaps = ["解决问题", "远程协作"]
        state = build_state(
            {
                "training_type": "remote_collaboration",
                "ability_gaps": gaps,
            }
        )

        result = await TrainingAgent(client=QueueClient(), service=service).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(
            [{"training_type": "remote_collaboration", "ability_gaps": gaps}],
            service.generate_calls,
        )
        self.assertEqual("TrainingService", result.service_name)
        self.assertEqual("generate_and_score_training", result.tool_calls[0].tool_name)

    async def test_generate_uses_service_task_and_contains_no_mock_task(self) -> None:
        service = RecordingTrainingService()
        state = build_state(
            {
                "training_type": "remote_collaboration",
                "ability_gaps": ["解决问题"],
            }
        )

        await TrainingAgent(client=QueueClient(), service=service).run(state)

        task = state.training_plan["trainings"][0]
        expected = service.inner.generate("remote_collaboration", ["解决问题"])
        self.assertEqual(expected, task)
        self.assertEqual("train-remote-003", task["training_id"])
        self.assertNotIn("mock", json.dumps(task, ensure_ascii=False).lower())

    async def test_score_passes_complete_structured_analysis_to_service(self) -> None:
        service = RecordingTrainingService()
        state = await self._generate_remote(service)
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(analysis_for_remote_001(), feedback())

        result = await TrainingAgent(client=client, service=service).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(analysis_for_remote_001(), service.score_calls[-1]["agent_analysis"])
        self.assertIs(client.calls[0]["response_schema"], TrainingAnalysis)
        prompt = client.calls[0]["messages"][0]["content"]
        for level in ("fully", "mostly", "partial", "barely", "missing"):
            self.assertIn(level, prompt)

    def test_analysis_schema_supports_exact_five_coverage_levels(self) -> None:
        value = TrainingAnalysis.model_validate(
            {
                "dimensions": [
                    {"dimension": f"维度{index}", "coverage": level, "reason": "有效依据"}
                    for index, level in enumerate(
                        ("fully", "mostly", "partial", "barely", "missing"),
                        start=1,
                    )
                ]
            }
        )
        self.assertEqual(
            ["fully", "mostly", "partial", "barely", "missing"],
            [item.coverage for item in value.dimensions],
        )

    def test_analysis_schema_rejects_long_or_private_reason(self) -> None:
        for reason in ("过长" * 101, "请联系 demo@example.com 获取依据"):
            with self.subTest(reason=reason[:20]):
                with self.assertRaises(ValidationError):
                    TrainingAnalysis.model_validate(
                        {
                            "dimensions": [
                                {
                                    "dimension": "信息完整",
                                    "coverage": "fully",
                                    "reason": reason,
                                }
                            ]
                        }
                    )

    async def test_extra_llm_dimension_is_not_passed_to_service(self) -> None:
        service = RecordingTrainingService()
        state = await self._generate_remote(service, session_id="extra-dimension")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        analysis = analysis_for_remote_001()
        analysis["dimensions"].append(
            {
                "dimension": "LLM额外维度",
                "coverage": "fully",
                "reason": "该维度不在题目中。",
            }
        )
        client = QueueClient(analysis, feedback())

        await TrainingAgent(client=client, service=service).run(state)

        self.assertIsNone(service.score_calls[-1]["agent_analysis"])

    async def test_missing_dimension_is_scored_by_service_as_missing(self) -> None:
        service = RecordingTrainingService()
        state = await self._generate_remote(service, session_id="missing-dimension")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(analysis_for_remote_001(omit_last=True), feedback())

        await TrainingAgent(client=client, service=service).run(state)

        score = state.training_plan["latest_score"]
        self.assertIn(
            "incomplete_analysis:责任清晰",
            score["data_quality_flags"],
        )
        responsibility = next(
            item for item in score["dimension_scores"] if item["dimension"] == "责任清晰"
        )
        self.assertEqual(0.0, responsibility["score"])

    async def test_numeric_llm_signal_is_rejected_by_service_and_falls_back(self) -> None:
        service = RecordingTrainingService()
        state = await self._generate_remote(service, session_id="numeric-signal")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        contaminated = analysis_for_remote_001()
        contaminated["dimensions"][0]["score"] = 99
        client = QueueClient(RawResponse(contaminated), feedback())

        await TrainingAgent(client=client, service=service).run(state)

        self.assertEqual(contaminated, service.score_calls[-1]["agent_analysis"])
        self.assertIn(
            "agent_analysis_rejected:numeric_field",
            state.training_plan["latest_score"]["data_quality_flags"],
        )

    async def test_all_score_numbers_are_copied_from_service(self) -> None:
        service = FixedScoreTrainingService()
        state = await self._generate_remote(service, session_id="fixed-score")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(analysis_for_remote_001(), feedback())

        await TrainingAgent(client=client, service=service).run(state)

        self.assertEqual(service.FIXED_SCORE, state.training_plan["latest_score"])

    async def test_feedback_llm_failure_does_not_change_service_score(self) -> None:
        service = RecordingTrainingService()
        state = await self._generate_remote(service, session_id="feedback-failure")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(
            analysis_for_remote_001(),
            LLMValidationError("feedback failed"),
        )

        result = await TrainingAgent(client=client, service=service).run(state)

        expected = service.inner.score(
            "train-remote-001", LONG_ANSWER, analysis_for_remote_001()
        )
        self.assertEqual("success", result.status)
        self.assertEqual(expected, state.training_plan["latest_score"])
        self.assertEqual(
            expected["overall_comment"],
            state.training_plan["natural_language_feedback"]["commentary"],
        )

    async def test_service_error_becomes_failed_agent_result_without_fake_task(self) -> None:
        service = ErrorTrainingService()
        state = build_state(
            {
                "training_type": "remote_collaboration",
                "ability_gaps": ["远程协作"],
            },
            session_id="service-error",
        )

        result = await TrainingAgent(client=QueueClient(), service=service).run(state)

        self.assertEqual("failed", result.status)
        self.assertTrue(result.fallback_used)
        self.assertIsNone(state.training_plan)
        self.assertIn("TrainingServiceError", result.error)

    async def test_score_service_error_preserves_existing_task_and_fails_safe(self) -> None:
        service = ScoreErrorTrainingService()
        state = await self._generate_remote(service, session_id="score-service-error")
        original_plan = deepcopy(state.training_plan)
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(analysis_for_remote_001())

        result = await TrainingAgent(client=client, service=service).run(state)

        self.assertEqual("failed", result.status)
        self.assertTrue(result.fallback_used)
        self.assertEqual(original_plan, state.training_plan)
        self.assertNotIn("latest_score", state.training_plan)

    async def test_same_input_and_mock_llm_have_stable_business_structure(self) -> None:
        outputs = []
        for index in range(2):
            service = RecordingTrainingService()
            state = await self._generate_remote(service, session_id=f"stable-{index}")
            state.student_input = {
                "training": {
                    "training_type": "remote_collaboration",
                    "training_id": "train-remote-001",
                    "user_answer": LONG_ANSWER,
                }
            }
            client = QueueClient(analysis_for_remote_001(), feedback())
            await TrainingAgent(client=client, service=service).run(state)
            outputs.append(
                {
                    "trainings": state.training_plan["trainings"],
                    "latest_score": state.training_plan["latest_score"],
                    "natural_language_feedback": state.training_plan[
                        "natural_language_feedback"
                    ],
                }
            )

        self.assertEqual(outputs[0], outputs[1])

    async def test_legacy_full_chain_generates_all_real_types_through_service(self) -> None:
        service = RecordingTrainingService()
        state = build_state(None, session_id="legacy-full-chain")

        result = await TrainingAgent(client=QueueClient(), service=service).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(list(TRAINING_TYPES), [call["training_type"] for call in service.generate_calls])
        self.assertEqual(3, len(state.training_plan["trainings"]))
        self.assertTrue(
            all(item["training_id"].startswith("train-") for item in state.training_plan["trainings"])
        )

    async def test_logs_do_not_store_user_answer(self) -> None:
        private_answer = LONG_ANSWER + " 私密但非身份信息的正文"
        service = RecordingTrainingService()
        state = await self._generate_remote(service, session_id="safe-log")
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": private_answer,
            }
        }
        client = QueueClient(analysis_for_remote_001(), feedback())

        await TrainingAgent(client=client, service=service).run(state)

        logs = json.dumps(
            [item.model_dump(mode="json") for item in state.agent_logs],
            ensure_ascii=False,
        )
        self.assertNotIn(private_answer, logs)

    def test_resource_gaps_come_from_real_match_result(self) -> None:
        match_result = real_match_result()
        expected_gaps = [item["dimension"] for item in match_result["skill_gaps"]]
        state = build_state(None, session_id="real-resource-gaps")
        state.match_result = match_result
        state.job_profile = {"title": "数据分析师"}
        resource_service = RecordingResourceService()
        agent = TrainingAgent(
            client=QueueClient(),
            resource_service=resource_service,
        )

        result = agent._recommend_resources(state)

        self.assertEqual(
            [{"ability_gaps": expected_gaps, "target_job": "数据分析师"}],
            resource_service.calls,
        )
        self.assertEqual(
            resource_service.inner.recommend_resources(
                expected_gaps,
                "数据分析师",
            ),
            result,
        )

    def test_resource_gap_order_is_not_recomputed_from_priority(self) -> None:
        state = build_state(None, session_id="resource-gap-order")
        state.match_result = {
            "skill_gaps": [
                {"dimension": "数据库/SQL", "priority": 3},
                {"dimension": "数据分析", "priority": 1},
                {"dimension": "Python", "priority": 2},
            ]
        }
        resource_service = RecordingResourceService()
        agent = TrainingAgent(
            client=QueueClient(),
            resource_service=resource_service,
        )

        agent._recommend_resources(state)

        self.assertEqual(
            ["数据库/SQL", "数据分析", "Python"],
            resource_service.calls[0]["ability_gaps"],
        )

    def test_resource_empty_gaps_are_passed_as_empty(self) -> None:
        state = build_state(None, session_id="resource-empty-gaps")
        state.match_result = {"skill_gaps": []}
        resource_service = RecordingResourceService()
        agent = TrainingAgent(
            client=QueueClient(),
            resource_service=resource_service,
        )

        result = agent._recommend_resources(state)

        self.assertEqual([], resource_service.calls[0]["ability_gaps"])
        self.assertEqual(10, len(result["learning_resources"]))

    def test_resource_flags_and_output_fields_are_preserved(self) -> None:
        state = build_state(None, session_id="resource-flags")
        state.match_result = {
            "skill_gaps": [
                {"dimension": "数据分析", "priority": 1},
                {"dimension": "未知标签XYZ", "priority": 2},
                {"dimension": "机器学习", "priority": 3},
            ]
        }
        agent = TrainingAgent(client=QueueClient())

        result = agent._recommend_resources(state)

        self.assertEqual(
            {
                "learning_resources",
                "job_resources",
                "certificate_suggestions",
                "data_quality_flags",
            },
            set(result),
        )
        self.assertEqual("数据分析演示项目", result["learning_resources"][0]["title"])
        self.assertIn("unknown_tag:未知标签XYZ", result["data_quality_flags"])
        self.assertIn("no_resource_for_tag:机器学习", result["data_quality_flags"])
        self.assertEqual([], result["job_resources"])
        self.assertIn("job_resources_unavailable", result["data_quality_flags"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("resource_id", serialized)
        self.assertNotIn("demo_only", serialized)

    async def test_score_flow_writes_resource_result_without_resource_llm_call(self) -> None:
        training_service = RecordingTrainingService()
        state = await self._generate_remote(
            training_service,
            session_id="score-with-resources",
        )
        state.match_result = {
            "skill_gaps": [
                {"dimension": "数据分析", "priority": 1},
                {"dimension": "Python", "priority": 2},
            ]
        }
        state.job_profile = {"title": "数据分析师"}
        state.student_input = {
            "training": {
                "training_type": "remote_collaboration",
                "training_id": "train-remote-001",
                "user_answer": LONG_ANSWER,
            }
        }
        client = QueueClient(analysis_for_remote_001(), feedback())
        resource_service = RecordingResourceService()

        result = await TrainingAgent(
            client=client,
            service=training_service,
            resource_service=resource_service,
        ).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(
            [{"ability_gaps": ["数据分析", "Python"], "target_job": "数据分析师"}],
            resource_service.calls,
        )
        self.assertEqual(
            resource_service.inner.recommend_resources(
                ["数据分析", "Python"],
                "数据分析师",
            ),
            state.resource_result,
        )
        self.assertEqual(2, len(client.calls))

    def test_training_agent_does_not_copy_ability_normalizer(self) -> None:
        self.assertNotIn("AbilityTagNormalizer", inspect.getsource(TrainingAgent))


if __name__ == "__main__":
    unittest.main()
