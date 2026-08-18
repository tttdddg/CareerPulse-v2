import json
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from pydantic import ValidationError

from app.schemas.job_schema import JobProfile
from app.schemas.match_schema import MatchResult
from app.schemas.profile_schema import StudentProfile
from app.services.match_service import MatchService


def requirement(tag, required_level, weight, importance="important", evidence=None):
    return {
        "tag": tag,
        "required_level": required_level,
        "weight": weight,
        "importance": importance,
        "evidence": evidence,
    }


def profile(*abilities, completeness=None, missing_fields=None):
    result = {"abilities": list(abilities)}
    if completeness is not None:
        result["completeness"] = completeness
    if missing_fields is not None:
        result["missing_fields"] = missing_fields
    return result


def ability(tag, level, confidence=None, evidence=None):
    result = {"tag": tag, "level": level}
    if confidence is not None:
        result["confidence"] = confidence
    if evidence is not None:
        result["evidence"] = evidence
    return result


def job(*requirements):
    return {"required_abilities": list(requirements)}


class MatchServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = MatchService()
        self.target = job(
            requirement("Python", 4, 0.5),
            requirement("SQL/数据库", 3, 0.3),
            requirement("沟通表达", 2, 0.2),
        )

    def test_high_match(self):
        result = self.service.calculate(
            profile(ability("Python", 5), ability("SQL/数据库", 3), ability("沟通表达", 4)),
            self.target,
        )
        self.assertEqual(result["overall_score"], 100.0)
        self.assertEqual(result["ability_gaps"], [])
        self.assertEqual(result["strengths"], ["Python", "SQL/数据库", "沟通表达"])

    def test_medium_match(self):
        result = self.service.calculate(
            profile(ability("Python", 3), ability("SQL/数据库", 2), ability("沟通表达", 1)),
            self.target,
        )
        self.assertEqual(result["overall_score"], 67.5)
        self.assertEqual([item["gap"] for item in result["ability_gaps"]], [1, 1, 1])

    def test_low_match_and_missing_key_ability(self):
        result = self.service.calculate(profile(ability("沟通表达", 1)), self.target)
        self.assertEqual(result["overall_score"], 50.0)
        self.assertEqual(result["match_level"], "insufficient_data")
        self.assertEqual(result["ability_gaps"][0], {
            "tag": "Python", "current_level": 0, "required_level": 4, "gap": 4, "priority": 1
        })
        self.assertEqual(result["ability_gaps"][1]["tag"], "SQL/数据库")

    def test_empty_student_abilities_are_zero(self):
        result = self.service.calculate(profile(), self.target)
        self.assertEqual(result["overall_score"], 0.0)
        self.assertTrue(all(item["current_level"] == 0 for item in result["ability_gaps"]))

    def test_empty_job_abilities_returns_fixed_schema(self):
        result = self.service.calculate(profile(ability("Python", 3)), job())
        self.assertEqual(result["overall_score"], 0.0)
        self.assertEqual(result["match_level"], "insufficient_data")
        for field in (
            "dimensions", "ability_gaps", "gap_analysis", "strengths",
            "dimension_matches", "matched_skills", "missing_skills",
            "skill_gaps", "hard_constraint_results", "evidence",
        ):
            self.assertEqual(result[field], [])
        self.assertEqual(result["matching_algorithm_version"], "deterministic-v1")
        self.assertEqual(result["calculation_version"], "deterministic-match-v2")
        MatchResult.model_validate(result)

    def test_dimensions_score_gap_and_weight(self):
        result = self.service.calculate(profile(ability("Python", 2)), job(requirement("Python", 4, 1.0)))
        self.assertEqual(result["dimensions"], [{
            "name": "Python", "student_score": 50.0, "job_required": 100.0,
            "gap": -50.0, "weight": 1.0,
        }])
        self.assertEqual(result["gap_analysis"], [{
            "item": "Python", "status": "insufficient", "suggestion": "",
        }])

    def test_required_level_errors_prevent_zero_division(self):
        for value in (0, 6, 2.5, True, None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "required_level"):
                self.service.calculate(profile(), job(requirement("Python", value, 1.0)))

    def test_weight_errors(self):
        for value in (-0.1, 1.1, float("nan"), True, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "weight"):
                self.service.calculate(profile(), job(requirement("Python", 3, value)))
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            self.service.calculate(profile(), job(requirement("Python", 3, 0.5)))

    def test_difficulty_errors_prevent_zero_division(self):
        for value in (0, -1, 3.1, float("nan")):
            with self.subTest(value=value):
                tag_data = json.dumps([{
                    "tag": "Python", "difficulty": value, "deprecated": False
                }])
                with patch.object(Path, "open", mock_open(read_data=tag_data)):
                    with self.assertRaisesRegex(ValueError, "difficulty"):
                        MatchService("unused-tags.json")

    def test_invalid_student_level_errors(self):
        with self.assertRaisesRegex(ValueError, "level for Python"):
            self.service.calculate(profile(ability("Python", 0)), self.target)

    def test_unmapped_tag_errors(self):
        with self.assertRaisesRegex(ValueError, "cannot be mapped"):
            self.service.calculate(profile(ability("Python与数据分析", 3)), self.target)
        with self.assertRaisesRegex(ValueError, "cannot be mapped"):
            self.service.calculate(profile(), job(requirement("未知标签", 3, 1.0)))

    def test_aliases_are_normalized_before_matching(self):
        result = self.service.calculate(
            profile(ability("python", 4)),
            job(requirement("Python 编程", 4, 1.0)),
        )
        self.assertEqual(result["overall_score"], 100.0)
        self.assertEqual(result["dimensions"][0]["name"], "Python")

    def test_priority_uses_gap_weight_over_difficulty(self):
        result = self.service.calculate(
            profile(),
            job(requirement("Python", 3, 0.4), requirement("学习能力", 2, 0.6)),
        )
        self.assertEqual([item["tag"] for item in result["ability_gaps"]], ["学习能力", "Python"])
        self.assertEqual([item["priority"] for item in result["ability_gaps"]], [1, 2])

    def test_same_input_is_exactly_deterministic(self):
        student = profile(ability("Python", 3), ability("SQL/数据库", 2))
        first = self.service.calculate(student, self.target)
        for _ in range(10):
            self.assertEqual(self.service.calculate(student, self.target), first)

    def test_missing_skill_is_unknown_not_zero_in_new_schema(self):
        result = self.service.calculate(
            profile(ability("沟通表达", 3, 0.8, "匿名课程展示")),
            job(requirement("Python", 4, 1.0, "critical", "JD要求Python")),
        )
        dimension = result["dimension_matches"][0]
        self.assertIsNone(dimension["student_level"])
        self.assertIsNone(dimension["gap"])
        self.assertIsNone(dimension["score"])
        self.assertEqual(dimension["status"], "unknown")
        self.assertEqual(result["missing_skills"], ["Python"])
        self.assertEqual(result["skill_gaps"], [])
        self.assertEqual(result["overall_score"], 0.0)
        self.assertEqual(result["match_level"], "insufficient_data")
        self.assertEqual(result["hard_constraint_results"][0]["status"], "unknown")
        self.assertIsNone(result["hard_constraint_results"][0]["passed"])

    def test_real_stage2_profiles_produce_evidence_backed_result(self):
        data_dir = Path(__file__).resolve().parents[1] / "app" / "data"
        students = json.loads((data_dir / "students_demo.json").read_text(encoding="utf-8"))
        jobs = json.loads((data_dir / "jobs_demo.json").read_text(encoding="utf-8"))
        student = StudentProfile.model_validate(students[2])
        target = JobProfile.model_validate(jobs[1])

        result = self.service.calculate(student, target)

        self.assertEqual(result["overall_score"], 90.42)
        self.assertEqual(result["match_level"], "high")
        self.assertEqual(result["matched_skills"], ["数据分析", "Python", "数据可视化"])
        self.assertEqual([item["dimension"] for item in result["skill_gaps"]], ["SQL/数据库", "沟通表达"])
        self.assertEqual(result["confidence"], 0.8756)
        self.assertEqual(
            [item["status"] for item in result["hard_constraint_results"]],
            ["passed", "failed"],
        )
        self.assertEqual(result["evidence"][0]["student_evidence"], "完成公开演示数据研究")
        MatchResult.model_validate(result)

    def test_confidence_changes_reliability_not_score(self):
        target = job(requirement("Python", 4, 1.0, evidence="JD要求Python"))
        low = self.service.calculate(
            profile(ability("Python", 3, 0.2, "匿名项目"), completeness=0.8), target
        )
        high = self.service.calculate(
            profile(ability("Python", 3, 0.9, "匿名项目"), completeness=0.8), target
        )
        self.assertEqual(low["overall_score"], high["overall_score"])
        self.assertLess(low["confidence"], high["confidence"])
        self.assertIn("low_student_evidence_confidence:Python", low["data_quality_flags"])

    def test_unknown_dimensions_do_not_lower_observed_score(self):
        result = self.service.calculate(
            profile(ability("Python", 4, 0.9, "匿名项目")),
            job(
                requirement("Python", 4, 0.6),
                requirement("SQL/数据库", 4, 0.4),
            ),
        )
        self.assertEqual(result["overall_score"], 100.0)
        self.assertEqual(result["match_level"], "high")
        self.assertEqual(result["missing_skills"], ["SQL/数据库"])
        self.assertLess(result["confidence"], 0.9)

    def test_zero_weight_dimension_is_explicitly_excluded(self):
        result = self.service.calculate(
            profile(ability("SQL/数据库", 3, 0.8, "匿名课程设计")),
            job(
                requirement("Python", 4, 0.0, "critical"),
                requirement("SQL/数据库", 3, 1.0),
            ),
        )
        excluded = result["dimension_matches"][0]
        self.assertEqual(excluded["status"], "excluded")
        self.assertNotIn("Python", result["missing_skills"])
        self.assertEqual(result["hard_constraint_results"], [])
        self.assertEqual(result["overall_score"], 100.0)

    def test_match_level_boundaries_are_deterministic(self):
        levels = {1: "weak", 2: "fair", 3: "good", 4: "high", 5: "high"}
        target = job(requirement("Python", 5, 1.0))
        for current, expected in levels.items():
            with self.subTest(current=current):
                result = self.service.calculate(profile(ability("Python", current)), target)
                self.assertEqual(result["match_level"], expected)

    def test_invalid_confidence_completeness_importance_and_evidence(self):
        invalid_cases = (
            (profile(ability("Python", 3, 1.1, "证据")), self.target, "confidence"),
            (profile(ability("Python", 3), completeness=-0.1), self.target, "completeness"),
            (profile(ability("Python", 3)), job(requirement("Python", 3, 1.0, "mandatory")), "importance"),
            (profile(ability("Python", 3, 0.8, "")), self.target, "evidence"),
        )
        for student, target, message in invalid_cases:
            with self.subTest(message=message), self.assertRaisesRegex((TypeError, ValueError), message):
                self.service.calculate(student, target)

    def test_raw_mapping_student_evidence_privacy_is_enforced(self):
        private_evidence = "匿名项目，联系邮箱 demo@example.com"
        with self.assertRaisesRegex(ValidationError, "student evidence"):
            self.service.calculate(
                profile(ability("Python", 3, 0.8, private_evidence)),
                job(requirement("Python", 4, 1.0)),
            )

    def test_match_schema_rejects_inconsistent_unknown_dimension(self):
        result = self.service.calculate(profile(), job(requirement("Python", 4, 1.0)))
        result["dimension_matches"][0]["student_level"] = 1
        with self.assertRaises(ValidationError):
            MatchResult.model_validate(result)


if __name__ == "__main__":
    unittest.main()
