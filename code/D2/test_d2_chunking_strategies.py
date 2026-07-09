import importlib
import unittest

from D2.d2_chunking_strategies import (
    _detect_boundary_positions,
    semantic_chunk,
)


class SemanticChunkingTests(unittest.TestCase):
    def test_identical_embeddings_do_not_create_breakpoints(self):
        text = "连接池需要合理配置。连接池需要持续监控。连接池需要避免泄漏。"

        def embed_same(sentences):
            return [[1.0, 0.0] for _ in sentences]

        chunks = semantic_chunk(
            text,
            embed_same,
            min_chunk_chars=1,
            max_chunk_chars=1000,
        )

        self.assertEqual(chunks, [text])


class DynamicOverlapTests(unittest.TestCase):
    def test_detects_markdown_structure_boundaries(self):
        text = (
            "# 标题\n"
            "正文段落\n\n"
            "| 字段 | 含义 |\n"
            "| --- | --- |\n"
            "| code | 错误码 |\n\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
        )

        boundaries = _detect_boundary_positions(text)

        self.assertIn(text.index("| 字段 | 含义 |"), boundaries)
        self.assertIn(text.index("```python"), boundaries)
        self.assertIn(text.rindex("```"), boundaries)


class CompareScriptTests(unittest.TestCase):
    def test_compare_script_can_be_imported_as_module(self):
        module = importlib.import_module("D2.d2_5_chunking_compare")

        self.assertTrue(hasattr(module, "main"))


if __name__ == "__main__":
    unittest.main()
