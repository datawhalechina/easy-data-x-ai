"""
Collection class - represents a collection and provides unified data operation interface

Design Pattern:
1. Collection itself contains no business logic
2. All operations are delegated to the client that created it
3. Different clients can have completely different underlying implementations
4. User-facing interface is completely consistent
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .embedding_function import Documents as EmbeddingDocuments
    from .embedding_function import EmbeddingFunction
    from .query_types import QueryHint
    from .schema import SparseVectorIndexConfig
    from .sparse_embedding_function import SparseEmbeddingFunction


class Collection:
    """
    Collection unified interface class

    Design Principles:
    - Collection is a lightweight wrapper that only holds metadata
    - All operations delegate to the client via self._client._collection_*() methods
    - Different clients (OceanBase, Seekdb, Milvus, etc.) provide different implementations
    - Users see identical interface regardless of which client created the collection
    """

    def __init__(
        self,
        client: Any,  # BaseClient instance
        name: str,
        collection_id: str | None = None,
        dimension: int | None = None,
        embedding_function: Optional["EmbeddingFunction[EmbeddingDocuments]"] = None,
        distance: str | None = None,
        sparse_vector_index_config: Optional["SparseVectorIndexConfig"] = None,
        **metadata,
    ):
        """
        Initialize collection object

        Args:
            client: The client instance that created this collection
            name: Collection name
            collection_id: Collection unique identifier (some databases may need this)
            dimension: Vector dimension
            embedding_function: Embedding function to convert documents to embeddings
            distance: Distance metric used by the index (e.g., 'l2', 'cosine', 'inner_product')
            sparse_vector_index_config: Sparse vector index configuration (optional).
                When set, the collection supports sparse vector operations.
            **metadata: Other metadata
        """
        self._client = client  # Core: hold reference to the client
        self._name = name
        self._id = collection_id
        self._dimension = dimension
        self._embedding_function = embedding_function
        self._distance = distance
        self._sparse_vector_index_config = sparse_vector_index_config
        self._metadata = metadata

    # ==================== Properties ====================

    @property
    def name(self) -> str:
        """Collection name"""
        return self._name

    @property
    def id(self) -> str | None:
        """Collection ID"""
        return self._id

    @property
    def dimension(self) -> int | None:
        """Vector dimension"""
        return self._dimension

    @property
    def client(self) -> Any:
        """Associated client"""
        return self._client

    @property
    def metadata(self) -> dict[str, Any]:
        """Collection metadata"""
        return self._metadata

    @property
    def embedding_function(self) -> Optional["EmbeddingFunction[EmbeddingDocuments]"]:
        """Embedding function for this collection"""
        return self._embedding_function

    @property
    def distance(self) -> str | None:
        """Distance metric used by the index (e.g., 'l2', 'cosine', 'inner_product')"""
        return self._distance

    @property
    def sparse_vector_index_config(self) -> Optional["SparseVectorIndexConfig"]:
        """Sparse vector index configuration, if any."""
        return self._sparse_vector_index_config

    @property
    def sparse_embedding_function(self) -> Optional["SparseEmbeddingFunction"]:
        """Sparse embedding function for this collection, if configured."""
        if self._sparse_vector_index_config is not None:
            return self._sparse_vector_index_config.embedding_function
        return None

    def __repr__(self) -> str:
        return f"Collection(name='{self._name}', dimension={self._dimension}, client={self._client.mode})"

    def fork(self, forked_name: str) -> "Collection":
        """
        Fork (duplicate) this collection to create a new collection with the same data.

        The forked collection is independent - modifications to one collection do not
        affect the other. The original collection remains unchanged.

        Args:
            forked_name: Name for the new forked collection. Must be a valid collection name
                        (letters, digits, and underscores only, not empty).

        Returns:
            Collection: The newly created forked collection.

        Raises:
            ValueError: If fork is not enabled for this database, if the collection name
                       is invalid, or if a collection with the given name already exists.

        Note:
            - Fork is only available for seekdb database version 1.1.0.0 or higher.

        Examples:
        .. code-block:: python
            # Fork a collection
            original = client.get_collection("my_collection")
            forked = original.fork("my_collection_backup")

            # Verify both collections have the same data
            assert original.count() == forked.count()

            # Add data to forked collection (original is unaffected)
            forked.add(ids="new_id", embeddings=[1.0, 2.0, 3.0], documents="New document")
            assert original.count() == 3  # Original unchanged
            assert forked.count() == 4    # Forked has new data

        """
        self._client._collection_fork(collection=self, forked_name=forked_name)
        collection = self._client.get_collection(forked_name, embedding_function=self._embedding_function)
        return collection

    # ==================== DML Operations ====================
    # All methods delegate to client's internal implementation

    def add(
        self,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Add data to collection

        Args:
            ids: Single ID or list of IDs
            embeddings: Single embedding or list of embeddings (optional if documents provided and embedding_function is set)
            metadatas: Single metadata dict or list of metadata dicts (optional)
            documents: Single document or list of documents (optional)
                       If provided without embeddings, embedding_function will be used to generate embeddings
            **kwargs: Additional parameters

        Examples:
            # Add single item with embeddings
            collection.add(ids="1", embeddings=[0.1, 0.2, 0.3], metadatas={"tag": "A"})

            # Add multiple items with embeddings
            collection.add(
                ids=["1", "2", "3"],
                embeddings=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
                metadatas=[{"tag": "A"}, {"tag": "B"}, {"tag": "C"}]
            )

            # Add items with documents (embeddings will be auto-generated if embedding_function is set)
            collection.add(
                ids=["1", "2"],
                documents=["Hello world", "How are you?"],
                metadatas=[{"tag": "A"}, {"tag": "B"}]
            )
        """
        return self._client._collection_add(
            collection_id=self._id,
            collection_name=self._name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
            embedding_function=self._embedding_function,
            sparse_vector_index_config=self._sparse_vector_index_config,
            **kwargs,
        )

    def update(
        self,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Update existing data in collection

        Args:
            ids: Single ID or list of IDs to update
            embeddings: New embeddings (optional)
            metadatas: New metadata (optional)
            documents: New documents (optional)
            **kwargs: Additional parameters

        Note:
            IDs must exist, otherwise an error will be raised

        Examples:
            # Update single item
            collection.update(ids="1", metadatas={"tag": "B"})

            # Update multiple items
            collection.update(
                ids=["1", "2"],
                embeddings=[[0.9, 0.8], [0.7, 0.6]]
            )
        """
        return self._client._collection_update(
            collection_id=self._id,
            collection_name=self._name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
            embedding_function=self._embedding_function,
            sparse_vector_index_config=self._sparse_vector_index_config,
            **kwargs,
        )

    def upsert(
        self,
        ids: str | list[str],
        embeddings: list[float] | list[list[float]] | None = None,
        metadatas: dict | list[dict] | None = None,
        documents: str | list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Insert or update data in collection

        Args:
            ids: Single ID or list of IDs
            embeddings: embeddings (optional if documents provided)
            metadatas: Metadata (optional)
            documents: Documents (optional)
            **kwargs: Additional parameters

        Note:
            If ID exists, update it; otherwise, insert new data

        Examples:
            # Upsert single item
            collection.upsert(ids="1", embeddings=[0.1, 0.2], metadatas={"tag": "A"})

            # Upsert multiple items
            collection.upsert(
                ids=["1", "2", "3"],
                embeddings=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
            )
        """
        return self._client._collection_upsert(
            collection_id=self._id,
            collection_name=self._name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
            embedding_function=self._embedding_function,
            sparse_vector_index_config=self._sparse_vector_index_config,
            **kwargs,
        )

    def delete(
        self,
        ids: str | list[str] | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        """
        Delete data from collection

        Args:
            ids: Single ID or list of IDs to delete (optional)
            where: Filter condition on metadata (optional)
            where_document: Filter condition on documents (optional)
            **kwargs: Additional parameters

        Note:
            At least one of ids, where, or where_document must be provided

        Examples:
            # Delete by IDs
            collection.delete(ids=["1", "2", "3"])

            # Delete by metadata filter
            collection.delete(where={"tag": "A"})

            # Delete by document filter
            collection.delete(where_document={"$contains": "keyword"})
        """
        return self._client._collection_delete(
            collection_id=self._id,
            collection_name=self._name,
            ids=ids,
            where=where,
            where_document=where_document,
            **kwargs,
        )

    # ==================== DQL Operations ====================

    def query(
        self,
        query_embeddings: list[float] | list[list[float]] | None = None,
        query_texts: str | list[str] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        include: list[str] | None = None,
        query_key: Any | None = None,
        query_hint: "QueryHint | None" = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Query collection by vector similarity

        Args:
            query_embeddings: Query vector(s) (optional if query_texts provided).
                For dense vector queries: list[float] or list[list[float]].
                For sparse vector queries, provide query_texts instead and let the
                configured sparse embedding function generate sparse vectors.
            query_texts: Query text(s) to be embedded (optional if query_embeddings provided)
            n_results: Number of results to return (default: 10)
            where: Filter condition on metadata supporting:
                   - Comparison operators: $eq, $lt, $gt, $lte, $gte, $ne, $in, $nin
                   - Logical operators: $or, $and, $not
            where_document: Filter condition on documents supporting:
                   - $contains: full-text search
                   - $regex: regular expression matching
                   - Logical operators: $or, $and
            include: Fields to include in results, e.g., ["documents", "metadatas", "embeddings"] (optional)
                     By default, returns "documents" and "metadatas". Always includes "_id".
            query_key: Specify which index to query. Default is None (dense vector).
                       Use ``K.SPARSE_EMBEDDING`` (or ``"#sparse_embedding"``)
                       to query using sparse vector index.
            query_hint: Query optimization hints for database execution (optional)
            **kwargs: Additional parameters

        Returns:
            Dict with keys (chromadb-compatible format):
            - ids: List[List[str]] - List of ID lists, one list per query
            - documents: Optional[List[List[str]]] - List of document lists, one list per query (if included)
            - metadatas: Optional[List[List[Dict]]] - List of metadata lists, one list per query (if included)
            - embeddings: Optional[List[List[List[float]]]] - List of embedding lists, one list per query (if included)
            - distances: Optional[List[List[float]]] - List of distance lists, one list per query

        Examples:
            # Query by single embedding (dense vector)
            results = collection.query(
                query_embeddings=[0.1, 0.2, 0.3],
                n_results=5
            )

            # Query by texts (will be embedded automatically)
            results = collection.query(
                query_texts=["my query text"],
                n_results=10
            )

            # Sparse vector query using query_key
            results = collection.query(
                query_texts=["fox animal"],
                query_key=K.SPARSE_EMBEDDING,
                n_results=5
            )

            # Query with query hint
            from pyseekdb.client.query_types import QueryHint
            results = collection.query(
                query_texts=["machine learning"],
                n_results=5,
                where={"score": {"$gte": 90}},
                query_hint=QueryHint(parallel=8, query_timeout=10.0)
            )
        """
        return self._client._collection_query(
            collection_id=self._id,
            collection_name=self._name,
            query_embeddings=query_embeddings,
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include,
            query_hint=query_hint,
            embedding_function=self._embedding_function,
            distance=self._distance,
            query_key=query_key,
            sparse_vector_index_config=self._sparse_vector_index_config,
            **kwargs,
        )

    def get(
        self,
        ids: str | list[str] | None = None,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include: list[str] | None = None,
        query_hint: "QueryHint | None" = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Get data from collection by IDs or filters

        Args:
            ids: Single ID or list of IDs to retrieve (optional)
            where: Filter condition on metadata (optional)
            where_document: Filter condition on documents (optional)
            limit: Maximum number of results to return (optional)
            offset: Number of results to skip (optional)
            include: Fields to include in results, e.g., ["metadatas", "documents", "embeddings"] (optional)
            query_hint: Query optimization hints for database execution (optional)
            **kwargs: Additional parameters

        Returns:
            Dict with keys (chromadb-compatible format):
            - ids: List[str] - List of IDs
            - documents: Optional[List[str]] - List of documents (if included)
            - metadatas: Optional[List[Dict]] - List of metadata dictionaries (if included)
            - embeddings: Optional[List[List[float]]] - List of embeddings (if included)

        Note:
            If no parameters provided, returns all data (up to limit)

        Examples:
            # Get by single ID
            results = collection.get(ids="1")
            # results["ids"] contains ["1"]
            # results["documents"] contains document for ID "1"

            # Get by multiple IDs
            results = collection.get(ids=["1", "2", "3"])
            # results["ids"] contains ["1", "2", "3"]
            # results["documents"] contains documents for all IDs

            # Get by filter
            results = collection.get(
                where={"tag": "A"},
                limit=10
            )
            # results["ids"] contains all matching IDs
            # results["documents"] contains all matching documents

            # Get all data
            results = collection.get(limit=100)

            # Get with query hint
            from pyseekdb.client.query_types import QueryHint
            results = collection.get(
                where={"category": "AI"},
                limit=10,
                query_hint=QueryHint(parallel=4, query_timeout=5.0)
            )
        """
        return self._client._collection_get(
            collection_id=self._id,
            collection_name=self._name,
            ids=ids,
            where=where,
            where_document=where_document,
            limit=limit,
            offset=offset,
            include=include,
            query_hint=query_hint,
            **kwargs,
        )

    def hybrid_search(
        self,
        query: dict[str, Any] | None = None,
        knn: dict[str, Any] | None = None,
        rank: dict[str, Any] | None = None,
        n_results: int = 10,
        include: list[str] | None = None,
        query_hint: "QueryHint | None" = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Hybrid search combining full-text search and vector similarity search

        Args:
            query: Full-text search configuration dict with:
                - where_document: Document filter conditions (e.g., {"$contains": "text"})
                - where: Metadata filter conditions (e.g., {"page": {"$gte": 5}})
                - n_results: Number of results for full-text search (optional)
            knn: Vector search configuration dict with:
                - query_texts: Query text(s) to be embedded (optional if query_embeddings provided)
                - query_embeddings: Query vector(s) (optional if query_texts provided)
                - where: Metadata filter conditions (optional)
                - n_results: Number of results for vector search (optional)
            rank: Ranking configuration dict (e.g., {"rrf": {"rank_window_size": 60, "rank_constant": 60}})
            n_results: Final number of results to return after ranking (default: 10)
            include: Fields to include in results (e.g., ["documents", "metadatas", "embeddings"])
            query_hint: Query optimization hints for database execution (optional)
            **kwargs: Additional parameters

        Returns:
            Dict with keys (query-compatible format):
            - ids: List[List[str]] - List of ID lists (one list for hybrid search result)
            - documents: Optional[List[List[str]]] - List of document lists (if included)
            - metadatas: Optional[List[List[Dict]]] - List of metadata lists (if included)
            - embeddings: Optional[List[List[List[float]]]] - List of embedding lists (if included)
            - distances: Optional[List[List[float]]] - List of distance lists

        Examples:
            # Hybrid search with both full-text and vector search
            results = collection.hybrid_search(
                query={
                    "where_document": {"$contains": "machine learning"},
                    "where": {"category": {"$eq": "science"}},
                    "n_results": 10
                },
                knn={
                    "query_texts": ["AI research"],
                    "where": {"year": {"$gte": 2020}},
                    "n_results": 10
                },
                rank={"rrf": {}},
                n_results=5,
                include=["documents", "metadatas", "embeddings"]
            )
            # results["ids"][0] contains IDs for the hybrid search
            # results["documents"][0] contains documents for the hybrid search
            # results["distances"][0] contains distances for the hybrid search

            # Hybrid search with query hint
            from pyseekdb.client.query_types import QueryHint
            results = collection.hybrid_search(
                query={
                    "where_document": {"$contains": "AI"},
                    "n_results": 8
                },
                knn={
                    "query_texts": ["artificial intelligence"],
                    "n_results": 8
                },
                rank={"rrf": {"rank_window_size": 60}},
                n_results=10,
                query_hint=QueryHint(parallel=6, query_timeout=15.0)
            )
        """
        # When no query/knn provided, return only ids/distances by default
        if include is None and not query and not knn:
            include = []

        return self._client._collection_hybrid_search(
            collection_id=self._id,
            collection_name=self._name,
            query=query,
            knn=knn,
            rank=rank,
            n_results=n_results,
            include=include,
            query_hint=query_hint,
            embedding_function=self._embedding_function,
            dimension=self._dimension,
            **kwargs,
        )

    def refresh_index(self) -> None:
        """
        Flush async vector index build tasks.

        This executes ``CALL dbms_index_manager.refresh();`` and returns only
        after the database completes the refresh procedure.

        Note:
            This method is only available for seekdb version 1.3.0.0 or higher.
            In 1.2.0.0 and earlier, this method is a no-op.
        """
        self._client.refresh_index()

    # ==================== Collection Info ====================

    def count(self) -> int:
        """
        Get the number of items in collection

        Returns:
            Item count

        Examples:
            count = collection.count()
            print(f"Collection has {count} items")
        """
        return self._client._collection_count(collection_id=self._id, collection_name=self._name)

    def peek(self, limit: int = 10) -> dict[str, Any]:
        """
        Quickly preview the first few items in the collection

        Args:
            limit: Number of items to preview (default: 10)

        Returns:
            Dict with keys (chromadb-compatible format):
            - ids: List[str] - List of IDs
            - documents: List[str] - List of documents (always included)
            - metadatas: List[Dict] - List of metadata dictionaries (always included)
            - embeddings: List[List[float]] - List of embeddings (always included)

        Examples:
            # Preview first 5 items (returns all columns by default)
            preview = collection.peek(limit=5)
            for i in range(len(preview["ids"])):
                print(f"ID: {preview['ids'][i]}, Document: {preview['documents'][i]}")
                print(f"Metadata: {preview['metadatas'][i]}, Embedding: {preview['embeddings'][i]}")
        """
        return self._client._collection_get(
            collection_id=self._id,
            collection_name=self._name,
            limit=limit,
            offset=0,
            include=["documents", "metadatas", "embeddings"],
        )
