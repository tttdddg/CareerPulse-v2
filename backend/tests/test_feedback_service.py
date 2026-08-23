"""Deterministic FeedbackService coverage."""

from __future__ import annotations

import json
import unittest
from typing import Any

from app.services.feedback_service import (
    FLAG_COMPETITIVENESS_UNAVAILABLE,
    FLAG_FIRST_GROWTH_SNAPSHOT,
    FLAG_LOW_SATISFACTION_RECORDED,
    TREND_DECLINING,
    TREND_IMPROVING,
    TREND_STABLE,
    TRENDS,
    FeedbackService,
)


def serialize(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class FeedbackServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FeedbackService()

    GAPS = [
        {"dimension": "需求分析", "priority": 1},
        {"dimension": "大模型应用", "priority": 2},
        {"dimension": "项目管理", "priority": 3},
    ]

    def test_validation_rejects_bad_inputs(self) -> None:
        cases = [
            lambda: self.service.save_feedback(session_id=None, user_id="u1", satisfaction=4),
            lambda: self.service.save_feedback(session_id="  ", user_id="u1", satisfaction=4),
            lambda: self.service.save_feedback(session_id="s1", user_id=None, satisfaction=4),
            lambda: self.service.save_feedback(session_id="s1", user_id="", satisfaction=4),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=None),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=0),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=6),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=2.5),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=True),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, path_rating=0),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, path_rating=6),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, training_rating="ok"),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, resource_rating=5.5),
            lambda: self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, resource_rating=True),
        ]
        for make in cases:
            with self.subTest():
                result = make()
                self.assertIn("error", result)

    def test_validation_rejects_private_comments(self) -> None:
        for sensitive in (
            "联系 demo@example.com",
            "手机 13800138000",
            "身份证 11010519491231002X",
        ):
            result = self.service.save_feedback(
                session_id="s1", user_id="u1", satisfaction=4, comments=sensitive
            )
            self.assertIn("error", result)
            self.assertIn("privacy_violation", result["error"])

    def test_save_persists_record_in_memory(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            comments="不错", skill_gaps=self.GAPS, training_target_abilities=["需求分析"],
        )
        self.assertTrue(result["feedback_saved"])

        record = self.service.get_feedback("s1")
        self.assertIsNotNone(record)
        self.assertEqual("s1", record["session_id"])
        self.assertEqual("u1", record["user_id"])
        self.assertEqual(4, record["satisfaction"])
        self.assertEqual(2, record["training_rating"])
        self.assertEqual(["需求分析"], record["training_target_abilities"])

    def test_missing_feedback_record_returns_none(self) -> None:
        self.assertIsNone(self.service.get_feedback("nope"))

    def test_low_training_rating_raises_priority(self) -> None:
        gaps = [
            {"dimension": "需求分析", "priority": 2},
            {"dimension": "大模型应用", "priority": 3},
        ]
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            skill_gaps=gaps, training_target_abilities=["需求分析"],
        )
        updates = result["updated_priorities"]
        self.assertEqual(1, len(updates))
        item = updates[0]
        self.assertEqual("需求分析", item["tag"])
        self.assertEqual(2, item["old_priority"])
        self.assertEqual(1, item["new_priority"])
        self.assertIn("训练反馈低", item["reason"])

    def test_priority_adjustment_floor_is_one(self) -> None:
        gaps = [{"dimension": "需求分析", "priority": 1}]
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            skill_gaps=gaps, training_target_abilities=["需求分析"],
        )
        self.assertEqual(1, result["updated_priorities"][0]["new_priority"])

    def test_high_training_rating_lowers_priority(self) -> None:
        gaps = [
            {"dimension": "需求分析", "priority": 2},
            {"dimension": "大模型应用", "priority": 3},
            {"dimension": "项目管理", "priority": 4},
        ]
        result = self.service.save_feedback(
            session_id="s2", user_id="u1", satisfaction=5, training_rating=5,
            skill_gaps=gaps, training_target_abilities=["需求分析"],
        )
        item = result["updated_priorities"][0]
        self.assertEqual(2, item["old_priority"])
        self.assertEqual(3, item["new_priority"])
        self.assertIn("紧迫度下调", item["reason"])

    def test_priority_adjustment_cap_is_gap_count(self) -> None:
        gaps = [
            {"dimension": "需求分析", "priority": 4},
            {"dimension": "大模型应用", "priority": 5},
        ]
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=5, training_rating=4,
            skill_gaps=gaps, training_target_abilities=["大模型应用"],
        )
        self.assertEqual(2, result["updated_priorities"][0]["new_priority"])

    def test_neutral_rating_does_not_adjust(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=3,
            skill_gaps=self.GAPS, training_target_abilities=["需求分析"],
        )
        self.assertEqual([], result["updated_priorities"])

    def test_target_not_in_gaps_does_not_adjust(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            skill_gaps=self.GAPS, training_target_abilities=["Python"],
        )
        self.assertEqual([], result["updated_priorities"])

    def test_no_skill_gaps_does_not_adjust(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            training_target_abilities=["需求分析"],
        )
        self.assertEqual([], result["updated_priorities"])

    def test_low_satisfaction_blocks_adjustment_with_flag(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=1, training_rating=3,
            skill_gaps=self.GAPS, training_target_abilities=["需求分析"],
        )
        self.assertEqual([], result["updated_priorities"])
        self.assertIn(FLAG_LOW_SATISFACTION_RECORDED, result["data_quality_flags"])

    def test_updated_priorities_item_structure(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, training_rating=2,
            skill_gaps=self.GAPS, training_target_abilities=["需求分析"],
        )
        item = result["updated_priorities"][0]
        for key in ("tag", "old_priority", "new_priority", "reason"):
            self.assertIn(key, item)

    def test_growth_first_snapshot_is_stable(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, overall_score=60.0,
        )
        snapshot = result["growth_snapshot"]
        self.assertEqual(TREND_STABLE, snapshot["growth_trend"])
        self.assertEqual(60.0, snapshot["competitiveness_score"])
        self.assertIn(FLAG_FIRST_GROWTH_SNAPSHOT, result["data_quality_flags"])

    def test_growth_competitiveness_unavailable_flag(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4,
        )
        self.assertEqual(0.0, result["growth_snapshot"]["competitiveness_score"])
        self.assertIn(FLAG_COMPETITIVENESS_UNAVAILABLE, result["data_quality_flags"])

    def test_growth_trend_improving_declining_stable(self) -> None:
        self.service.save_feedback(session_id="s1", user_id="u1", satisfaction=4, overall_score=60.0)
        up = self.service.save_feedback(session_id="s2", user_id="u1", satisfaction=4, overall_score=70.0)
        improve = up["growth_snapshot"]["growth_trend"]
        self.assertEqual(TREND_IMPROVING, improve)
        self.assertNotIn(FLAG_FIRST_GROWTH_SNAPSHOT, up["data_quality_flags"])

        down = self.service.save_feedback(session_id="s3", user_id="u1", satisfaction=4, overall_score=50.0)
        self.assertEqual(TREND_DECLINING, down["growth_snapshot"]["growth_trend"])

        fresh = FeedbackService()
        fresh.save_feedback(session_id="s1", user_id="u2", satisfaction=4, overall_score=60.0)
        same = fresh.save_feedback(session_id="s2", user_id="u2", satisfaction=4, overall_score=60.0)
        self.assertEqual(TREND_STABLE, same["growth_snapshot"]["growth_trend"])

    def test_growth_trend_from_completed_counts(self) -> None:
        fresh = FeedbackService()
        fresh.save_feedback(session_id="s1", user_id="u1", satisfaction=4, completed_trainings=0)
        up = fresh.save_feedback(session_id="s2", user_id="u1", satisfaction=4, completed_trainings=1)
        self.assertEqual(TREND_IMPROVING, up["growth_snapshot"]["growth_trend"])

    def test_only_three_trend_values_are_produced(self) -> None:
        svc = FeedbackService()
        svc.save_feedback(session_id="a", user_id="u", satisfaction=4, overall_score=50.0)
        svc.save_feedback(session_id="b", user_id="u", satisfaction=4, overall_score=70.0)
        svc.save_feedback(session_id="c", user_id="u", satisfaction=4, overall_score=60.0)
        svc.save_feedback(session_id="d", user_id="u", satisfaction=4, overall_score=60.0)
        snapshot = svc.get_growth("u")
        self.assertIsNotNone(snapshot)
        self.assertIn(snapshot["growth_trend"], TRENDS)
        self.assertIn(snapshot["growth_trend"], (TREND_IMPROVING, TREND_DECLINING, TREND_STABLE))

    def test_output_structure(self) -> None:
        result = self.service.save_feedback(
            session_id="s1", user_id="u1", satisfaction=4, overall_score=60.0,
        )
        for key in ("feedback_saved", "growth_archive_updated", "updated_priorities", "growth_snapshot", "data_quality_flags"):
            self.assertIn(key, result)
        self.assertTrue(result["feedback_saved"])
        self.assertTrue(result["growth_archive_updated"])
        for key in ("competitiveness_score", "completed_trainings", "completed_phases", "growth_trend"):
            self.assertIn(key, result["growth_snapshot"])

    def test_is_deterministic_across_fresh_instances(self) -> None:
        kwargs = {
            "session_id": "s1",
            "user_id": "u1",
            "satisfaction": 4,
            "training_rating": 2,
            "comments": "整体不错",
            "skill_gaps": self.GAPS,
            "training_target_abilities": ["需求分析"],
            "overall_score": 60.0,
        }

        def build() -> dict[str, Any]:
            return FeedbackService().save_feedback(**kwargs)

        first = build()
        for _ in range(9):
            self.assertEqual(serialize(first), serialize(build()))


if __name__ == "__main__":
    unittest.main()