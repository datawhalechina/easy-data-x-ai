import ast
import math
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from d4_7_hot_cold_tier import calc_retention as tier_retention
from d4_8_memory_cleanup import LifecycleMemoryStore, calc_retention as cleanup_retention


class RetentionHalfLifeTests(unittest.TestCase):
    def test_tier_retention_halves_at_each_configured_interval(self):
        for half_life in (15.0, 30.0, 60.0):
            for intervals, expected in ((0, 1.0), (1, 0.5), (2, 0.25)):
                with self.subTest(half_life=half_life, intervals=intervals):
                    self.assertAlmostEqual(
                        tier_retention(intervals * half_life, 0, half_life),
                        expected,
                    )

    def test_cleanup_retention_halves_since_last_access(self):
        now = datetime(2026, 1, 1)
        for half_life in (15.0, 30.0, 60.0):
            for intervals, expected in ((0, 1.0), (1, 0.5), (2, 0.25)):
                with self.subTest(half_life=half_life, intervals=intervals):
                    memory = LifecycleMemoryStore().add(
                        "A recalled fact",
                        "alice",
                        created_at=now - timedelta(days=365),
                        last_accessed_at=now - timedelta(days=intervals * half_life),
                    )
                    self.assertAlmostEqual(
                        cleanup_retention(memory, now, half_life), expected,
                    )


class RecallHalfLifeTests(unittest.TestCase):
    def test_recall_balances_half_life_with_access_bonus(self):
        now = 1_800_000_000.0
        records = {
            "ids": [["recent", "reinforced"]],
            "documents": [["Recent fact", "Reinforced fact"]],
            "metadatas": [[
                {"created_at": now - 10 * 86400, "access_count": 0},
                {"created_at": now - 30 * 86400, "access_count": 3},
            ]],
        }

        class Collection:
            def count(self):
                return 2

            def query(self, **_kwargs):
                return deepcopy(records)

            def update(self, **kwargs):
                self.updated = kwargs

        for filename, function in (
            ("d4_3_with_memory.py", "search_memory"),
            ("d4_4_memory_agent.py", "recall_memory"),
        ):
            with self.subTest(filename=filename):
                path = Path(__file__).with_name(filename)
                tree = ast.parse(path.read_text(encoding="utf-8"))
                # Load the real retrieval functions without optional API/DB imports.
                functions = [
                    node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name in {function, "_require_memory_collection"}
                ]
                namespace = {"math": math, "time": SimpleNamespace(time=lambda: now)}
                exec(
                    compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"),
                    namespace,
                )
                collection = Collection()
                self.assertEqual(
                    namespace[function]("fact", collection=collection),
                    ["Reinforced fact", "Recent fact"],
                )
                self.assertEqual(collection.updated["ids"], ["recent", "reinforced"])
                self.assertEqual(
                    [meta["access_count"] for meta in collection.updated["metadatas"]],
                    [1, 4],
                )


if __name__ == "__main__":
    unittest.main()
