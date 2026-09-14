#!/usr/bin/env python3
"""检查当前环境是否具备运行课程示例的 seekdb 条件。

在仓库根目录执行：
    .venv/Scripts/python code/check_seekdb_env.py
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seekdb_runtime import embedded_available, resolve_seekdb_mode


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    mode = resolve_seekdb_mode()
    has_embedded = embedded_available()
    print(f"平台 seekdb Embedded 可用: {'是' if has_embedded else '否'}")
    print(f"当前 SEEKDB_MODE 解析结果: {mode}")

    if mode == "embedded" and not has_embedded:
        print(
            "\n❌ Embedded 不可用且未配置 Server。\n"
            "请先启动 Server：\n"
            "  docker compose -f code/docker-compose.yml up -d\n"
            "再设置环境变量后重试：\n"
            "  $env:SEEKDB_MODE='server'\n"
            "  $env:SEEKDB_HOST='127.0.0.1'\n"
            "  $env:SEEKDB_PORT='2881'\n"
            "  $env:SEEKDB_DATABASE='easy_data_x_ai_demo'\n"
            "  $env:SEEKDB_ALLOW_DESTRUCTIVE='1'\n"
        )
        return 1

    if mode == "server":
        host = os.getenv("SEEKDB_HOST", "127.0.0.1")
        port = int(os.getenv("SEEKDB_PORT", "2881"))
        if not _port_open(host, port):
            print(
                f"\n❌ seekdb Server 未监听 {host}:{port}。\n"
                "请执行: docker compose -f code/docker-compose.yml up -d\n"
                "就绪后再次运行本脚本。"
            )
            return 1
        print(f"✓ Server 端口可达: {host}:{port}")
    else:
        print("✓ Embedded 模式可用（无需 Docker）")

    print(
        "\n集成测试额外变量（Windows/macOS 建议设置）：\n"
        "  SEEKDB_TEST_HOST / SEEKDB_TEST_PORT / SEEKDB_TEST_DATABASE\n"
        "  SEEKDB_TEST_X2_DATABASE / SEEKDB_ALLOW_DESTRUCTIVE=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
