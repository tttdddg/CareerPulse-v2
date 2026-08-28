"""Unit tests for AntBox-friendly MCP adapter input normalization."""

from __future__ import annotations

import unittest

from app.mcp.input_normalization import (
    normalize_enum_text,
    parse_optional_float,
    parse_optional_int,
    parse_optional_list,
)


class MCPInputNormalizationTests(unittest.TestCase):
    def test_optional_list_accepts_antbox_delimiters_and_empty_values(self) -> None:
        cases = (
            ("Vue, Python, FastAPI", ["Vue", "Python", "FastAPI"]),
            ("Vue，Python，FastAPI", ["Vue", "Python", "FastAPI"]),
            ("Vue、Python、FastAPI", ["Vue", "Python", "FastAPI"]),
            ("Vue\nPython\nFastAPI", ["Vue", "Python", "FastAPI"]),
            ("Vue", ["Vue"]),
            ("", []),
            (None, None),
            ("AI 聊天助手，招聘匹配系统", ["AI 聊天助手", "招聘匹配系统"]),
            ("AI 应用项目", ["AI 应用项目"]),
            ('["Python", "Vue3", "FastAPI"]', ["Python", "Vue3", "FastAPI"]),
            ('["AI, 应用项目", "招聘匹配系统"]', ["AI, 应用项目", "招聘匹配系统"]),
            ("[]", []),
            ([" Vue ", "", "Python"], ["Vue", "Python"]),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(
                    expected,
                    parse_optional_list(raw, field_name="skills"),
                )
        for raw in ('["Python", 3]', '["Python",'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "skills"):
                    parse_optional_list(raw, field_name="skills")

    def test_optional_numbers_accept_strings_and_reject_invalid_values(self) -> None:
        self.assertEqual(4, parse_optional_int("4", field_name="satisfaction"))
        self.assertEqual(4, parse_optional_int("4.0", field_name="satisfaction"))
        self.assertEqual(4, parse_optional_int(4, field_name="satisfaction"))
        self.assertEqual(
            0.5,
            parse_optional_float("0.5", field_name="years_of_experience"),
        )
        self.assertEqual(
            4.0,
            parse_optional_float(4, field_name="years_of_experience"),
        )
        self.assertIsNone(parse_optional_int(None, field_name="job_id"))
        self.assertIsNone(
            parse_optional_float(None, field_name="years_of_experience")
        )
        for raw in ("four", "4.5", "", True):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "satisfaction"):
                    parse_optional_int(raw, field_name="satisfaction")
        for raw in ("unknown", "NaN", "Infinity", "", False):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "years_of_experience"):
                    parse_optional_float(raw, field_name="years_of_experience")

    def test_enum_normalization_maps_only_explicit_aliases(self) -> None:
        aliases = {
            "remote_collaboration": "remote_collaboration",
            "远程协作": "remote_collaboration",
            "AI办公任务": "ai_office_task",
            "跨角色沟通": "cross_role_communication",
        }
        self.assertEqual(
            "remote_collaboration",
            normalize_enum_text(
                "remote_collaboration",
                field_name="training_type",
                aliases=aliases,
                supported_message="supported values are limited",
            ),
        )
        self.assertEqual(
            "remote_collaboration",
            normalize_enum_text(
                "远程协作",
                field_name="training_type",
                aliases=aliases,
                supported_message="supported values are limited",
            ),
        )
        self.assertEqual(
            "ai_office_task",
            normalize_enum_text(
                "AI 办公任务",
                field_name="training_type",
                aliases=aliases,
                supported_message="supported values are limited",
            ),
        )
        self.assertIsNone(
            normalize_enum_text(
                None,
                field_name="training_type",
                aliases=aliases,
                supported_message="supported values are limited",
            )
        )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            normalize_enum_text(
                "AI 应用开发工程师面试自我介绍",
                field_name="training_type",
                aliases=aliases,
                supported_message="supported values are limited",
            )


if __name__ == "__main__":
    unittest.main()
