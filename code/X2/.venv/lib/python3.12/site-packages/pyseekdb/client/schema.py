"""
Schema and index configuration for collection creation.

The Schema class provides fine-grained control over index configuration,
including dense vector index (HNSW), sparse vector index, and fulltext index.

Schema replaces the simpler Configuration approach while maintaining backward
compatibility. When a Schema is provided to ``create_collection``, the older
``configuration`` and ``embedding_function`` parameters are ignored.

Example:
    >>> from pyseekdb import Schema, SparseVectorIndexConfig, VectorIndexConfig
    >>> from pyseekdb.utils.embedding_functions import BM25EmbeddingFunction
    >>>
    >>> schema = Schema(
    ...     vector_index=VectorIndexConfig(hnsw=HNSWConfiguration(dimension=384, distance="cosine")),
    ...     sparse_vector_index=SparseVectorIndexConfig(
    ...         embedding_function=BM25EmbeddingFunction(),
    ...         source_key=K.DOCUMENT
    ...     )
    ... )
    >>> collection = client.create_collection("my_collection", schema=schema)
"""

from __future__ import annotations

from typing import Any

from .configuration import FulltextIndexConfig, HNSWConfiguration, SparseVectorIndexConfig, VectorIndexConfig


class Schema:
    """
    Schema configuration for collection creation.

    Schema provides fine-grained control over indexes and their parameters.
    When provided to ``create_collection``, the older ``configuration`` and
    ``embedding_function`` parameters are ignored.

    Default behavior:
    - If ``vector_index`` is not specified, a default HNSW index with L2 distance is used.
    - If ``fulltext_index`` is not specified, a default fulltext index with IK analyzer is used.
    - ``sparse_vector_index`` is optional and defaults to None (no sparse index).

    Args:
        vector_index: HNSW configuration for dense vector index (optional).
        sparse_vector_index: Sparse vector index configuration (optional).
        fulltext_index: Fulltext index configuration (optional).
        embedding_function: Dense embedding function (optional). If provided with
            ``vector_index``, this is associated with the dense vector index.

    Example:
        >>> # Simple schema with sparse vector index
        >>> schema = Schema(
        ...     sparse_vector_index=SparseVectorIndexConfig(
        ...         embedding_function=BM25EmbeddingFunction(),
        ...         source_key=K.DOCUMENT
        ...     )
        ... )
        >>>
        >>> # Full schema with all indexes
        >>> schema = Schema(
        ...     vector_index=VectorIndexConfig(
        ...         hnsw=HNSWConfiguration(dimension=768, distance="cosine"),
        ...         embedding_function=OpenAIEmbeddingFunction(api_key_env="OPENAI_API_KEY")
        ...     ),
        ...     sparse_vector_index=SparseVectorIndexConfig(
        ...         embedding_function=BM25EmbeddingFunction()
        ...     ),
        ...     fulltext_index=FulltextIndexConfig(analyzer="ik"),
        ...
        ... )
        >>>
        >>> # Schema using create_index chaining
        >>> schema = Schema().create_index(
        ...     VectorIndexConfig(
        ...         hnsw=HNSWConfiguration(dimension=768, distance="cosine"),
        ...         embedding_function=OpenAIEmbeddingFunction(api_key_env="OPENAI_API_KEY")
        ...     )
        ... ).create_index(
        ...     SparseVectorIndexConfig(embedding_function=BM25EmbeddingFunction())
        ... )
    """

    def __init__(
        self,
        vector_index: VectorIndexConfig | HNSWConfiguration | None = None,
        sparse_vector_index: SparseVectorIndexConfig | None = None,
        fulltext_index: FulltextIndexConfig | None = None,
    ):
        if isinstance(vector_index, VectorIndexConfig):
            self.vector_index = vector_index
        elif isinstance(vector_index, HNSWConfiguration):
            self.vector_index = VectorIndexConfig(hnsw=vector_index)
        elif vector_index is None:
            # Default: will be resolved during create_collection
            self.vector_index = VectorIndexConfig()
        else:
            raise TypeError(
                f"Unsupported vector index configuration type: {type(vector_index).__name__}. "
                f"Expected VectorIndexConfig, HNSWConfiguration, or None."
            )
        self.sparse_vector_index = sparse_vector_index
        self.fulltext_index = fulltext_index

    def create_index(self, config: Any) -> Schema:
        """
        Add an index configuration to this schema.

        Supports method chaining for fluent API usage.

        Args:
            config: Index configuration object. Can be:
                - ``VectorIndexConfig``: configures the dense vector index
                - ``HNSWConfiguration``: configures the dense vector index with `DefaultEmbeddingFunction`
                - ``SparseVectorIndexConfig``: configures the sparse vector index
                - ``FulltextIndexConfig``: configures the fulltext index

        Returns:
            This Schema instance (for chaining).

        Raises:
            TypeError: If config is not a recognized index configuration type.

        Example:
            >>> schema = Schema().create_index(
            ...     HNSWConfiguration(dimension=384, distance="cosine")
            ... ).create_index(
            ...     SparseVectorIndexConfig(embedding_function=BM25EmbeddingFunction())
            ... )
        """
        if isinstance(config, HNSWConfiguration):
            self.vector_index = VectorIndexConfig(hnsw=config)
        elif isinstance(config, VectorIndexConfig):
            self.vector_index = config
        elif isinstance(config, SparseVectorIndexConfig):
            self.sparse_vector_index = config
        elif isinstance(config, FulltextIndexConfig):
            self.fulltext_index = config
        else:
            raise TypeError(
                f"Unsupported index configuration type: {type(config).__name__}. "
                f"Expected VectorIndexConfig, HNSWConfiguration, SparseVectorIndexConfig, or FulltextIndexConfig."
            )
        return self

    def __repr__(self) -> str:
        parts = []
        if self.vector_index is not None:
            parts.append(f"vector_index={self.vector_index}")
        if self.sparse_vector_index is not None:
            parts.append(f"sparse_vector_index={self.sparse_vector_index}")
        if self.fulltext_index is not None:
            parts.append(f"fulltext_index={self.fulltext_index}")
        return f"Schema({', '.join(parts)})"
