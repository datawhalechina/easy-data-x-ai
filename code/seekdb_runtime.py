"""D1～D4 共用的 seekdb Embedded / Server 客户端工厂。"""

from __future__ import annotations

import os
from importlib.util import find_spec
from pathlib import Path

import pyseekdb

EMBEDDED_UNAVAILABLE_HINT = (
    "Embedded 模式依赖 pylibseekdb（当前平台未安装或不支持）。"
    "macOS/Windows 请启动 seekdb Server，并设置：\n"
    "  SEEKDB_MODE=server\n"
    "  SEEKDB_HOST=127.0.0.1\n"
    "  SEEKDB_PORT=2881\n"
    "  SEEKDB_DATABASE=<隔离演示库名>\n"
    "  SEEKDB_ALLOW_DESTRUCTIVE=1  # 仅演示/测试库\n"
    "启动方式见 code/README.md 与 code/docker-compose.yml。"
)


def embedded_available() -> bool:
    """Embedded 仅在安装了平台匹配的 pylibseekdb 时可用。"""
    return find_spec("pylibseekdb") is not None


def resolve_seekdb_mode() -> str:
    """只接受显式 Server 配置，避免环境变量意外指向远端数据库。"""
    mode = os.getenv("SEEKDB_MODE", "").strip().lower()
    if mode in {"server", "remote"}:
        return "server"
    if mode in {"embedded", "local"}:
        return "embedded"
    if mode:
        raise ValueError("SEEKDB_MODE 只能是 embedded 或 server")
    return "embedded"


def _server_port() -> int:
    raw_port = os.getenv("SEEKDB_PORT", "2881")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("SEEKDB_PORT 必须是 1 到 65535 之间的整数") from exc
    if not 1 <= port <= 65535:
        raise ValueError("SEEKDB_PORT 必须是 1 到 65535 之间的整数")
    return port


def create_seekdb_client(path: str | Path):
    """按环境选择客户端；Server 模式不使用本地数据库路径。"""
    if resolve_seekdb_mode() == "server":
        database = os.getenv("SEEKDB_DATABASE", "").strip()
        if not database:
            raise ValueError("Server 模式必须显式配置 SEEKDB_DATABASE")
        return pyseekdb.Client(
            host=os.getenv("SEEKDB_HOST", "127.0.0.1"),
            port=_server_port(),
            tenant=os.getenv("SEEKDB_TENANT", "sys"),
            database=database,
            user=os.getenv("SEEKDB_USER", "root"),
            password=os.getenv("SEEKDB_PASSWORD", ""),
        )
    if not embedded_available():
        raise RuntimeError(EMBEDDED_UNAVAILABLE_HINT)
    return pyseekdb.Client(path=str(Path(path).expanduser().resolve()))


def require_destructive_seekdb_access(action: str) -> None:
    """远端写入/清理必须由调用方显式授权，防止示例误改共享数据库。"""
    if (
        resolve_seekdb_mode() == "server"
        and os.getenv("SEEKDB_ALLOW_DESTRUCTIVE") != "1"
    ):
        raise PermissionError(
            f"{action} 会修改 Server 数据；"
            "请仅对隔离测试库设置 SEEKDB_ALLOW_DESTRUCTIVE=1"
        )
