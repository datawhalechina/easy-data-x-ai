"""Unified seekdb connection helpers for X2."""

from __future__ import annotations

import os
import platform
import socket
from typing import Literal

import pyseekdb
from pyseekdb.client.client_seekdb_embedded import _PYLIBSEEKDB_AVAILABLE

from database.collections import DEFAULT_SEEKDB_PATH

DEFAULT_DATABASE = "x2_skills"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2881
DEFAULT_TENANT = "sys"
DEFAULT_USER = "root"

SeekdbMode = Literal["embedded", "server"]


def resolve_mode() -> SeekdbMode:
    """Pick embedded vs server mode from env and platform capabilities."""
    explicit = os.environ.get("SEEKDB_MODE", "").strip().lower()
    if explicit in ("server", "remote"):
        return "server"
    if explicit in ("embedded", "local"):
        return "embedded"
    if os.environ.get("SEEKDB_HOST"):
        return "server"
    if not _PYLIBSEEKDB_AVAILABLE:
        return "server"
    return "embedded"


def server_endpoint() -> tuple[str, int]:
    host = os.environ.get("SEEKDB_HOST", DEFAULT_HOST)
    port = int(os.environ.get("SEEKDB_PORT", str(DEFAULT_PORT)))
    return host, port


def create_client(path: str = DEFAULT_SEEKDB_PATH) -> pyseekdb.Client:
    """Create a pyseekdb client using the resolved deployment mode."""
    mode = resolve_mode()
    database = os.environ.get("SEEKDB_DATABASE", DEFAULT_DATABASE)
    password = os.environ.get("SEEKDB_PASSWORD", "")
    user = os.environ.get("SEEKDB_USER", DEFAULT_USER)
    tenant = os.environ.get("SEEKDB_TENANT", DEFAULT_TENANT)

    if mode == "server":
        host, port = server_endpoint()
        return pyseekdb.Client(
            host=host,
            port=port,
            tenant=tenant,
            database=database,
            user=user,
            password=password,
        )
    return pyseekdb.Client(path=path, database=database)


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def connection_hint(mode: SeekdbMode | None = None) -> str:
    mode = mode or resolve_mode()
    lines = [
        "seekdb 未就绪。请按以下步骤启动：",
        "",
        "  cd code/X2",
        "  docker compose up -d",
        "  python database/check_seekdb.py",
        "",
    ]
    if mode == "server":
        host, port = server_endpoint()
        lines.extend([
            f"  当前配置: {host}:{port} (Server 模式)",
            "  可复制 .env.example 为 .env 后按需修改 SEEKDB_* 变量。",
        ])
    else:
        lines.extend([
            "  Linux 嵌入式模式可直接使用，无需 Docker。",
            f"  数据目录: {DEFAULT_SEEKDB_PATH}",
        ])
    if platform.system() == "Darwin":
        lines.append("")
        lines.append("  提示: macOS 不支持嵌入式 seekdb，课程推荐使用 Docker Server 模式。")
    return "\n".join(lines)


def check_connection(path: str = DEFAULT_SEEKDB_PATH) -> tuple[bool, str]:
    """Return (ok, message). Does not raise."""
    mode = resolve_mode()
    database = os.environ.get("SEEKDB_DATABASE", DEFAULT_DATABASE)

    if mode == "server":
        host, port = server_endpoint()
        if not _port_open(host, port):
            return False, f"无法连接 {host}:{port}\n\n{connection_hint(mode)}"

    try:
        client = create_client(path)
        client.list_collections()
        return True, f"✓ seekdb 可用 ({mode} 模式, database={database})"
    except Exception as exc:
        return False, f"连接失败: {exc}\n\n{connection_hint(mode)}"


def require_connection(path: str = DEFAULT_SEEKDB_PATH) -> pyseekdb.Client:
    ok, message = check_connection(path)
    if not ok:
        raise ConnectionError(message)
    return create_client(path)


def ensure_database(name: str | None = None) -> None:
    """Create the target database if it does not exist (Server mode)."""
    db_name = name or os.environ.get("SEEKDB_DATABASE", DEFAULT_DATABASE)
    mode = resolve_mode()
    if mode != "server":
        return

    import pyseekdb

    host, port = server_endpoint()
    tenant = os.environ.get("SEEKDB_TENANT", DEFAULT_TENANT)
    user = os.environ.get("SEEKDB_USER", DEFAULT_USER)
    password = os.environ.get("SEEKDB_PASSWORD", "")

    admin = pyseekdb.AdminClient(
        host=host,
        port=port,
        tenant=tenant,
        user=user,
        password=password,
    )
    existing = {db.name for db in admin.list_databases()}
    if db_name not in existing:
        admin.create_database(db_name)

