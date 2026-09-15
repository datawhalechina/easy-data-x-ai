#!/usr/bin/env python3
"""显式运行仓库中的各组 Python 测试，并阻止零测试误报成功。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class TestGroup:
    name: str
    start_dir: str
    pattern: str
    python_path: str
    timeout_seconds: int = 180


TEST_GROUPS = (
    TestGroup("配置", "code", "test_config.py", "code"),
    TestGroup("seekdb 运行模式", "code", "test_seekdb_runtime.py", "code"),
    TestGroup("seekdb 环境自检", "code", "test_check_seekdb_env.py", "code"),
    TestGroup("测试运行器", "code", "test_run_tests.py", "code"),
    TestGroup("D1 导入路径", "code", "test_example_import_paths.py", "code"),
    TestGroup("D1 工具循环", "code/D1", "test_tool_call_loop.py", "code/D1"),
    TestGroup("D1 可运行性", "code/D1", "test_d1_runnability.py", "code"),
    TestGroup("D2", "code/D2", "test*.py", "code"),
    TestGroup("D3", "code/D3", "test*.py", "code"),
    TestGroup("D4", "code/D4", "test*.py", "code"),
    TestGroup("X1 示例入口", "code/X1", "test*.py", "code/X1"),
    TestGroup("X2", "code/X2/tests", "test*.py", "code/X2"),
    TestGroup("X4", "code/X4/tests", "test*.py", "code"),
    TestGroup("X5 MCP", "code/X5", "test*.py", "code/X5"),
    TestGroup("P5", "code/P5/tests", "test*.py", "code/P5"),
)


def extract_test_count(output: str) -> int:
    """从 unittest 输出提取数量；缺失或为零时直接失败。"""
    matches = re.findall(r"\bRan\s+(\d+)\s+tests?\b", output)
    if len(matches) != 1 or int(matches[0]) == 0:
        raise RuntimeError("测试组没有实际执行任何测试")
    return int(matches[0])


def reject_skipped_tests(output: str) -> None:
    """发布门槛不允许用 skip 代替真实集成验证。"""
    skipped = sum(int(value) for value in re.findall(r"skipped=(\d+)", output))
    if skipped:
        raise RuntimeError(f"测试组跳过了 {skipped} 个测试")


def _text_output(value: str | bytes | None) -> str:
    """兼容不同 Python 版本在超时异常中返回 bytes。"""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run_group(group: TestGroup) -> int:
    env = os.environ.copy()
    python_path = str(REPO_ROOT / group.python_path)
    existing_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        os.pathsep.join((python_path, existing_path))
        if existing_path
        else python_path
    )
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        group.start_dir,
        "-p",
        group.pattern,
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=group.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = _text_output(exc.stdout) + _text_output(exc.stderr)
        print(f"\n===== {group.name} =====")
        if output:
            print(output.rstrip())
        raise RuntimeError(
            f"{group.name} 测试超时（{group.timeout_seconds} 秒）"
        ) from exc
    output = result.stdout + result.stderr
    print(f"\n===== {group.name} =====")
    print(output.rstrip())
    if result.returncode != 0:
        raise RuntimeError(f"{group.name} 测试失败")
    count = extract_test_count(output)
    reject_skipped_tests(output)
    return count


def main() -> int:
    total = 0
    try:
        for group in TEST_GROUPS:
            total += run_group(group)
    except RuntimeError as exc:
        print(f"\n测试运行失败：{exc}", file=sys.stderr)
        return 1
    print(f"\n全部测试通过，共执行 {total} 个测试。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
