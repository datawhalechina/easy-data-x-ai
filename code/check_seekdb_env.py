#!/usr/bin/env python3
"""检查当前环境是否具备运行课程示例的 seekdb 条件。

在仓库根目录执行：
    python code/check_seekdb_env.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seekdb_runtime import embedded_available, resolve_seekdb_mode, server_client_options


def main() -> int:
    try:
        mode = resolve_seekdb_mode()
        options = server_client_options() if mode == "server" else None
    except ValueError as exc:
        print(f"❌ seekdb 配置无效：{exc}")
        return 1
    print(f"当前 SEEKDB_MODE 解析结果: {mode}")

    if mode == "embedded" and not embedded_available():
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

    if options is not None:
        try:
            # 与 pyseekdb 使用相同的 user@tenant 登录格式；不创建库、表或集合。
            with pymysql.connect(
                host=options["host"],
                port=options["port"],
                user=f"{options['user']}@{options['tenant']}",
                password=options["password"],
                database=options["database"],
                charset="utf8mb4",
                connect_timeout=3,
                read_timeout=3,
                write_timeout=3,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    if cursor.fetchone() != (1,):
                        raise ValueError("Server 未返回预期查询结果")
        except (pymysql.MySQLError, OSError, ValueError) as exc:
            print(
                f"\n❌ seekdb Server 连接或查询失败：{exc}\n"
                "请确认 Server 已就绪、账号密码正确，且 SEEKDB_DATABASE 对应的库已创建。\n"
                "准备步骤见 code/README.md。"
            )
            return 1
        print(
            f"✓ Server 登录与只读查询成功："
            f"{options['host']}:{options['port']}/{options['database']}"
        )
    else:
        print("✓ Embedded 原生扩展可加载；数据库初始化请通过示例或集成测试验证。")

    print(
        "\n集成测试额外变量（Windows/macOS 建议设置）：\n"
        "  SEEKDB_TEST_HOST / SEEKDB_TEST_PORT / SEEKDB_TEST_DATABASE\n"
        "  SEEKDB_TEST_X2_DATABASE / SEEKDB_ALLOW_DESTRUCTIVE=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
