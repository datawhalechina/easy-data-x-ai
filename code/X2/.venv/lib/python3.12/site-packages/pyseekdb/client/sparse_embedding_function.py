"""
Sparse embedding function interface and implementations

This module provides the SparseEmbeddingFunction protocol, SparseVector type,
and a registry for sparse embedding functions.

Sparse vectors are important in information retrieval for capturing surface-level
term matching. While dense vectors excel at semantic understanding, sparse vectors
often provide more predictable matching results, especially in specialized domains.
"""

from __future__ import annotations

import contextlib
import logging
import math
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    ClassVar,
    Protocol,
    TypeVar,
    runtime_checkable,
)

logger = logging.getLogger(__name__)

# Type aliases
Documents = str | list[str]


@dataclass
class SparseVector:
    """
    Sparse vector representation.

    A sparse vector is a dictionary mapping integer indices (feature/token positions)
    to float values (weights). Only non-zero entries are stored, making this efficient
    for high-dimensional but sparse data (e.g., BM25 scores, SPLADE activations).

    Format compatible with OceanBase/seekdb: ``{index: weight, ...}``

    Example:
        >>> sv = SparseVector.from_dict({100: 0.5, 200: 0.3, 500: 0.8})
        >>> print(sv.embeddings)
        {100: 0.5, 200: 0.3, 500: 0.8}

        >>> sv = SparseVector.from_indices([100, 200, 500], [0.5, 0.3, 0.8])
        >>> print(sv.embeddings)
        {100: 0.5, 200: 0.3, 500: 0.8}
    """

    embeddings: dict[int, float] | None = field(default=None)

    @staticmethod
    def from_dict(embeddings: dict[int, float]) -> SparseVector:
        """
        Create a SparseVector from a dictionary.

        Args:
            embeddings: Dictionary mapping integer indices to float weights.

        Returns:
            A new SparseVector instance.

        Example:
            >>> sv = SparseVector.from_dict({100: 0.5, 200: 0.3, 500: 0.8})
        """
        if not isinstance(embeddings, dict):
            raise TypeError(f"embeddings must be a dict, got {type(embeddings).__name__}")
        normalized: dict[int, float] = {}
        for idx, weight in embeddings.items():
            if not isinstance(idx, int):
                raise TypeError(f"sparse index key must be int, got {type(idx).__name__}")
            if not isinstance(weight, (int, float)):
                raise TypeError(f"sparse value must be numeric, got {type(weight).__name__}")
            w = float(weight)
            if not math.isfinite(w):
                raise ValueError(f"sparse value must be finite, got {weight}")
            normalized[idx] = w
        return SparseVector(embeddings=normalized)

    @staticmethod
    def from_indices(indices: list[int], values: list[float]) -> SparseVector:
        """
        Create a SparseVector from parallel lists of indices and values.

        Args:
            indices: List of integer indices (feature/token positions).
            values: List of float weights corresponding to each index.

        Returns:
            A new SparseVector instance.

        Raises:
            ValueError: If indices and values have different lengths.

        Example:
            >>> sv = SparseVector.from_indices([100, 200, 500], [0.5, 0.3, 0.8])
        """
        if len(indices) != len(values):
            raise ValueError(
                f"indices and values must have the same length, got {len(indices)} indices and {len(values)} values"
            )
        return SparseVector(embeddings=dict(zip(indices, values, strict=True)))

    def to_sql_string(self) -> str:
        """
        Convert the sparse vector to OceanBase SQL format.

        Returns:
            SQL string representation, e.g., ``'{100:0.5, 200:0.3, 500:0.8}'``

        Raises:
            ValueError: If the sparse vector is empty or None.
        """
        if not self.embeddings:
            raise ValueError("Cannot convert empty sparse vector to SQL string")
        parts = [f"{k}:{v}" for k, v in self.embeddings.items()]
        return "'{" + ", ".join(parts) + "}'"

    def __repr__(self) -> str:
        if self.embeddings is None:
            return "SparseVector(None)"
        count = len(self.embeddings)
        return f"SparseVector({count} non-zero entries)"


# Type alias for list of sparse vectors
SparseVectors = list[SparseVector]


def _sparse_vector_to_sql(sv: SparseVector | dict[int, float]) -> str:
    """
    Convert a sparse vector (SparseVector or raw dict) to SQL string format.

    Args:
        sv: SparseVector instance or dict[int, float]

    Returns:
        SQL string, e.g., ``'{100:0.5, 200:0.3}'``
    """
    if isinstance(sv, SparseVector):
        return sv.to_sql_string()
    elif isinstance(sv, dict):
        if not sv:
            raise ValueError("Cannot convert empty sparse vector dict to SQL string")
        parts = [f"{k}:{v}" for k, v in sv.items()]
        return "'{" + ", ".join(parts) + "}'"
    else:
        raise TypeError(f"Expected SparseVector or dict, got {type(sv).__name__}")


@runtime_checkable
class SparseEmbeddingFunction(Protocol):
    """
    Protocol for sparse embedding functions that convert documents to sparse vectors.

    Sparse vectors are suitable for keyword-based retrieval (e.g., BM25, SPLADE).
    Similar to ``EmbeddingFunction``, but produces sparse vectors (dict[int, float])
    instead of dense vectors (list[float]).

    Implementations should provide:
    - ``__call__()``: Convert documents to sparse vectors
    - ``name()``: Static method returning a unique name identifier (for registration and routing)
    - ``get_config()``: Return configuration dictionary (for persistence)
    - ``build_from_config()``: Static method to restore instance from config

    Example:
        >>> class BM25EmbeddingFunction(SparseEmbeddingFunction):
        ...     def __call__(self, documents: Documents) -> SparseVectors:
        ...         # Generate BM25 sparse vectors
        ...         ...
        ...
        ...     @staticmethod
        ...     def name() -> str:
        ...         return "bm25"
        ...
        ...     def get_config(self) -> dict:
        ...         return {"k1": self.k1, "b": self.b}
        ...
        ...     @staticmethod
        ...     def build_from_config(config) -> "BM25EmbeddingFunction":
        ...         return BM25EmbeddingFunction(**config)
    """

    @abstractmethod
    def __call__(self, documents: Documents) -> SparseVectors:
        """
        Convert documents to sparse vectors.

        Args:
            documents: Document content (str or list[str])

        Returns:
            List of SparseVector instances.
            Each SparseVector contains a dict[int, float] where:
            - key: vocabulary/feature index position (typically a hash or vocab index)
            - value: corresponding weight (e.g., BM25 score, SPLADE activation)
        """
        ...

    @staticmethod
    def name() -> str:
        """Return unique name identifier (for registration and routing)."""
        return ""

    @abstractmethod
    def get_config(self) -> dict[str, Any]:
        """
        Get configuration dictionary (for persistence).

        Returns:
            Configuration dictionary. Should NOT include 'name' field
            (handled by upper layer).
        """
        return NotImplemented

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> SparseEmbeddingFunction:
        """Restore instance from configuration dictionary."""
        ...

    @staticmethod
    def support_persistence(sparse_embedding_function: Any) -> bool:
        """
        Check if the sparse embedding function supports persistence.

        Args:
            sparse_embedding_function: The sparse embedding function to check.

        Returns:
            True if persistence is supported, False otherwise.
        """
        if sparse_embedding_function is None:
            return False
        if (
            not hasattr(sparse_embedding_function, "name")
            or not hasattr(sparse_embedding_function, "build_from_config")
            or not hasattr(sparse_embedding_function, "get_config")
        ):
            return False
        try:
            if sparse_embedding_function.get_config() is NotImplemented or not sparse_embedding_function.name():
                return False
        except Exception:
            return False
        return True


class SparseEmbeddingFunctionRegistry:
    """
    Registry for sparse embedding function classes.

    Maps sparse embedding function names (returned by their ``name()`` method)
    to their corresponding classes, allowing dynamic instantiation from
    persisted configurations.

    To register a custom sparse embedding function:

    Option 1 (Recommended): Use the ``@register_sparse_embedding_function`` decorator:
        >>> @register_sparse_embedding_function
        ... class MySparseFn(SparseEmbeddingFunction):
        ...     # ... implementation ...

    Option 2: Manually register:
        >>> SparseEmbeddingFunctionRegistry.register(MySparseFn)
    """

    _registry: ClassVar[dict[str, type]] = {}
    _initialized: ClassVar[bool] = False

    @classmethod
    def _initialize(cls) -> None:
        """Initialize the registry with built-in sparse embedding functions."""
        if cls._initialized:
            return

        cls._initialized = True

        with contextlib.suppress(ImportError, ValueError):
            from pyseekdb.utils.embedding_functions.huggingface_sparse_embedding_function import (
                HuggingFaceSparseEmbeddingFunction,  # noqa: F401
            )

        with contextlib.suppress(ImportError, ValueError):
            from pyseekdb.utils.embedding_functions.bm25_sparse_embedding_function import (
                BM25SparseEmbeddingFunction,  # noqa: F401
            )

    @classmethod
    def register(cls, sparse_embedding_function_class: type) -> None:
        """
        Register a sparse embedding function class.

        Args:
            sparse_embedding_function_class: The sparse embedding function class to register.
                Must implement ``name()``, ``get_config()``, and ``build_from_config()``.

        Raises:
            ValueError: If the class doesn't have required methods or name is already registered.
        """
        cls._initialize()

        if not hasattr(sparse_embedding_function_class, "name") or not hasattr(
            sparse_embedding_function_class, "build_from_config"
        ):
            raise ValueError(
                f"Sparse embedding function class {sparse_embedding_function_class.__name__} "
                f"must have a static name() method and static build_from_config() method"
            )

        name = sparse_embedding_function_class.name()
        if name in cls._registry and cls._registry[name] != sparse_embedding_function_class:
            raise ValueError(
                f"Sparse embedding function name '{name}' is already registered to {cls._registry[name].__name__}"
            )

        cls._registry[name] = sparse_embedding_function_class
        logger.debug(f"Registered sparse embedding function '{name}' -> {sparse_embedding_function_class.__name__}")

    @classmethod
    def get_class(cls, name: str) -> type | None:
        """
        Get a sparse embedding function class by name.

        Args:
            name: The name identifier of the sparse embedding function.

        Returns:
            The sparse embedding function class if found, None otherwise.
        """
        cls._initialize()
        return cls._registry.get(name)

    @classmethod
    def list_registered(cls) -> list[str]:
        """
        List all registered sparse embedding function names.

        Returns:
            List of registered sparse embedding function names.
        """
        cls._initialize()
        return list(cls._registry.keys())

    @classmethod
    def build_from_config(cls, name: str, config: dict[str, Any]) -> SparseEmbeddingFunction:
        """
        Build a sparse embedding function from a name and config.

        Args:
            name: The name identifier of the sparse embedding function.
            config: Configuration dictionary.

        Returns:
            A SparseEmbeddingFunction instance.

        Raises:
            ValueError: If the name is not registered.
        """
        cls._initialize()
        fn_class = cls._registry.get(name)
        if fn_class is None:
            raise ValueError(f"Sparse embedding function '{name}' is not registered")
        return fn_class.build_from_config(config)


T = TypeVar("T", bound=type)


def register_sparse_embedding_function(sparse_embedding_function_class: type[T]) -> type[T]:
    """
    Decorator to automatically register a sparse embedding function class.

    Example:
        >>> @register_sparse_embedding_function
        ... class MyBM25Function:
        ...     def __call__(self, documents):
        ...         ...
        ...     @staticmethod
        ...     def name() -> str:
        ...         return "my_bm25"
        ...     def get_config(self) -> dict:
        ...         return {}
        ...     @staticmethod
        ...     def build_from_config(config) -> "MyBM25Function":
        ...         return MyBM25Function()
    """
    SparseEmbeddingFunctionRegistry.register(sparse_embedding_function_class)
    return sparse_embedding_function_class
