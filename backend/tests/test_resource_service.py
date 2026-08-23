"""Deterministic ResourceService coverage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from app.services.resource_service import (
    FLAG_JOB_RESOURCES_UNAVAILABLE,
    FLAG_NO_RESOURCE_FOR_TAG,
    FLAG_UNKNOWN_TAG,
    RESOURCE_LIMIT,
    ResourceService,
)

_DATA_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "resources.json"


def load_resources() -> list[dict[str, Any]]:
    with _DATA_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


DATA = load_resources()


def serialize(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def title_list(result: dict[str, Any]) -> list[str]:
    return [item["title"] for item in result["learning_resources"]]


class ResourceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ResourceService(resources=DATA)

    def test_gaps_follow_input_order(self) -> None:
        result = self.service.recommend_resources(["数据分析", "Python", "SQL/数据库"])
        self.assertEqual(
            ["数据分析演示项目", "Python基础演示课程", "SQL练习演示集"],
            title_list(result),
        )

    def test_cross_tag_multi_resources_preserve_group_order(self) -> None:
        result = self.service.recommend_resources(["需求分析", "产品规划"])
        self.assertEqual(
            ["需求分析演示读本", "产品规划演示课程"],
            title_list(result),
        )

    def test_empty_gaps_recommend_all_sorted_and_truncated(self) -> None:
        result = self.service.recommend_resources([])
        self.assertEqual(RESOURCE_LIMIT, len(result["learning_resources"]))
        self.assertEqual(
            [
                "Python基础演示课程",
                "SQL练习演示集",
                "数据分析演示项目",
                "需求分析演示读本",
                "产品规划演示课程",
                "大模型应用演示实验",
                "后端API演示项目",
                "远程协作演示手册",
                "沟通表达演示训练",
                "项目管理认证说明",
            ],
            title_list(result),
        )
        for truncated in ("数据可视化演示课程", "Git协作演示练习"):
            self.assertNotIn(truncated, title_list(result))

    def test_gap_without_resource_produces_flag(self) -> None:
        result = self.service.recommend_resources(["机器学习"])
        self.assertEqual([], result["learning_resources"])
        self.assertIn(f"{FLAG_NO_RESOURCE_FOR_TAG}:机器学习", result["data_quality_flags"])

        combined = self.service.recommend_resources(["机器学习", "数据分析"])
        self.assertEqual(["数据分析演示项目"], title_list(combined))
        self.assertIn(f"{FLAG_NO_RESOURCE_FOR_TAG}:机器学习", combined["data_quality_flags"])

    def test_unknown_tag_is_skipped_with_flag(self) -> None:
        result = self.service.recommend_resources(["未知标签XYZ", "数据分析"])
        self.assertEqual(["数据分析演示项目"], title_list(result))
        self.assertIn(f"{FLAG_UNKNOWN_TAG}:未知标签XYZ", result["data_quality_flags"])

    def test_non_string_gap_is_skipped_with_flag(self) -> None:
        result = self.service.recommend_resources([None, "数据分析"])
        self.assertEqual(["数据分析演示项目"], title_list(result))
        self.assertIn(f"{FLAG_UNKNOWN_TAG}:None", result["data_quality_flags"])

    def test_job_resources_always_empty_with_flag(self) -> None:
        result = self.service.recommend_resources(["数据分析"])
        self.assertEqual([], result["job_resources"])
        self.assertIn(FLAG_JOB_RESOURCES_UNAVAILABLE, result["data_quality_flags"])

    def test_certificate_suggestions_from_certificate_resources(self) -> None:
        result = self.service.recommend_resources(["PMP"])
        self.assertEqual(["PMP"], result["certificate_suggestions"])
        self.assertEqual(["项目管理认证说明"], title_list(result))

        no_cert = self.service.recommend_resources(["沟通表达"])
        self.assertEqual([], no_cert["certificate_suggestions"])

    def test_normalization_variants_match_canonical_resource(self) -> None:
        for gap in ("Python", "python", "  PYTHON  ", "Python 编程", "Python编程"):
            result = self.service.recommend_resources([gap])
            self.assertEqual(["Python基础演示课程"], title_list(result), gap)

    def test_output_fields_exclude_internal_marks(self) -> None:
        result = self.service.recommend_resources(["Python"])
        item = result["learning_resources"][0]
        self.assertEqual(
            {"title", "type", "url", "target_ability", "description"},
            set(item.keys()),
        )
        self.assertNotIn("resource_id", item)
        self.assertNotIn("demo_only", item)

    def test_limit_truncation_when_over_ten_matches(self) -> None:
        many = [
            {
                "resource_id": f"res-m{i:03d}",
                "title": f"资源{i:03d}",
                "type": "course",
                "url": f"https://example.com/{i:03d}",
                "target_ability": "Python",
                "description": "批量演示资源",
                "demo_only": True,
            }
            for i in range(1, 13)
        ]
        service = ResourceService(resources=many)
        result = service.recommend_resources(["Python"])
        self.assertEqual(RESOURCE_LIMIT, len(result["learning_resources"]))
        self.assertEqual(
            ["资源001", "资源002", "资源003", "资源004", "资源005"],
            title_list(result)[:5],
        )

    def test_output_is_deterministic(self) -> None:
        first = self.service.recommend_resources(["需求分析", "机器学习", "产品规划", "未知标签"])
        for _ in range(9):
            self.assertEqual(
                serialize(first),
                serialize(self.service.recommend_resources(["需求分析", "机器学习", "产品规划", "未知标签"])),
            )


if __name__ == "__main__":
    unittest.main()