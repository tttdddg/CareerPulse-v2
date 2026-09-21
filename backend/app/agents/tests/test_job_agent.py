"""Focused JobAgent database-boundary tests."""

from __future__ import annotations

import unittest
from typing import Any

from app.agents.job_agent import JobAgent, _SOFT_SKILL_TAGS, _TAG_ALIASES
from app.orchestrator.career_state import CareerState
from app.schemas.profile_schema import active_ability_tags_by_category
from app.services.ability_normalization import AbilityTagNormalizer


class NoCallClient:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        raise AssertionError("database job context must not call the LLM")


class JobAgentDatabaseTests(unittest.IsolatedAsyncioTestCase):
    def test_tag_views_are_derived_from_authoritative_json(self) -> None:
        self.assertEqual(
            active_ability_tags_by_category("soft_skill"),
            _SOFT_SKILL_TAGS,
        )
        self.assertEqual(
            AbilityTagNormalizer().explicit_aliases(),
            _TAG_ALIASES,
        )

    async def test_database_profile_is_returned_without_recalculating_vector(self) -> None:
        client = NoCallClient()
        profile = {
            "job_id": 7,
            "title": "后端开发工程师",
            "normalized_title": "后端开发",
            "industry": "企业服务/SaaS",
            "required_abilities": [
                {
                    "tag": "Python",
                    "required_level": 5,
                    "weight": 1.0,
                    "importance": "critical",
                    "evidence": None,
                }
            ],
            "soft_skills": [],
            "salary_range": None,
            "job_description": "数据库类型画像",
        }
        state = CareerState(
            session_id="job-agent-database",
            target_job_input={"job_id": 7},
            job_profile=profile,
            job_data_source="postgresql",
        )

        result = await JobAgent(client=client).run(state)

        self.assertEqual("success", result.status)
        self.assertEqual(profile, state.job_profile)
        self.assertEqual(0, client.calls)
        self.assertEqual([], state.trend_result["hot_skills"])
        self.assertIn("PostgreSQL", state.trend_result["data_source"])


if __name__ == "__main__":
    unittest.main()
