from __future__ import annotations

import os
import sys
import unittest
import subprocess
import tempfile
from contextlib import redirect_stdout
from importlib.util import find_spec
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch


X2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(X2_ROOT))

from models.example import Example
from models.rule import Rule
from models.skill import Skill
from database.schema import EXAMPLES_COLLECTION, RULES_COLLECTION, SKILLS_COLLECTION


def real_database_env() -> dict[str, str]:
    """配置外部测试库时使用 Server；否则在可用时使用 Embedded。

    不在 pylibseekdb 缺失时强行设置 SEEKDB_MODE=embedded，
    否则 Windows/macOS 会撞上与生产 resolve_mode() 不一致的
    “Embedded Client is not available” 崩溃。
    """
    host = os.getenv("SEEKDB_TEST_HOST")
    if host:
        return {
            "SEEKDB_MODE": "server",
            "SEEKDB_HOST": host,
            "SEEKDB_PORT": os.getenv("SEEKDB_TEST_PORT", "2881"),
            "SEEKDB_USER": os.getenv("SEEKDB_TEST_USER", "root"),
            "SEEKDB_PASSWORD": os.getenv("SEEKDB_TEST_PASSWORD", ""),
            "SEEKDB_DATABASE": os.getenv(
                "SEEKDB_TEST_X2_DATABASE",
                "easy_data_x_ai_x2_test",
            ),
        }
    if find_spec("pylibseekdb") is None:
        raise RuntimeError(
            "X2 集成测试需要 seekdb。当前平台没有 pylibseekdb，"
            "Embedded 不可用。请启动 seekdb Server 后设置：\n"
            "  SEEKDB_TEST_HOST=127.0.0.1\n"
            "  SEEKDB_TEST_PORT=2881\n"
            "  SEEKDB_TEST_X2_DATABASE=easy_data_x_ai_x2_test\n"
            "  SEEKDB_ALLOW_DESTRUCTIVE=1\n"
            "启动步骤见 code/X2/README.md（cd code/X2 && docker compose up -d）。"
        )
    return {"SEEKDB_MODE": "embedded", "SEEKDB_DATABASE": "x2_skills"}


def clear_x2_collections(client) -> None:
    """只清理本测试负责的三个集合，保证外部测试库可重复运行。"""
    for name in (SKILLS_COLLECTION, RULES_COLLECTION, EXAMPLES_COLLECTION):
        if client.has_collection(name):
            client.delete_collection(name)


class DatabasePackageTests(unittest.TestCase):
    def test_schema_module_exposes_collection_contract(self) -> None:
        from database import schema

        self.assertEqual(schema.SKILLS_COLLECTION, "x2_skills")
        self.assertEqual(schema.skill_doc_id("demo"), "skill:demo")


class DatabaseIntegrationTests(unittest.TestCase):
    def test_fresh_database_creates_initializes_migrates_and_queries(self) -> None:
        from database.seekdb_client import create_client, ensure_database
        from services.migration_service import MigrationService
        from services.query_service import QueryService
        from storage import create_storage

        skill_markdown = """---
name: embedded-demo
description: Embedded 端到端测试
category: test
---
## Formatting rules
- 必须保留原始标题内容

示例：
```python
print("ok")
```
"""
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            real_database_env(),
            clear=False,
        ):
            skill_file = Path(temp_dir) / "SKILL.md"
            skill_file.write_text(skill_markdown, encoding="utf-8")
            database_path = str(Path(temp_dir) / "seekdb")

            # Embedded 引擎在单个 Python 进程中只能绑定一个数据目录。
            # 建库、客户端绑定和端到端读写必须复用同一路径与生命周期。
            ensure_database(path=database_path)
            with create_client(database_path) as client:
                clear_x2_collections(client)
                self.assertEqual(client.list_collections(), [])

            storage = create_storage(database_path)
            try:
                storage.init(force=True)
                result = MigrationService(storage).migrate_skill_file(str(skill_file))
                complete = QueryService(storage).get_skill_complete("embedded-demo")

                self.assertEqual(result["status"], "success")
                self.assertEqual(complete["skill"]["description"], "Embedded 端到端测试")
                self.assertEqual(complete["rule_count"], 1)
                self.assertEqual(complete["example_count"], 1)
            finally:
                clear_x2_collections(storage.client)
                storage.close()

    def test_init_tool_uses_requested_path_for_database_creation(self) -> None:
        from database import init_seekdb

        storage = unittest.mock.Mock()
        storage.get_migration_summary.return_value = {
            "skill_count": 0,
            "rule_count": 0,
            "example_count": 0,
        }
        with (
            patch.object(init_seekdb, "ensure_database") as ensure,
            patch.object(init_seekdb, "check_connection", return_value=(True, "ok")),
            patch.object(init_seekdb, "create_storage", return_value=storage),
            patch.object(sys, "argv", ["init_seekdb.py", "--db-path", "/tmp/x2-custom"]),
        ):
            init_seekdb.main()

        ensure.assert_called_once_with(path="/tmp/x2-custom")

    def test_storage_init_ensures_database_before_binding_collections(self) -> None:
        from storage import seekdb_storage

        calls: list[str] = []
        storage = seekdb_storage.SeekdbStorage("/tmp/x2-storage")
        with (
            patch.object(
                seekdb_storage,
                "ensure_database",
                side_effect=lambda **_kwargs: calls.append("ensure"),
            ),
            patch.object(
                storage,
                "_bind_collections",
                side_effect=lambda: calls.append("bind"),
            ),
        ):
            storage.init()

        self.assertEqual(calls, ["ensure", "bind"])

    def test_database_admin_client_is_closed_after_creation_check(self) -> None:
        from database import seekdb_client

        class Admin:
            exited = False

            def __enter__(self):
                return self

            def __exit__(self, *_args: Any) -> None:
                self.exited = True

            def list_databases(self):
                return []

            def create_database(self, _name: str) -> None:
                return None

        admin = Admin()
        with (
            patch.dict(os.environ, {"SEEKDB_MODE": "embedded"}, clear=True),
            patch.object(seekdb_client.pyseekdb, "AdminClient", return_value=admin),
        ):
            seekdb_client.ensure_database(path="/tmp/x2-admin-close")

        self.assertTrue(admin.exited)

    def test_connection_check_closes_temporary_client(self) -> None:
        from database import seekdb_client

        class Client:
            exited = False

            def __enter__(self):
                return self

            def __exit__(self, *_args: Any) -> None:
                self.exited = True

            def list_collections(self):
                return []

        client = Client()
        with (
            patch.dict(os.environ, {"SEEKDB_MODE": "embedded"}, clear=True),
            patch.object(seekdb_client, "create_client", return_value=client),
        ):
            ok, _message = seekdb_client.check_connection("/tmp/x2-client-close")

        self.assertTrue(ok)
        self.assertTrue(client.exited)


class SeekdbConfigurationTests(unittest.TestCase):
    def test_x2_env_loads_defaults_without_overriding_system_environment(self) -> None:
        from database.seekdb_client import load_x2_env

        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "SEEKDB_HOST=from-file\nSEEKDB_PORT=2882\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"SEEKDB_HOST": "from-system"}, clear=True):
                load_x2_env(env_path)

                self.assertEqual(os.environ["SEEKDB_HOST"], "from-system")
                self.assertEqual(os.environ["SEEKDB_PORT"], "2882")

    def test_seekdb_port_must_be_in_tcp_range(self) -> None:
        from database.seekdb_client import server_endpoint

        for invalid_port in ("0", "65536", "not-a-port"):
            with self.subTest(port=invalid_port), patch.dict(
                os.environ,
                {"SEEKDB_PORT": invalid_port},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "SEEKDB_PORT"):
                    server_endpoint()

    def test_unready_server_prints_short_chinese_message_and_exits_nonzero(self) -> None:
        from database import check_seekdb
        from database import seekdb_client

        output = StringIO()
        with (
            patch.dict(
                os.environ,
                {
                    "SEEKDB_MODE": "server",
                    "SEEKDB_HOST": "127.0.0.1",
                    "SEEKDB_PORT": "2881",
                },
                clear=True,
            ),
            patch.object(seekdb_client, "_port_open", return_value=False),
            patch.object(sys, "argv", ["check_seekdb.py"]),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            check_seekdb.main()

        self.assertNotEqual(raised.exception.code, 0)
        self.assertIn("seekdb Server 未就绪", output.getvalue())
        self.assertLessEqual(len(output.getvalue().strip().splitlines()), 3)

    def test_invalid_port_process_exits_nonzero(self) -> None:
        env = os.environ.copy()
        env.update({"SEEKDB_MODE": "server", "SEEKDB_PORT": "0"})

        result = subprocess.run(
            [sys.executable, str(X2_ROOT / "database" / "check_seekdb.py")],
            cwd=X2_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SEEKDB_PORT 必须是 1 到 65535 之间的整数", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_init_tool_handles_unready_server_without_traceback(self) -> None:
        from database import init_seekdb

        output = StringIO()
        with (
            patch.object(
                init_seekdb,
                "ensure_database",
                side_effect=ConnectionError("seekdb Server 未就绪：127.0.0.1:2881。"),
            ),
            patch.object(sys, "argv", ["init_seekdb.py"]),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            init_seekdb.main()

        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "seekdb Server 未就绪：127.0.0.1:2881。",
        )

    def test_migrate_tool_handles_unready_server_without_traceback(self) -> None:
        from tools import migrate

        output = StringIO()
        with (
            patch.object(
                migrate,
                "ensure_database",
                side_effect=ConnectionError("seekdb Server 未就绪：127.0.0.1:2881。"),
            ),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            migrate.ensure_storage("unused")

        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "seekdb Server 未就绪：127.0.0.1:2881。",
        )

    def test_query_tool_handles_unready_server_without_traceback(self) -> None:
        from tools import query_tool

        output = StringIO()
        with (
            patch.object(
                query_tool,
                "check_connection",
                return_value=(False, "seekdb Server 未就绪：127.0.0.1:2881。"),
            ),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            query_tool.ensure_storage("unused")

        self.assertNotEqual(raised.exception.code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "seekdb Server 未就绪：127.0.0.1:2881。",
        )


class _HybridCollection:
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.hybrid_kwargs: dict[str, Any] | None = None

    def query(self, **_kwargs: Any) -> dict[str, Any]:
        return self.result

    def hybrid_search(self, **kwargs: Any) -> dict[str, Any]:
        self.hybrid_kwargs = kwargs
        return self.result


class HybridSearchTests(unittest.TestCase):
    def _storage_with_result(self, result: dict[str, Any]):
        from storage.seekdb_storage import SeekdbStorage

        storage = SeekdbStorage("unused")
        collection = _HybridCollection(result)
        storage._skills_col = collection
        storage._ensure_collections = lambda: None
        return storage, collection

    def test_search_uses_fulltext_knn_and_rrf_contract(self) -> None:
        metadata = {
            "name": "api-doc-writing",
            "description": "API documentation",
            "content": "content",
        }
        storage, collection = self._storage_with_result(
            {"ids": [["skill:api-doc-writing"]], "metadatas": [[metadata]]}
        )

        skills = storage.search_skills("API documentation", n_results=3)

        self.assertEqual([skill.name for skill in skills], ["api-doc-writing"])
        self.assertEqual(
            collection.hybrid_kwargs,
            {
                "query": {
                    "where_document": {"$contains": "API documentation"},
                    "n_results": 3,
                },
                "knn": {
                    "query_texts": ["API documentation"],
                    "n_results": 3,
                },
                "rank": {"rrf": {}},
                "n_results": 3,
                "include": ["metadatas"],
            },
        )

    def test_hybrid_search_empty_result_returns_empty_list(self) -> None:
        storage, collection = self._storage_with_result(
            {"ids": [[]], "metadatas": [[]]}
        )

        self.assertEqual(storage.search_skills("not found"), [])
        self.assertIsNotNone(collection.hybrid_kwargs)


class _MemoryStorage:
    def __init__(self, *, existing: bool = True) -> None:
        self.skill = (
            Skill(
                name="rollback-demo",
                description="old description",
                content="old content",
                skill_id="skill:rollback-demo",
            )
            if existing
            else None
        )
        self.rules = (
            [
                Rule(
                    skill_name="rollback-demo",
                    rule_type="format",
                    rule_key="old-rule",
                    rule_value="old rule",
                )
            ]
            if existing
            else []
        )
        self.examples = (
            [
                Example(
                    skill_name="rollback-demo",
                    code="old example",
                    order_index=0,
                )
            ]
            if existing
            else []
        )
        self.fail_new_examples = False

    def snapshot(self) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        return (
            self.skill.to_dict() if self.skill else None,
            [rule.to_dict() for rule in self.rules],
            [example.to_dict() for example in self.examples],
        )

    def get_skill_by_name(self, name: str) -> Skill | None:
        return self.skill if self.skill and self.skill.name == name else None

    def get_rules_by_skill(self, skill_name: str) -> list[Rule]:
        return [rule for rule in self.rules if rule.skill_name == skill_name]

    def get_examples_by_skill(self, skill_name: str) -> list[Example]:
        return [example for example in self.examples if example.skill_name == skill_name]

    def delete_rules_by_skill(self, skill_name: str) -> int:
        old_count = len(self.rules)
        self.rules = [rule for rule in self.rules if rule.skill_name != skill_name]
        return old_count - len(self.rules)

    def delete_examples_by_skill(self, skill_name: str) -> int:
        old_count = len(self.examples)
        self.examples = [
            example for example in self.examples if example.skill_name != skill_name
        ]
        return old_count - len(self.examples)

    def update_skill(self, skill: Skill) -> bool:
        skill.id = self.skill.id
        self.skill = skill
        return True

    def create_skill(self, skill: Skill) -> str:
        skill.id = f"skill:{skill.name}"
        self.skill = skill
        return skill.id

    def delete_skill_by_name(self, name: str) -> bool:
        if self.skill is None or self.skill.name != name:
            return False
        self.skill = None
        self.delete_rules_by_skill(name)
        self.delete_examples_by_skill(name)
        return True

    def insert_rules(self, rules: list[Rule]) -> int:
        self.rules.extend(rules)
        return len(rules)

    def insert_examples(self, examples: list[Example]) -> int:
        if self.fail_new_examples and any(example.code != "old example" for example in examples):
            raise RuntimeError("example write failed")
        self.examples.extend(examples)
        return len(examples)


class ForceMigrationTests(unittest.TestCase):
    def _new_skill_file(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "SKILL.md"
        path.write_text(
            """---
name: rollback-demo
description: new description
---
## Formatting rules
- 必须使用新的标题格式

```python
print("new")
```
""",
            encoding="utf-8",
        )
        return temp_dir, path

    def test_force_extraction_failure_does_not_mutate_existing_records(self) -> None:
        from services import migration_service

        temp_dir, path = self._new_skill_file()
        self.addCleanup(temp_dir.cleanup)
        storage = _MemoryStorage()
        before = storage.snapshot()

        with (
            patch.object(
                migration_service.ExampleExtractor,
                "extract",
                side_effect=ValueError("invalid examples"),
            ),
            self.assertRaisesRegex(ValueError, "invalid examples"),
        ):
            migration_service.MigrationService(storage).migrate_skill_file(
                str(path),
                force=True,
            )

        self.assertEqual(storage.snapshot(), before)

    def test_force_write_failure_restores_existing_skill_rules_and_examples(self) -> None:
        from services.migration_service import MigrationService

        temp_dir, path = self._new_skill_file()
        self.addCleanup(temp_dir.cleanup)
        storage = _MemoryStorage()
        storage.fail_new_examples = True
        before = storage.snapshot()

        with self.assertRaisesRegex(RuntimeError, "example write failed"):
            MigrationService(storage).migrate_skill_file(str(path), force=True)

        self.assertEqual(storage.snapshot(), before)

    def test_new_skill_write_failure_rolls_back_and_can_be_retried(self) -> None:
        from services.migration_service import MigrationService

        temp_dir, path = self._new_skill_file()
        self.addCleanup(temp_dir.cleanup)
        storage = _MemoryStorage(existing=False)
        storage.fail_new_examples = True

        with self.assertRaisesRegex(RuntimeError, "example write failed"):
            MigrationService(storage).migrate_skill_file(str(path))

        self.assertEqual(storage.snapshot(), (None, [], []))

        storage.fail_new_examples = False
        result = MigrationService(storage).migrate_skill_file(str(path))
        self.assertEqual(result["status"], "success")


if __name__ == "__main__":
    unittest.main()
