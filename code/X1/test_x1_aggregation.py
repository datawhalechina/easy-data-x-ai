from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


PART1 = Path(__file__).resolve().parent / "part1_decay_conflict"


def load_example(name: str):
    spec = importlib.util.spec_from_file_location(name, PART1 / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolve = load_example("x1_5_conflict_resolve").resolve_conflict
aggregate = load_example("x1_6_retrieval_aggregate").deterministic_aggregate


class MemoryAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture = json.loads((PART1 / "fixtures/sample_memories.json").read_text(encoding="utf-8"))
        self.memories = {memory["id"]: memory for memory in fixture["memories"]}

    def test_deleted_preference_is_not_returned_and_history_is_preserved(self) -> None:
        store = [self.memories["mem_007"]]
        self.assertEqual(aggregate(store, "用户喜欢吃什么？")["result_count"], 1)
        resolve(store, "用户非常讨厌披萨，从来不吃", "DELETE", "mem_007")
        self.assertFalse(store[0]["is_active"])
        self.assertTrue(store[0]["should_forget"])
        before = copy.deepcopy(store)

        result = aggregate(store, "用户喜欢吃什么？")

        self.assertEqual(result["results"], [])
        self.assertEqual(result["result_count"], 0)
        self.assertEqual(store, before)

    def test_all_inactive_candidates_from_different_topics_return_no_results(self) -> None:
        candidates = [self.memories["mem_009"], self.memories["mem_011"]]
        before = copy.deepcopy(candidates)

        result = aggregate(candidates, "用户的技术栈是什么？")

        self.assertEqual(result["results"], [])
        self.assertEqual(result["result_count"], 0)
        self.assertEqual(candidates, before)

    def test_inactive_higher_scoring_topic_does_not_displace_active_memory(self) -> None:
        inactive = {**self.memories["mem_009"], "_sem_score": 1.0}
        active = {**self.memories["mem_012"], "_sem_score": 0.2}
        candidates = [inactive, active]
        before = copy.deepcopy(candidates)

        result = aggregate(candidates, "用户的技术栈是什么？")

        self.assertEqual(result["results"], [active])
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(candidates, before)

    def test_updated_version_is_returned_without_mutating_version_history(self) -> None:
        store = [self.memories["mem_009"]]
        resolve(store, "用户已全面转向 Go 语言开发", "UPDATE", "mem_009")
        before = copy.deepcopy(store)

        result = aggregate(store, "用户用什么编程语言？")

        self.assertEqual(result["results"], [store[1]])
        self.assertEqual(store[1]["replaces"], "mem_009")
        self.assertEqual(store, before)

    def test_coexisting_active_preferences_are_preserved(self) -> None:
        candidates = [self.memories["mem_007"], self.memories["mem_008"]]
        before = copy.deepcopy(candidates)

        result = aggregate(candidates, "用户喜欢吃什么？")

        self.assertEqual(result["results"], candidates)
        self.assertEqual(result["result_count"], 2)
        self.assertEqual(candidates, before)

    def test_empty_candidates_and_implicit_active_default(self) -> None:
        self.assertEqual(aggregate([], "用户喜欢什么？")["result_count"], 0)
        memory = self.memories["mem_007"]
        del memory["is_active"]
        self.assertEqual(aggregate([memory], "用户喜欢吃什么？")["results"], [memory])


if __name__ == "__main__":
    unittest.main()
