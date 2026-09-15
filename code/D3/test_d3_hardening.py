import contextlib
import io
import json
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from rag_data import knowledge_chunks

D3_DIR = Path(__file__).resolve().parent


class FakeCollection:
    def __init__(self):
        self.add_calls = []
        self.upsert_calls = []

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)

    def count(self):
        return 13

    def get(self, **kwargs):
        return {"ids": ["kb_013"]}

    def query(self, **kwargs):
        return {
            "documents": [["OB-4.3.0 版本新特性"]],
            "metadatas": [[{"version": "4.3.0"}]],
        }

    def hybrid_search(self, **kwargs):
        return {
            "documents": [["数据库性能优化"]],
            "metadatas": [[{"version": "4.2"}]],
        }


class FakeDatabase:
    def __init__(self):
        self.collection = FakeCollection()
        self.deleted = []
        self.get_or_create_calls = []

    def has_collection(self, name):
        return True

    def delete_collection(self, name):
        self.deleted.append(name)

    def create_collection(self, name):
        return self.collection

    def get_collection(self, name):
        return self.collection

    def get_or_create_collection(self, name):
        self.get_or_create_calls.append(name)
        return self.collection


class FakeMessage:
    def __init__(self, *, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = types.SimpleNamespace(name=name, arguments=arguments)


class SequenceCompletions:
    def __init__(self, messages):
        self._messages = list(messages)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._messages:
            raise AssertionError("模型调用次数超出测试预期")
        message = self._messages.pop(0)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)]
        )


class SequenceClient:
    def __init__(self, messages):
        self.completions = SequenceCompletions(messages)
        self.chat = types.SimpleNamespace(completions=self.completions)


def load_script(filename):
    database = FakeDatabase()
    client_paths = []

    def make_database(*args, **kwargs):
        client_paths.append(kwargs.get("path"))
        return database

    direct_answer = FakeMessage(content="测试回答")
    default_client = SequenceClient([direct_answer] * 20)
    fake_pyseekdb = types.SimpleNamespace(Client=make_database)
    fake_openai = types.SimpleNamespace(OpenAI=lambda **kwargs: default_client)

    with patch.dict(
        sys.modules,
        {"pyseekdb": fake_pyseekdb, "openai": fake_openai},
    ), contextlib.redirect_stdout(io.StringIO()):
        namespace = runpy.run_path(str(D3_DIR / filename), run_name="d3_test")

    return namespace, database, client_paths


def run_create_db_client(filename, *, seekdb_mode="embedded"):
    """加载脚本，并在假 pyseekdb + Embedded 可用前提下执行 create_db_client。

    调用必须发生在 patch 仍生效的上下文内，否则会落到真实 pyseekdb。
    """
    database = FakeDatabase()
    client_paths = []

    def make_database(*args, **kwargs):
        client_paths.append(kwargs.get("path"))
        return database

    direct_answer = FakeMessage(content="测试回答")
    default_client = SequenceClient([direct_answer] * 20)
    fake_pyseekdb = types.SimpleNamespace(Client=make_database)
    fake_openai = types.SimpleNamespace(OpenAI=lambda **kwargs: default_client)

    with (
        patch.dict(
            sys.modules,
            {"pyseekdb": fake_pyseekdb, "openai": fake_openai},
        ),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        namespace = runpy.run_path(str(D3_DIR / filename), run_name="d3_test")
        create_db_client = namespace.get("create_db_client")
        if create_db_client is None:
            raise AssertionError(f"{filename} 未定义 create_db_client")

        import seekdb_runtime

        with (
            patch.dict("os.environ", {"SEEKDB_MODE": seekdb_mode}, clear=False),
            patch.object(seekdb_runtime, "pyseekdb", fake_pyseekdb),
            patch.object(seekdb_runtime, "embedded_available", return_value=True),
        ):
            create_db_client()

    return namespace, database, client_paths


class DatabaseSafetyTests(unittest.TestCase):
    def test_importing_scripts_does_not_open_or_modify_database(self):
        for filename in (
            "d3_1_ingest.py",
            "d3_2_agentic_rag.py",
            "d3_3_compare.py",
            "d3_4_production.py",
        ):
            with self.subTest(filename=filename):
                _, database, client_paths = load_script(filename)
                self.assertEqual([], client_paths)
                self.assertEqual([], database.deleted)

    def test_database_path_is_anchored_to_d3_directory(self):
        expected = D3_DIR / "d3_seekdb"
        for filename in (
            "d3_1_ingest.py",
            "d3_2_agentic_rag.py",
            "d3_3_compare.py",
            "d3_4_production.py",
        ):
            with self.subTest(filename=filename):
                _, _, client_paths = run_create_db_client(filename)
                self.assertEqual([str(expected)], client_paths)

    def test_ingest_reuses_collection_and_upserts_documents(self):
        namespace, _, _ = load_script("d3_1_ingest.py")
        build_knowledge_base = namespace.get("build_knowledge_base")
        self.assertIsNotNone(build_knowledge_base)

        database = FakeDatabase()
        collection = build_knowledge_base(database)

        self.assertEqual(["d3_product_kb"], database.get_or_create_calls)
        self.assertEqual([], database.deleted)
        self.assertEqual([], collection.add_calls)
        self.assertEqual(1, len(collection.upsert_calls))
        self.assertEqual(len(knowledge_chunks), len(collection.upsert_calls[0]["ids"]))

    def test_incremental_update_uses_atomic_upsert(self):
        namespace, _, _ = load_script("d3_4_production.py")
        upsert_document = namespace.get("upsert_document")
        self.assertIsNotNone(upsert_document)

        collection = FakeCollection()
        upsert_document(
            collection,
            {
                "id": "kb_013",
                "content": "新版本",
                "doc_type": "release_notes",
                "version": "4.3.0",
            },
        )

        self.assertEqual([], collection.add_calls)
        self.assertEqual(1, len(collection.upsert_calls))
        self.assertEqual(["kb_013"], collection.upsert_calls[0]["ids"])


class RetrievalTests(unittest.TestCase):
    def test_keyword_extractor_preserves_error_code_and_quarter(self):
        namespace, _, _ = load_script("d3_2_agentic_rag.py")
        extract_search_keyword = namespace.get("extract_search_keyword")
        self.assertIsNotNone(extract_search_keyword)

        self.assertEqual("E-4012", extract_search_keyword("遇到 E-4012 错误怎么解决？"))
        self.assertEqual("Q3", extract_search_keyword("2024年Q3的总营收是多少？"))

    def test_execute_search_uses_extracted_keyword(self):
        namespace, _, _ = load_script("d3_2_agentic_rag.py")
        execute_search = namespace["execute_search"]

        class RecordingCollection(FakeCollection):
            def __init__(self):
                super().__init__()
                self.hybrid_calls = []

            def hybrid_search(self, **kwargs):
                self.hybrid_calls.append(kwargs)
                return {"documents": [["错误码 E-4012"]]}

        collection = RecordingCollection()
        try:
            result = execute_search("遇到 E-4012 错误怎么解决？", collection)
        except TypeError as exc:
            self.fail(f"execute_search 必须支持注入 collection：{exc}")

        self.assertIn("E-4012", result)
        self.assertEqual(
            "E-4012",
            collection.hybrid_calls[0]["query"]["where_document"]["$contains"],
        )


class ToolLoopTests(unittest.TestCase):
    def setUp(self):
        namespace, _, _ = load_script("d3_2_agentic_rag.py")
        self.run_agent_loop = namespace.get("run_agent_loop")

    def require_loop(self):
        self.assertIsNotNone(self.run_agent_loop)
        return self.run_agent_loop

    def test_executes_every_tool_call_in_one_model_message(self):
        run_agent_loop = self.require_loop()
        client = SequenceClient(
            [
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "call_1",
                            "search_knowledge_base",
                            json.dumps({"query": "E-4012"}),
                        ),
                        FakeToolCall(
                            "call_2",
                            "search_knowledge_base",
                            json.dumps({"query": "Q3"}),
                        ),
                    ]
                ),
                FakeMessage(content="综合回答"),
            ]
        )
        queries = []

        answer = run_agent_loop(
            "请综合回答",
            api_client=client,
            search_fn=lambda query: queries.append(query) or f"结果：{query}",
        )

        self.assertEqual("综合回答", answer)
        self.assertEqual(["E-4012", "Q3"], queries)
        tool_messages = [
            item
            for item in client.completions.calls[1]["messages"]
            if isinstance(item, dict) and item.get("role") == "tool"
        ]
        self.assertEqual(["call_1", "call_2"], [item["tool_call_id"] for item in tool_messages])

    def test_rejects_missing_or_duplicate_tool_call_ids_before_search(self):
        run_agent_loop = self.require_loop()
        for calls in (
            [FakeToolCall("", "search_knowledge_base", '{"query": "E-4012"}')],
            [
                FakeToolCall("same", "search_knowledge_base", '{"query": "E-4012"}'),
                FakeToolCall("same", "search_knowledge_base", '{"query": "Q3"}'),
            ],
        ):
            queries = []
            with self.subTest(calls=calls), self.assertRaisesRegex(
                ValueError,
                "id",
            ):
                run_agent_loop(
                    "问题",
                    api_client=SequenceClient([FakeMessage(tool_calls=calls)]),
                    search_fn=lambda query: queries.append(query) or query,
                )
            self.assertEqual([], queries)

    def test_supports_multiple_tool_rounds(self):
        run_agent_loop = self.require_loop()
        client = SequenceClient(
            [
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "call_1",
                            "search_knowledge_base",
                            '{"query": "第一轮"}',
                        )
                    ]
                ),
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "call_2",
                            "search_knowledge_base",
                            '{"query": "第二轮"}',
                        )
                    ]
                ),
                FakeMessage(content="最终回答"),
            ]
        )
        queries = []

        answer = run_agent_loop(
            "多轮问题",
            api_client=client,
            search_fn=lambda query: queries.append(query) or query,
        )

        self.assertEqual("最终回答", answer)
        self.assertEqual(["第一轮", "第二轮"], queries)

    def test_unknown_tool_and_invalid_json_become_tool_errors(self):
        run_agent_loop = self.require_loop()
        client = SequenceClient(
            [
                FakeMessage(
                    tool_calls=[
                        FakeToolCall("call_1", "unknown_tool", "{}"),
                        FakeToolCall(
                            "call_2",
                            "search_knowledge_base",
                            "{bad json",
                        ),
                    ]
                ),
                FakeMessage(content="已根据错误信息调整"),
            ]
        )
        queries = []

        answer = run_agent_loop(
            "错误工具",
            api_client=client,
            search_fn=lambda query: queries.append(query) or query,
        )

        self.assertEqual("已根据错误信息调整", answer)
        self.assertEqual([], queries)
        tool_messages = [
            item
            for item in client.completions.calls[1]["messages"]
            if isinstance(item, dict) and item.get("role") == "tool"
        ]
        self.assertIn("未知工具", tool_messages[0]["content"])
        self.assertIn("参数不是有效 JSON", tool_messages[1]["content"])

    def test_empty_final_content_returns_safe_message(self):
        run_agent_loop = self.require_loop()
        client = SequenceClient([FakeMessage(content=None)])

        answer = run_agent_loop(
            "空响应",
            api_client=client,
            search_fn=lambda query: query,
        )

        self.assertEqual("模型未返回有效内容。", answer)

    def test_stops_after_maximum_tool_rounds(self):
        run_agent_loop = self.require_loop()
        endless_calls = [
            FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        f"call_{index}",
                        "search_knowledge_base",
                        json.dumps({"query": f"query_{index}"}),
                    )
                ]
            )
            for index in range(1, 5)
        ]
        client = SequenceClient(endless_calls)
        queries = []

        answer = run_agent_loop(
            "无限调用",
            api_client=client,
            search_fn=lambda query: queries.append(query) or query,
            max_tool_rounds=2,
        )

        self.assertIn("达到最大工具调用轮数（2）", answer)
        self.assertEqual(["query_1", "query_2"], queries)
        self.assertEqual(3, len(client.completions.calls))

    def test_small_talk_does_not_search_product_knowledge_base(self):
        class PromptAwareCompletions:
            def __init__(self):
                self.calls = []

            def create(inner_self, **kwargs):
                inner_self.calls.append(kwargs)
                system_prompt = kwargs["messages"][0]["content"]
                if "仅当用户询问产品知识" in system_prompt:
                    message = FakeMessage(content="你好！")
                else:
                    message = FakeMessage(
                        tool_calls=[
                            FakeToolCall(
                                "call-chat",
                                "search_knowledge_base",
                                '{"query": "你好"}',
                            )
                        ]
                    )
                return types.SimpleNamespace(
                    id="chatcmpl-offline",
                    object="chat.completion",
                    created=1722144000,
                    model="offline-model",
                    choices=[
                        types.SimpleNamespace(
                            index=0,
                            message=message,
                            finish_reason="stop",
                        )
                    ],
                    usage=types.SimpleNamespace(
                        prompt_tokens=10,
                        completion_tokens=2,
                        total_tokens=12,
                    ),
                )

        completions = PromptAwareCompletions()
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=completions)
        )
        searches = []

        answer = self.require_loop()(
            "你好，今天心情怎么样？",
            api_client=client,
            search_fn=lambda query: searches.append(query) or query,
            max_tool_rounds=0,
        )

        self.assertEqual("你好！", answer)
        self.assertEqual([], searches)


class ProductionDemoToolSafetyTests(unittest.TestCase):
    def test_tool_description_demo_handles_missing_choice_or_message(self):
        namespace, _, _ = load_script("d3_4_production.py")
        ask_with_tool_desc = namespace["ask_with_tool_desc"]

        responses = (
            types.SimpleNamespace(choices=[]),
            types.SimpleNamespace(choices=[types.SimpleNamespace(message=None)]),
        )

        for response in responses:
            with self.subTest(response=response):
                completions = types.SimpleNamespace(create=lambda **_kwargs: response)
                client = types.SimpleNamespace(
                    chat=types.SimpleNamespace(completions=completions)
                )
                result = ask_with_tool_desc(
                    "测试问题",
                    "测试描述",
                    "测试",
                    api_client=client,
                )
                self.assertIn("模型未返回有效内容", result)

    def test_tool_description_demo_handles_untrusted_model_output(self):
        namespace, _, _ = load_script("d3_4_production.py")
        ask_with_tool_desc = namespace["ask_with_tool_desc"]

        cases = [
            (
                FakeMessage(
                    tool_calls=[
                        FakeToolCall("call_1", "unknown_tool", "{}")
                    ]
                ),
                "未知工具",
            ),
            (
                FakeMessage(
                    tool_calls=[
                        FakeToolCall(
                            "call_2",
                            "search_knowledge_base",
                            "{bad json",
                        )
                    ]
                ),
                "参数不是有效 JSON",
            ),
            (FakeMessage(content=None), "未返回有效内容"),
        ]

        for message, expected in cases:
            with self.subTest(expected=expected):
                client = SequenceClient([message])
                try:
                    result = ask_with_tool_desc(
                        "测试问题",
                        "测试描述",
                        "测试",
                        api_client=client,
                    )
                except (KeyError, TypeError, json.JSONDecodeError) as exc:
                    self.fail(f"模型输出不可信时不应崩溃：{exc}")
                self.assertIn(expected, result)


if __name__ == "__main__":
    unittest.main()
