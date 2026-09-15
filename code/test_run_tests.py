from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from run_tests import (
    TEST_GROUPS,
    TestGroup,
    extract_test_count,
    reject_skipped_tests,
    run_group,
)


class TestRunnerSafetyTests(unittest.TestCase):
    def test_extracts_positive_test_count(self) -> None:
        self.assertEqual(extract_test_count("Ran 12 tests in 0.2s"), 12)

    def test_rejects_zero_or_missing_test_count(self) -> None:
        for output in ("Ran 0 tests in 0.0s", "unexpected output"):
            with self.subTest(output=output):
                with self.assertRaisesRegex(RuntimeError, "测试"):
                    extract_test_count(output)

    def test_rejects_ambiguous_or_zero_test_summaries(self) -> None:
        for output in (
            "Ran 1 test\nRan 0 tests\nOK",
            "Ran 2 tests\nRan 2 tests\nOK",
        ):
            with self.subTest(output=output):
                with self.assertRaisesRegex(RuntimeError, "测试"):
                    extract_test_count(output)

    def test_runner_includes_all_standalone_example_groups(self) -> None:
        """防止 D1 可运行性、X1 或 X5 再次从仓库级测试入口中消失。"""
        group_names = {group.name for group in TEST_GROUPS}
        self.assertTrue(
            {"seekdb 运行模式", "seekdb 环境自检", "D1 可运行性", "X1 示例入口", "X5 MCP"}.issubset(
                group_names
            )
        )

    def test_group_timeout_becomes_a_diagnostic_failure(self) -> None:
        group = TestGroup("挂起用例", "code", "test*.py", "code", timeout_seconds=1)
        with (
            patch(
                "run_tests.subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["python"],
                    timeout=1,
                    output=b"partial output",
                ),
            ),
            self.assertRaisesRegex(RuntimeError, "挂起用例.*超时"),
        ):
            run_group(group)

    def test_skipped_tests_are_not_reported_as_fully_verified(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "跳过了 2 个测试"):
            reject_skipped_tests("Ran 10 tests\nOK (skipped=2)")


if __name__ == "__main__":
    unittest.main()
