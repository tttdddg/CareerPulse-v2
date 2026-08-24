"""Deterministic TrainingService coverage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from app.services.training_service import TrainingService

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


def load_tasks() -> list[dict[str, Any]]:
    with (DATA_DIR / "training_tasks.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def signal(*dims: tuple[str, str, str]) -> dict[str, Any]:
    """Build a valid agent_analysis signal from (dimension, coverage, reason)."""
    return {
        "dimensions": [
            {"dimension": dim, "coverage": coverage, "reason": reason}
            for dim, coverage, reason in dims
        ]
    }


def serialize(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


LONG_ANSWER = "这是一个用于主路径评分的完整回答，包含足够多的文字内容，确保长度超过二十个字的长度门槛。"


class TrainingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TrainingService()
        self.tasks = load_tasks()

    def _task(self, training_id: str) -> dict[str, Any]:
        return next(item for item in self.tasks if item["training_id"] == training_id)

    def test_generate_modes_pick_matching_pool(self) -> None:
        for training_type in ("remote_collaboration", "ai_office_task", "cross_role_communication"):
            result = self.service.generate(training_type)
            self.assertEqual("generate", result["mode"])
            self.assertEqual(training_type, result["type"])
            self.assertTrue(result["training_id"].startswith("train-"))

    def test_generate_ability_gap_prioritizes_overlap(self) -> None:
        result = self.service.generate("remote_collaboration", ["解决问题"])
        self.assertEqual("train-remote-003", result["training_id"])

        double = self.service.generate("remote_collaboration", ["解决问题", "远程协作"])
        self.assertEqual("train-remote-003", double["training_id"])

    def test_generate_overlap_2_beats_overlap_1(self) -> None:
        result = self.service.generate(
            "remote_collaboration", ["远程协作", "时间管理"]
        )
        self.assertEqual("train-remote-004", result["training_id"])

    def test_generate_tie_break_is_lexicographic(self) -> None:
        for _ in range(10):
            self.assertEqual("train-remote-001", self.service.generate("remote_collaboration")["training_id"])
            self.assertEqual("train-ai-001", self.service.generate("ai_office_task")["training_id"])
            self.assertEqual("train-cross-001", self.service.generate("cross_role_communication")["training_id"])

    def test_generate_is_deterministic(self) -> None:
        first = self.service.generate("remote_collaboration", ["解决问题", "沟通表达"])
        for _ in range(9):
            self.assertEqual(serialize(first), serialize(self.service.generate("remote_collaboration", ["解决问题", "沟通表达"])))

    def test_generate_unsupported_type_returns_error(self) -> None:
        result = self.service.generate("mock_interview")
        self.assertIn("error", result)
        self.assertIn("unsupported_training_type", result["error"])

    def test_generate_empty_type_pool_returns_error(self) -> None:
        only_remote = [task for task in self.tasks if task["type"] == "remote_collaboration"]
        service = TrainingService(tasks=only_remote)
        result = service.generate("ai_office_task")
        self.assertIn("error", result)
        self.assertIn("no_training_task_for_type", result["error"])

    def test_generate_output_structure(self) -> None:
        result = self.service.generate("ai_office_task")
        for key in (
            "mode", "training_id", "type", "title", "scenario",
            "task_description", "evaluation_criteria",
            "target_abilities", "reference_answer",
        ):
            self.assertIn(key, result)
        self.assertEqual("generate", result["mode"])
        self.assertTrue(result["evaluation_criteria"])
        criterion = result["evaluation_criteria"][0]
        for key in ("dimension", "max_score", "weight", "description"):
            self.assertIn(key, criterion)

    def test_score_unknown_training_id_returns_error(self) -> None:
        result = self.service.score("train-missing-000", "任意回答")
        self.assertIn("error", result)
        self.assertIn("training_not_found", result["error"])

    def test_score_main_path_full_coverage(self) -> None:
        analysis = signal(
            ("信息完整", "fully", "包含进展、风险和下一步"),
            ("异步友好", "fully", "使用异步工具并给出期限"),
            ("责任清晰", "fully", "明确负责人"),
        )
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        self.assertNotIn("error", result)
        self.assertEqual([100.0, 100.0, 100.0], [item["score"] for item in result["dimension_scores"]])
        self.assertEqual(100.0, result["total_score"])
        self.assertEqual(1, result["ability_updates"][0]["level_change"])

    def test_score_main_path_mixed_coverage_values(self) -> None:
        analysis = signal(
            ("信息完整", "fully", "完全包含"),
            ("异步友好", "partial", "部分说明"),
            ("责任清晰", "missing", "未提及"),
        )
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        self.assertEqual([100.0, 50.0, 0.0], [item["score"] for item in result["dimension_scores"]])
        self.assertEqual(round(100 * 0.4 + 50 * 0.35 + 0 * 0.25, 2), result["total_score"])

    def test_score_main_path_missing_dimension_flag(self) -> None:
        analysis = signal(
            ("信息完整", "fully", "完整"),
            ("异步友好", "mostly", "较好"),
        )
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        self.assertEqual(0.0, result["dimension_scores"][2]["score"])
        self.assertIn("incomplete_analysis:责任清晰", result["data_quality_flags"])

    def test_score_main_path_empty_signal_is_all_missing(self) -> None:
        result = self.service.score("train-remote-001", LONG_ANSWER, {"dimensions": []})
        self.assertEqual([0.0, 0.0, 0.0], [item["score"] for item in result["dimension_scores"]])
        self.assertIn("incomplete_analysis:信息完整", result["data_quality_flags"])

    def test_score_main_path_unrelated_dimension_falls_back(self) -> None:
        analysis = signal(
            ("无关维度", "fully", "不属于题目的维度"),
            ("异步友好", "fully", "正常依据"),
        )
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        self.assertEqual("score", result["mode"])
        flags = result.get("data_quality_flags", [])
        self.assertTrue(any(item.startswith("agent_analysis_rejected:unrelated_dimension") for item in flags), flags)

    def test_score_main_path_invalid_coverage_falls_back(self) -> None:
        analysis = signal(("信息完整", "great", "依据"))
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        flags = result.get("data_quality_flags", [])
        self.assertTrue(any(item.startswith("agent_analysis_rejected:invalid_coverage") for item in flags), flags)
        self.assertEqual("score", result["mode"])

    def test_score_main_path_numeric_field_falls_back(self) -> None:
        analysis = {"dimensions": [{"dimension": "信息完整", "coverage": "fully", "reason": "依据"}], "total_score": 60}
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        flags = result.get("data_quality_flags", [])
        self.assertIn("agent_analysis_rejected:numeric_field", flags)
        self.assertEqual("score", result["mode"])
        self.assertFalse(any(item["score"] == 100.0 for item in result["dimension_scores"]))

    def test_score_main_path_privacy_reason_falls_back(self) -> None:
        analysis = signal(("信息完整", "fully", "依据联系请发 demo@example.com"))
        result = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        flags = result.get("data_quality_flags", [])
        self.assertTrue(any(item.startswith("agent_analysis_rejected:privacy_reason") for item in flags), flags)

    def test_score_empty_answer_resets_to_zero(self) -> None:
        analysis = signal(
            ("信息完整", "fully", "依据"),
            ("异步友好", "fully", "依据"),
            ("责任清晰", "fully", "依据"),
        )
        result = self.service.score("train-remote-001", "", analysis)
        self.assertEqual([0.0, 0.0, 0.0], [item["score"] for item in result["dimension_scores"]])
        self.assertEqual(0.0, result["total_score"])
        self.assertIn("empty_answer", result["data_quality_flags"])
        self.assertEqual(-1, result["ability_updates"][0]["level_change"])

    def test_score_shorter_than_twenty_chars_capped_at_80(self) -> None:
        analysis = signal(
            ("信息完整", "fully", "依据"),
            ("异步友好", "fully", "依据"),
            ("责任清晰", "fully", "依据"),
        )
        result = self.service.score("train-remote-001", "短回答内容", analysis)
        self.assertEqual([80.0, 80.0, 80.0], [item["score"] for item in result["dimension_scores"]])
        self.assertEqual(80.0, result["total_score"])

    def test_score_ability_update_threshold_boundaries(self) -> None:
        at_80 = signal(
            ("数据准确", "fully", "依据"),
            ("表达清晰", "mostly", "依据"),
            ("可追溯", "partial", "依据"),
        )
        result80 = self.service.score("train-ai-002", LONG_ANSWER, at_80)
        self.assertEqual(80.0, result80["total_score"])
        self.assertEqual(1, result80["ability_updates"][0]["level_change"])

        just_below_80 = signal(
            ("数据准确", "fully", "依据"),
            ("表达清晰", "mostly", "依据"),
            ("可追溯", "barely", "依据"),
        )
        result_below_80 = self.service.score("train-ai-002", LONG_ANSWER, just_below_80)
        self.assertLess(result_below_80["total_score"], 80.0)
        self.assertEqual(0, result_below_80["ability_updates"][0]["level_change"])

        at_40 = signal(
            ("数据准确", "missing", "依据"),
            ("表达清晰", "partial", "依据"),
            ("可追溯", "fully", "依据"),
        )
        result40 = self.service.score("train-ai-002", LONG_ANSWER, at_40)
        self.assertEqual(40.0, result40["total_score"])
        self.assertEqual(0, result40["ability_updates"][0]["level_change"])

        just_below_40 = signal(
            ("数据准确", "missing", "依据"),
            ("表达清晰", "missing", "依据"),
            ("可追溯", "mostly", "依据"),
        )
        result_below_40 = self.service.score("train-ai-002", LONG_ANSWER, just_below_40)
        self.assertLess(result_below_40["total_score"], 40.0)
        self.assertEqual(-1, result_below_40["ability_updates"][0]["level_change"])

    def test_score_fallback_window_hit_ratio(self) -> None:
        result = self.service.score("train-remote-001", "信息已经提供且内容完整，充分覆盖。")
        dims = result["dimension_scores"]
        info = dims[0]
        self.assertEqual(round(2 / 3 * 100, 2), info["score"])

    def test_score_fallback_all_windows_hit(self) -> None:
        result = self.service.score("train-remote-001", "信息完整，异步友好，责任清晰，全部覆盖。")
        self.assertEqual(100.0, result["dimension_scores"][0]["score"])

    def test_score_fallback_negation_intercepts(self) -> None:
        blocked = self.service.score(
            "train-remote-003", "本次会议没有分工的相关安排，大家各自处理后汇报进度。"
        )
        self.assertEqual(0.0, blocked["dimension_scores"][0]["score"])

        normal = self.service.score(
            "train-remote-003", "本次会议明确了分工并安排对应角色，指定协调人与时间线跟进计划。"
        )
        self.assertEqual(100.0, normal["dimension_scores"][0]["score"])

    def test_score_fallback_does_not_use_reference_answer(self) -> None:
        reference = self._task("train-remote-001")["reference_answer"]
        result = self.service.score("train-remote-001", reference)
        first = result["dimension_scores"][0]
        self.assertLessEqual(first["score"], 100.0)
        self.assertEqual(0.0, first["score"])

    def test_score_unsupported_inputs_are_fail_safe_and_deterministic(self) -> None:
        invalid = self.service.score("train-ai-001", "答案")
        flags = invalid.get("data_quality_flags", [])
        self.assertEqual("score", invalid["mode"])
        for _ in range(9):
            self.assertEqual(serialize(invalid), serialize(self.service.score("train-ai-001", "答案")))

    def test_score_private_info_returns_error(self) -> None:
        for sensitive in (
            "联系我 demo@example.com",
            "手机号 13800138000",
            "身份证 11010519491231002X",
        ):
            result = self.service.score("train-ai-001", sensitive)
            self.assertIn("error", result)
            self.assertIn("privacy_violation", result["error"])

    def test_score_output_structure_and_criteria_alignment(self) -> None:
        result = self.service.score("train-ai-001", LONG_ANSWER)
        for key in (
            "mode", "training_id", "total_score", "dimension_scores",
            "overall_comment", "improvement_suggestions", "ability_updates",
        ):
            self.assertIn(key, result)
        criteria = self._task("train-ai-001")["evaluation_criteria"]
        self.assertEqual([item["dimension"] for item in criteria],
                         [item["dimension"] for item in result["dimension_scores"]])
        for item in result["dimension_scores"]:
            self.assertIn("comment", item)
        self.assertIn("level_change", result["ability_updates"][0])

    def test_score_main_path_is_deterministic(self) -> None:
        analysis = signal(
            ("信息完整", "mostly", "依据"),
            ("异步友好", "barely", "依据"),
            ("责任清晰", "partial", "依据"),
        )
        first = self.service.score("train-remote-001", LONG_ANSWER, analysis)
        for _ in range(9):
            self.assertEqual(serialize(first), serialize(self.service.score("train-remote-001", LONG_ANSWER, analysis)))

    def test_score_fallback_path_is_deterministic(self) -> None:
        first = self.service.score("train-cross-002", "基于证据展示口径与限制，并统一口径。")
        for _ in range(9):
            self.assertEqual(serialize(first), serialize(self.service.score("train-cross-002", "基于证据展示口径与限制，并统一口径。")))


if __name__ == "__main__":
    unittest.main()