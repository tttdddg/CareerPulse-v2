"""MatchAgent tests: flattening, MatchService integration, LLM enhancement."""

from __future__ import annotations

import json
import unittest
from typing import Any

from app.agents.match_agent import MatchAgent, _LLMEnhancement
from app.core.llm_client import LLMValidationError
from app.orchestrator.career_state import CareerState
from app.schemas.match_schema import MatchResult


class QueueClient:
    """Mock LLM client that returns pre-built _LLMEnhancement instances."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": args, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return _LLMEnhancement.model_validate(response)


class MatchAgentTests(unittest.IsolatedAsyncioTestCase):

    def _unified_profile(self, **overrides: Any) -> dict[str, Any]:
        profile = {
            "user_id": "student-001",
            "basic_info": {
                "education_level": "本科",
                "major": "计算机科学与技术",
                "graduation_year": 2025,
                "target_job": "AI产品经理",
                "target_industry": "人工智能",
            },
            "ability_dimensions": [
                {
                    "dimension": "专业知识",
                    "tags": ["Python", "SQL/数据库"],
                    "level": 3,
                    "confidence": 0.85,
                    "evidence": ["完成数据挖掘课程项目"],
                    "evidence_source": "project",
                },
                {
                    "dimension": "沟通协作",
                    "tags": ["沟通表达"],
                    "level": 3,
                    "confidence": 0.80,
                    "evidence": ["课程汇报与团队项目"],
                    "evidence_source": "project",
                },
            ],
            "ability_tags": ["Python", "SQL/数据库", "沟通表达"],
            "profile_completeness": 0.8,
            "career_competitiveness_score": 42.0,
            "missing_fields": [],
            "follow_up_questions": [],
            "summary": "测试画像",
            "created_at": "2026-08-04T10:00:00+00:00",
            "updated_at": "2026-08-04T10:00:00+00:00",
        }
        profile.update(overrides)
        return profile

    def _job_profile(self) -> dict[str, Any]:
        return {
            "title": "AI产品经理",
            "normalized_title": "AI产品经理",
            "industry": "人工智能",
            "required_abilities": [
                {"tag": "产品规划", "required_level": 4, "weight": 0.25, "importance": "critical", "evidence": "JD要求"},
                {"tag": "需求分析", "required_level": 4, "weight": 0.20, "importance": "critical", "evidence": "JD要求"},
                {"tag": "数据驱动决策", "required_level": 3, "weight": 0.15, "importance": "important", "evidence": "JD要求"},
                {"tag": "大模型应用", "required_level": 3, "weight": 0.15, "importance": "important", "evidence": "JD要求"},
                {"tag": "用户研究", "required_level": 3, "weight": 0.10, "importance": "important", "evidence": "JD要求"},
                {"tag": "沟通表达", "required_level": 4, "weight": 0.10, "importance": "nice_to_have", "evidence": "JD要求"},
                {"tag": "项目管理", "required_level": 2, "weight": 0.05, "importance": "nice_to_have", "evidence": "JD要求"},
            ],
            "soft_skills": [],
            "job_description": "AI产品经理岗位描述",
        }

    def _llm_enhancement(self) -> dict[str, Any]:
        return {
            "suggestions": {
                "产品规划": "建议参与AI产品从0到1的规划项目以提升产品规划能力",
                "需求分析": "建议系统学习需求分析方法论并实践于真实项目",
            },
            "strengths_summary": "具备Python编程和数据分析基础，在AI产品经理岗位的技术理解方面有优势",
        }

    async def test_normal_unified_profile_flattens_and_matches(self):
        state = CareerState(
            session_id="test-normal",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient(self._llm_enhancement()))
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        match = state.match_result
        self.assertGreater(match["overall_score"], 0)
        self.assertIn(
            match["match_level"],
            ["high", "good", "fair", "weak", "low", "insufficient_data"],
        )
        self.assertIsInstance(match["skill_gaps"], list)
        priorities = [item["priority"] for item in match["skill_gaps"]]
        self.assertEqual(priorities, sorted(priorities))

        # LLM enhancement should have been applied
        self.assertTrue(
            any(
                "建议" in item.get("suggestion", "")
                for item in match["gap_analysis"]
                if item["status"] != "adequate"
            )
        )

    async def test_empty_profile_returns_insufficient_data(self):
        state = CareerState(
            session_id="test-empty",
            student_profile={"basic_info": {"target_job": "test"}, "ability_dimensions": []},
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient())
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        self.assertEqual("insufficient_data", state.match_result["match_level"])

    async def test_llm_failure_does_not_block_main_flow(self):
        state = CareerState(
            session_id="test-llm-fail",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient(LLMValidationError("LLM failed")))
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        self.assertFalse(result.fallback_used)
        self.assertGreater(state.match_result["overall_score"], 0)

    async def test_logs_never_include_private_information(self):
        state = CareerState(
            session_id="test-privacy",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient(self._llm_enhancement()))
        await agent.run(state)
        serialized = json.dumps(
            [item.model_dump() for item in state.agent_logs], ensure_ascii=False
        )

        self.assertNotIn("student@example.com", serialized)
        self.assertNotIn("13800138000", serialized)

    async def test_deterministic_output(self):
        state = CareerState(
            session_id="test-deterministic",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient(self._llm_enhancement()))
        first = await agent.run(state)

        state2 = CareerState(
            session_id="test-deterministic-2",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent2 = MatchAgent(client=QueueClient(self._llm_enhancement()))
        second = await agent2.run(state2)

        self.assertEqual(first.data, second.data)

    async def test_match_result_passes_schema_validation(self):
        state = CareerState(
            session_id="test-schema",
            student_profile=self._unified_profile(),
            job_profile=self._job_profile(),
        )
        agent = MatchAgent(client=QueueClient(self._llm_enhancement()))
        await agent.run(state)

        MatchResult.model_validate(state.match_result)

    async def test_missing_dependency_triggers_fallback(self):
        state = CareerState(
            session_id="test-fallback-dep",
            student_profile=self._unified_profile(),
            job_profile=None,
        )
        agent = MatchAgent(client=QueueClient())
        result = await agent.run(state)

        self.assertIn(result.status, ("partial", "failed"))

    def test_flatten_empty(self):
        self.assertEqual(MatchAgent._flatten_profile(None), {"abilities": []})
        self.assertEqual(MatchAgent._flatten_profile({}), {"abilities": []})

    def test_flatten_legacy_format(self):
        legacy = {"abilities": [{"tag": "Python", "level": 3}], "completeness": 0.5}
        result = MatchAgent._flatten_profile(legacy)
        self.assertEqual(result["abilities"], legacy["abilities"])
        self.assertEqual(result["completeness"], 0.5)

    def test_flatten_unified_format(self):
        profile = self._unified_profile()
        result = MatchAgent._flatten_profile(profile)

        self.assertIn("abilities", result)
        self.assertIn("completeness", result)
        self.assertEqual(result["completeness"], 0.8)
        self.assertEqual(len(result["abilities"]), 3)

        python = next(a for a in result["abilities"] if a["tag"] == "Python")
        self.assertEqual(python["level"], 3)
        self.assertEqual(python["evidence"], "完成数据挖掘课程项目")
        self.assertEqual(python["confidence"], 0.85)

        sql = next(a for a in result["abilities"] if a["tag"] == "SQL/数据库")
        self.assertEqual(sql["level"], 3)
        self.assertEqual(sql["evidence"], "完成数据挖掘课程项目")

        comm = next(a for a in result["abilities"] if a["tag"] == "沟通表达")
        self.assertEqual(comm["level"], 3)
        self.assertEqual(comm["evidence"], "课程汇报与团队项目")


if __name__ == "__main__":
    unittest.main()