"""PathAgent tests: flattening, PathService integration, three outputs, LLM enhancement."""

from __future__ import annotations

import json
import unittest
from typing import Any

from app.agents.match_agent import MatchAgent
from app.agents.path_agent import PathAgent, _LLMStageEnhancement
from app.core.llm_client import LLMValidationError
from app.orchestrator.career_state import CareerState
from app.schemas.match_schema import MatchResult
from app.schemas.path_schema import PathResult
from app.services.match_service import MatchService


class QueueClient:
    """Mock LLM client that returns pre-built _LLMStageEnhancement instances."""

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
        return _LLMStageEnhancement.model_validate(response)


class PathAgentTests(unittest.IsolatedAsyncioTestCase):

    def _unified_profile_student_c(self) -> dict[str, Any]:
        return {
            "user_id": "student-003",
            "basic_info": {
                "education_level": "硕士",
                "major": "统计学（演示）",
                "graduation_year": 2026,
                "target_job": "数据分析师",
                "target_industry": "电子商务",
                "city": "上海",
                "years_of_experience": 0.5,
            },
            "ability_dimensions": [
                {
                    "dimension": "专业知识",
                    "tags": ["Python", "SQL/数据库", "数据分析", "数据可视化"],
                    "level": 4,
                    "confidence": 0.85,
                    "evidence": ["完成匿名统计建模项目", "完成模拟业务查询任务"],
                    "evidence_source": "project",
                },
                {
                    "dimension": "沟通协作",
                    "tags": ["沟通表达"],
                    "level": 2,
                    "confidence": 0.65,
                    "evidence": ["参与匿名项目汇报"],
                    "evidence_source": "project",
                },
            ],
            "ability_tags": ["Python", "SQL/数据库", "数据分析", "数据可视化", "沟通表达"],
            "profile_completeness": 0.8,
            "career_competitiveness_score": 66.0,
            "missing_fields": [],
            "follow_up_questions": [],
            "summary": "演示学生C画像",
            "created_at": "2026-08-04T10:00:00+00:00",
            "updated_at": "2026-08-04T10:00:00+00:00",
        }

    def _job_profile_data_analyst(self) -> dict[str, Any]:
        return {
            "job_id": 91002,
            "title": "数据分析师",
            "normalized_title": "数据分析师",
            "industry": "电子商务",
            "required_abilities": [
                {"tag": "数据分析", "required_level": 4, "weight": 0.3, "importance": "critical", "evidence": "JD要求"},
                {"tag": "SQL/数据库", "required_level": 4, "weight": 0.25, "importance": "critical", "evidence": "JD要求"},
                {"tag": "Python", "required_level": 3, "weight": 0.2, "importance": "important", "evidence": "JD要求"},
                {"tag": "数据可视化", "required_level": 3, "weight": 0.15, "importance": "important", "evidence": "JD要求"},
                {"tag": "沟通表达", "required_level": 3, "weight": 0.1, "importance": "nice_to_have", "evidence": "JD要求"},
            ],
            "soft_skills": ["沟通表达", "解决问题"],
            "salary_range": None,
            "job_description": "匿名演示岗位画像",
        }

    def _compute_match(self, student_profile: dict, job_profile: dict) -> dict[str, Any]:
        """Use MatchService to produce a valid match_result."""
        flat = MatchAgent._flatten_profile(student_profile)
        return MatchService().calculate(flat, job_profile)

    def _llm_enhancement_all_stages(self) -> dict[str, Any]:
        return {
            "stages": [
                {
                    "stage_index": 1,
                    "objectives": ["建立数据分析助理的核心工作流程", "掌握基础数据清洗和报表工具"],
                    "suggested_actions": ["参与至少2个数据分析项目", "完成SQL高级查询训练"],
                    "completion_criteria": "能够独立完成标准数据分析报表",
                },
                {
                    "stage_index": 2,
                    "objectives": ["深化统计分析能力", "学习业务分析方法论"],
                    "suggested_actions": ["负责一个完整业务分析项目", "学习因果推断方法"],
                    "completion_criteria": "能够独立承担业务分析任务并交付洞察报告",
                },
                {
                    "stage_index": 3,
                    "objectives": ["达到数据分析师岗位要求", "建立可展示的分析作品集"],
                    "suggested_actions": ["完成一个端到端数据分析项目", "准备岗位面试案例"],
                    "completion_criteria": "具备数据分析师岗位要求的完整能力体系",
                },
            ],
        }

    async def test_normal_path_recommendation_three_outputs(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-path-normal",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        self.assertFalse(result.fallback_used)

        # path_plan
        pp = state.path_plan
        self.assertIsNotNone(pp)
        self.assertIn("target_job", pp)
        self.assertIn("plan_3year", pp)
        self.assertIn("plan_5year", pp)
        self.assertIn("alternative_paths", pp)
        self.assertEqual("graph-search-v1", pp["path_algorithm_version"])
        self.assertGreater(len(pp["plan_3year"]["phases"]), 0)
        self.assertGreater(len(pp["plan_5year"]["phases"]), 0)

        # learning_plan
        lp = state.learning_plan
        self.assertIsNotNone(lp)
        self.assertIn("phases", lp)
        self.assertGreater(len(lp["phases"]), 0)
        for phase in lp["phases"]:
            self.assertIn("phase", phase)
            self.assertIn("title", phase)
            self.assertIn("tasks", phase)
            self.assertGreater(len(phase["tasks"]), 0)

        # career_roadmap
        cr = state.career_roadmap
        self.assertIsNotNone(cr)
        self.assertIn("target_job", cr.get("three_year_roadmap", {}))
        self.assertIn("horizon_years", cr.get("three_year_roadmap", {}))
        self.assertIn("stages", cr.get("three_year_roadmap", {}))
        self.assertIn("selected_path_id", cr.get("three_year_roadmap", {}))
        self.assertEqual("graph-search-v1", cr.get("three_year_roadmap", {}).get("path_algorithm_version"))

    async def test_normal_path_fills_career_roadmap_from_path_result(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-roadmap",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        await agent.run(state)

        # Full PathResult
        self.assertIn("status", state.career_roadmap)
        self.assertIn("three_year_roadmap", state.career_roadmap)
        self.assertIn("five_year_roadmap", state.career_roadmap)
        self.assertIn("candidate_paths", state.career_roadmap)

    async def test_missing_job_profile_triggers_fallback(self):
        profile = self._unified_profile_student_c()
        state = CareerState(
            session_id="test-fallback",
            student_profile=profile,
            job_profile=None,
            match_result=None,
        )
        agent = PathAgent(client=QueueClient())
        result = await agent.run(state)

        self.assertIn(result.status, ("partial", "failed"))

    async def test_llm_failure_does_not_block_main_flow(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-llm-fail",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(LLMValidationError("LLM failed")))
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        self.assertFalse(result.fallback_used)
        self.assertIsNotNone(state.path_plan)
        self.assertIsNotNone(state.career_roadmap)

    async def test_logs_never_include_private_information(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-privacy",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        await agent.run(state)
        serialized = json.dumps(
            [item.model_dump() for item in state.agent_logs], ensure_ascii=False
        )

        self.assertNotIn("student@example.com", serialized)
        self.assertNotIn("13800138000", serialized)

    async def test_deterministic_output(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-deterministic",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        first = await agent.run(state)

        state2 = CareerState(
            session_id="test-deterministic-2",
            student_profile=self._unified_profile_student_c(),
            job_profile=self._job_profile_data_analyst(),
            match_result=self._compute_match(self._unified_profile_student_c(), self._job_profile_data_analyst()),
        )
        agent2 = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        second = await agent2.run(state2)

        self.assertEqual(first.data, second.data)

    async def test_apply_agent_data_writes_all_three_outputs(self):
        profile = self._unified_profile_student_c()
        job = self._job_profile_data_analyst()
        match = self._compute_match(profile, job)
        state = CareerState(
            session_id="test-apply",
            student_profile=profile,
            job_profile=job,
            match_result=match,
        )
        agent = PathAgent(client=QueueClient(self._llm_enhancement_all_stages()))
        result = await agent.run(state)

        self.assertEqual("success", result.status)
        self.assertIsNotNone(state.path_plan)
        self.assertIsNotNone(state.learning_plan)
        self.assertIsNotNone(state.career_roadmap)

    def test_flatten_profile(self):
        result = PathAgent._flatten_profile(None)
        self.assertEqual(result["abilities"], [])
        self.assertEqual(result["student_id"], None)
        self.assertEqual(result["name"], "匿名用户")

        result = PathAgent._flatten_profile({})
        self.assertEqual(result["abilities"], [])

        unified = self._unified_profile_student_c()
        result = PathAgent._flatten_profile(unified)
        self.assertIn("abilities", result)
        self.assertEqual(len(result["abilities"]), 5)
        self.assertEqual(result["completeness"], 0.8)
        self.assertNotIn("city", result["basic_info"])
        self.assertEqual(result["competitiveness_score"], 66.0)

        legacy = {"abilities": [{"tag": "Python", "level": 3}], "completeness": 0.5}
        result = PathAgent._flatten_profile(legacy)
        self.assertEqual(result["abilities"], legacy["abilities"])

    def test_extract_preferences(self):
        self.assertEqual(PathAgent._extract_preferences(None), {})
        profile = self._unified_profile_student_c()
        pref = PathAgent._extract_preferences(profile)
        self.assertEqual(pref["target_industry"], "电子商务")
        self.assertEqual(pref["target_job"], "数据分析师")
        self.assertEqual(pref["desired_city"], "上海")


if __name__ == "__main__":
    unittest.main()