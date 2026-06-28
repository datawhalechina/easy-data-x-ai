"""
pyseekdb - Unified vector database client wrapper

Based on seekdb and pymysql, providing a simple and unified API.

Supports two modes:

* **Embedded mode** - using local seekdb
* **Remote server mode** - connecting to remote server via pymysql (supports both seekdb Server and OceanBase Server)

Examples:

Embedded mode - Collection management:

.. code-block:: python

    import pyseekdb
    client = pyseekdb.Client(path="./seekdb.db", database="test")
    collection = client.get_or_create_collection("my_collection")

Remote server mode (seekdb Server) - Collection management:

.. code-block:: python

    import pyseekdb
    client = pyseekdb.Client(
        host='localhost',
        port=2881,
        tenant="sys",
        database="test",
        user="root",
        password="pass"
    )
    collection = client.get_or_create_collection("my_collection")

Remote server mode (OceanBase Server) - Collection management:

.. code-block:: python

    import pyseekdb
    client = pyseekdb.Client(
        host='localhost',
        port=2881,
        tenant="test",
        database="test",
        user="root",
        password="pass"
    )
    collection = client.get_or_create_collection("my_collection")

Admin client - Database management:

.. code-block:: python

    import pyseekdb
    admin = pyseekdb.AdminClient(path="./seekdb.db")
    admin.create_database("new_db")
    databases = admin.list_databases()
"""

import importlib.metadata

# Note: pylibseekdb built with ABI=0 and onnxruntime built with ABI=1, so there's a conflict between the two libraries.
# pylibseekdb is built both with ABI=0 and the -Bsymbolic flag, so we can load libraries with ABI=1 first
# and then pylibseekdb to avoid these conflicts.
if importlib.util.find_spec("onnxruntime"):
    import onnxruntime  # noqa: F401

# torch and pylibseekdb both use openmp library, which is conflict on macos.
if importlib.util.find_spec("torch"):
    import torch  # noqa: F401

from .client import (
    AdminAPI,
    AdminClient,
    BaseClient,
    BaseConnection,
    BengProperties,
    Client,
    ClientAPI,
    Configuration,
    Database,
    DefaultEmbeddingFunction,
    EmbeddingFunction,
    FulltextIndexConfig,
    HNSWConfiguration,
    IKMode,
    IKProperties,
    K,
    Ngram2Properties,
    NgramProperties,
    RemoteServerClient,
    Schema,
    SpaceProperties,
    SparseEmbeddingFunction,
    SparseEmbeddingFunctionRegistry,
    SparseVector,
    SparseVectorIndexConfig,
    VectorIndexConfig,
    Version,
    get_default_embedding_function,
    register_embedding_function,
    register_sparse_embedding_function,
)
from .client.collection import Collection

try:
    __version__ = importlib.metadata.version("pyseekdb")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.1.dev1"

__author__ = "OceanBase <open_oceanbase@oceanbase.com>"

__all__ = [
    "AdminAPI",
    "AdminClient",
    "BaseClient",
    "BaseConnection",
    "BengProperties",
    "Client",
    "ClientAPI",
    "Collection",
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
    "RemoteServerClient",
    "Schema",
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
