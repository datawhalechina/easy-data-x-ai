"""
pyseekdb client module

Provides client and admin factory functions with strict separation:

Collection Management (ClientAPI):
- Client() - Smart factory for Embedded/Remote Server mode
- Returns: _ClientProxy (collection operations only)

Database Management (AdminAPI):
- AdminClient() - Smart factory for Embedded/Remote Server mode
- Returns: _AdminClientProxy (database operations only)

All factories use the underlying ServerAPI implementations:
- SeekdbEmbeddedClient - Local seekdb (requires pylibseekdb, Linux only)
- RemoteServerClient - Remote server via pymysql (supports both seekdb Server and OceanBase Server)
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from .admin_client import AdminAPI, _AdminClientProxy, _ClientProxy
from .base_connection import BaseConnection
from .client_base import BaseClient, ClientAPI
from .client_seekdb_server import RemoteServerClient
from .configuration import (
    BengProperties,
    Configuration,
    FulltextIndexConfig,
    HNSWConfiguration,
    IKMode,
    IKProperties,
    Ngram2Properties,
    NgramProperties,
    SpaceProperties,
    SparseVectorIndexConfig,
    VectorIndexConfig,
)
from .database import Database
from .embedding_function import (
    DefaultEmbeddingFunction,
    EmbeddingFunction,
    get_default_embedding_function,
    register_embedding_function,
)
from .query_types import QueryHint
from .schema import Schema
from .sparse_embedding_function import (
    SparseEmbeddingFunction,
    SparseEmbeddingFunctionRegistry,
    SparseVector,
    register_sparse_embedding_function,
)
from .types import K
from .version import Version

if TYPE_CHECKING:
    from .client_seekdb_embedded import SeekdbEmbeddedClient

logger = logging.getLogger(__name__)


def _resolve_password(password: str) -> str:
    """Get password from env if not provided (keeps existing behavior)."""
    return password or os.environ.get("SEEKDB_PASSWORD", "")


def _default_seekdb_path() -> str:
    # Keep existing behavior: default to "seekdb.db" under current working directory.
    return os.path.abspath("seekdb.db")


def _create_server_client(
    *,
    path: str | None,
    host: str | None,
    port: int | None,
    tenant: str,
    database: str,
    user: str | None,
    password: str,
    is_admin: bool,
    **kwargs: Any,
) -> BaseClient:
    """
    Create the underlying server client (single change point).

    Keep simple but clean: only two backends today (embedded vs remote). We still avoid duplicated
    if/else by sharing this helper between Client() and AdminClient().
    """
    if path is not None:
        from .client_seekdb_embedded import SeekdbEmbeddedClient

        if is_admin:
            logger.debug(f"Creating embedded admin client: path={path}")
        else:
            logger.debug(f"Creating embedded client: path={path}, database={database}")
        return SeekdbEmbeddedClient(path=path, database=database, **kwargs)

    if host is not None:
        # Keep existing defaults
        if port is None:
            port = 2881
        if user is None:
            user = "root"
        if is_admin:
            logger.debug(f"Creating remote server admin client: {user}@{tenant}@{host}:{port}")
        else:
            logger.debug(f"Creating remote server client: {user}@{tenant}@{host}:{port}/{database}")
        return RemoteServerClient(
            host=host,
            port=port,
            tenant=tenant,
            database=database,
            user=user,
            password=password,
            **kwargs,
        )

    # Default behavior: embedded mode if available, otherwise require host
    from .client_seekdb_embedded import _PYLIBSEEKDB_AVAILABLE

    if _PYLIBSEEKDB_AVAILABLE:
        from .client_seekdb_embedded import SeekdbEmbeddedClient

        default_path = _default_seekdb_path()
        if is_admin:
            logger.debug(f"Creating embedded admin client (default): path={default_path}")
        else:
            logger.debug(f"Creating embedded client (default): path={default_path}, database={database}")
        return SeekdbEmbeddedClient(path=default_path, database=database, **kwargs)

    raise ValueError(
        "Default embedded mode is not available because pylibseekdb could not be imported. "
        "Please provide host/port parameters to use RemoteServerClient."
    )


def __getattr__(name: str) -> Any:
    """
    Lazily expose optional embedded client symbols.

    This avoids importing pylibseekdb during `import pyseekdb`, which can crash
    on unsupported interpreter/platform combinations (e.g. some Python 3.14 CI environments).
    """
    if name == "SeekdbEmbeddedClient":
        from .client_seekdb_embedded import SeekdbEmbeddedClient

        return SeekdbEmbeddedClient
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "AdminAPI",
    "AdminClient",
    "BaseClient",
    "BaseConnection",
    "BengProperties",
    "Client",
    "ClientAPI",
    "Configuration",
    "Database",
    "DefaultEmbeddingFunction",
    "EmbeddingFunction",
    "FulltextIndexConfig",
    "HNSWConfiguration",
    "IKMode",
    "IKProperties",
    "K",
    "Ngram2Properties",
    "NgramProperties",
    "QueryHint",
    "RemoteServerClient",
    "Schema",
    "SeekdbEmbeddedClient",
    "SpaceProperties",
    "SparseEmbeddingFunction",
    "SparseEmbeddingFunctionRegistry",
    "SparseVector",
    "SparseVectorIndexConfig",
    "VectorIndexConfig",
    "Version",
    "get_default_embedding_function",
    "register_embedding_function",
    "register_sparse_embedding_function",
]


def Client(
    path: str | None = None,
    host: str | None = None,
    port: int | None = None,
    tenant: str = "sys",
    database: str = "test",
    user: str | None = None,
    password: str = "",  # Can be retrieved from SEEKDB_PASSWORD environment variable
    **kwargs,
) -> _ClientProxy:
    """
    Smart client factory function (returns ClientProxy for collection operations only)

    Automatically selects embedded or remote server mode based on parameters:
    - If path is provided, uses embedded mode
    - If host/port is provided, uses remote server mode (supports both seekdb Server and OceanBase Server)
    - If neither path nor host is provided, defaults to embedded mode with current working directory as path

    Returns a ClientProxy that only exposes collection operations.
    For database management, use AdminClient().

    Args:
        path: seekdb data directory path (embedded mode). If not provided and host is also not provided,
              defaults to current working directory
        host: server address (remote server mode)
        port: server port (remote server mode, default 2881)
        tenant: tenant name (remote server mode, default "sys" for seekdb Server, "test" for OceanBase)
        database: database name
        user: username (remote server mode, without tenant suffix)
        password: password (remote server mode). If not provided, will be retrieved from SEEKDB_PASSWORD environment variable
        **kwargs: other parameters

    Returns:
        _ClientProxy: A proxy that only exposes collection operations

    Examples:
        >>> # Embedded mode with explicit path
        >>> client = Client(path="/path/to/seekdb", database="db1")
        >>> client.create_collection("my_collection")  # ✅ Available

        >>> # Embedded mode (default, uses current working directory)
        >>> client = Client(database="db1")
        >>> client.create_collection("my_collection")  # ✅ Available

        >>> # Remote server mode (seekdb Server)
        >>> client = Client(
        ...     host='localhost',
        ...     port=2881,
        ...     tenant="sys",
        ...     database="db1",
        ...     user="root",
        ...     password="pass"
        ... )

        >>> # Remote server mode (OceanBase Server)
        >>> client = Client(
        ...     host='localhost',
        ...     port=2881,
        ...     tenant="test",
        ...     database="db1",
        ...     user="root",
        ...     password="pass"
        ... )
    """
    password = _resolve_password(password)
    server = _create_server_client(
        path=path,
        host=host,
        port=port,
        tenant=tenant,
        database=database,
        user=user,
        password=password,
        is_admin=False,
        **kwargs,
    )

    # Return ClientProxy (only exposes collection operations)
    return _ClientProxy(server=server)


def AdminClient(
    path: str | None = None,
    host: str | None = None,
    port: int | None = None,
    tenant: str = "sys",
    user: str | None = None,
    password: str = "",  # Can be retrieved from SEEKDB_PASSWORD environment variable
    **kwargs,
) -> _AdminClientProxy:
    """
    Smart admin client factory function (proxy pattern)

    Automatically selects embedded or remote server mode based on parameters:
    - If path is provided, uses embedded mode
    - If host/port is provided, uses remote server mode (supports both seekdb Server and OceanBase Server)

    Returns a lightweight AdminClient proxy that only exposes database operations.
    For collection management, use Client().

    Args:
        path: seekdb data directory path (embedded mode)
        host: server address (remote server mode)
        port: server port (remote server mode, default 2881)
        tenant: tenant name (remote server mode, default "sys" for seekdb Server, "test" for OceanBase)
        user: username (remote server mode, without tenant suffix)
        password: password (remote server mode). If not provided, will be retrieved from SEEKDB_PASSWORD environment variable
        **kwargs: other parameters

    Returns:
        _AdminClientProxy: A proxy that only exposes database operations

    Examples:
        >>> # Embedded mode
        >>> admin = AdminClient(path="/path/to/seekdb")
        >>> admin.create_database("new_db")  # ✅ Available
        >>> # admin.create_collection("coll")  # ❌ Not available

        >>> # Remote server mode (seekdb Server)
        >>> admin = AdminClient(
        ...     host='localhost',
        ...     port=2881,
        ...     tenant="sys",
        ...     user="root",
        ...     password="pass"
        ... )

        >>> # Remote server mode (OceanBase Server)
        >>> admin = AdminClient(
        ...     host='localhost',
        ...     port=2881,
        ...     tenant="test",
        ...     user="root",
        ...     password="pass"
        ... )
    """
    password = _resolve_password(password)
    # Keep existing semantics: admin operations always use system database.
    server = _create_server_client(
        path=path,
        host=host,
        port=port,
        tenant=tenant,
        database="information_schema",
        user=user,
        password=password,
        is_admin=True,
        **kwargs,
    )

    # Return AdminClient proxy (only exposes database operations)
    return _AdminClientProxy(server=server)
