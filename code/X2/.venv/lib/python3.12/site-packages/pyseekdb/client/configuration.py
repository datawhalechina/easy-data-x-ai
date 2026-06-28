import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict

from pyseekdb.client.embedding_function import DefaultEmbeddingFunction, EmbeddingFunction
from pyseekdb.client.sparse_embedding_function import SparseEmbeddingFunction
from pyseekdb.client.types import _NOT_PROVIDED, K

# Default configuration constants
# Note: Default embedding function (DefaultEmbeddingFunction) produces 384-dim embeddings
# So we use 384 as the default dimension to match
DEFAULT_VECTOR_DIMENSION = 384  # Matches DefaultEmbeddingFunction dimension
DEFAULT_DISTANCE_METRIC = "cosine"
PrimitiveValue = str | int | float | bool


def _ensure_primitive_properties(properties: dict[str, Any] | None, *, field_name: str = "properties") -> None:
    if properties is None:
        return
    if not isinstance(properties, dict):
        raise TypeError(f"{field_name} must be a dictionary")
    for value in properties.values():
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError(f"{field_name} must be a dictionary of string, int, float, or bool, got {value}")


def _normalize_str_enum(value: str | Enum, *, field_name: str) -> str:
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
    return value.lower()


def _validate_int_range(value: Any, *, key: str, min_value: int, max_value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer, got {type(value).__name__}")
    if value < min_value or value > max_value:
        raise ValueError(f"{key} must be between {min_value} and {max_value}, got '{value}'")


def _validate_float_range(value: Any, *, key: str, min_value: float, max_value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number, got {type(value).__name__}")
    numeric_value = float(value)
    if numeric_value < min_value or numeric_value > max_value:
        raise ValueError(f"{key} must be between {min_value} and {max_value}, got '{value}'")


def _validate_space_or_beng_properties(properties: dict[str, PrimitiveValue]) -> None:
    if not properties:
        return
    min_token_size = properties.get("min_token_size")
    max_token_size = properties.get("max_token_size")
    if min_token_size is not None:
        _validate_int_range(min_token_size, key="min_token_size", min_value=1, max_value=16)
    if max_token_size is not None:
        _validate_int_range(max_token_size, key="max_token_size", min_value=10, max_value=84)
    if min_token_size is not None and max_token_size is not None and max_token_size < min_token_size:
        raise ValueError(
            "max_token_size should not be less than min_token_size. "
            f"max_token_size='{max_token_size}', min_token_size='{min_token_size}'"
        )


def _validate_ngram_properties(properties: dict[str, PrimitiveValue]) -> None:
    if not properties:
        return
    if "ngram_token_size" in properties:
        _validate_int_range(properties["ngram_token_size"], key="ngram_token_size", min_value=1, max_value=10)


def _validate_ngram2_properties(properties: dict[str, PrimitiveValue]) -> None:
    if not properties:
        return
    min_ngram_size = properties.get("min_ngram_size")
    max_ngram_size = properties.get("max_ngram_size")
    if min_ngram_size is not None:
        _validate_int_range(min_ngram_size, key="min_ngram_size", min_value=1, max_value=16)
    if max_ngram_size is not None:
        _validate_int_range(max_ngram_size, key="max_ngram_size", min_value=1, max_value=16)
    if min_ngram_size is not None and max_ngram_size is not None and max_ngram_size < min_ngram_size:
        raise ValueError(
            "max_ngram_size should not be less than min_ngram_size. "
            f"max_ngram_size='{max_ngram_size}', min_ngram_size='{min_ngram_size}'"
        )


def _normalize_ik_mode(properties: dict[str, PrimitiveValue]) -> None:
    if not properties:
        return
    if "ik_mode" not in properties:
        return
    ik_mode = properties["ik_mode"]
    if isinstance(ik_mode, IKMode):
        ik_mode = ik_mode.value
    if not isinstance(ik_mode, str):
        raise TypeError(f"ik_mode must be a string, got {type(ik_mode).__name__}")
    ik_mode = ik_mode.lower()
    if ik_mode not in {mode.value for mode in IKMode}:
        raise ValueError(f"ik_mode should be one of ['smart', 'max_word'], got '{ik_mode}'")
    properties["ik_mode"] = ik_mode


def _validate_fulltext_properties_by_analyzer(analyzer: str, properties: dict[str, PrimitiveValue] | None) -> None:
    if not properties:
        return
    if analyzer in {FulltextAnalyzer.SPACE.value, FulltextAnalyzer.BENG.value}:
        _validate_space_or_beng_properties(properties)
    elif analyzer == FulltextAnalyzer.NGRAM.value:
        _validate_ngram_properties(properties)
    elif analyzer == FulltextAnalyzer.NGRAM2.value:
        _validate_ngram2_properties(properties)
    elif analyzer == FulltextAnalyzer.IK.value:
        _normalize_ik_mode(properties)


def _validate_hnsw_base_fields(config: "HNSWConfiguration") -> None:
    if isinstance(config.dimension, bool) or not isinstance(config.dimension, int):
        raise TypeError(f"dimension must be an integer, got {type(config.dimension).__name__}")
    _validate_int_range(config.dimension, key="dimension", min_value=1, max_value=4096)

    config.distance = _normalize_str_enum(config.distance, field_name="distance")
    valid_distances = [e.value for e in DistanceMetric]
    if config.distance not in valid_distances:
        raise ValueError(f"distance must be one of {valid_distances}, got {config.distance}")

    config.type = _normalize_str_enum(config.type, field_name="type")
    valid_types = [e.value for e in HNSWIndexType]
    if config.type not in valid_types:
        raise ValueError(f"type must be one of {valid_types}, got {config.type}")

    config.lib = _normalize_str_enum(config.lib, field_name="lib")
    valid_libs = [e.value for e in HNSWIndexLib]
    if config.lib not in valid_libs:
        raise ValueError(f"lib must be one of {valid_libs}, got {config.lib}")


def _normalize_hnsw_properties(properties: dict[str, PrimitiveValue]) -> None:
    reserved_keys = [
        key
        for key in properties
        if key.lower()
        in {
            "distance",
            "type",
            "lib",
            "m",
            "ef_construction",
            "ef_search",
            "extra_info_max_size",
            "refine_k",
            "refine_type",
            "bq_bits_query",
            "bq_use_fht",
        }
    ]
    for key in reserved_keys:
        warnings.warn(f"{key} is a reserved keyword in properties, it will be ignored", stacklevel=2)
        properties.pop(key)


def _validate_hnsw_configuration(config: "HNSWConfiguration") -> None:
    if config.M is not None:
        _validate_int_range(config.M, key="M", min_value=5, max_value=128)
    if config.ef_construction is not None:
        _validate_int_range(config.ef_construction, key="ef_construction", min_value=5, max_value=1000)
    if config.ef_search is not None:
        _validate_int_range(config.ef_search, key="ef_search", min_value=1, max_value=1000)
    if config.extra_info_max_size is not None:
        _validate_int_range(config.extra_info_max_size, key="extra_info_max_size", min_value=0, max_value=16384)
    if config.refine_k is not None:
        _validate_float_range(config.refine_k, key="refine_k", min_value=1.0, max_value=1000.0)
    if config.refine_type is not None:
        config.refine_type = _normalize_str_enum(config.refine_type, field_name="refine_type")
        valid_refine_types = [e.value for e in BQRefineType]
        if config.refine_type not in valid_refine_types:
            raise ValueError(f"refine_type must be one of {valid_refine_types}, got {config.refine_type}")
    if config.bq_bits_query is not None and config.bq_bits_query not in {0, 4, 32}:
        raise ValueError(f"bq_bits_query must be one of [0, 4, 32], got '{config.bq_bits_query}'")
    if config.bq_use_fht is not None and not isinstance(config.bq_use_fht, bool):
        raise TypeError(f"bq_use_fht must be a bool, got {type(config.bq_use_fht).__name__}")


class DistanceMetric(str, Enum):
    """
    Distance metric constants for vector similarity calculation.

    Values can be used as strings (e.g., DistanceMetric.L2 == 'l2').
    """

    L2 = "l2"
    COSINE = "cosine"
    INNER_PRODUCT = "inner_product"


class HNSWIndexType(str, Enum):
    HNSW = "hnsw"
    HNSW_SQ = "hnsw_sq"
    HNSW_BQ = "hnsw_bq"


class HNSWIndexLib(str, Enum):
    VSAG = "vsag"


class FulltextAnalyzer(str, Enum):
    SPACE = "space"
    NGRAM = "ngram"
    BENG = "beng"
    IK = "ik"
    NGRAM2 = "ngram2"


class IKMode(str, Enum):
    SMART = "smart"
    MAX_WORD = "max_word"


class BQRefineType(str, Enum):
    SQ8 = "sq8"
    FP32 = "fp32"


@dataclass
class FulltextIndexConfig:
    """
    Fulltext analyzer configuration for fulltext indexing.

    Args:
        analyzer: Analyzer name, can be 'space', 'ngram', 'ngram2', 'beng', 'ik' and so on (default: 'ik')
        properties: Optional dictionary of parser-specific parameters (key: string, value: primitive type)
    """

    analyzer: str | FulltextAnalyzer = FulltextAnalyzer.IK.value
    properties: dict[str, PrimitiveValue] | None = None

    def __post_init__(self):
        self.analyzer = _normalize_str_enum(self.analyzer, field_name="analyzer")
        _ensure_primitive_properties(self.properties)

        valid_analyzers = {analyzer.value for analyzer in FulltextAnalyzer}
        if self.analyzer not in valid_analyzers:
            warnings.warn(
                f"Unknown analyzer '{self.analyzer}'. "
                "This may be a newer kernel analyzer. SDK will pass through properties as-is.",
                UserWarning,
                stacklevel=2,
            )
            return

        if not self.properties:
            return

        _validate_fulltext_properties_by_analyzer(self.analyzer, self.properties)


@dataclass
class HNSWConfiguration:
    """
    HNSW (Hierarchical Navigable Small World) index configuration

    Args:
        dimension: Vector dimension (number of elements in each vector)
        distance: Distance metric for similarity calculation (e.g., 'l2', 'cosine', 'inner_product')
        properties: Optional dictionary of properties for the HNSW index (key: string, value: primitive type)
        Please refer to [HNSW configuration](https://en.oceanbase.com/docs/common-oceanbase-database-10000000003351043) for detailed information.
    """

    dimension: int = DEFAULT_VECTOR_DIMENSION
    distance: str | DistanceMetric = DistanceMetric.COSINE.value
    type: str | HNSWIndexType = HNSWIndexType.HNSW.value
    lib: str | HNSWIndexLib = HNSWIndexLib.VSAG.value
    M: int | None = None
    ef_construction: int | None = None
    ef_search: int | None = None
    extra_info_max_size: int | None = None
    refine_k: float | None = None
    refine_type: str | BQRefineType | None = None
    bq_bits_query: int | None = None
    bq_use_fht: bool | None = None
    properties: dict[str, PrimitiveValue] | None = None

    def __post_init__(self):
        _validate_hnsw_base_fields(self)
        _validate_hnsw_configuration(self)

        _ensure_primitive_properties(self.properties)
        if not self.properties:
            return

        _normalize_hnsw_properties(self.properties)


class IKProperties(TypedDict, total=False):
    ik_mode: str | IKMode


class SpaceProperties(TypedDict, total=False):
    min_token_size: int
    max_token_size: int


class NgramProperties(TypedDict, total=False):
    ngram_token_size: int


class Ngram2Properties(TypedDict, total=False):
    min_ngram_size: int
    max_ngram_size: int


class BengProperties(TypedDict, total=False):
    min_token_size: int
    max_token_size: int


@dataclass
class VectorIndexConfig:
    hnsw: HNSWConfiguration | None = None
    embedding_function: EmbeddingFunction | None = _NOT_PROVIDED

    def __post_init__(self):
        if self.embedding_function is _NOT_PROVIDED:
            self.embedding_function = DefaultEmbeddingFunction()
        if self.hnsw is not None:
            self.hnsw.__post_init__()


@dataclass
class SparseVectorIndexConfig:
    """
    Sparse vector index configuration.

    Sparse vectors are suitable for keyword-based retrieval (e.g., BM25, SPLADE).
    They complement dense vectors and can be used for hybrid search.

    Args:
        embedding_function: Sparse embedding function (e.g., BM25EmbeddingFunction, SpladeEmbeddingFunction).
        source_key: Source field key specifying which field to generate sparse vectors from.
            - ``K.DOCUMENT`` or ``"#document"``: use the document field (default)
            - A plain string like ``"title"``: use ``metadata["title"]``
        lib: Vector index library (default: "vsag")
        distance: Distance metric (default: "inner_product"). Only inner_product is supported
            for sparse vectors.
        type: Index type (default: "sindi")
        prune: Whether to enable pruning (default: False)
        refine: Whether to enable refining (default: False)
        drop_ratio_build: Drop ratio for index building (default: 0.0)
        drop_ratio_search: Drop ratio for search (default: 0.0)
        refine_k: Refine K factor (default: 4.0)

    Note:
        - Each collection can have at most one sparse vector index.
        - Sparse vectors are stored in the ``sparse_embedding`` column.
        - ``embedding_function`` is required and must support persistence.
        - Sparse vectors are always generated from ``source_key`` by ``embedding_function``.

    Example:
        >>> # Auto-generate from document field
        >>> config = SparseVectorIndexConfig(
        ...     embedding_function=BM25EmbeddingFunction(),
        ...     source_key=K.DOCUMENT
        ... )
        >>>
        >>> # Auto-generate from metadata field
        >>> config = SparseVectorIndexConfig(
        ...     embedding_function=BM25EmbeddingFunction(),
        ...     source_key="title"
        ... )
        >>>
    """

    embedding_function: SparseEmbeddingFunction
    source_key: str | K | None = K.DOCUMENT  # Default: generate from document field
    lib: str = "vsag"
    distance: str = DistanceMetric.INNER_PRODUCT.value
    type: str = "sindi"
    prune: bool = False
    refine: bool = False
    drop_ratio_build: float = 0.0
    drop_ratio_search: float = 0.0
    refine_k: float = 4.0
    properties: dict[str, PrimitiveValue] | None = None

    def __post_init__(self):  # noqa: C901
        if self.distance != DistanceMetric.INNER_PRODUCT.value:
            raise ValueError(
                f"Sparse vector index only supports {DistanceMetric.INNER_PRODUCT.value} distance, got '{self.distance}'"
            )
        if self.lib.lower() != "vsag":
            raise ValueError(f"Sparse vector index only supports 'vsag' library, got '{self.lib}'")
        if self.type.lower() != "sindi":
            raise ValueError(f"Sparse vector index only supports 'sindi' type, got '{self.type}'")
        if not isinstance(self.prune, bool):
            raise TypeError(f"prune must be a bool, got '{type(self.prune).__name__}'")
        if not isinstance(self.refine, bool):
            raise TypeError(f"refine must be a bool, got '{type(self.refine).__name__}'")
        if self.drop_ratio_build < 0.0 or self.drop_ratio_build > 0.9:
            raise ValueError(f"drop_ratio_build must be between 0.0 and 0.9, got '{self.drop_ratio_build}'")
        if self.drop_ratio_search < 0.0 or self.drop_ratio_search > 0.9:
            raise ValueError(f"drop_ratio_search must be between 0.0 and 0.9, got '{self.drop_ratio_search}'")
        if self.refine_k < 1.0 or self.refine_k > 1000.0:
            raise ValueError(f"refine_k must be between 1.0 and 1000.0, got '{self.refine_k}'")
        _ensure_primitive_properties(self.properties)

        self._validate_source_key()
        if self.embedding_function is None:
            raise ValueError(
                "embedding_function is None. Please provide an embedding_function to generate sparse vectors."
            )
        if not SparseEmbeddingFunction.support_persistence(self.embedding_function):
            raise ValueError(
                "Sparse embedding function must support persistence. "
                "Please implement name(), get_config(), and build_from_config()."
            )

    def _validate_source_key(self) -> None:
        if self.source_key is None:
            self.source_key = K.DOCUMENT
            return

        key = self.source_key.name if hasattr(self.source_key, "name") else self.source_key
        if key == K.DOCUMENT.name:
            self.source_key = K.DOCUMENT
            return

        if not isinstance(key, str):
            raise TypeError(f"source_key must be a string, FieldKey, or None, got {type(key).__name__}")

        if key.startswith("#"):
            raise ValueError(f"source_key must not start with '#' except '#document', got '{self.source_key}'")
        self.source_key = key

    def resolve_source_key(self) -> tuple[str, str | None]:
        """
        Resolve the source_key to determine data source.

        Returns:
            Tuple of (source_type, metadata_key) where:
            - source_type is "document" or "metadata"
            - metadata_key is the metadata field name (only for "metadata" source_type)
        """
        if self.source_key is None:
            raise ValueError("source_key is None. Please provide a source_key to generate sparse vectors.")
        if self.source_key is K.DOCUMENT or self.source_key == K.DOCUMENT.name:
            return ("document", None)
        # Plain string refers to metadata field
        return ("metadata", self.source_key)


class Configuration:
    """
    Configuration for collection creation

    Args:
        hnsw: HNSWConfiguration or None
        fulltext_config: FulltextIndexConfig or None. If None, defaults to FulltextIndexConfig(analyzer='ik')
    """

    def __init__(
        self,
        hnsw: HNSWConfiguration | None = None,
        fulltext_config: FulltextIndexConfig | None = None,
    ):
        self.hnsw = hnsw
        self.fulltext_config = fulltext_config
        warnings.warn("Configuration is deprecated. Please use Schema instead.", DeprecationWarning, stacklevel=2)


# Type alias for configuration parameter that can be HNSWConfiguration, None, or sentinel
ConfigurationParam = Configuration | HNSWConfiguration | None
