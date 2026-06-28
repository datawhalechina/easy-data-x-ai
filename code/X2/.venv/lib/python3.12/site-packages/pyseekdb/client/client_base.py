"""
Base client interface definition
"""

import contextlib
import json
import logging
import re
import struct
import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pymysql.converters import escape_string

from .admin_client import DEFAULT_TENANT, AdminAPI
from .base_connection import BaseConnection
from .collection import Collection
from .configuration import (
    DEFAULT_DISTANCE_METRIC,
    DEFAULT_VECTOR_DIMENSION,
    Configuration,
    ConfigurationParam,
    FulltextIndexConfig,
    HNSWConfiguration,
    VectorIndexConfig,
)
from .database import Database
from .embedding_function import (
    Documents as EmbeddingDocuments,
)
from .embedding_function import (
    EmbeddingFunction,
    EmbeddingFunctionRegistry,
    get_default_embedding_function,
)
from .filters import FilterBuilder
from .meta_info import CollectionFieldNames, CollectionNames
from .query_types import QueryHint
from .schema import Schema, SparseVectorIndexConfig
from .sparse_embedding_function import (
    SparseEmbeddingFunction,
    SparseEmbeddingFunctionRegistry,
    SparseVector,
    _sparse_vector_to_sql,
)
from .sql_utils import _query_hint_to_sql, is_query_sql
from .types import K as FieldKey
from .version import Version

# Type alias for embedding_function parameter that can be EmbeddingFunction, None, or sentinel
EmbeddingFunctionParam = EmbeddingFunction[EmbeddingDocuments] | None | Any

_COLLECTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

# Maximum allowed length for user-facing collection names.
_MAX_COLLECTION_NAME_LENGTH = 512

logger = logging.getLogger(__name__)

from .types import _NOT_PROVIDED, _NotProvided  # noqa: E402, F401


def _extract_hnsw_config(config: ConfigurationParam) -> HNSWConfiguration | None:
    if config is None:
        return None
    elif isinstance(config, HNSWConfiguration):
        return config
    elif isinstance(config, Configuration):
        return config.hnsw
    else:
        raise TypeError(f"configuration must be Configuration, HNSWConfiguration, or None, got {type(config)}")


def _extract_fulltext_config(
    config: ConfigurationParam,
) -> FulltextIndexConfig | None:
    if config is None:
        return None
    elif isinstance(config, HNSWConfiguration):
        # HNSWConfiguration doesn't have fulltext config, return None (will use default)
        return None
    elif isinstance(config, Configuration):
        # If Configuration has fulltext_config, return it; otherwise return None (will use default)
        return config.fulltext_config
    else:
        # Should not reach here due to type checking, but handle gracefully
        return None


def _validate_collection_name(name: str) -> None:
    """
    Validate collection name against allowed charset and length constraints.

    Rules:
    - Type must be str
    - Length between 1 and _MAX_COLLECTION_NAME_LENGTH
    - Only [a-zA-Z0-9_]

    Raises:
        TypeError: If name is not a string.
        ValueError: If name is empty, too long, or contains invalid characters.
    """
    if not isinstance(name, str):
        raise TypeError(
            f"Invalid collection name: '{name}'. Collection name must be a string, got {type(name).__name__}"
        )
    if not name:
        raise ValueError(f"Invalid collection name: '{name}'. Collection name must not be empty")
    if len(name) > _MAX_COLLECTION_NAME_LENGTH:
        raise ValueError(
            f"Invalid collection name: '{name}'. Collection name too long: {len(name)} characters; maximum allowed is {_MAX_COLLECTION_NAME_LENGTH}."
        )
    if _COLLECTION_NAME_PATTERN.match(name) is None:
        raise ValueError(
            f"Invalid collection name: '{name}'. Collection name contains invalid characters. "
            "Only letters, digits, and underscore are allowed: [a-zA-Z0-9_]"
        )


def _get_fulltext_index_sql(
    fulltext_config: FulltextIndexConfig | None = None,
) -> str:
    """
    Generate FULLTEXT INDEX SQL clause from fulltext configuration.

    Args:
        fulltext_config: FulltextIndexConfig or None. If None, defaults to IK parser.

    Returns:
        SQL clause string for FULLTEXT INDEX (e.g., "WITH PARSER ik" or "WITH PARSER ngram PARSER_PROPERTIES=(size=2)")
    """
    if fulltext_config is None:
        # Default to IK parser for backward compatibility
        return "WITH PARSER ik"

    parser_name = fulltext_config.analyzer
    properties = fulltext_config.properties or {}

    # Build SQL clause with parser name
    if properties:
        # Format parameters as key=value pairs
        # Quote string values, leave numbers and booleans as-is
        param_parts = []
        for k, v in properties.items():
            if isinstance(v, str):
                param_parts.append(f"{k}='{v}'")
            else:
                param_parts.append(f"{k}={v}")
        param_str = ", ".join(param_parts)
        return f"WITH PARSER {parser_name} PARSER_PROPERTIES=({param_str})"
    else:
        return f"WITH PARSER {parser_name}"


def _get_vector_index_sql(hnsw_config: HNSWConfiguration) -> str:
    """
    Generate VECTOR INDEX SQL clause from HNSWConfiguration.
    """
    properties = hnsw_config.properties or {}
    property_parts = []
    for k, v in properties.items():
        if isinstance(v, str):
            property_parts.append(f"{k}='{v}'")
        else:
            property_parts.append(f"{k}={v}")
    optional_fields = (
        ("M", hnsw_config.M),
        ("ef_construction", hnsw_config.ef_construction),
        ("ef_search", hnsw_config.ef_search),
        ("extra_info_max_size", hnsw_config.extra_info_max_size),
        ("refine_k", hnsw_config.refine_k),
        ("refine_type", hnsw_config.refine_type),
        ("bq_bits_query", hnsw_config.bq_bits_query),
        ("bq_use_fht", hnsw_config.bq_use_fht),
    )
    for key, value in optional_fields:
        if value is not None:
            if isinstance(value, str):
                property_parts.append(f"{key}='{value}'")
            elif isinstance(value, bool):
                property_parts.append(f"{key}={str(value).lower()}")
            else:
                property_parts.append(f"{key}={value}")
    property_str = ", ".join(property_parts)
    properties_str = f", {property_str}" if property_str else ""
    return f"WITH (DISTANCE={hnsw_config.distance}, TYPE={hnsw_config.type}, LIB={hnsw_config.lib}{properties_str})"


def _get_sparse_vector_index_sql(sparse_config: SparseVectorIndexConfig) -> str:
    """
    Generate VECTOR INDEX SQL clause for sparse vector index from SparseVectorIndexConfig.

    Example output:
        WITH (DISTANCE=inner_product, TYPE=sindi, LIB=vsag)
    """
    parts = [
        f"DISTANCE={sparse_config.distance}",
        f"TYPE={sparse_config.type}",
        f"LIB={sparse_config.lib}",
    ]
    # Add optional parameters only if they differ from defaults
    if sparse_config.prune is not None:
        parts.append(f"prune={str(sparse_config.prune).lower()}")
    if sparse_config.refine is not None:
        parts.append(f"refine={str(sparse_config.refine).lower()}")
    if sparse_config.drop_ratio_build is not None:
        parts.append(f"drop_ratio_build={sparse_config.drop_ratio_build}")
    if sparse_config.drop_ratio_search is not None:
        parts.append(f"drop_ratio_search={sparse_config.drop_ratio_search}")
    if sparse_config.refine_k is not None:
        parts.append(f"refine_k={sparse_config.refine_k}")
    if sparse_config.properties:
        for k, v in sparse_config.properties.items():
            if isinstance(v, str):
                parts.append(f"{k}='{v}'")
            else:
                parts.append(f"{k}={v}")
    return f"WITH ({', '.join(parts)})"


def _embedding_to_hexstring(embedding: list[float]) -> str:
    """
    Convert embedding (list of floats) to a hex string.

    Args:
        embedding: List of floats

    Returns:
        Hex string representing the binary serialization of all floats in the list.
    """
    if not embedding:
        return ""
    # Pack as binary (float32 for compactness, common in vector DBs)
    binary = struct.pack(f"<{len(embedding)}f", *embedding)
    hexstr = binary.hex()
    return f"X'{hexstr}'"


class ClientAPI(ABC):
    """
    Client API interface for collection operations only.
    This is what end users interact with through the Client proxy.
    """

    @abstractmethod
    def create_collection(
        self,
        name: str,
        schema: Schema | None = None,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
        **kwargs,
    ) -> "Collection":
        """
        Create collection

        Args:
            name: Collection name
            schema: Schema configuration for fine-grained index control, including
                   sparse vector index support. When provided, ``configuration`` and
                   ``embedding_function`` parameters are ignored.
            configuration: Index configuration (Configuration or HNSWConfiguration).
                          For backward compatibility, HNSWConfiguration is still accepted.
                          Configuration can include fulltext analyzer configuration (FulltextIndexConfig).
                          Ignored if ``schema`` is provided.
            embedding_function: Embedding function to convert documents to embeddings.
                               Defaults to DefaultEmbeddingFunction.
                               If explicitly set to None, collection will not have an embedding function.
                               Ignored if ``schema`` is provided.
            **kwargs: Additional parameters
        """
        pass

    @abstractmethod
    def get_collection(self, name: str, embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED) -> "Collection":
        """Get an existing collection.

        Args:
            name: The name of the collection to retrieve.
            embedding_function: The embedding function to use. If not provided,
                it will try to load the function used when creating the collection.
                If explicitly set to None, no embedding function will be used.

        Returns:
            The ``Collection`` object.

        Raises:
            ValueError: If the collection does not exist.

        Examples:
            >>> collection = client.get_collection("my_collection")
        """
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete collection"""
        pass

    @abstractmethod
    def list_collections(self) -> list["Collection"]:
        """List all collections"""
        pass

    @abstractmethod
    def has_collection(self, name: str) -> bool:
        """Check if collection exists"""
        pass


@dataclass
class _CollectionMeta:
    """
    Collection metadata in sdk_collections table.
    """

    collection_id: str
    collection_name: str
    settings: str | None

    @staticmethod
    def from_row(row: Any) -> "_CollectionMeta":
        if isinstance(row, dict):
            # Server client returns dict, get the first value
            collection_id = row["COLLECTION_ID"]
            collection_name = row["COLLECTION_NAME"]
            settings = row["SETTINGS"]
        elif isinstance(row, (tuple, list)):
            # Embedded client returns tuple, first element is collection id
            collection_id = row[0] if len(row) > 0 else ""
            collection_name = row[1] if len(row) > 1 else ""
            settings = row[2] if len(row) > 2 else ""
        else:
            raise TypeError(f"Unsupported sdk_collections row type: {type(row).__name__}")
        return _CollectionMeta(collection_id=collection_id, collection_name=collection_name, settings=settings)


class BaseClient(BaseConnection, AdminAPI):
    """
    Abstract base class for all clients.

    Design Pattern:
    1. Provides public collection management methods (create_collection, get_collection, etc.)
    2. Defines internal operation interfaces (_collection_* methods) called by Collection objects
    3. Subclasses implement all abstract methods to provide specific business logic

    Benefits of this design:
    - Collection object interface is unified regardless of which client created it
    - Different clients can have completely different underlying implementations (SQL/gRPC/REST)
    - Easy to extend with new client types

    Inherits connection management from BaseConnection and database operations from AdminAPI.
    """

    # ==================== Database Type Detection ====================

    def detect_db_type_and_version(self) -> tuple[str, "Version"]:  # noqa: C901
        """
        Detect database type and version.

        Works for all three modes: seekdb-embedded, seekdb-server, and oceanbase.
        Version detection is case-insensitive for seekdb.

        Returns:
            (db_type, version): ("seekdb", Version("x.x.x.x")) or ("oceanbase", Version("x.x.x.x"))

        Raises:
            ValueError: If unable to detect database type or version

        Examples:
            >>> db_type, version = client.detect_db_type_and_version()
            >>> version > Version("1.0.0.0")
            True
        """
        from .version import Version

        def _get_value(result, key: str) -> str | None:
            """Extract value from query result"""
            if not result or len(result) == 0:
                return None
            row = result[0]
            if isinstance(row, dict):
                value = row.get(key, "")
            elif isinstance(row, (tuple, list)) and len(row) > 0:
                value = row[0]
            else:
                value = str(row)
            return str(value).strip() if value else None

        def _query(sql: str, key: str) -> str | None:
            """Execute SQL and return value"""
            try:
                result = self._execute(sql)
                return _get_value(result, key)
            except Exception as e:
                logger.debug(f"Failed to execute {sql}: {e}")
                return None

        def _extract_seekdb_version(version_str: str) -> str | None:
            """Extract version from seekdb version string (case-insensitive)"""
            # Use case-insensitive pattern matching
            for pattern in [
                r"seekdb[-\s]v?(\d+\.\d+\.\d+\.\d+)",
                r"seekdb[-\s]v?(\d+\.\d+\.\d+)",
            ]:
                match = re.search(pattern, version_str, re.IGNORECASE)
                if match:
                    return match.group(1)
            return None

        # Ensure connection is established
        self._ensure_connection()

        # Check version() for seekdb (case-insensitive)
        version_result = _query("SELECT version() as version", "version")
        if version_result and re.search(r"seekdb", version_result, re.IGNORECASE):
            seekdb_version_str = _extract_seekdb_version(version_result)
            if seekdb_version_str:
                return ("seekdb", Version(seekdb_version_str))
            else:
                raise ValueError(f"Detected seekdb in version string, but failed to extract version: {version_result}")
        # Query ob_version() for OceanBase
        ob_version_str = _query("SELECT ob_version() as ob_version", "ob_version")
        if ob_version_str:
            # Try to parse OceanBase version (may have different format)
            try:
                return ("oceanbase", Version(ob_version_str))
            except ValueError as e:
                # If OceanBase version doesn't match standard format, try to extract numeric parts
                parts = re.findall(r"\d+", ob_version_str)
                if len(parts) >= 3:
                    # Take first 3 or 4 parts
                    version_str = ".".join(parts[:4] if len(parts) >= 4 else parts[:3])
                    return ("oceanbase", Version(version_str))
                else:
                    # Fallback: return as-is but wrap in Version with minimal format
                    # This handles edge cases where version format is unusual
                    raise ValueError(f"Unable to parse OceanBase version: {ob_version_str}") from e

        # Truncate potentially verbose or sensitive database responses in error message
        def _truncate(val, length=20):
            if val is None:
                return "None"
            val_str = str(val)
            return val_str[:length] + ("..." if len(val_str) > length else "")

        raise ValueError(
            f"Unable to detect database type. version()={_truncate(version_result)}, "
            f"ob_version()={_truncate(ob_version_str)}"
        )

    # ==================== Database Management (User-facing) ====================

    def _database_tenant(self, tenant: str) -> str | None:
        """Resolve effective tenant for database operations."""
        return None

    def _database_context(self, tenant: str | None) -> str:
        return f" in tenant: {tenant}" if tenant else ""

    def _parse_schema_row(self, row: Any) -> tuple[str | None, str | None, str | None]:
        if isinstance(row, dict):
            return (
                row.get("SCHEMA_NAME"),
                row.get("DEFAULT_CHARACTER_SET_NAME"),
                row.get("DEFAULT_COLLATION_NAME"),
            )
        if isinstance(row, (tuple, list)):
            name = row[0] if len(row) > 0 else None
            charset = row[1] if len(row) > 1 else None
            collation = row[2] if len(row) > 2 else None
            return name, charset, collation
        return None, None, None

    def create_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """
        Create database

        Args:
            name: database name
            tenant: tenant name (for OceanBase)
        """
        effective_tenant = self._database_tenant(tenant)
        logger.debug(f"Creating database: {name}{self._database_context(effective_tenant)}")
        sql = f"CREATE DATABASE IF NOT EXISTS `{name}`"
        self._execute(sql)
        logger.debug(f"✅ Database created: {name}{self._database_context(effective_tenant)}")

    def get_database(self, name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """
        Get database object

        Args:
            name: database name
            tenant: tenant name (for OceanBase)
        """
        effective_tenant = self._database_tenant(tenant)
        logger.debug(f"Getting database: {name}{self._database_context(effective_tenant)}")
        sql = (
            "SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
            "FROM information_schema.SCHEMATA "
            f"WHERE SCHEMA_NAME = '{name}'"
        )
        result = self._execute(sql)

        if not result:
            raise ValueError(f"Database not found: {name}")

        db_name, charset, collation = self._parse_schema_row(result[0])
        if not db_name:
            raise ValueError(f"Database not found: {name}")

        return Database(
            name=db_name,
            tenant=effective_tenant,
            charset=charset,
            collation=collation,
        )

    def delete_database(self, name: str, tenant: str = DEFAULT_TENANT) -> None:
        """
        Delete database

        Args:
            name: database name
            tenant: tenant name (for OceanBase)
        """
        effective_tenant = self._database_tenant(tenant)
        logger.debug(f"Deleting database: {name}{self._database_context(effective_tenant)}")
        sql = f"DROP DATABASE IF EXISTS `{name}`"
        self._execute(sql)
        logger.debug(f"✅ Database deleted: {name}{self._database_context(effective_tenant)}")

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
        """
        effective_tenant = self._database_tenant(tenant)
        logger.debug(f"Listing databases{self._database_context(effective_tenant)}")
        sql = "SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA"

        if limit is not None:
            if offset is not None:
                sql += f" LIMIT {offset}, {limit}"
            else:
                sql += f" LIMIT {limit}"

        result = self._execute(sql)

        databases = []
        for row in result:
            db_name, charset, collation = self._parse_schema_row(row)
            if not db_name:
                continue
            databases.append(
                Database(
                    name=db_name,
                    tenant=effective_tenant,
                    charset=charset,
                    collation=collation,
                )
            )

        logger.debug(f"✅ Found {len(databases)} databases{self._database_context(effective_tenant)}")
        return databases

    def fork_database(self, source_name: str, destination_name: str, tenant: str = DEFAULT_TENANT) -> Database:
        """
        Fork (duplicate) a database to create a new independent copy.

        Args:
            source_name: source database name
            destination_name: destination database name (must not already exist)
            tenant: tenant name (for OceanBase)

        Returns:
            Database object for the newly created destination database
        """
        if not self._fork_database_enabled():
            raise ValueError("Fork database is not enabled (requires seekdb >= 1.2.0)")

        effective_tenant = self._database_tenant(tenant)
        logger.debug(f"Forking database: {source_name} -> {destination_name}{self._database_context(effective_tenant)}")
        sql = f"FORK DATABASE `{source_name}` TO `{destination_name}`"
        try:
            self._execute(sql)
        except Exception as ex:
            args = getattr(ex, "args", ())
            if args and isinstance(args[0], int) and args[0] == 1007:
                raise ValueError(f"Database '{destination_name}' already exists") from ex

            msg = str(ex).lower()
            if ("database exists" in msg or "already exists" in msg) and "database" in msg:
                raise ValueError(f"Database '{destination_name}' already exists") from ex
            raise
        logger.debug(f"✅ Successfully forked database '{source_name}' to '{destination_name}'")
        return self.get_database(destination_name, tenant=tenant)

    # ==================== Collection Management (User-facing) ====================

    def _prepare_schema_parameters(  # noqa: C901
        self,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
    ) -> Schema:
        # Handle embedding function first
        # If not provided (sentinel), use default embedding function
        if embedding_function is _NOT_PROVIDED:
            embedding_function = get_default_embedding_function()

        # Calculate actual dimension from embedding function if provided
        actual_dimension = None
        if embedding_function is not None:
            try:
                # First, try to get dimension from the embedding function's dimension property
                # This avoids initializing the model (e.g., onnxruntime) during collection creation
                if hasattr(embedding_function, "dimension"):
                    actual_dimension = embedding_function.dimension
                    logger.debug(f"Using embedding function dimension: {actual_dimension}")
                else:
                    # Fallback: if no dimension attribute, call the function to calculate dimension
                    # This may trigger model initialization, but is necessary for custom embedding functions
                    test_embeddings = embedding_function.__call__("seekdb")
                    if test_embeddings and len(test_embeddings) > 0:
                        actual_dimension = len(test_embeddings[0])
                        logger.info(f"Calculated embedding function dimension: {actual_dimension}")
                    else:
                        raise ValueError(  # noqa: TRY301
                            "Embedding function returned empty result when called with 'seekdb'"
                        )
            except Exception as e:
                raise ValueError(
                    f"Failed to get dimension from embedding function: {e}. "
                    f"Please ensure the embedding function has a 'dimension' attribute or can be called with a string input."
                ) from e

        # Handle configuration
        # Extract HNSWConfiguration from ConfigurationParam (handles both Configuration and HNSWConfiguration)
        hnsw_config = None

        if configuration is _NOT_PROVIDED:
            # Use default configuration, but if embedding_function is provided, use its dimension
            if actual_dimension is not None:
                hnsw_config = HNSWConfiguration(dimension=actual_dimension, distance=DEFAULT_DISTANCE_METRIC)
            else:
                hnsw_config = HNSWConfiguration(dimension=DEFAULT_VECTOR_DIMENSION, distance=DEFAULT_DISTANCE_METRIC)
        elif configuration is None:
            # Configuration is explicitly set to None
            # Try to calculate dimension from embedding_function
            if embedding_function is None:
                raise ValueError(
                    "Cannot create collection: configuration is explicitly set to None and "
                    "embedding_function is also None. Cannot determine dimension without either a configuration "
                    "or an embedding function. Please either:\n"
                    "  1. Provide a configuration with dimension specified (e.g., HNSWConfiguration(dimension=128, distance='cosine')), or\n"
                    "  2. Provide an embedding_function to calculate dimension automatically, or\n"
                    "  3. Do not set configuration=None (use default configuration)."
                )

            # Use calculated dimension from embedding function and default distance metric
            if actual_dimension is not None:
                hnsw_config = HNSWConfiguration(dimension=actual_dimension, distance=DEFAULT_DISTANCE_METRIC)
            else:
                raise ValueError(
                    "Failed to calculate dimension from embedding function. "
                    "Please ensure the embedding function can be called with a string input."
                )
        else:
            # Extract HNSWConfiguration from Configuration or use HNSWConfiguration directly
            hnsw_config = _extract_hnsw_config(configuration)

            # If Configuration was provided but hnsw is None, create default HNSWConfiguration
            if hnsw_config is None:
                if actual_dimension is not None:
                    hnsw_config = HNSWConfiguration(dimension=actual_dimension, distance=DEFAULT_DISTANCE_METRIC)
                else:
                    hnsw_config = HNSWConfiguration(
                        dimension=DEFAULT_VECTOR_DIMENSION,
                        distance=DEFAULT_DISTANCE_METRIC,
                    )

        # If embedding_function is provided, validate configuration dimension matches
        if embedding_function is not None and actual_dimension is not None:
            if hnsw_config.dimension != actual_dimension:
                raise ValueError(
                    f"Configuration dimension ({hnsw_config.dimension}) doesn't match "
                    f"embedding function dimension ({actual_dimension}). "
                    f"Please update configuration to use dimension={actual_dimension} or remove dimension from configuration."
                )
            # Use actual dimension from embedding function
            dimension = actual_dimension
        else:
            # No embedding function, use configuration dimension
            dimension = hnsw_config.dimension

        hnsw_config.dimension = dimension
        fulltext_config = _extract_fulltext_config(configuration)
        vic = VectorIndexConfig(hnsw=hnsw_config)
        vic.embedding_function = embedding_function
        return Schema(
            vector_index=vic,
            fulltext_index=fulltext_config,
        )

    def create_collection(
        self,
        name: str,
        schema: Schema | None = None,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
        **kwargs,
    ) -> "Collection":
        """Create a new collection.

        Args:
            name: The name of the collection to create. Must contain only alphanumeric
                characters or underscores.
            schema: Schema configuration. Defaults to None (uses default schema). Can be a ``Schema`` object.
            configuration: Index configuration. Defaults to None (uses HNSW with
                Cosine distance and dimension 384). Can be a ``Configuration`` or
                ``HNSWConfiguration`` object. If set to None, the dimension will be
                inferred from the embedding function.
            embedding_function: The embedding function to use for this collection.
                Defaults to ``DefaultEmbeddingFunction`` (all-MiniLM-L6-v2). If set to None,
                no embedding function will be used (embeddings must be provided manually).
            **kwargs: Additional parameters for collection creation.

        Returns:
            The created ``Collection`` object.

        Raises:
            ValueError: If the collection name is invalid, already exists, or if the
                configuration/embedding function combination is invalid (e.g., dimension mismatch).
            TypeError: If the configuration object is of an invalid type.

        Examples:
            Create a collection with default settings:

            >>> client.create_collection("my_collection")

            Create a collection with a custom embedding function:

            >>> from pyseekdb import DefaultEmbeddingFunction
            >>> ef = DefaultEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            >>> collection = client.create_collection("my_docs", embedding_function=ef)

            Create a collection with specific configuration:

            >>> from pyseekdb import HNSWConfiguration
            >>> config = HNSWConfiguration(dimension=128, distance="l2")
            >>> collection = client.create_collection(
            ...     "custom_config",
            ...     configuration=config,
            ...     embedding_function=None
            ... )
        """
        _validate_collection_name(name)
        if self.has_collection(name):
            raise ValueError(f"Collection '{name}' already exists")

        # Resolve schema: either use the provided schema or build one from legacy params
        if schema is not None:
            if configuration is not _NOT_PROVIDED or embedding_function is not _NOT_PROVIDED:
                warnings.warn(
                    "schema and configuration/embedding_function are both provided, schema will be used",
                    stacklevel=2,
                )
        else:
            # Legacy path: convert configuration + embedding_function into a Schema
            schema = self._prepare_schema_parameters(configuration, embedding_function)

        logger.debug(f"schema: {schema}")

        # Resolve HNSW configuration dimension if not set
        hnsw_config = schema.vector_index.hnsw
        dense_embedding_function = schema.vector_index.embedding_function
        if hnsw_config is None:
            # Determine dimension from embedding function
            actual_dimension = self._get_embedding_function_dimension(dense_embedding_function)
            hnsw_config = HNSWConfiguration(dimension=actual_dimension, distance=DEFAULT_DISTANCE_METRIC)
        else:
            # Validate dimension matches embedding function if available
            if dense_embedding_function is not None:
                actual_dimension = self._get_embedding_function_dimension(dense_embedding_function)
                if hnsw_config.dimension != actual_dimension:
                    raise ValueError(
                        f"Configuration dimension ({hnsw_config.dimension}) doesn't match "
                        f"embedding function dimension ({actual_dimension})."
                    )

        dimension = hnsw_config.dimension
        if dimension < 1 or dimension > 4096:
            raise ValueError(f"Dimension must be between 1 and 4096, got {dimension}")

        # Extract fulltext parser configuration
        fulltext_index_clause = _get_fulltext_index_sql(schema.fulltext_index)

        # Sparse vector index
        sparse_vector_index_config = schema.sparse_vector_index
        sparse_field_sql = (
            f"{CollectionFieldNames.SPARSE_EMBEDDING} SPARSEVECTOR,\n" if sparse_vector_index_config else ""
        )
        sparse_index_sql = (
            f",\n            VECTOR INDEX idx_sparse ({CollectionFieldNames.SPARSE_EMBEDDING}) {_get_sparse_vector_index_sql(sparse_vector_index_config)}"
            if sparse_vector_index_config
            else ""
        )

        # Construct table name
        collection_id = None
        if kwargs.get("_collection_version", 2) == 1:
            # for testing purpose
            table_name = self._create_collection_meta_v1(name)
        else:
            collection_meta = self._create_collection_meta_v2(
                name, dense_embedding_function, sparse_vector_index_config=sparse_vector_index_config
            )
            collection_id = collection_meta.get("collection_id")
            table_name = collection_meta["table_name"]

        # Construct CREATE TABLE SQL statement with HEAP organization
        sql = f"""CREATE TABLE `{table_name}` (
            _id varbinary(512) PRIMARY KEY NOT NULL,
            document string,
            embedding vector({dimension}),
            {sparse_field_sql}metadata json,
            FULLTEXT INDEX idx_fts(document) {fulltext_index_clause},
            VECTOR INDEX idx_vec (embedding) {_get_vector_index_sql(hnsw_config)}{sparse_index_sql}
        ) ORGANIZATION = HEAP;"""

        # Execute SQL to create table
        logger.debug(f"Creating table: {table_name} with SQL: {sql}")
        self._execute(sql)

        # Create and return Collection object
        return Collection(
            client=self,
            name=name,
            collection_id=collection_id,
            dimension=dimension,
            embedding_function=schema.vector_index.embedding_function,
            distance=hnsw_config.distance,
            sparse_vector_index_config=sparse_vector_index_config,
            **kwargs,
        )

    def _get_embedding_function_dimension(self, embedding_function: EmbeddingFunction) -> int:
        """Get the dimension from an embedding function."""
        try:
            if hasattr(embedding_function, "dimension"):
                dim = embedding_function.dimension
                logger.debug(f"Using embedding function dimension: {dim}")
                return dim
            else:
                test_embeddings = embedding_function.__call__("seekdb")
                if test_embeddings and len(test_embeddings) > 0:
                    dim = len(test_embeddings[0])
                    logger.info(f"Calculated embedding function dimension: {dim}")
                    return dim
                else:
                    raise ValueError(  # noqa: TRY301
                        "Embedding function returned empty result when called with 'seekdb'"
                    )
        except Exception as e:
            raise ValueError(
                f"Failed to get dimension from embedding function: {e}. "
                f"Please ensure the embedding function has a 'dimension' attribute or can be called with a string input."
            ) from e

    def _create_sdk_collections_if_not_exists(self) -> None:
        try:
            create_table_sql = """CREATE TABLE IF NOT EXISTS sdk_collections (
                collection_id CHAR(32) PRIMARY KEY DEFAULT (replace(uuid(), '-', '')),
                collection_name STRING,
                settings JSON COMMENT "Generated by SDK, don't modify",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_name(collection_name)
            ) COMMENT='Settings of collections created by SDK';"""
            self._execute(create_table_sql)
        except Exception as e:
            raise ValueError(f"Failed to create sdk_collections table: {e}") from e

    def _create_collection_meta_v2(
        self,
        collection_name: str,
        embedding_function,
        sparse_vector_index_config: SparseVectorIndexConfig | None = None,
    ) -> dict[str, str]:
        try:
            results = {}
            settings = {"version": 2}
            if embedding_function is not None and EmbeddingFunction.support_persistence(embedding_function):
                settings["embedding_function"] = {
                    "name": embedding_function.name(),
                    "properties": embedding_function.get_config(),
                }

            # Persist sparse vector index config
            if sparse_vector_index_config is not None:
                sparse_settings = {}
                source_key = sparse_vector_index_config.source_key
                if source_key is not None:
                    # Convert FieldKey to string for serialization
                    sparse_settings["source_key"] = source_key.name if hasattr(source_key, "name") else str(source_key)
                sparse_ef = sparse_vector_index_config.embedding_function
                if sparse_ef is not None and SparseEmbeddingFunction.support_persistence(sparse_ef):
                    sparse_settings["embedding_function"] = {
                        "name": sparse_ef.name(),
                        "properties": sparse_ef.get_config(),
                    }
                settings["sparse_vector_index"] = sparse_settings

            settings_str = escape_string(json.dumps(settings))

            self._create_sdk_collections_if_not_exists()
            collection_name_in_table = escape_string(collection_name)
            delete_sql = f"DELETE FROM `{CollectionNames.sdk_collections_table_name()}` WHERE COLLECTION_NAME = '{collection_name_in_table}'"
            self._execute(delete_sql)
            insert_sql = f"INSERT INTO `{CollectionNames.sdk_collections_table_name()}` (COLLECTION_NAME, SETTINGS) VALUES ('{collection_name_in_table}', '{settings_str}')"
            self._execute(insert_sql)
            collection_id = self._get_collection_id(collection_name)
            results["collection_id"] = collection_id
            results["table_name"] = CollectionNames.table_name_v2(collection_id)
            return results  # noqa: TRY300
        except Exception as e:
            raise ValueError(f"Failed to create collection metadata: {e}") from e

    def _create_collection_meta_v1(self, collection_name: str) -> str:
        try:
            table_name = CollectionNames.table_name(collection_name)
            return table_name  # noqa: TRY300
        except Exception as e:
            raise ValueError(f"Failed to create collection metadata: {e}") from e

    def get_collection(self, name: str, embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED) -> "Collection":
        try:
            collection = self._get_collection_v1(name, embedding_function)
        except ValueError as e:
            logger.debug(f"Failed to get collection v1: {e}, trying v2...")
            collection = self._get_collection_v2(name, embedding_function)
        return collection

    def _resolve_collection_metadata_from_sdk_collections(self, collection_name: str) -> _CollectionMeta | None:
        """
        Resolve collection metadata infromation from sdk_collections table
        """
        try:
            query_sql = f"SELECT COLLECTION_ID, COLLECTION_NAME, SETTINGS FROM `{CollectionNames.sdk_collections_table_name()}` WHERE COLLECTION_NAME = '{collection_name}'"
            rows = self._execute(query_sql)
            if rows:
                return _CollectionMeta.from_row(rows[0])

            # not a v2 collection
            show_tables_sql = f"SHOW TABLES LIKE '{CollectionNames.table_name(collection_name)}'"
            result = self._execute(show_tables_sql)
            if result:
                return _CollectionMeta(collection_id=None, collection_name=collection_name, settings=None)
        except Exception as e:
            raise ValueError(f"Failed to resolve collection metadata from sdk_collections table: {e}") from e
        return None

    def _resolve_collection_metadata_from_table(self, table_name: str, collection_name: str) -> dict[str, Any]:  # noqa: C901
        """
        Resolve collection metadata infromation from collection table (not sdk_collections table)
        """
        metadata = {
            "dimension": None,
            "distance": None,
        }
        # Check if table exists by describing it
        try:
            table_info = self._execute(f"DESCRIBE `{table_name}`")
            if not table_info or len(table_info) == 0:
                raise ValueError(  # noqa: TRY301
                    f"Collection ('{collection_name}') not found: Table('{table_name}') not exists"
                )
        except Exception as e:
            # If DESCRIBE fails, check if it's because table doesn't exist
            error_msg = str(e).lower()
            if "doesn't exist" in error_msg or "not found" in error_msg or "table" in error_msg:
                raise ValueError(f"Collection ('{collection_name}') not found: Table('{table_name}') not exists") from e
            raise

        # Extract dimension from embedding column
        for row in table_info:
            # Handle both dict and tuple formats
            if isinstance(row, dict):
                field_name = row.get("Field", row.get("field", ""))
                field_type = row.get("Type", row.get("type", ""))
            elif isinstance(row, (tuple, list)):
                field_name = row[0] if len(row) > 0 else ""
                field_type = row[1] if len(row) > 1 else ""
            else:
                continue

            if field_name == "embedding" and "vector" in str(field_type).lower():
                # Extract dimension from vector(dimension) format
                match = re.search(r"vector\s*\(\s*(\d+)\s*\)", str(field_type), re.IGNORECASE)
                if match:
                    metadata["dimension"] = int(match.group(1))
                break

        # Extract distance from CREATE TABLE statement
        try:
            create_table_result = self._execute(f"SHOW CREATE TABLE `{table_name}`")
            if create_table_result and len(create_table_result) > 0:
                # Handle both dict and tuple formats
                if isinstance(create_table_result[0], dict):
                    create_stmt = create_table_result[0].get(
                        "Create Table", create_table_result[0].get("create table", "")
                    )
                elif isinstance(create_table_result[0], (tuple, list)):
                    # CREATE TABLE statement is usually in the second column
                    create_stmt = create_table_result[0][1] if len(create_table_result[0]) > 1 else ""
                else:
                    create_stmt = str(create_table_result[0])

                # Extract distance from VECTOR INDEX ... with(distance=..., ...)
                # Pattern: VECTOR INDEX ... with(distance=l2, ...) or with(distance='l2', ...)
                # Match: with(distance=value, ...) where value can be l2, cosine, inner_product, or ip
                distance_match = re.search(
                    r'with\s*\([^)]*distance\s*=\s*([\'"]?)(\w+)\1',
                    create_stmt,
                    re.IGNORECASE,
                )
                if distance_match:
                    distance = metadata["distance"] = distance_match.group(2).lower()
                    # Normalize distance values
                    if distance == "ip":
                        distance = "inner_product"
                    elif distance in ["l2", "cosine", "inner_product"]:
                        pass
                    else:
                        # Unknown distance, default to None
                        logger.warning(
                            f"Unknown distance value '{distance}' in CREATE TABLE statement, defaulting to None"
                        )
                        metadata["distance"] = None
        except Exception as e:
            # If SHOW CREATE TABLE fails, log warning but continue
            logger.warning(f"Failed to get CREATE TABLE statement for '{table_name}': {e}")

        return metadata

    def _resolve_embedding_function(self, settings: str | None) -> EmbeddingFunction[EmbeddingDocuments]:
        if not settings:
            return None
        settings_json = json.loads(settings)
        ef_settings = settings_json.get("embedding_function", {})
        ef_name = ef_settings.get("name", "")
        if not ef_name:
            return None
        embedding_function_class = EmbeddingFunctionRegistry.get_class(ef_name)
        if not embedding_function_class:
            raise ValueError(f"Embedding function class '{ef_name}' not found")
        return embedding_function_class.build_from_config(ef_settings.get("properties", {}))

    def _resolve_sparse_vector_index_config(self, settings: str | None) -> SparseVectorIndexConfig | None:
        """Restore SparseVectorIndexConfig from persisted settings JSON."""
        if not settings:
            return None
        settings_json = json.loads(settings)
        sparse_settings = settings_json.get("sparse_vector_index")
        if not sparse_settings:
            return None

        # Resolve sparse embedding function (required)
        sparse_ef = None
        ef_info = sparse_settings.get("embedding_function")
        if not ef_info:
            raise ValueError("Sparse vector index settings missing required embedding_function configuration")

        ef_name = ef_info.get("name", "")
        if not ef_name:
            raise ValueError("Sparse vector index settings missing embedding_function name")

        sparse_ef_class = SparseEmbeddingFunctionRegistry.get_class(ef_name)
        if sparse_ef_class is None:
            raise ValueError(f"Sparse embedding function class '{ef_name}' not found in registry")
        sparse_ef = sparse_ef_class.build_from_config(ef_info.get("properties", {}))

        # Resolve source_key
        source_key_str = sparse_settings.get("source_key")
        source_key = FieldKey.DOCUMENT
        if source_key_str:
            if source_key_str == "#document" or source_key_str == FieldKey.DOCUMENT.name:
                source_key = FieldKey.DOCUMENT
            else:
                source_key = source_key_str

        return SparseVectorIndexConfig(
            embedding_function=sparse_ef,
            source_key=source_key,
        )

    def _validate_embedding_function(
        self,
        embedding_function: EmbeddingFunction | None,
        embedding_function_persistence: EmbeddingFunction | None,
    ) -> EmbeddingFunction[EmbeddingDocuments]:
        """
        Validate embedding function

        Args:
            embedding_function: Embedding function user provided
            embedding_function_persistence: Embedding function restored from table metadata

        Returns:
            Embedding function
        """

        if embedding_function_persistence is not None and embedding_function is not _NOT_PROVIDED:
            if embedding_function is None or embedding_function_persistence.name() != embedding_function.name():
                raise ValueError(
                    "Both embedding function from parameter (not _NOT_PROVIDED, default value) and embedding function from persistence provided."
                )
            else:
                return embedding_function_persistence
        if embedding_function is _NOT_PROVIDED:
            return (
                embedding_function_persistence
                if embedding_function_persistence is not None
                else get_default_embedding_function()
            )
        else:
            return embedding_function

    def _get_collection_v2(self, name: str, embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED) -> "Collection":
        collection_meta = self._resolve_collection_metadata_from_sdk_collections(name)
        if not collection_meta or not collection_meta.collection_id:
            raise ValueError(f"Collection '{name}' does not exist")

        try:
            embedding_function_persistence = self._resolve_embedding_function(collection_meta.settings)
            embedding_function = self._validate_embedding_function(embedding_function, embedding_function_persistence)
            metadata = self._resolve_collection_metadata_from_table(
                CollectionNames.table_name_v2(collection_meta.collection_id), name
            )

            # Resolve sparse vector index config from persisted settings
            sparse_vector_index_config = self._resolve_sparse_vector_index_config(collection_meta.settings)

            return Collection(
                client=self,
                name=name,
                collection_id=collection_meta.collection_id,
                embedding_function=embedding_function,
                dimension=metadata["dimension"],
                distance=metadata["distance"],
                sparse_vector_index_config=sparse_vector_index_config,
            )
        except Exception as e:
            raise ValueError(f"Failed to get collection: {e}") from e

    def _get_collection_v1(self, name: str, embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED) -> "Collection":
        """
        Get a collection object (user-facing API)

        Args:
            name: Collection name
            embedding_function: Embedding function to convert documents to embeddings.
                               Defaults to DefaultEmbeddingFunction.
                               If explicitly set to None, collection will not have an embedding function.

        Returns:
            Collection object

        Raises:
            ValueError: If collection does not exist
        """
        # Construct table name
        table_name = CollectionNames.table_name(name)

        metadata = self._resolve_collection_metadata_from_table(table_name, name)

        # Handle embedding function
        # If not provided (sentinel), use default embedding function
        if embedding_function is _NOT_PROVIDED:
            embedding_function = get_default_embedding_function()

        # Create and return Collection object
        return Collection(client=self, name=name, embedding_function=embedding_function, **metadata)

    def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: The name of the collection to delete.

        Raises:
            ValueError: If the collection does not exist.

        Examples:
            >>> client.delete_collection("my_collection")
        """
        try:
            self._delete_collection_v2(name)
            logger.debug(f"✅ Successfully deleted collection v2 '{name}' from sdk_collections table")
        except ValueError:
            self._delete_collection_v1(name)
            logger.debug(f"✅ Successfully deleted collection v1 '{name}' from table")

    def _delete_collection_v2(self, name: str) -> None:
        """
        Delete a collection (user-facing API)

        Args:
            name: Collection name
        """
        collection = self._get_collection_v2(name)
        if not collection:
            raise ValueError(f"Collection '{name}' does not exist")
        drop_table_sql = f"DROP TABLE `{CollectionNames.table_name_v2(collection.id)}`"
        query_sql = f"DELETE FROM `{CollectionNames.sdk_collections_table_name()}` WHERE COLLECTION_NAME = '{name}'"
        self._execute(drop_table_sql)
        self._execute(query_sql)
        logger.debug(f"✅ Successfully deleted collection '{name}' from sdk_collections table")

    def _delete_collection_v1(self, name: str) -> None:
        """
        Delete a collection (user-facing API)

        Args:
            name: Collection name

        Raises:
            ValueError: If collection does not exist
        """
        # Construct table name
        table_name = CollectionNames.table_name(name)

        # Check if table exists first
        if not self._has_collection_v1(name):
            raise ValueError(f"Collection '{name}' does not exist")

        # Execute DROP TABLE SQL
        self._execute(f"DROP TABLE IF EXISTS `{table_name}`")

    def list_collections(self) -> list["Collection"]:
        """List all collections in the database.

        Returns:
            A list of ``Collection`` objects.

        Examples:
            >>> collections = client.list_collections()
            >>> for col in collections:
            ...     print(col.name)
        """
        collections = self._list_collections_v1()
        collections.extend(self._list_collections_v2())
        return collections

    def _list_collections_v2(self) -> list["Collection"]:
        collections = []
        try:
            # Detect if the sdk_collections table exists before querying it
            sdk_collections_table = CollectionNames.sdk_collections_table_name()
            has_sdk_collections = False
            try:
                check_table_sql = f"SHOW TABLES LIKE '{sdk_collections_table}'"
                check_result = self._execute(check_table_sql)
                if check_result:
                    # Table exists (SHOW TABLES LIKE returns at least one row if exists)
                    has_sdk_collections = True
            except Exception:
                has_sdk_collections = False

            if has_sdk_collections:
                query_sql = f"SELECT COLLECTION_NAME FROM {sdk_collections_table}"
                rows = self._execute(query_sql)
                for row in rows:
                    try:
                        # Extract collection name
                        if isinstance(row, dict):
                            # Server client returns dict, get the first value
                            collection_name = next(iter(row.values()), "")
                        elif isinstance(row, (tuple, list)):
                            # Embedded client returns tuple, first element is collection name
                            collection_name = row[0] if len(row) > 0 else ""
                        else:
                            collection_name = str(row)
                        collection = self.get_collection(collection_name)
                        collections.append(collection)
                    except Exception as e:
                        logger.warning(
                            f"Failed to get collection. The data may be corrupted. The collection name: '{collection_name}': {e}"
                        )
                        continue

        except Exception as e:
            raise ValueError(f"Failed to list collections: {e}") from e
        return collections

    def _list_collections_v1(self) -> list["Collection"]:
        """
        List all collections from table names that start with collection prefix

        Returns:
            List of Collection objects
        """
        # List all tables that start with collection prefix
        # Use SHOW TABLES LIKE pattern to filter collection tables
        pattern = CollectionNames.table_pattern()
        try:
            tables = self._execute(f"SHOW TABLES LIKE '{pattern}'")
        except Exception:
            # Fallback: try to query information_schema
            try:
                # Get current database name
                db_result = self._execute("SELECT DATABASE()")
                if db_result and len(db_result) > 0:
                    db_name = (
                        db_result[0][0]
                        if isinstance(db_result[0], (tuple, list))
                        else db_result[0].get("DATABASE()", "")
                    )
                    tables = self._execute(
                        f"SELECT TABLE_NAME FROM information_schema.TABLES "
                        f"WHERE TABLE_SCHEMA = '{db_name}' AND TABLE_NAME LIKE '{pattern}'"
                    )
                else:
                    return []
            except Exception:
                return []

        collections = []
        for row in tables:
            # Extract table name
            if isinstance(row, dict):
                # Server client returns dict, get the first value
                table_name = next(iter(row.values()), "")
            elif isinstance(row, (tuple, list)):
                # Embedded client returns tuple, first element is table name
                table_name = row[0] if len(row) > 0 else ""
            else:
                table_name = str(row)

            # Extract collection name from table name
            if CollectionNames.is_collection_table(table_name):
                collection_name = CollectionNames.collection_name(table_name)

                # Get collection with dimension
                try:
                    collection = self.get_collection(collection_name)
                    collections.append(collection)
                except Exception as e:
                    logger.debug(f"Failed to get collection '{collection_name}': {e}")
                    continue

        return collections

    def count_collection(self) -> int:
        """Count the total number of collections.

        Returns:
            The number of collections.

        Examples:
            >>> count = client.count_collection()
            >>> print(f"Database has {count} collections")
        """
        collections = self.list_collections()
        return len(collections)

    def has_collection(self, name: str) -> bool:
        """Check if a collection exists.

        Args:
            name: The name of the collection to check.

        Returns:
            True if the collection exists, False otherwise.

        Examples:
            >>> if client.has_collection("my_collection"):
            ...     print("Collection exists!")
        """
        return self._has_collection_v2(name) or self._has_collection_v1(name)

    def _has_collection_v2(self, name: str) -> bool:
        try:
            query_sql = f"SELECT COLLECTION_ID FROM {CollectionNames.sdk_collections_table_name()} WHERE COLLECTION_NAME = '{name}'"
            rows = self._execute(query_sql)
            if not rows or len(rows) == 0:
                return False
            if isinstance(rows[0], dict):
                collection_id = rows[0]["COLLECTION_ID"]
            elif isinstance(rows[0], (tuple, list)):
                collection_id = rows[0][0] if len(rows[0]) > 0 else ""
            else:
                collection_id = str(rows[0])
            desc_sql = f"DESCRIBE `{CollectionNames.table_name_v2(collection_id)}`"
            desc_result = self._execute(desc_sql)
            return not (not desc_result or len(desc_result) == 0)
        except Exception:
            return False

    def _has_collection_v1(self, name: str) -> bool:
        """
        Check if a collection exists

        Args:
            name: Collection name

        Returns:
            True if exists, False otherwise
        """
        # Construct table name
        table_name = CollectionNames.table_name(name)

        # Check if table exists
        try:
            # Try to describe the table
            table_info = self._execute(f"DESCRIBE `{table_name}`")
            return table_info is not None and len(table_info) > 0
        except Exception:
            # If DESCRIBE fails, table doesn't exist
            return False

    def get_or_create_collection(
        self,
        name: str,
        schema: Schema | None = None,
        configuration: ConfigurationParam = _NOT_PROVIDED,
        embedding_function: EmbeddingFunctionParam = _NOT_PROVIDED,
        **kwargs,
    ) -> "Collection":
        """Get a collection if it exists, otherwise create it.

        Args:
            name: The name of the collection.
            schema: Schema configuration for fine-grained index control, including
                   sparse vector index support. When provided, ``configuration`` and
                   ``embedding_function`` parameters are ignored.
            configuration: Index configuration. Defaults to None (uses HNSW with
                Cosine distance and dimension 384). Can be a ``Configuration`` or
                ``HNSWConfiguration`` object. If set to None, the dimension will be
                inferred from the embedding function. Ignored if ``schema`` is provided.
            embedding_function: The embedding function to use for this collection.
                Defaults to ``DefaultEmbeddingFunction`` (all-MiniLM-L6-v2). If set to None,
                no embedding function will be used (embeddings must be provided manually).
                Ignored if ``schema`` is provided.
            **kwargs: Additional parameters passed to ``create_collection`` if the collection is created.

        Returns:
            The existing or newly created ``Collection`` object.

        Raises:
            ValueError: If the configuration/embedding function combination is invalid (e.g., dimension mismatch).

        Examples:
            >>> collection = client.get_or_create_collection("my_collection")
        """
        # Validate collection name before any database interaction
        _validate_collection_name(name)

        # First, try to get the collection
        if self.has_collection(name):
            # Collection exists, return it
            # Pass embedding_function (could be _NOT_PROVIDED, None, or an EmbeddingFunction instance)
            return self.get_collection(name, embedding_function=embedding_function)

        # Collection doesn't exist, create it with provided or default configuration
        return self.create_collection(
            name=name,
            schema=schema,
            configuration=configuration,
            embedding_function=embedding_function,
            **kwargs,
        )

    def _get_collection_table_name(self, collection_id: str | None, collection_name: str) -> str:
        """
        Get collection table name
        """
        if collection_id:
            return CollectionNames.table_name_v2(collection_id)
        return CollectionNames.table_name(collection_name)

    def _fork_table_enabled(self) -> bool:
        db_type, version = self.detect_db_type_and_version()
        version_110 = Version("1.1.0.0")
        logger.debug(f"db_type: {db_type}, version: {version}")
        return db_type.lower() == "seekdb" and version >= version_110

    def _fork_database_enabled(self) -> bool:
        db_type, version = self.detect_db_type_and_version()
        version_120 = Version("1.2.0.0")
        logger.debug(f"db_type: {db_type}, version: {version}")
        return db_type.lower() == "seekdb" and version >= version_120

    def _refresh_enabled(self) -> bool:
        db_type, version = self.detect_db_type_and_version()
        version_130 = Version("1.3.0.0")
        logger.debug(f"db_type: {db_type}, version: {version}")
        return db_type.lower() == "seekdb" and version >= version_130

    def refresh_index(self) -> None:
        """
        Flush async vector index build tasks when supported.

        For unsupported database versions, this method is a no-op to keep
        collection-level API calls backward compatible.
        """
        if not self._refresh_enabled():
            return

        self._execute("CALL dbms_index_manager.refresh();")

    def _get_collection_id(self, collection_name: str) -> str:
        collection_id_query_sql = f"SELECT COLLECTION_ID FROM `{CollectionNames.sdk_collections_table_name()}` WHERE COLLECTION_NAME = '{collection_name}'"
        collection_id_query_result = self._execute(collection_id_query_sql)
        if not collection_id_query_result or len(collection_id_query_result) == 0:
            raise ValueError(f"Collection not found: '{collection_name}'")
        if isinstance(collection_id_query_result[0], dict):
            collection_id = collection_id_query_result[0]["COLLECTION_ID"]
        elif isinstance(collection_id_query_result[0], (tuple, list)):
            collection_id = collection_id_query_result[0][0] if len(collection_id_query_result[0]) > 0 else ""
        else:
            collection_id = str(collection_id_query_result[0])
        return collection_id

    def _collection_fork(self, collection: Collection, forked_name: str) -> None:
        """
        Fork a collection

        Args:
            collection: Collection to fork
            forked_name: Forked collection name
        """
        if not self._fork_table_enabled():
            raise ValueError("Fork is not enabled for this database")

        _validate_collection_name(forked_name)

        if self.has_collection(forked_name):
            raise ValueError(f"Collection '{forked_name}' already exists")

        # Ensure sdk_collections exists (especially for v1-only databases)
        self._create_sdk_collections_if_not_exists()

        source_table_name = self._get_collection_table_name(collection.id, collection.name)
        collection_meta = self._resolve_collection_metadata_from_sdk_collections(collection.name)
        if not collection_meta:
            raise ValueError(f"Collection '{collection.name}' does not exist")
        forked_table_name = None
        try:
            settings_str = (
                f"'{escape_string(collection_meta.settings)}'" if collection_meta.settings is not None else "NULL"
            )
            insert_sql = f"INSERT INTO `{CollectionNames.sdk_collections_table_name()}` (COLLECTION_NAME, SETTINGS) VALUES ('{forked_name}', {settings_str})"
            self._execute(insert_sql)
            collection_id = self._get_collection_id(forked_name)
            forked_table_name = CollectionNames.table_name_v2(collection_id)

            fork_table_sql = f"FORK TABLE `{source_table_name}` TO `{forked_table_name}`"
            self._execute(fork_table_sql)
        except Exception as ex:
            try:
                if forked_table_name:
                    drop_table_sql = f"DROP TABLE IF EXISTS `{forked_table_name}`"
                    self._execute(drop_table_sql)
                delete_item_sql = f"DELETE FROM `{CollectionNames.sdk_collections_table_name()}` WHERE COLLECTION_NAME = '{forked_name}'"
                self._execute(delete_item_sql)
            except Exception as ex2:
                logger.warning(f"failed to clean data after failed to fork collection: {ex2}")

            raise ValueError(f"Failed to fork collection: {ex}") from ex
        logger.debug(f"✅ Successfully forked collection '{collection.name}' to '{forked_name}'")

    # ==================== Collection Internal Operations (Called by Collection) ====================
    # These methods are called by Collection objects, different clients implement different logic

    # -------------------- DML Operations --------------------

    def _generate_sparse_embeddings(  # noqa: C901
        self,
        sparse_config: SparseVectorIndexConfig,
        documents: list[str] | None,
        metadatas: list[dict] | None,
        num_items: int,
    ) -> list[SparseVector | None]:
        """
        Generate sparse embeddings based on SparseVectorIndexConfig.

        Returns a list of SparseVector (or None) for each item.
        """
        sparse_ef = sparse_config.embedding_function
        if sparse_ef is None:
            raise ValueError("Sparse embedding function is not provided")

        source_type, metadata_key = sparse_config.resolve_source_key()

        # Gather source texts
        source_texts = []
        for i in range(num_items):
            if source_type == "document":
                text = documents[i] if documents and i < len(documents) else None
                if text is None:
                    raise ValueError(
                        f"Sparse vector index is configured to generate from document field, "
                        f"but document at index {i} is None."
                    )
                if not isinstance(text, str):
                    raise TypeError(
                        f"Sparse vector index source_key refers to document field, "
                        f"but value at index {i} is not a string: {type(text).__name__}"
                    )
                source_texts.append(text)
            elif source_type == "metadata":
                meta = metadatas[i] if metadatas and i < len(metadatas) else None
                if meta is None:
                    raise ValueError(
                        f"Sparse vector index is configured to generate from metadata['{metadata_key}'], "
                        f"but metadata at index {i} is None."
                    )
                text = meta.get(metadata_key)
                if text is None:
                    raise ValueError(
                        f"Sparse vector index is configured to generate from metadata['{metadata_key}'], "
                        f"but metadata['{metadata_key}'] at index {i} is None."
                    )
                if not isinstance(text, str):
                    raise TypeError(
                        f"Sparse vector index source_key refers to metadata['{metadata_key}'], "
                        f"but value at index {i} is not a string: {type(text).__name__}"
                    )
                source_texts.append(text)
            else:
                raise ValueError(f"Invalid source type: {source_type}")

        # Generate sparse embeddings
        logger.debug(f"Generating sparse embeddings for {len(source_texts)} items")
        try:
            sparse_vectors = sparse_ef(source_texts)
        except Exception as e:
            raise ValueError(f"Failed to generate sparse embeddings: {e}") from e
        else:
            if len(sparse_vectors) != num_items:
                raise ValueError(
                    f"Sparse embedding function returned {len(sparse_vectors)} vectors, expected {num_items}."
                )
            logger.debug(f"✅ Successfully generated {len(sparse_vectors)} sparse embeddings")
            return sparse_vectors

    def _collection_add(  # noqa: C901
        self,
        collection_id: str | None,
        collection_name: str,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        embedding_function: EmbeddingFunction[EmbeddingDocuments] | None = None,
        **kwargs,
    ) -> None:
        """
        [Internal] Add data to collection - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            ids: Single ID or list of IDs
            embeddings: Single embedding or list of embeddings (optional)
            metadatas: Single metadata dict or list of metadata dicts (optional)
            documents: Single document or list of documents (optional)
            embedding_function: EmbeddingFunction instance to convert documents to embeddings.
                               Required if documents provided but embeddings not provided.
                               Must implement __call__ method that accepts Documents
                               and returns Embeddings (List[List[float]]).
            **kwargs: Additional parameters
        """
        logger.debug(f"Adding data to collection '{collection_name}'")

        # Normalize inputs to lists
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(documents, str):
            documents = [documents]
        if metadatas is not None and isinstance(metadatas, dict):
            metadatas = [metadatas]
        if (
            embeddings is not None
            and isinstance(embeddings, list)
            and len(embeddings) > 0
            and not isinstance(embeddings[0], list)
        ):
            embeddings = [embeddings]

        # Handle vector generation logic:
        # 1. If embeddings are provided, use them directly without embedding
        # 2. If embeddings are not provided but documents are provided:
        #    - If embedding_function is provided, use it to generate embeddings from documents
        #    - If embedding_function is not provided, raise an error
        # 3. If neither embeddings nor documents are provided, raise an error
        # NOTE: The embedding_function is passed through `get_collection` and `create_collection` parameters.
        # If embedding_function parameter passed in `get_collection` and `create_collection` is None,
        # then the embedding function is not provided. If developers passed through `_NOT_PROVIDED` (default value),
        # then the embedding function is the default embedding function.

        if embeddings:
            # embeddings provided, use them directly without embedding
            pass
        elif documents:
            # embeddings not provided but documents are provided, check for embedding_function
            if embedding_function is not None:
                logger.debug(f"Generating embeddings for {len(documents)} documents using embedding function")
                try:
                    embeddings = embedding_function(documents)
                    logger.debug(f"✅ Successfully generated {len(embeddings)} embeddings")
                except Exception as e:
                    logger.exception("Failed to generate embeddings")
                    raise ValueError(f"Failed to generate embeddings from documents: {e}") from e
            else:
                raise ValueError(
                    "Documents provided but no embeddings and no embedding function. "
                    "Either:\n"
                    "  1. Provide embeddings directly when calling add(), or\n"
                    "  2. Provide embedding_function to auto-generate embeddings from documents."
                )
        else:
            # Neither embeddings nor documents provided, raise an error
            raise ValueError(
                "Neither embeddings nor documents provided. "
                "Please provide either:\n"
                "  1. embeddings directly, or\n"
                "  2. documents with embedding_function to generate embeddings."
            )

        # Determine number of items
        num_items = 0
        if ids:
            num_items = len(ids)
        elif documents:
            num_items = len(documents)
        elif embeddings:
            num_items = len(embeddings)
        elif metadatas:
            num_items = len(metadatas)

        if num_items == 0:
            raise ValueError("No items to add")

        # Validate lengths match
        if ids and len(ids) != num_items:
            raise ValueError(f"Number of ids ({len(ids)}) does not match number of items ({num_items})")
        if documents and len(documents) != num_items:
            raise ValueError(f"Number of documents ({len(documents)}) does not match number of items ({num_items})")
        if metadatas and len(metadatas) != num_items:
            raise ValueError(f"Number of metadatas ({len(metadatas)}) does not match number of items ({num_items})")
        if embeddings and len(embeddings) != num_items:
            raise ValueError(f"Number of embeddings ({len(embeddings)}) does not match number of items ({num_items})")

        # Get table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Handle sparse embeddings generation
        sparse_config = kwargs.get("sparse_vector_index_config")
        sparse_embeddings = None
        has_sparse = sparse_config is not None
        if has_sparse:
            sparse_embeddings = self._generate_sparse_embeddings(sparse_config, documents, metadatas, num_items)

        # Build INSERT SQL
        values_list = []
        for i in range(num_items):
            # Process ID - support any string format
            id_val = ids[i] if ids else None
            if id_val:
                if not isinstance(id_val, str):
                    id_val = str(id_val)
                id_sql = self._convert_id_to_sql(id_val)
            else:
                raise ValueError("ids must be provided for add operation")

            # Process document
            doc_val = documents[i] if documents else None
            if doc_val is not None:
                # Use pymysql's escape_string for safe escaping
                doc_val_escaped = escape_string(doc_val)
                doc_sql = f"'{doc_val_escaped}'"
            else:
                doc_sql = "NULL"

            # Process metadata
            meta_val = metadatas[i] if metadatas else None
            if meta_val is not None:
                # Convert to JSON string and escape using pymysql's escape_string
                meta_json = json.dumps(meta_val, ensure_ascii=False)
                meta_json_escaped = escape_string(meta_json)
                meta_sql = f"'{meta_json_escaped}'"
            else:
                meta_sql = "NULL"

            # Process vector
            vec_val = embeddings[i] if embeddings else None
            vec_sql = "NULL" if vec_val is None else _embedding_to_hexstring(vec_val)

            # Process sparse vector
            if has_sparse:
                sparse_val = sparse_embeddings[i] if sparse_embeddings else None
                sparse_sql = "NULL" if sparse_val is None else _sparse_vector_to_sql(sparse_val)
                values_list.append(f"({id_sql}, {doc_sql}, {meta_sql}, {vec_sql}, {sparse_sql})")
            else:
                values_list.append(f"({id_sql}, {doc_sql}, {meta_sql}, {vec_sql})")

        # Build column list
        columns = f"{CollectionFieldNames.ID}, {CollectionFieldNames.DOCUMENT}, {CollectionFieldNames.METADATA}, {CollectionFieldNames.EMBEDDING}"
        if has_sparse:
            columns += f", {CollectionFieldNames.SPARSE_EMBEDDING}"

        # Build final SQL
        sql = f"""INSERT INTO `{table_name}` ({columns})
                 VALUES {",".join(values_list)}"""

        logger.debug(f"Executing SQL: {sql}")
        self._execute(sql)
        logger.debug(f"✅ Successfully added {num_items} item(s) to collection '{collection_name}'")

    def _collection_update(  # noqa: C901
        self,
        collection_id: str | None,
        collection_name: str,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        embedding_function: EmbeddingFunction[EmbeddingDocuments] | None = None,
        **kwargs,
    ) -> None:
        """
        [Internal] Update data in collection - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            ids: Single ID or list of IDs to update
            embeddings: New embeddings (optional)
            metadatas: New metadata (optional)
            documents: New documents (optional)
            embedding_function: EmbeddingFunction instance to convert documents to embeddings.
                               Required if documents provided but embeddings not provided.
                               Must implement __call__ method that accepts Documents
                               and returns Embeddings (List[List[float]]).
            **kwargs: Additional parameters
        """
        logger.debug(f"Updating data in collection '{collection_name}'")

        # Normalize inputs to lists
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(documents, str):
            documents = [documents]
        if metadatas is not None and isinstance(metadatas, dict):
            metadatas = [metadatas]
        if (
            embeddings is not None
            and isinstance(embeddings, list)
            and len(embeddings) > 0
            and not isinstance(embeddings[0], list)
        ):
            embeddings = [embeddings]

        # Handle vector generation logic:
        # 1. If embeddings are provided, use them directly without embedding
        # 2. If embeddings are not provided but documents are provided:
        #    - If embedding_function is provided, use it to generate embeddings from documents
        #    - If embedding_function is not provided, raise an error
        # 3. If neither embeddings nor documents are provided:
        #    - If metadatas are provided, allow update (metadata-only update)
        #    - If metadatas are not provided, raise an error

        if embeddings:
            # embeddings provided, use them directly without embedding
            pass
        elif documents:
            # embeddings not provided but documents are provided, check for embedding_function
            if embedding_function is not None:
                logger.debug(f"Generating embeddings for {len(documents)} documents using embedding function")
                try:
                    embeddings = embedding_function(documents)
                    logger.debug(f"✅ Successfully generated {len(embeddings)} embeddings")
                except Exception as e:
                    logger.exception("Failed to generate embeddings")
                    raise ValueError(f"Failed to generate embeddings from documents: {e}") from e
            else:
                raise ValueError(
                    "Documents provided but no embeddings and no embedding function. "
                    "Either:\n"
                    "  1. Provide embeddings directly when calling update(), or\n"
                    "  2. Provide embedding_function to auto-generate embeddings from documents."
                )
        elif not metadatas:
            # Neither embeddings nor documents nor metadatas provided, raise an error
            raise ValueError(
                "Neither embeddings nor documents nor metadatas provided. "
                "Please provide at least one of:\n"
                "  1. embeddings directly, or\n"
                "  2. documents with embedding_function to generate embeddings, or\n"
                "  3. metadatas to update metadata only."
            )

        # Validate inputs
        if not ids:
            raise ValueError("ids must not be empty")

        # Validate lengths match
        if documents and len(documents) != len(ids):
            raise ValueError(f"Number of documents ({len(documents)}) does not match number of ids ({len(ids)})")
        if metadatas and len(metadatas) != len(ids):
            raise ValueError(f"Number of metadatas ({len(metadatas)}) does not match number of ids ({len(ids)})")
        if embeddings and len(embeddings) != len(ids):
            raise ValueError(f"Number of embeddings ({len(embeddings)}) does not match number of ids ({len(ids)})")

        # Get table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Handle sparse embeddings generation
        sparse_config = kwargs.get("sparse_vector_index_config")
        sparse_embeddings = None
        if sparse_config is not None:
            source_type, _ = sparse_config.resolve_source_key()
            should_generate = (source_type == "document" and documents) or (source_type == "metadata" and metadatas)
            if should_generate:
                sparse_embeddings = self._generate_sparse_embeddings(sparse_config, documents, metadatas, len(ids))

        # Update each item
        for i in range(len(ids)):
            # Process ID - support any string format
            id_val = ids[i]
            if not isinstance(id_val, str):
                id_val = str(id_val)
            id_sql = self._convert_id_to_sql(id_val)

            # Build SET clause
            set_clauses = []

            if documents:
                doc_val = documents[i]
                if doc_val is not None:
                    doc_val_escaped = escape_string(doc_val)
                    set_clauses.append(f"{CollectionFieldNames.DOCUMENT} = '{doc_val_escaped}'")

            if metadatas:
                meta_val = metadatas[i]
                if meta_val is not None:
                    meta_json = json.dumps(meta_val, ensure_ascii=False)
                    meta_json_escaped = escape_string(meta_json)
                    set_clauses.append(f"{CollectionFieldNames.METADATA} = '{meta_json_escaped}'")

            if embeddings:
                vec_val = embeddings[i]
                if vec_val is not None:
                    vec_str = "[" + ",".join(map(str, vec_val)) + "]"
                    set_clauses.append(f"{CollectionFieldNames.EMBEDDING} = '{vec_str}'")

            # Handle sparse embedding update
            if sparse_embeddings and sparse_embeddings[i] is not None:
                sparse_sql = _sparse_vector_to_sql(sparse_embeddings[i])
                set_clauses.append(f"{CollectionFieldNames.SPARSE_EMBEDDING} = {sparse_sql}")

            if not set_clauses:
                continue

            # Build UPDATE SQL
            sql = f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE {CollectionFieldNames.ID} = {id_sql}"

            logger.debug(f"Executing SQL: {sql}")
            self._execute(sql)

        logger.debug(f"✅ Successfully updated {len(ids)} item(s) in collection '{collection_name}'")

    def _collection_upsert(  # noqa: C901
        self,
        collection_id: str | None,
        collection_name: str,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        embedding_function: EmbeddingFunction[EmbeddingDocuments] | None = None,
        **kwargs,
    ) -> None:
        """
        [Internal] Insert or update data in collection - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            ids: Single ID or list of IDs
            embeddings: embeddings (optional)
            metadatas: Metadata (optional)
            documents: Documents (optional)
            embedding_function: EmbeddingFunction instance to convert documents to embeddings.
                               Required if documents provided but embeddings not provided.
                               Must implement __call__ method that accepts Documents
                               and returns Embeddings (List[List[float]]).
            **kwargs: Additional parameters
        """
        logger.debug(f"Upserting data in collection '{collection_name}'")

        # Normalize inputs to lists
        if isinstance(ids, str):
            ids = [ids]
        if isinstance(documents, str):
            documents = [documents]
        if metadatas is not None and isinstance(metadatas, dict):
            metadatas = [metadatas]
        if (
            embeddings is not None
            and isinstance(embeddings, list)
            and len(embeddings) > 0
            and not isinstance(embeddings[0], list)
        ):
            embeddings = [embeddings]

        # Handle vector generation logic:
        # 1. If embeddings are provided, use them directly without embedding
        # 2. If embeddings are not provided but documents are provided:
        #    - If embedding_function is provided, use it to generate embeddings from documents
        #    - If embedding_function is not provided, raise an error
        # 3. If neither embeddings nor documents are provided:
        #    - If metadatas are provided, allow upsert (metadata-only upsert)
        #    - If metadatas are not provided, raise an error

        if embeddings:
            # embeddings provided, use them directly without embedding
            pass
        elif documents:
            # embeddings not provided but documents are provided, check for embedding_function
            if embedding_function is not None:
                logger.debug(f"Generating embeddings for {len(documents)} documents using embedding function")
                try:
                    embeddings = embedding_function(documents)
                    logger.info(f"✅ Successfully generated {len(embeddings)} embeddings")
                except Exception as e:
                    logger.exception("Failed to generate embeddings")
                    raise ValueError(f"Failed to generate embeddings from documents: {e}") from e
            else:
                raise ValueError(
                    "Documents provided but no embeddings and no embedding function. "
                    "Either:\n"
                    "  1. Provide embeddings directly when calling upsert(), or\n"
                    "  2. Provide embedding_function to auto-generate embeddings from documents."
                )
        elif not metadatas:
            # Neither embeddings nor documents nor metadatas provided, raise an error
            raise ValueError(
                "Neither embeddings nor documents nor metadatas provided. "
                "Please provide at least one of:\n"
                "  1. embeddings directly, or\n"
                "  2. documents with embedding_function to generate embeddings, or\n"
                "  3. metadatas to update metadata only."
            )

        # Validate inputs
        if not ids:
            raise ValueError("ids must not be empty")

        # Validate lengths match
        if documents and len(documents) != len(ids):
            raise ValueError(f"Number of documents ({len(documents)}) does not match number of ids ({len(ids)})")
        if metadatas and len(metadatas) != len(ids):
            raise ValueError(f"Number of metadatas ({len(metadatas)}) does not match number of ids ({len(ids)})")
        if embeddings and len(embeddings) != len(ids):
            raise ValueError(f"Number of embeddings ({len(embeddings)}) does not match number of ids ({len(ids)})")

        # Get table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Handle sparse embeddings generation
        sparse_config = kwargs.get("sparse_vector_index_config")
        sparse_embeddings = None
        if sparse_config is not None:
            source_type, _ = sparse_config.resolve_source_key()
            should_generate = (source_type == "document" and documents) or (source_type == "metadata" and metadatas)
            if should_generate:
                sparse_embeddings = self._generate_sparse_embeddings(sparse_config, documents, metadatas, len(ids))

        # Upsert each item
        for i in range(len(ids)):
            # Process ID - support any string format
            id_val = ids[i]
            if not isinstance(id_val, str):
                id_val = str(id_val)
            id_sql = self._convert_id_to_sql(id_val)

            # Check if record exists
            existing = self._collection_get(
                collection_id=collection_id,
                collection_name=collection_name,
                ids=[ids[i]],  # Use original string ID for query
                include=["documents", "metadatas", "embeddings"],
            )

            # Get values for this item
            doc_val = documents[i] if documents else None
            meta_val = metadatas[i] if metadatas else None
            vec_val = embeddings[i] if embeddings else None

            if existing and len(existing.get("ids", [])) > 0:
                # Update existing record - only update provided fields
                existing_doc = existing.get("documents", [None])[0] if existing.get("documents") else None
                existing_meta = existing.get("metadatas", [None])[0] if existing.get("metadatas") else None
                existing_vec = existing.get("embeddings", [None])[0] if existing.get("embeddings") else None

                # Use provided values or keep existing values
                final_document = doc_val if doc_val is not None else existing_doc
                final_metadata = meta_val if meta_val is not None else existing_meta
                final_vector = vec_val if vec_val is not None else existing_vec

                # Build SET clause
                set_clauses = []

                if doc_val is not None:
                    if final_document is not None:
                        doc_val_escaped = escape_string(final_document)
                        set_clauses.append(f"{CollectionFieldNames.DOCUMENT} = '{doc_val_escaped}'")
                    else:
                        set_clauses.append(f"{CollectionFieldNames.DOCUMENT} = NULL")

                if meta_val is not None:
                    meta_json = json.dumps(final_metadata, ensure_ascii=False) if final_metadata else "{}"
                    meta_json_escaped = escape_string(meta_json)
                    set_clauses.append(f"{CollectionFieldNames.METADATA} = '{meta_json_escaped}'")

                if vec_val is not None:
                    vec_str = _embedding_to_hexstring(final_vector) if final_vector else "NULL"
                    set_clauses.append(f"{CollectionFieldNames.EMBEDDING} = {vec_str}")

                # Handle sparse embedding update
                if sparse_embeddings and sparse_embeddings[i] is not None:
                    sparse_sql = _sparse_vector_to_sql(sparse_embeddings[i])
                    set_clauses.append(f"{CollectionFieldNames.SPARSE_EMBEDDING} = {sparse_sql}")

                if set_clauses:
                    sql = (
                        f"UPDATE `{table_name}` SET {', '.join(set_clauses)} WHERE {CollectionFieldNames.ID} = {id_sql}"
                    )
                    logger.debug(f"Executing SQL: {sql}")
                    self._execute(sql)
            else:
                # Insert new record
                if doc_val is not None:
                    doc_val_escaped = escape_string(doc_val)
                    doc_sql = f"'{doc_val_escaped}'"
                else:
                    doc_sql = "NULL"

                if meta_val is not None:
                    meta_json = json.dumps(meta_val, ensure_ascii=False)
                    meta_json_escaped = escape_string(meta_json)
                    meta_sql = f"'{meta_json_escaped}'"
                else:
                    meta_sql = "NULL"

                vec_sql = "NULL" if vec_val is None else _embedding_to_hexstring(vec_val)

                # Build column list and values for insert
                columns = f"{CollectionFieldNames.ID}, {CollectionFieldNames.DOCUMENT}, {CollectionFieldNames.METADATA}, {CollectionFieldNames.EMBEDDING}"
                values = f"{id_sql}, {doc_sql}, {meta_sql}, {vec_sql}"

                if sparse_embeddings and sparse_embeddings[i] is not None:
                    sparse_sql = _sparse_vector_to_sql(sparse_embeddings[i])
                    columns += f", {CollectionFieldNames.SPARSE_EMBEDDING}"
                    values += f", {sparse_sql}"

                sql = f"""INSERT INTO `{table_name}` ({columns})
                         VALUES ({values})"""
                logger.debug(f"Executing SQL: {sql}")
                self._execute(sql)

        logger.debug(f"✅ Successfully upserted {len(ids)} item(s) in collection '{collection_name}'")

    def _collection_delete(
        self,
        collection_id: str | None,
        collection_name: str,
        ids: str | list[str] | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """
        [Internal] Delete data from collection - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            ids: Single ID or list of IDs to delete (optional)
            where: Filter condition on metadata (optional)
            where_document: Filter condition on documents (optional)
            **kwargs: Additional parameters
        """
        logger.debug(f"Deleting data from collection '{collection_name}'")

        # Validate that at least one filter is provided
        if not ids and not where and not where_document:
            raise ValueError("At least one of ids, where, or where_document must be provided")

        # Normalize ids to list
        id_list = None
        if ids is not None:
            id_list = [ids] if isinstance(ids, str) else ids

        # Get table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Build WHERE clause
        where_clause, params = self._build_where_clause(where, where_document, id_list)

        # Build DELETE SQL
        sql = f"DELETE FROM `{table_name}` {where_clause}"

        logger.debug(f"Executing SQL: {sql}")
        logger.debug(f"Parameters: {params}")

        # Execute DELETE using parameterized query
        conn = self._ensure_connection()
        use_context_manager = self._use_context_manager_for_cursor()
        self._execute_query_with_cursor(conn, sql, params, use_context_manager)

        logger.debug(f"✅ Successfully deleted data from collection '{collection_name}'")

    # -------------------- DQL Operations --------------------
    # Note: _collection_query() and _collection_get() are implemented below with common SQL-based logic

    def _normalize_query_embeddings(
        self, query_embeddings: list[float] | list[list[float]] | None
    ) -> list[list[float]]:
        """
        Normalize query embeddings to list of lists format

        Args:
            query_embeddings: Single vector or list of embeddings

        Returns:
            List of embeddings (each vector is a list of floats)
        """
        if query_embeddings is None:
            return []

        # Check if it's a single vector (list of numbers)
        if query_embeddings and isinstance(query_embeddings[0], (int, float)):
            return [query_embeddings]

        return query_embeddings

    def _normalize_include_fields(self, include: list[str] | None) -> dict[str, bool]:
        """
        Normalize include parameter to a dictionary

        Args:
            include: List of fields to include (e.g., ["documents", "metadatas", "embeddings"])

        Returns:
            Dictionary with field names as keys and True as values
            Default includes: documents, metadatas (but not embeddings)
        """
        # Default includes documents and metadatas
        default_fields = {"documents": True, "metadatas": True}

        if include is None:
            return default_fields

        # Build include dict from list
        include_dict = {}
        for field in include:
            include_dict[field] = True

        return include_dict

    def _embed_texts(
        self,
        texts: str | list[str],
        embedding_function: EmbeddingFunction[EmbeddingDocuments] | None = None,
        **kwargs,
    ) -> list[list[float]]:
        """
        Embed text(s) to vector(s)

        Args:
            texts: Single text or list of texts
            embedding_function: EmbeddingFunction instance to convert texts to embeddings.
                               Must implement __call__ method that accepts Documents
                               and returns Embeddings (List[List[float]]).
                               If not provided, raises NotImplementedError.
            **kwargs: Additional parameters for embedding (unused for now)

        Returns:
            List of embeddings (List[List[float]]), where each inner list is an embedding vector

        Raises:
            NotImplementedError: If embedding_function is not provided
        """
        if embedding_function is None:
            raise NotImplementedError(
                "Text embedding is not implemented. "
                "Please provide query_embeddings directly or set embedding_function in collection."
            )

        # Normalize texts to list
        if isinstance(texts, str):
            texts = [texts]

        # Use embedding function to generate embeddings
        return embedding_function(texts)

    def _normalize_row(self, row: Any, cursor_description: Any | None = None) -> dict[str, Any]:
        """
        Normalize database row to dictionary format

        Args:
            row: Database row (can be dict or tuple)
            cursor_description: Cursor description for tuple rows

        Returns:
            Dictionary with column names as keys
        """
        if isinstance(row, dict):
            return row

        # Convert tuple to dict using cursor description
        if cursor_description is not None:
            row_dict = {}
            for idx, col_desc in enumerate(cursor_description):
                row_dict[col_desc[0]] = row[idx]
            return row_dict

        # Fallback: assume it's already a dict or try to convert
        return dict(row) if hasattr(row, "_asdict") else row

    def _execute_query_with_cursor(
        self, conn: Any, sql: str, params: list[Any], use_context_manager: bool = True
    ) -> list[dict[str, Any]]:
        """
        Execute SQL query and return normalized rows

        Args:
            conn: Database connection
            sql: SQL query string
            params: Query parameters
            use_context_manager: Whether to use context manager for cursor (default: True)

        Returns:
            List of normalized row dictionaries
        """
        if use_context_manager:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                if not self._should_fetch_results(cursor, sql):
                    return []
                rows = cursor.fetchall()
                # Normalize rows
                normalized_rows = []
                for row in rows:
                    normalized_rows.append(self._normalize_row(row, cursor.description))
                return normalized_rows
        else:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                if not self._should_fetch_results(cursor, sql):
                    return []
                rows = cursor.fetchall()
                # Normalize rows
                normalized_rows = []
                for row in rows:
                    normalized_rows.append(self._normalize_row(row, cursor.description))
                return normalized_rows
            finally:
                cursor.close()

    def _build_select_clause(self, include_fields: dict[str, bool]) -> str:
        """
        Build SELECT clause based on include fields

        Args:
            include_fields: Dictionary of fields to include

        Returns:
            SELECT clause string
        """
        select_fields = ["_id"]
        if include_fields.get("embeddings") or include_fields.get("embedding"):
            select_fields.append("embedding")
        if include_fields.get("documents") or include_fields.get("document"):
            select_fields.append("document")
        if include_fields.get("metadatas") or include_fields.get("metadata"):
            select_fields.append("metadata")

        return ", ".join(select_fields)

    def _build_where_clause(
        self,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        id_list: list[str] | None = None,
    ) -> tuple[str, list[Any]]:
        """
        Build WHERE clause from filters

        Args:
            where: Metadata filter
            where_document: Document filter
            id_list: List of IDs to filter

        Returns:
            Tuple of (where_clause, params)
        """
        where_clauses = []
        params = []

        # Add ids filter if provided
        if id_list:
            # Process IDs for varbinary(512) _id field - support any string format
            processed_ids = []
            for id_val in id_list:
                if not isinstance(id_val, str):
                    id_val = str(id_val)
                id_sql, id_param = self._convert_id_to_sql_with_paramters(id_val)
                processed_ids.append(id_sql)
                params.append(id_param)

            where_clauses.append(f"_id IN ({','.join(processed_ids)})")

        # Add metadata filter
        if where:
            meta_clause, meta_params = FilterBuilder.build_metadata_filter(where, "metadata")
            if meta_clause:
                where_clauses.append(meta_clause)
                params.extend(meta_params)

        # Add document filter
        if where_document:
            doc_clause, doc_params = FilterBuilder.build_document_filter(where_document, "document")
            if doc_clause:
                where_clauses.append(doc_clause)
                params.extend(doc_params)

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return where_clause, params

    def _parse_row_value(self, value: Any) -> Any:
        """
        Parse row value (handle JSON strings)

        Args:
            value: Raw value from database

        Returns:
            Parsed value
        """
        if value is None:
            return None

        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value

        return value

    def _convert_id_to_sql(self, id_val: str) -> str:
        """
        Convert string ID to SQL format for varbinary(512) _id field

        Args:
            id_val: String ID (can be any string like "id1", "item-123", etc.)

        Returns:
            SQL expression to convert string to binary (e.g., "CAST('id1' AS BINARY)")
        """
        if not isinstance(id_val, str):
            id_val = str(id_val)

        # Use pymysql's escape_string for safe escaping
        id_val_escaped = escape_string(id_val)
        # Use CAST to convert string to binary for varbinary(512) field
        return f"CAST('{id_val_escaped}' AS BINARY)"

    def _convert_id_to_sql_with_paramters(self, id_val: str) -> (str, str):
        """
        Convert ID to SQL format for varbinary(512) _id field with parameters
        """
        return "CAST(%s AS BINARY)", (id_val)

    def _convert_id_from_bytes(self, record_id: Any) -> str:
        """
        Convert _id from bytes to string format

        Args:
            record_id: Record ID from database (can be bytes, str, or other format)

        Returns:
            String ID
        """
        if record_id is None:
            return None

        # If it's already a string, return as is
        if isinstance(record_id, str):
            return record_id

        # Convert bytes to string (UTF-8 decode)
        if isinstance(record_id, bytes):
            try:
                return record_id.decode("utf-8")
            except UnicodeDecodeError:
                # If UTF-8 decode fails, return hex representation as fallback
                return record_id.hex()

        # For other formats, convert to string
        return str(record_id)

    def _process_query_row(self, row: dict[str, Any], include_fields: dict[str, bool]) -> dict[str, Any]:
        """
        Process a row from query results

        Args:
            row: Normalized row dictionary
            include_fields: Fields to include

        Returns:
            Result item dictionary
        """
        # Convert _id from bytes to string format
        record_id = self._convert_id_from_bytes(row["_id"])
        result_item = {"_id": record_id}

        if "document" in row and row["document"] is not None:
            result_item["document"] = row["document"]

        if "embedding" in row and row["embedding"] is not None:
            result_item["embedding"] = self._parse_row_value(row["embedding"])

        if "metadata" in row and row["metadata"] is not None:
            result_item["metadata"] = self._parse_row_value(row["metadata"])

        if "distance" in row:
            result_item["distance"] = float(row["distance"])

        return result_item

    def _process_get_row(self, row: dict[str, Any], include_fields: dict[str, bool]) -> dict[str, Any]:
        """
        Process a row from get results

        Args:
            row: Normalized row dictionary
            include_fields: Fields to include

        Returns:
            Result item dictionary with id, document, embedding, metadata
        """
        # Convert _id from bytes to string format
        record_id = self._convert_id_from_bytes(row["_id"])

        document = None
        embedding = None
        metadata = None

        # Include document if requested
        if (include_fields.get("documents") or include_fields.get("document")) and "document" in row:
            document = row["document"]

        # Include metadata if requested
        if (include_fields.get("metadatas") or include_fields.get("metadata")) and row.get("metadata") is not None:
            metadata = self._parse_row_value(row["metadata"])

        # Include embedding if requested
        if (include_fields.get("embeddings") or include_fields.get("embedding")) and row.get("embedding") is not None:
            embedding = self._parse_row_value(row["embedding"])

        return {
            "id": record_id,
            "document": document,
            "embedding": embedding,
            "metadata": metadata,
        }

    def _use_context_manager_for_cursor(self) -> bool:
        """
        Whether to use context manager for cursor

        Returns:
            True if context manager should be used, False otherwise
        """
        # Default implementation: use context manager
        # Subclasses can override this if they need different behavior
        return True

    def _should_fetch_results(self, cursor: Any, sql: str) -> bool:
        description = getattr(cursor, "description", None)
        if description is not None:
            return True
        return is_query_sql(sql)

    def _execute(self, sql: str) -> Any:
        conn = self._ensure_connection()
        use_context_manager = self._use_context_manager_for_cursor()

        if use_context_manager:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                if self._should_fetch_results(cursor, sql):
                    return cursor.fetchall()
                return None

        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            if self._should_fetch_results(cursor, sql):
                return cursor.fetchall()
            return None
        finally:
            cursor.close()

    # -------------------- DQL Operations (Common Implementation) --------------------

    def _collection_query(  # noqa: C901
        self,
        collection_id: str | None,
        collection_name: str,
        query_embeddings: list[float] | list[list[float]] | None = None,
        query_texts: str | list[str] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        include: list[str] | None = None,
        query_key: FieldKey | None = None,
        query_hint: QueryHint | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        [Internal] Query collection by vector similarity - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            query_embeddings: Query vector(s) (preferred)
            query_texts: Query text(s) - will be embedded if provided (preferred)
            n_results: Number of results (default: 10)
            where: Metadata filter
            where_document: Document filter
            include: Fields to include
            **kwargs: Additional parameters, including:
                embedding_function: EmbeddingFunction instance to convert query_texts to embeddings.
                                   Required if query_texts is provided and collection doesn't have
                                   an embedding_function set. Must implement __call__ method that
                                   accepts Documents and returns Embeddings (List[List[float]]).
                distance: Distance metric to use for similarity calculation (e.g., 'l2', 'cosine', 'inner_product').
                         Defaults to 'l2' if not provided.

        Returns:
            Dict with keys:
            - ids: List[List[str]] - List of ID lists, one list per query
            - documents: Optional[List[List[str]]] - List of document lists, one list per query
            - metadatas: Optional[List[List[Dict]]] - List of metadata lists, one list per query
            - embeddings: Optional[List[List[List[float]]]] - List of embedding lists, one list per query
            - distances: Optional[List[List[float]]] - List of distance lists, one list per query
        """
        logger.debug(f"Querying collection '{collection_name}' with n_results={n_results}")
        conn = self._ensure_connection()

        # Convert collection name to table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Check if this is a sparse vector query
        sparse_config = kwargs.get("sparse_vector_index_config")
        is_sparse_query = query_key is not None and (
            query_key is FieldKey.SPARSE_EMBEDDING
            or query_key == FieldKey.SPARSE_EMBEDDING.name
            or (hasattr(query_key, "name") and query_key.name == "#sparse_embedding")
        )

        if is_sparse_query:
            return self._collection_query_sparse(
                conn=conn,
                table_name=table_name,
                query_embeddings=query_embeddings,
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=include,
                sparse_config=sparse_config,
                collection_name=collection_name,
                query_hint=query_hint,
                **kwargs,
            )

        # ===== Dense vector query path =====
        # Handle vector generation logic:
        # 1. If query_embeddings are provided, use them directly without embedding
        # 2. If query_embeddings are not provided but query_texts are provided:
        #    - If embedding_function is provided, use it to generate embeddings from query_texts
        #    - If embedding_function is not provided, raise an error
        # 3. If neither query_embeddings nor query_texts are provided, raise an error

        embedding_function = kwargs.get("embedding_function")

        if query_embeddings is not None:
            # Query embeddings provided, use them directly without embedding
            pass
        elif query_texts is not None:
            # Query embeddings not provided but query_texts are provided, check for embedding_function
            if embedding_function is not None:
                logger.debug("Embedding query texts...")
                query_embeddings = self._embed_texts(query_texts, embedding_function=embedding_function)
            else:
                raise ValueError(
                    "query_texts provided but no query_embeddings and no embedding_function. "
                    "Either:\n"
                    "  1. Provide query_embeddings directly, or\n"
                    "  2. Provide embedding_function to auto-generate embeddings from query_texts."
                )
        else:
            # Neither query_embeddings nor query_texts provided, raise an error
            raise ValueError(
                "Neither query_embeddings nor query_texts provided. "
                "Please provide either:\n"
                "  1. query_embeddings directly, or\n"
                "  2. query_texts with embedding_function to generate embeddings."
            )

        # Normalize query embeddings to list of lists
        query_embeddings = self._normalize_query_embeddings(query_embeddings)

        # Normalize include fields
        include_fields = self._normalize_include_fields(include)

        # Build SELECT clause
        select_clause = self._build_select_clause(include_fields)

        # Build WHERE clause from filters
        where_clause, params = self._build_where_clause(where, where_document)

        # Get distance metric from kwargs, default to DEFAULT_DISTANCE_METRIC if not provided
        distance = kwargs.get("distance", DEFAULT_DISTANCE_METRIC)

        # Map distance metric to SQL function name
        distance_function_map = {
            "l2": "l2_distance",
            "cosine": "cosine_distance",
            "inner_product": "inner_product",
        }

        # Get the distance function name, default to 'l2_distance' if distance is not recognized
        distance_func = distance_function_map.get(distance, "l2_distance")

        if distance not in distance_function_map:
            logger.warning(f"Unknown distance metric '{distance}', defaulting to 'l2_distance'")

        use_context_manager = self._use_context_manager_for_cursor()

        # Collect results for each query vector separately
        all_ids = []
        all_documents = []
        all_metadatas = []
        all_embeddings = []
        all_distances = []

        for query_vector in query_embeddings:
            # Convert vector to string format for SQL
            vector_str = _embedding_to_hexstring(query_vector)

            # Build query hint
            hint_sql = _query_hint_to_sql(query_hint, table_name=table_name)

            # Build SQL query with vector distance calculation
            # Reference: SELECT id, vec FROM t2 ORDER BY l2_distance(vec, '[0.1, 0.2, 0.3]') APPROXIMATE LIMIT 5;
            # Need to include distance in SELECT for result processing
            # Use the appropriate distance function based on the index configuration
            sql = f"""
                SELECT {hint_sql} {select_clause},
                       {distance_func}(embedding, {vector_str}) AS distance
                FROM `{table_name}`
                {where_clause}
                ORDER BY {distance_func}(embedding, {vector_str})
                APPROXIMATE
                LIMIT %s
            """

            # Execute query
            query_params = [*params, n_results]
            logger.debug(f"Executing SQL: {sql}")
            logger.debug(f"Parameters: {query_params}")

            rows = self._execute_query_with_cursor(conn, sql, query_params, use_context_manager)

            # Collect results for this query vector
            query_ids = []
            query_documents = []
            query_metadatas = []
            query_embeddings = []
            query_distances = []

            for row in rows:
                result_item = self._process_query_row(row, include_fields)
                query_ids.append(result_item.get("_id"))

                if "documents" in include_fields or include is None:
                    query_documents.append(result_item.get("document"))

                if "metadatas" in include_fields or include is None:
                    query_metadatas.append(result_item.get("metadata") or {})

                if "embeddings" in include_fields:
                    query_embeddings.append(result_item.get("embedding"))

                query_distances.append(result_item.get("distance"))

            all_ids.append(query_ids)
            if "documents" in include_fields or include is None:
                all_documents.append(query_documents)
            if "metadatas" in include_fields or include is None:
                all_metadatas.append(query_metadatas)
            if "embeddings" in include_fields:
                all_embeddings.append(query_embeddings)
            all_distances.append(query_distances)

        # Build result dictionary in chromadb format
        result = {"ids": all_ids, "distances": all_distances}

        if "documents" in include_fields or include is None:
            result["documents"] = all_documents

        if "metadatas" in include_fields or include is None:
            result["metadatas"] = all_metadatas

        if "embeddings" in include_fields:
            result["embeddings"] = all_embeddings

        logger.debug(
            f"✅ Query completed for '{collection_name}' with {len(query_embeddings)} vectors, returning {len(all_ids)} result lists"
        )
        return result

    def _collection_query_sparse(  # noqa: C901
        self,
        conn,
        table_name: str,
        query_embeddings: list[float] | list[list[float]] | None = None,
        query_texts: str | list[str] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        include: list[str] | None = None,
        sparse_config=None,
        collection_name: str = "",
        query_hint=None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        [Internal] Query collection by sparse vector similarity.

        Supports:
        1. Text-based sparse vector query via query_texts + sparse embedding function

        Args:
            conn: Database connection
            table_name: Table name
            query_embeddings: Not supported for sparse query path. Use query_texts instead.
            query_texts: Query text(s) to be converted to sparse vectors
            n_results: Number of results
            where: Metadata filter
            where_document: Document filter
            include: Fields to include
            sparse_config: SparseVectorIndexConfig instance
            collection_name: Collection name (for logging)
        """
        logger.debug(f"Sparse vector query on collection '{collection_name}'")

        # Resolve sparse query vectors
        sparse_query_vectors: list[SparseVector] = []

        if query_embeddings is not None:
            raise ValueError(
                "For sparse vector queries, query_embeddings is not supported. "
                "Please provide query_texts and use the configured sparse embedding function."
            )
        elif query_texts is not None:
            # Generate sparse vectors from query texts using sparse embedding function
            if sparse_config is None or sparse_config.embedding_function is None:
                raise ValueError(
                    "query_texts provided for sparse vector query but no sparse embedding function is configured."
                )
            sparse_ef = sparse_config.embedding_function
            # Normalize query_texts to list
            if isinstance(query_texts, str):
                query_texts = [query_texts]
            logger.debug(f"Generating sparse embeddings for {len(query_texts)} query texts...")
            sparse_vectors = sparse_ef(query_texts)
            sparse_query_vectors = sparse_vectors
        else:
            raise ValueError(
                "Neither query_embeddings nor query_texts provided for sparse vector query. "
                "Please provide query_texts with a configured sparse embedding function."
            )

        if not sparse_query_vectors:
            raise ValueError("No sparse query vectors resolved.")

        hint_sql = _query_hint_to_sql(query_hint, table_name=table_name)

        # Normalize include fields
        include_fields = self._normalize_include_fields(include)

        # Build SELECT clause
        select_clause = self._build_select_clause(include_fields)

        # Build WHERE clause from filters
        where_clause, params = self._build_where_clause(where, where_document)

        # Sparse vector queries always use inner_product distance
        distance_func = "inner_product"

        use_context_manager = self._use_context_manager_for_cursor()

        # Collect results for each sparse query vector separately
        all_ids = []
        all_documents = []
        all_metadatas = []
        all_embeddings = []
        all_distances = []

        for sv in sparse_query_vectors:
            # Convert sparse vector to SQL string format
            sv_sql = _sparse_vector_to_sql(sv)

            # Build SQL query with sparse vector distance calculation
            sql = f"""
                SELECT {hint_sql} {select_clause},
                       {distance_func}(sparse_embedding, {sv_sql}) AS distance
                FROM `{table_name}`
                {where_clause}
                ORDER BY {distance_func}(sparse_embedding, {sv_sql})
                APPROXIMATE
                LIMIT %s
            """.strip()

            # Execute query
            query_params = [*params, n_results]
            logger.debug(f"Executing sparse SQL: {sql}")
            logger.debug(f"Parameters: {query_params}")

            rows = self._execute_query_with_cursor(conn, sql, query_params, use_context_manager)

            # Collect results for this query vector
            query_ids = []
            query_documents = []
            query_metadatas = []
            query_embeddings_list = []
            query_distances = []

            for row in rows:
                result_item = self._process_query_row(row, include_fields)
                query_ids.append(result_item.get("_id"))

                if "documents" in include_fields or include is None:
                    query_documents.append(result_item.get("document"))

                if "metadatas" in include_fields or include is None:
                    query_metadatas.append(result_item.get("metadata") or {})

                if "embeddings" in include_fields:
                    query_embeddings_list.append(result_item.get("embedding"))

                query_distances.append(result_item.get("distance"))

            all_ids.append(query_ids)
            if "documents" in include_fields or include is None:
                all_documents.append(query_documents)
            if "metadatas" in include_fields or include is None:
                all_metadatas.append(query_metadatas)
            if "embeddings" in include_fields:
                all_embeddings.append(query_embeddings_list)
            all_distances.append(query_distances)

        # Build result dictionary in chromadb format
        result = {"ids": all_ids, "distances": all_distances}

        if "documents" in include_fields or include is None:
            result["documents"] = all_documents

        if "metadatas" in include_fields or include is None:
            result["metadatas"] = all_metadatas

        if "embeddings" in include_fields:
            result["embeddings"] = all_embeddings

        logger.debug(
            f"Sparse query completed for '{collection_name}' with {len(sparse_query_vectors)} vectors, "
            f"returning {len(all_ids)} result lists"
        )
        return result

    def _collection_get(  # noqa: C901
        self,
        collection_id: str | None,
        collection_name: str,
        ids: str | list[str] | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include: list[str] | None = None,
        query_hint: QueryHint | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        [Internal] Get data from collection by IDs or filters - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            ids: Single ID or list of IDs (optional)
            where: Filter condition on metadata (optional)
            where_document: Filter condition on documents (optional)
            limit: Maximum number of results (optional)
            offset: Number of results to skip (optional)
            include: Fields to include in results (optional)
            query_hint: Query optimization hints for database execution (optional)
            **kwargs: Additional parameters

        Returns:
            Dict with keys:
            - ids: List[str] - List of IDs
            - documents: Optional[List[str]] - List of documents
            - metadatas: Optional[List[Dict]] - List of metadata dictionaries
            - embeddings: Optional[List[List[float]]] - List of embeddings
        """
        logger.debug(f"Getting data from collection '{collection_name}'")
        conn = self._ensure_connection()

        # Convert collection name to table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Set defaults
        if limit is None:
            limit = 100
        if offset is None:
            offset = 0

        # Normalize ids to list
        id_list = None
        if ids is not None:
            id_list = [ids] if isinstance(ids, str) else ids

        # Note: get() now returns dict format (not QueryResult)
        # Normalize include fields (default includes documents and metadatas)
        include_fields = self._normalize_include_fields(include)

        # Build SELECT clause - always include _id
        select_clause = self._build_select_clause(include_fields)

        use_context_manager = self._use_context_manager_for_cursor()

        # Build WHERE clause from filters
        where_clause, params = self._build_where_clause(where, where_document, id_list)

        # Build query hint
        hint_sql = _query_hint_to_sql(query_hint, table_name=table_name)

        # Build SQL query
        sql = f"""
            SELECT {hint_sql} {select_clause}
            FROM `{table_name}`
            {where_clause}
            LIMIT %s OFFSET %s
        """

        # Execute query
        query_params = [*params, limit, offset]
        logger.debug(f"Executing SQL: {sql}")
        logger.debug(f"Parameters: {query_params}")

        rows = self._execute_query_with_cursor(conn, sql, query_params, use_context_manager)

        # Build result dictionary in chromadb format
        result_ids = []
        result_documents = []
        result_metadatas = []
        result_embeddings = []

        for row in rows:
            processed_row = self._process_get_row(row, include_fields)
            result_ids.append(processed_row["id"])

            if "documents" in include_fields or include is None:
                result_documents.append(processed_row["document"])

            if "metadatas" in include_fields or include is None:
                result_metadatas.append(processed_row["metadata"] or {})

            if "embeddings" in include_fields:
                result_embeddings.append(processed_row["embedding"])

        # Build result dictionary
        result = {"ids": result_ids}

        if "documents" in include_fields or include is None:
            result["documents"] = result_documents

        if "metadatas" in include_fields or include is None:
            result["metadatas"] = result_metadatas

        if "embeddings" in include_fields:
            result["embeddings"] = result_embeddings

        logger.debug(f"✅ Get completed for '{collection_name}', found {len(result_ids)} results")
        return result

    def _collection_hybrid_search(
        self,
        collection_id: str | None,
        collection_name: str,
        query: dict[str, Any] | None = None,
        knn: dict[str, Any] | None = None,
        rank: dict[str, Any] | None = None,
        n_results: int = 10,
        include: list[str] | None = None,
        query_hint: QueryHint | None = None,
        dimension: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        [Internal] Hybrid search combining full-text search and vector similarity search - Common SQL-based implementation

        Supports:
        1. Scalar query (metadata filtering only)
        2. Full-text search (with optional metadata filtering)
        3. Vector search (with optional metadata filtering)
        4. Scalar + vector search (with optional metadata filtering)

        Args:
            collection_id: Collection ID
            collection_name: Collection name
            query: Full-text search configuration dict with:
                - where_document: Document filter conditions (e.g., {"$contains": "text"})
                - where: Metadata filter conditions (e.g., {"page": {"$gte": 5}})
            knn: Vector search configuration dict with:
                - query_texts: Query text(s) to be embedded (optional if query_embeddings provided)
                - query_embeddings: Query vector(s) (optional if query_texts provided)
                - where: Metadata filter conditions (optional)
                - n_results: Number of results for vector search (optional)
            rank: Ranking configuration dict (e.g., {"rrf": {"rank_window_size": 60, "rank_constant": 60}})
            n_results: Final number of results to return after ranking (default: 10)
            include: Fields to include in results (optional)
            dimension: Collection vector dimension for validating query_embeddings (optional)
            **kwargs: Additional parameters, including:
                embedding_function: EmbeddingFunction instance to convert query_texts in knn to embeddings.
                                   Required if knn.query_texts is provided and collection doesn't have
                                   an embedding_function set. Must implement __call__ method that
                                   accepts Documents and returns Embeddings (List[List[float]]).

        Returns:
            Dict with keys (query-compatible format):
            - ids: List[List[str]] - List of ID lists (one list for hybrid search result)
            - documents: Optional[List[List[str]]] - List of document lists (if included)
            - metadatas: Optional[List[List[Dict]]] - List of metadata lists (if included)
            - embeddings: Optional[List[List[List[float]]]] - List of embedding lists (if included)
            - distances: Optional[List[List[float]]] - List of distance lists
        """
        logger.debug(f"Hybrid search in collection '{collection_name}' with n_results={n_results}")
        conn = self._ensure_connection()

        # Build table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Build search_parm JSON
        search_parm = self._build_search_parm(
            query,
            knn,
            rank,
            n_results,
            include=include,
            dimension=dimension,
            **kwargs,
        )

        # Convert search_parm to JSON string
        search_parm_json = json.dumps(search_parm, ensure_ascii=False)

        # Use variable binding to avoid datatype issues
        use_context_manager = self._use_context_manager_for_cursor()

        # Set the search_parm variable first (use safe escaping)
        escaped_params = escape_string(search_parm_json)
        set_sql = f"SET @search_parm = '{escaped_params}'"
        logger.debug(f"Setting search_parm: {set_sql}")
        logger.debug(f"Search parm JSON: {search_parm_json}")

        # Execute SET statement
        self._execute_query_with_cursor(conn, set_sql, [], use_context_manager)

        # Get SQL query from DBMS_HYBRID_SEARCH.GET_SQL
        get_sql_query = f"SELECT DBMS_HYBRID_SEARCH.GET_SQL('{table_name}', @search_parm) as query_sql FROM dual"
        logger.debug(f"Getting SQL query: {get_sql_query}")

        rows = self._execute_query_with_cursor(conn, get_sql_query, [], use_context_manager)

        if not rows or not rows[0].get("query_sql"):
            logger.warning("No SQL query returned from GET_SQL")
            return {
                "ids": [[]],
                "distances": [[]],
                "metadatas": [[]],
                "documents": [[]],
                "embeddings": [[]],
            }

        # Get the SQL query string
        query_sql = rows[0]["query_sql"]
        if isinstance(query_sql, str):
            # Remove any surrounding quotes if present
            query_sql = query_sql.strip().strip("'\"")

        # Add query hint to the generated SQL
        hint_sql = _query_hint_to_sql(query_hint, table_name=table_name)
        if hint_sql and query_sql.upper().startswith("SELECT"):
            # Insert hint after SELECT keyword
            query_sql = f"SELECT {hint_sql} {query_sql[len('SELECT') :]}"

        logger.debug(f"Executing query SQL: {query_sql}")

        # Execute the returned SQL query
        result_rows = self._execute_query_with_cursor(conn, query_sql, [], use_context_manager)

        # Transform SQL query results to standard format
        return self._transform_sql_result(result_rows, include)

    def _build_search_parm(  # noqa: C901
        self,
        query: dict[str, Any] | list[dict[str, Any]] | None,
        knn: dict[str, Any] | list[dict[str, Any]] | None,
        rank: dict[str, Any] | None,
        n_results: int,
        include: list[str] | None = None,
        dimension: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Build search_parm JSON from query, knn, and rank parameters

        Args:
            query: Full-text search configuration dict or list of dicts
            knn: Vector search configuration dict or list of dicts
            rank: Ranking configuration dict
            n_results: Final number of results to return
            include: Fields requested by the SDK caller. Used to infer the minimal OceanBase GET_SQL
                `_source` allowlist to avoid returning large unused columns (e.g. `embedding`).
            dimension: Collection dimension for validating query_embeddings (optional)
            **kwargs: Additional parameters, including:
                embedding_function: EmbeddingFunction instance to convert query_texts in knn to embeddings.
                                   Required if knn.query_texts is provided. Must implement __call__
                                   method that accepts Documents and returns Embeddings (List[List[float]]).

        Returns:
            search_parm dictionary
        """
        search_parm = {}

        # Build query part (full-text search or scalar query)
        query_expr_list: list[dict[str, Any]] = []
        if query:
            query_items = query if isinstance(query, list) else [query]
            for query_item in query_items:
                query_expr = self._build_query_expression(query_item)
                if query_expr:
                    query_expr_list.append(query_expr)
        if query_expr_list:
            search_parm["query"] = query_expr_list if len(query_expr_list) > 1 else query_expr_list[0]

        # Build knn part (vector search)
        knn_expr_list: list[dict[str, Any]] = []
        if knn:
            knn_items = knn if isinstance(knn, list) else [knn]
            for knn_item in knn_items:
                knn_expr = self._build_knn_expression(knn_item, dimension=dimension, **kwargs)
                if not knn_expr:
                    continue
                if isinstance(knn_expr, list):
                    knn_expr_list.extend(knn_expr)
                else:
                    knn_expr_list.append(knn_expr)
        if knn_expr_list:
            search_parm["knn"] = knn_expr_list if len(knn_expr_list) > 1 else knn_expr_list[0]

        if n_results is not None:
            search_parm["size"] = n_results

        # Build rank part
        if rank:
            search_parm["rank"] = rank

        # Always infer a minimal `_source` allowlist from include to reduce response payload.
        search_parm["_source"] = self._build_source_fields(include)

        return search_parm

    def _build_query_expression(self, query: dict[str, Any]) -> dict[str, Any] | None:
        """
        Build query expression from query dict

        Supports:
        - Scalar query (metadata filtering only): query.range or query.term
        - Full-text search: query.query_string
        - Full-text search with metadata filtering: query.bool with must and filter
        """
        where_document = query.get("where_document")
        where = query.get("where")
        boost = query.get("boost")

        # Case 1: Scalar query (metadata filtering only, no full-text search)
        if not where_document and where:
            filter_conditions = self._build_metadata_filter_for_search_parm(where)
            if filter_conditions:
                # If only one filter condition, check its type
                if len(filter_conditions) == 1:
                    filter_cond = filter_conditions[0]
                    # Directly return supported single condition types
                    if any(key in filter_cond for key in ("range", "term", "terms", "bool")):
                        return filter_cond
                # Multiple filter conditions, wrap in bool filter
                return {"bool": {"filter": filter_conditions}}

        # Case 2: Full-text search (with or without metadata filtering)
        if where_document:
            # Build document query using query_string
            doc_query = self._build_document_query(where_document, boost=boost)
            if doc_query:
                # Build filter from where condition
                filter_conditions = self._build_metadata_filter_for_search_parm(where)

                if filter_conditions:
                    # Full-text search with metadata filtering
                    return {"bool": {"must": [doc_query], "filter": filter_conditions}}
                else:
                    # Full-text search only
                    return doc_query

        return None

    def _build_document_query(  # noqa: C901
        self, where_document: dict[str, Any], boost: float | None = None
    ) -> dict[str, Any] | None:
        """
        Build document query from where_document condition using query_string

        Args:
            where_document: Document filter conditions
            boost: Optional weight for this document query

        Returns:
            query_string query dict
        """
        if not where_document:
            return None

        def _with_boost(expr: dict[str, Any] | None) -> dict[str, Any] | None:
            if boost is None or not expr:
                return expr

            def _apply_boost(target: Any) -> None:
                if not isinstance(target, dict):
                    return
                if "query_string" in target and isinstance(target["query_string"], dict):
                    target["query_string"]["boost"] = boost
                    return
                bool_clause = target.get("bool")
                if isinstance(bool_clause, dict):
                    for key in ("must", "should", "must_not", "filter"):
                        clause = bool_clause.get(key)
                        if isinstance(clause, list):
                            for item in clause:
                                _apply_boost(item)
                        elif isinstance(clause, dict):
                            _apply_boost(clause)

            _apply_boost(expr)
            return expr

        # Handle $contains - use query_string
        if "$contains" in where_document:
            # Use pymysql's escape_string for safe escaping of query content
            query_content = where_document["$contains"]
            escaped_query = escape_string(query_content)
            return _with_boost({"query_string": {"fields": ["document"], "query": escaped_query}})

        # Handle $not_contains - wrap query_string in must_not bool
        if "$not_contains" in where_document:
            return _with_boost({
                "bool": {
                    "must_not": [
                        {
                            "query_string": {
                                "fields": ["document"],
                                "query": where_document["$not_contains"],
                            }
                        }
                    ]
                }
            })

        # Handle $and with $contains
        if "$and" in where_document:
            and_conditions = where_document["$and"]
            contains_queries = []
            for condition in and_conditions:
                if isinstance(condition, dict) and "$contains" in condition:
                    contains_queries.append(condition["$contains"])

            if contains_queries:
                # Combine multiple $contains with AND (escape each query)
                escaped_queries = [escape_string(q) for q in contains_queries]
                return _with_boost({
                    "query_string": {
                        "fields": ["document"],
                        "query": " ".join(escaped_queries),
                    }
                })

        # Handle $or with $contains
        if "$or" in where_document:
            or_conditions = where_document["$or"]
            contains_queries = []
            for condition in or_conditions:
                if isinstance(condition, dict) and "$contains" in condition:
                    contains_queries.append(condition["$contains"])

            if contains_queries:
                # Combine multiple $contains with OR (escape each query)
                escaped_queries = [escape_string(q) for q in contains_queries]
                return _with_boost({
                    "query_string": {
                        "fields": ["document"],
                        "query": " OR ".join(escaped_queries),
                    }
                })

        # Default: if it's a string, treat as $contains
        if isinstance(where_document, str):
            return _with_boost({"query_string": {"fields": ["document"], "query": where_document}})

        return None

    def _build_metadata_filter_for_search_parm(self, where: dict[str, Any] | None) -> list[dict[str, Any]]:
        """
        Build metadata filter conditions for search_parm using JSON_EXTRACT format

        Args:
            where: Metadata filter conditions

        Returns:
            List of filter conditions in search_parm format
            Format: {"term": {"(JSON_EXTRACT(metadata, '$.field_name'))": "value"}}
            or {"range": {"(JSON_EXTRACT(metadata, '$.field_name'))": {"gte": 30, "lte": 90}}}
        """
        if not where:
            return []

        return self._build_metadata_filter_conditions(where)

    def _build_search_parm_field_name(self, key: str) -> str:
        """
        Build field name used in search_parm filters.
        Supports special "#id" to refer to the primary key column directly.
        """
        if key == "#id" or key == CollectionFieldNames.ID:
            return CollectionFieldNames.ID
        return f"(JSON_EXTRACT(metadata, '$.{key}'))"

    def _build_metadata_filter_conditions(  # noqa: C901
        self, condition: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Recursively build metadata filter conditions from nested dictionary

        Args:
            condition: Filter condition dictionary

        Returns:
            List of filter conditions
        """
        if not condition:
            return []

        result = []

        # Handle logical operators
        if "$and" in condition:
            must_conditions = []
            for sub_condition in condition["$and"]:
                sub_filters = self._build_metadata_filter_conditions(sub_condition)
                must_conditions.extend(sub_filters)
            if must_conditions:
                result.append({"bool": {"must": must_conditions}})
            return result

        if "$or" in condition:
            should_conditions = []
            for sub_condition in condition["$or"]:
                sub_filters = self._build_metadata_filter_conditions(sub_condition)
                should_conditions.extend(sub_filters)
            if should_conditions:
                result.append({"bool": {"should": should_conditions}})
            return result

        if "$not" in condition:
            not_filters = self._build_metadata_filter_conditions(condition["$not"])
            if not_filters:
                result.append({"bool": {"must_not": not_filters}})
            return result

        # Handle field conditions
        for key, value in condition.items():
            if key in ["$and", "$or", "$not"]:
                continue

            # Build field name with JSON_EXTRACT format (or _id for special key)
            field_name = self._build_search_parm_field_name(key)

            if isinstance(value, dict):
                # Handle comparison operators
                range_conditions = {}
                term_value = None

                for op, op_value in value.items():
                    if op == "$eq":
                        term_value = op_value
                    elif op == "$ne":
                        # $ne should be in must_not
                        result.append({"bool": {"must_not": [{"term": {field_name: op_value}}]}})
                    elif op == "$lt":
                        range_conditions["lt"] = op_value
                    elif op == "$lte":
                        range_conditions["lte"] = op_value
                    elif op == "$gt":
                        range_conditions["gt"] = op_value
                    elif op == "$gte":
                        range_conditions["gte"] = op_value
                    elif op == "$in":
                        # For $in, use terms query to match any value in list
                        if isinstance(op_value, (list, tuple)) and len(op_value) > 0:
                            result.append({"terms": {field_name: list(op_value)}})
                    elif op == "$nin" and isinstance(op_value, (list, tuple)) and len(op_value) > 0:
                        # For $nin, use must_not with terms query
                        result.append({"bool": {"must_not": [{"terms": {field_name: list(op_value)}}]}})

                if range_conditions:
                    result.append({"range": {field_name: range_conditions}})
                elif term_value is not None:
                    result.append({"term": {field_name: term_value}})
            else:
                # Direct equality
                result.append({"term": {field_name: value}})

        return result

    def _build_knn_expression(  # noqa: C901
        self, knn: dict[str, Any], dimension: int | None = None, **kwargs
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        Build knn expression from knn dict

        Args:
            knn: Vector search configuration dict with:
                - query_texts: Query text(s) to be embedded (optional if query_embeddings provided)
                - query_embeddings: Query vector(s) (optional if query_texts provided)
                - where: Metadata filter conditions (optional)
                - n_results: Number of results for vector search (optional)
                - boost: Optional weight for this knn search route
            **kwargs: Additional parameters, including:
                embedding_function: EmbeddingFunction instance to convert query_texts to embeddings.
                                   Required if query_texts is provided. Must implement __call__
                                   method that accepts Documents and returns Embeddings (List[List[float]]).
            dimension: Optional collection dimension for validating embeddings

        Returns:
            knn expression dict (or list of dicts when multiple query vectors) with optional filter
        """
        query_texts = knn.get("query_texts")
        query_embeddings = knn.get("query_embeddings")
        where = knn.get("where")
        n_results = knn.get("n_results", 10)
        boost = knn.get("boost")

        embedding_function = kwargs.get("embedding_function")

        def _normalize_vectors(raw_embeddings: Any) -> list[list[float]]:
            if raw_embeddings is None:
                return []
            if isinstance(raw_embeddings, list) and raw_embeddings and isinstance(raw_embeddings[0], list):
                return raw_embeddings  # type: ignore[return-value]
            if isinstance(raw_embeddings, list):
                return [raw_embeddings]  # type: ignore[list-item]
            return []

        vectors: list[list[float]] = []
        if query_embeddings is not None:
            vectors = _normalize_vectors(query_embeddings)
        elif query_texts is not None:
            if embedding_function is not None:
                try:
                    texts = query_texts if isinstance(query_texts, list) else [query_texts]
                    embeddings = self._embed_texts(texts, embedding_function=embedding_function)
                    if embeddings and len(embeddings) > 0:
                        vectors = embeddings
                except Exception as e:
                    logger.exception("Failed to generate embeddings from query_texts")
                    raise ValueError(f"Failed to generate embeddings from query_texts: {e}") from e
            else:
                raise ValueError(
                    "knn.query_texts provided but no knn.query_embeddings and no embedding_function. "
                    "Either:\n"
                    "  1. Provide knn.query_embeddings directly, or\n"
                    "  2. Provide embedding_function to auto-generate embeddings from knn.query_texts."
                )
        else:
            raise ValueError(
                "knn requires either query_embeddings or query_texts. "
                "Please provide either:\n"
                "  1. knn.query_embeddings directly, or\n"
                "  2. knn.query_texts with embedding_function to generate embeddings."
            )

        if not vectors:
            return None

        if dimension is not None:
            for vec in vectors:
                if len(vec) != dimension:
                    raise ValueError(f"Embedding dimension mismatch: expected {dimension}, got {len(vec)}")

        # Build knn expressions (one per vector)
        knn_exprs: list[dict[str, Any]] = []
        filter_conditions = self._build_metadata_filter_for_search_parm(where)
        for vector in vectors:
            expr = {"field": "embedding", "k": n_results, "query_vector": vector}
            if boost is not None:
                expr["boost"] = boost

            # Add filter using JSON_EXTRACT format
            if filter_conditions:
                expr["filter"] = filter_conditions

            knn_exprs.append(expr)

        return knn_exprs if len(knn_exprs) > 1 else knn_exprs[0]

    def _build_source_fields(self, include: list[str] | None) -> list[str]:
        """
        Infer OceanBase GET_SQL `_source` allowlist from include.
        """
        if include is None:
            requested = {"documents", "metadatas"}
        else:
            if not isinstance(include, list) or not all(isinstance(item, str) for item in include):
                raise TypeError("include must be a List[str] or None")
            requested = {item.lower() for item in include}

        source = ["_id"]

        if {"documents", "document"} & requested:
            source.append("document")
        if {"metadatas", "metadata"} & requested:
            source.append("metadata")
        if {"embeddings", "embedding"} & requested:
            source.append("embedding")

        return source

    def _transform_sql_result(  # noqa: C901
        self, result_rows: list[dict[str, Any]], include: list[str] | None
    ) -> dict[str, Any]:
        """
        Transform SQL query results to standard format (query-compatible format)

        Args:
            result_rows: List of row dictionaries from SQL query
            include: Fields to include in results (optional)

        Returns:
            Standard format dictionary with ids, distances, metadatas, documents, embeddings
            in query-compatible format (List[List[...]] for consistency with query method)
        """

        ids = []
        distances = []
        metadatas = []
        documents = []
        embeddings = []

        for row in result_rows:
            # Extract id (handle different column names and fallbacks)
            row_id = None
            for key in ("id", "_id", "ID", "Id", "_ID"):
                if key in row and row.get(key) is not None:
                    row_id = row.get(key)
                    break
            if row_id is None:
                for key in row:
                    if isinstance(key, str) and key.lower().endswith("id") and row.get(key) is not None:
                        row_id = row.get(key)
                        break
            row_id = self._convert_id_from_bytes(row_id)
            ids.append(row_id)

            # Extract distance/score (may be in different column names)
            distance = (
                row.get("_distance")
                or row.get("distance")
                or row.get("_score")
                or row.get("score")
                or row.get("DISTANCE")
                or row.get("_DISTANCE")
                or row.get("SCORE")
                or 0.0
            )
            distances.append(distance)

            # Extract metadata
            if include is None or "metadatas" in include or "metadata" in include:
                metadata = row.get("metadata") or row.get("METADATA")
                # Parse JSON string if needed
                if isinstance(metadata, str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        metadata = json.loads(metadata)
                metadatas.append(metadata or {})
            else:
                metadatas.append(None)

            # Extract document
            if include is None or "documents" in include or "document" in include:
                document = row.get("document") or row.get("DOCUMENT")
                documents.append(document)
            else:
                documents.append(None)

            # Extract embedding
            if include and ("embeddings" in include or "embedding" in include):
                embedding = row.get("embedding") or row.get("EMBEDDING")
                # Parse JSON string or list if needed
                if isinstance(embedding, str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        embedding = json.loads(embedding)
                embeddings.append(embedding)
            else:
                embeddings.append(None)

        # Return in query-compatible format (List[List[...]])
        result = {"ids": [ids], "distances": [distances]}

        if include is None or "documents" in include or "document" in include:
            result["documents"] = [documents]

        if include is None or "metadatas" in include or "metadata" in include:
            result["metadatas"] = [metadatas]

        if include and ("embeddings" in include or "embedding" in include):
            result["embeddings"] = [embeddings]

        return result

    def _transform_search_result(self, search_result: dict[str, Any], include: list[str] | None) -> dict[str, Any]:
        """Transform OceanBase search result to standard format"""
        # OceanBase SEARCH function returns results in a specific format
        # This needs to be adapted based on actual return format
        # For now, assuming it returns hits array

        hits = search_result.get("hits", {}).get("hits", [])

        ids = []
        distances = []
        metadatas = []
        documents = []
        embeddings = []

        for hit in hits:
            source = hit.get("_source", {})
            score = hit.get("_score", 0.0)

            ids.append(hit.get("_id"))
            distances.append(score)

            if include is None or "metadatas" in include or "metadata" in include:
                metadatas.append(source.get("metadata"))
            else:
                metadatas.append(None)

            if include is None or "documents" in include or "document" in include:
                documents.append(source.get("document"))
            else:
                documents.append(None)

            if include and ("embeddings" in include or "embedding" in include):
                embeddings.append(source.get("embedding"))
            else:
                embeddings.append(None)

        return {
            "ids": ids,
            "distances": distances,
            "metadatas": metadatas,
            "documents": documents,
            "embeddings": embeddings,
        }

    # -------------------- Collection Info --------------------

    def _collection_count(self, collection_id: str | None, collection_name: str) -> int:
        """
        [Internal] Get the number of items in collection - Common SQL-based implementation

        Args:
            collection_id: Collection ID
            collection_name: Collection name

        Returns:
            Item count
        """
        logger.debug(f"Counting items in collection '{collection_name}'")
        conn = self._ensure_connection()

        # Convert collection name to table name
        if collection_id:
            table_name = CollectionNames.table_name_v2(collection_id)
        else:
            table_name = CollectionNames.table_name(collection_name)

        # Execute COUNT query
        sql = f"SELECT COUNT(*) as cnt FROM `{table_name}`"
        logger.debug(f"Executing SQL: {sql}")

        use_context_manager = self._use_context_manager_for_cursor()
        rows = self._execute_query_with_cursor(conn, sql, [], use_context_manager)

        if not rows:
            count = 0
        else:
            # Extract count from result
            row = rows[0]
            if isinstance(row, dict):
                count = row.get("cnt", 0)
            elif isinstance(row, (tuple, list)):
                count = row[0] if len(row) > 0 else 0
            else:
                count = int(row) if row else 0

        logger.debug(f"✅ Collection '{collection_name}' has {count} items")
        return count
