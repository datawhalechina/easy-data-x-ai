import unittest

from D1.mock_knowledge_base import search_mock_knowledge_base


class MockKnowledgeBaseTests(unittest.TestCase):
    def test_retrieval_query_returns_only_retrieval_entry(self):
        result = search_mock_knowledge_base("seekdb 支持哪些检索方式？")

        self.assertIn("关键词、语义向量和混合检索", result)
        self.assertNotIn("嵌入模式", result)
        self.assertNotIn("Python SDK", result)

    def test_deployment_query_does_not_match_shared_single_characters(self):
        result = search_mock_knowledge_base("RAG 应用有哪些部署模式？")

        self.assertIn("嵌入模式和服务器模式", result)
        self.assertNotIn("关键词、语义向量", result)
        self.assertNotIn("Python SDK", result)

    def test_sdk_query_returns_only_sdk_entry(self):
        result = search_mock_knowledge_base("pyseekdb SDK 支持什么 API？")

        self.assertIn("Schemaless API", result)
        self.assertNotIn("部署模式", result)
        self.assertNotIn("关键词、语义向量", result)

    def test_unknown_or_blank_query_returns_explicit_miss(self):
        for query in ("价格是多少？", "   "):
            with self.subTest(query=query):
                result = search_mock_knowledge_base(query)

                self.assertIn("没有找到匹配条目", result)
                self.assertNotIn("支持关键词", result)
                self.assertNotIn("嵌入模式", result)
                self.assertNotIn("Python SDK", result)


if __name__ == "__main__":
    unittest.main()
