import unittest

from app.services.ability_normalization import AbilityTagNormalizer


class AbilityTagNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = AbilityTagNormalizer()

    def test_at_least_twenty_mapping_examples(self):
        examples = [
            ("Python", "Python"),
            ("python", "Python"),
            ("  PYTHON  ", "Python"),
            ("Python开发", "Python"),
            ("Python 编程", "Python"),
            ("Python   编程", "Python"),
            ("Python programming", "Python"),
            ("Python Web", "Python Web开发"),
            ("Python Web Development", "Python Web开发"),
            ("JS", "JavaScript/TypeScript"),
            ("typescript", "JavaScript/TypeScript"),
            ("SQL", "SQL/数据库"),
            ("database", "SQL/数据库"),
            ("K8S", "Docker/K8s"),
            ("Kubernetes", "Docker/K8s"),
            ("Data Analysis", "数据分析"),
            ("Machine Learning", "机器学习"),
            ("ml", "机器学习"),
            ("Deep Learning", "深度学习"),
            ("Frontend Development", "前端开发"),
            ("后端工程", "后端开发"),
            ("Requirement Analysis", "需求分析"),
            ("Product Planning", "产品规划"),
            ("Communication", "沟通表达"),
            ("Teamwork", "团队协作"),
            ("Problem Solving", "解决问题"),
            ("Git", "Git/版本控制"),
            ("检索增强生成", "RAG"),
            ("LLM", "LLM应用开发"),
            ("工具调用", "Tool Calling"),
            ("Model Context Protocol", "MCP"),
        ]
        self.assertGreaterEqual(len(examples), 20)
        for raw_tag, expected in examples:
            with self.subTest(raw_tag=raw_tag):
                result = self.normalizer.normalize(raw_tag)
                self.assertTrue(result["mapped"])
                self.assertEqual(result["original_tag"], raw_tag)
                self.assertEqual(result["standard_tag"], expected)
                self.assertTrue(result["rule_basis"])

    def test_related_but_distinct_capabilities_are_not_merged(self):
        expected = {
            "Python": "Python",
            "Python Web": "Python Web开发",
            "RAG": "RAG",
            "LLM": "LLM应用开发",
            "工具调用": "Tool Calling",
            "MCP": "MCP",
        }
        actual = {
            raw: self.normalizer.normalize(raw)["standard_tag"] for raw in expected
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(set(actual.values())), len(actual))

    def test_unsafe_boundaries_remain_unmapped(self):
        for raw_tag in (
            "Python数据分析",
            "Python/Django/Flask",
            "RAG+LLM",
            "MCP Tool Calling",
            "AI开发",
            "云原生",
            "熟悉多种编程语言",
        ):
            with self.subTest(raw_tag=raw_tag):
                result = self.normalizer.normalize(raw_tag)
                self.assertFalse(result["mapped"])
                self.assertIsNone(result["standard_tag"])
                self.assertIn("不做语义猜测", result["rule_basis"])

    def test_invalid_input_has_explicit_policy(self):
        for raw_tag in (None, "", "   ", 123):
            with self.subTest(raw_tag=raw_tag):
                result = self.normalizer.normalize(raw_tag)
                self.assertFalse(result["mapped"])
                self.assertIsNone(result["standard_tag"])
                self.assertIn("无效输入", result["rule_basis"])

    def test_strict_method_raises_for_unknown_tag(self):
        with self.assertRaisesRegex(ValueError, "cannot be mapped deterministically"):
            self.normalizer.normalize_or_raise("Python和Java")


if __name__ == "__main__":
    unittest.main()
