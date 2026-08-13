"""Valid and invalid examples for the Stage 3 unified schemas."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.ability_dimension import ABILITY_DIMENSIONS, AbilityDimension
from app.schemas.career_profile_schema import (
    AbilityDimensionProfile,
    AgentResponse,
    CareerTrend,
    EvidenceSource,
    JobProfile,
    StudentBasicInfo,
    StudentProfile,
    StudentProfileRequest,
)


def ability_payload(dimension: AbilityDimension = AbilityDimension.PROFESSIONAL_KNOWLEDGE):
    return {
        "dimension": dimension,
        "tags": ["数据分析"],
        "level": 3,
        "confidence": 0.8,
        "evidence": ["完成匿名课程项目"],
        "evidence_source": EvidenceSource.PROJECT,
    }


class CareerProfileSchemaTests(unittest.TestCase):
    def test_fixed_dimensions_are_complete_and_unique(self) -> None:
        self.assertEqual(7, len(ABILITY_DIMENSIONS))
        self.assertEqual(7, len(set(ABILITY_DIMENSIONS)))
        self.assertEqual(
            {
                "专业知识", "技术与工具", "项目实践", "沟通协作",
                "问题解决", "学习成长", "行业认知",
            },
            {item.value for item in ABILITY_DIMENSIONS},
        )

    def test_valid_student_job_trend_and_response_examples(self) -> None:
        ability = AbilityDimensionProfile.model_validate(ability_payload())
        student = StudentProfile(
            user_id="user-demo-001",
            basic_info=StudentBasicInfo(major="信息管理", target_job="数据分析师"),
            ability_dimensions=[ability],
            ability_tags=["数据分析"],
            profile_completeness=0.75,
            career_competitiveness_score=68.0,
            summary="具备基础数据分析项目经验。",
        )
        job = JobProfile(
            job_name="数据分析师",
            industry="互联网",
            city="上海",
            core_skills=["数据分析"],
            ability_dimensions=[ability],
            confidence=0.9,
        )
        trend = CareerTrend(
            job_name="数据分析师",
            trend_summary="岗位需求保持稳定。",
            stable_skills=["数据分析"],
            knowledge_sources=[{"name": "匿名招聘数据"}],
        )
        response = AgentResponse[StudentProfile](
            agent_name="ProfileAgent",
            status="success",
            data=student,
            summary="画像生成完成",
        )

        self.assertEqual(ability.dimension, job.ability_dimensions[0].dimension)
        self.assertEqual("数据分析师", trend.job_name)
        self.assertEqual(student, response.data)

    def test_ranges_reject_invalid_examples(self) -> None:
        for field, value in (("level", 0), ("level", 6), ("confidence", -0.1), ("confidence", 1.1)):
            payload = ability_payload()
            payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                AbilityDimensionProfile.model_validate(payload)

        valid = dict(
            user_id="user-demo-002",
            basic_info={},
            profile_completeness=0.5,
            career_competitiveness_score=50,
            summary="信息有限。",
        )
        for field, value in (("profile_completeness", -0.01), ("profile_completeness", 1.01)):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                StudentProfile.model_validate({**valid, field: value})

    def test_duplicate_dimensions_and_unsafe_mutable_defaults_are_rejected_or_isolated(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must not repeat"):
            JobProfile(
                job_name="数据分析师",
                industry="互联网",
                city="上海",
                ability_dimensions=[ability_payload(), ability_payload()],
                confidence=0.8,
            )

        first = CareerTrend(job_name="岗位A", trend_summary="样例A")
        second = CareerTrend(job_name="岗位B", trend_summary="样例B")
        first.risks.append("样例风险")
        self.assertEqual([], second.risks)

    def test_request_schema_requires_resume_or_form(self) -> None:
        StudentProfileRequest(user_id="u1", form_fields={"major": "计算机"})
        with self.assertRaisesRegex(ValidationError, "must be provided"):
            StudentProfileRequest(user_id="u1")


if __name__ == "__main__":
    unittest.main()
