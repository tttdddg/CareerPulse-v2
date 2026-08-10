import json
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from app.services.match_service import MatchService


def requirement(tag, required_level, weight):
    return {"tag": tag, "required_level": required_level, "weight": weight}


def profile(*abilities):
    return {"abilities": list(abilities)}


def ability(tag, level):
    return {"tag": tag, "level": level}


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
        self.assertEqual(result["overall_score"], 10.0)
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
        self.assertEqual(result, {
            "overall_score": 0.0,
            "dimensions": [],
            "ability_gaps": [],
            "gap_analysis": [],
            "strengths": [],
            "matching_algorithm_version": "deterministic-v1",
        })

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


if __name__ == "__main__":
    unittest.main()
