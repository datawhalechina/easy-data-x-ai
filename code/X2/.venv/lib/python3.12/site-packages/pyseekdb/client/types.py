# Sentinel object to distinguish between "parameter not provided" and "explicitly set to None"
class _NotProvided:
    """Sentinel object to indicate a parameter was not provided"""

    pass


_NOT_PROVIDED = _NotProvided()


class FieldKey:
    """
    Key constants for referencing collection fields.

    Used with ``SparseVectorIndexConfig.source_key`` to specify which field
    to use as source data for sparse vector generation, and with
    ``Collection.query(query_key=...)`` to specify which index to search.

    Special keys starting with '#' reference built-in collection columns.
    Plain strings reference metadata fields.

    Example:
        >>> # Use document field as source for sparse vectors
        >>> config = SparseVectorIndexConfig(source_key=K.DOCUMENT)
        >>>
        >>> # Use metadata field "title" as source
        >>> config = SparseVectorIndexConfig(source_key="title")
        >>>
        >>> # Query using sparse embedding index
        >>> results = collection.query(query_texts=["fox"], query_key=K.SPARSE_EMBEDDING)
    """

    ID: "FieldKey"
    DOCUMENT: "FieldKey"
    EMBEDDING: "FieldKey"
    SPARSE_EMBEDDING: "FieldKey"
    SCORE: "FieldKey"

    def __init__(self, name: str):
        self.name = name


FieldKey.ID = FieldKey("#id")
FieldKey.DOCUMENT = FieldKey("#document")
FieldKey.EMBEDDING = FieldKey("#embedding")
FieldKey.SPARSE_EMBEDDING = FieldKey("#sparse_embedding")
FieldKey.SCORE = FieldKey("#score")

K = FieldKey
