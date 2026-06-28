"""
Admin client interface and implementation for database management

Also includes ClientProxy for strict separation of Collection vs Database operations
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .database import Database
from .types import _NOT_PROVIDED

if TYPE_CHECKING:
    from .client_base import (
        BaseClient,
        ConfigurationParam,
        EmbeddingFunctionParam,
    )
    from .collection import Collection

SchemaParam = Any  # Type hint placeholder
ConfigurationParam = Any  # Type hint placeholder
EmbeddingFunctionParam = Any  # Type hint placeholder

DEFAULT_TENANT = "test"


class AdminAPI(ABC):
    """
    Abstract admin API interface for database management.
    Defines the contract for database operations.
    """

    @abstractmethod
    def create_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """
        Create database

        Args:
            name: database name
            tenant: tenant name (for OceanBase)
        """
        pass

    @abstractmethod
    def get_database(self, name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """
        Get database object

        Args:
            name: database name
            tenant: tenant name (for OceanBase)

        Returns:
            Database object
        """
        pass

    @abstractmethod
    def delete_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """
        Delete database

        Args:
            name: database name
            tenant: tenant name (for OceanBase)
        """
        pass

    @abstractmethod
    def list_databases(
        self,
        limit: int | None = None,
        offset: int | None = None,
        tenant: str = DEFAULT_TENANT,
    ) -> Sequence[Database]:
        """
        List all databases

        Args:
            limit: maximum number of results to return
            offset: number of results to skip
            tenant: tenant name (for OceanBase)

        Returns:
            Sequence of Database objects
        """
        pass

    @abstractmethod
    def fork_database(self, source_name: str, destination_name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """
        Fork (duplicate) a database to create a new independent copy.

        The destination database is logically equivalent to the source database at the
        fork snapshot moment, containing all user tables and their data. It can be used
        as an independent database for subsequent read/write operations.

        Args:
            source_name: source database name
            destination_name: destination database name (must not already exist)
            tenant: tenant name (for OceanBase)

        Returns:
            Database object for the newly created destination database

        Raises:
            ValueError: If fork is not supported (requires seekdb >= 1.2.0),
                        or if the destination database already exists.
        """
        pass


class _AdminClientProxy(AdminAPI):
    """
    A lightweight facade that delegates all operations to the underlying ServerAPI (BaseClient).
    The actual logic is in the specific client implementations (Embedded/Server/OceanBase).

    Note: This is an internal class. Users should use the AdminClient() factory function.
    """

    _server: "BaseClient"

    def __init__(self, server: "BaseClient") -> None:
        """
        Initialize admin client with a server implementation

        Args:
            server: The underlying client that implements the actual logic
        """
        self._server = server

    def create_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """Proxy to server implementation"""
        return self._server.create_database(name=name, tenant=tenant)

    def get_database(self, name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """Proxy to server implementation"""
        return self._server.get_database(name=name, tenant=tenant)

    def delete_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """Proxy to server implementation"""
        return self._server.delete_database(name=name, tenant=tenant)

    def list_databases(
        self,
        limit: int | None = None,
        offset: int | None = None,
        tenant: str = DEFAULT_TENANT,
    ) -> Sequence[Database]:
        """Proxy to server implementation"""
        return self._server.list_databases(limit=limit, offset=offset, tenant=tenant)

    def fork_database(self, source_name: str, destination_name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """Proxy to server implementation"""
        return self._server.fork_database(source_name=source_name, destination_name=destination_name, tenant=tenant)

    def __repr__(self):
        return f"<AdminClient server={self._server}>"

    def __enter__(self):
        """Context manager support - delegate to server"""
        self._server.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support - delegate to server"""
        return self._server.__exit__(exc_type, exc_val, exc_tb)


class _ClientProxy:
    """
    Internal client proxy for collection operations only.
    Strictly separates collection management from database management.

    Note: This is an internal class. Users should use the Client() factory function.
    """

    _server: "BaseClient"

    def __init__(self, server: "BaseClient") -> None:
        """
        Initialize client with a server implementation

        Args:
            server: The underlying client that implements the actual logic
        """
        self._server = server

    def create_collection(
        self,
        name: str,
        schema: SchemaParam = None,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
        **kwargs,
    ) -> "Collection":
        """Proxy to server implementation - collection operations only"""
        return self._server.create_collection(
            name=name,
            schema=schema,
            configuration=configuration,
            embedding_function=embedding_function,
            **kwargs,
        )

    def get_collection(self, name: str, embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED) -> "Collection":
        """Proxy to server implementation - collection operations only"""
        return self._server.get_collection(name=name, embedding_function=embedding_function)

    def delete_collection(self, name: str) -> None:
        """Proxy to server implementation - collection operations only"""
        return self._server.delete_collection(name=name)

    def list_collections(self) -> list["Collection"]:
        """Proxy to server implementation - collection operations only"""
        return self._server.list_collections()

    def has_collection(self, name: str) -> bool:
        """Proxy to server implementation - collection operations only"""
        return self._server.has_collection(name=name)

    def get_or_create_collection(
        self,
        name: str,
        schema: SchemaParam = None,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
        **kwargs,
    ) -> "Collection":
        """Proxy to server implementation - collection operations only"""
        return self._server.get_or_create_collection(
            name=name,
            schema=schema,
            configuration=configuration,
            embedding_function=embedding_function,
            **kwargs,
        )

    def count_collection(self) -> int:
        """Proxy to server implementation - collection operations only"""
        return self._server.count_collection()

    def __repr__(self):
        return f"<Client server={self._server}>"

    def __enter__(self):
        """Context manager support - delegate to server"""
        self._server.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support - delegate to server"""
        return self._server.__exit__(exc_type, exc_val, exc_tb)
