"""
HuggingFace sparse embedding function using sentence-transformers SparseEncoder.

Supports SPLADE and other sparse encoder models available on HuggingFace Hub.
Common models include:
  - prithivida/Splade_PP_en_v1
  - naver/splade-cocondenser-ensembledistil
  - naver/splade-cocondenser-selfdistil

Example:
    >>> from pyseekdb.utils.embedding_functions import HuggingFaceSparseEmbeddingFunction
    >>> ef = HuggingFaceSparseEmbeddingFunction(
    ...     model_name="prithivida/Splade_PP_en_v1",
    ...     device="cpu",
    ... )
    >>> sparse_vectors = ef(["Hello world", "How are you?"])

Requires: pip install sentence-transformers>=4.0
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, cast

import numpy as np

from pyseekdb.client.sparse_embedding_function import (
    Documents,
    SparseEmbeddingFunction,
    SparseVector,
    SparseVectors,
    register_sparse_embedding_function,
)

TaskType = Literal["document", "query"]


@register_sparse_embedding_function
class HuggingFaceSparseEmbeddingFunction(SparseEmbeddingFunction):
    """
    Sparse embedding function powered by HuggingFace SparseEncoder models.

    Uses ``sentence_transformers.SparseEncoder`` to produce sparse vectors
    (e.g., SPLADE activations) for keyword-based retrieval.

    The model is loaded lazily and cached at the class level, so multiple
    instances sharing the same ``model_name`` reuse one loaded model.

    Args:
        model_name: HuggingFace model identifier (e.g. ``"prithivida/Splade_PP_en_v1"``).
        device: Compute device (``"cpu"``, ``"cuda"``, ``"cuda:0"``, etc.).
        task: Encoding mode — ``"document"`` for indexing, ``"query"`` for searching.
            Defaults to ``"document"``.
        **kwargs: Extra keyword arguments forwarded to ``SparseEncoder()``.
    """

    models: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        model_name: str = "prithivida/Splade_PP_en_v1",
        device: str = "cpu",
        task: TaskType = "document",
        **kwargs: Any,
    ):
        try:
            from sentence_transformers import SparseEncoder
        except ImportError as exc:
            raise ValueError(
                "The sentence-transformers python package is not installed or does not support SparseEncoder. "
                "Please install it with `pip install sentence-transformers>=4.0`"
            ) from exc

        self.model_name = model_name
        self.device = device
        self.task: TaskType = task
        for key, value in kwargs.items():
            if not isinstance(value, (str, int, float, bool, list, dict, tuple)):
                raise TypeError(f"Keyword argument '{key}' must be a primitive type, got {type(value).__name__}")
        self.kwargs = kwargs

        # Create a hashable cache key including device and kwargs
        kwargs_key = tuple(sorted((k, v) for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))))
        cache_key = (model_name, device, kwargs_key)
        if cache_key not in self.models:
            self.models[cache_key] = SparseEncoder(model_name_or_path=model_name, device=device, **kwargs)
        self._model = self.models[cache_key]

    def __call__(self, documents: Documents) -> SparseVectors:
        """
        Encode documents into sparse vectors.

        Args:
            documents: A single string or list of strings.

        Returns:
            List of SparseVector instances, one per input document.
        """
        from sentence_transformers import SparseEncoder

        if isinstance(documents, str):
            documents = [documents]

        model = cast(SparseEncoder, self._model)
        if self.task == "document":
            embeddings = model.encode_document(list(documents))
        elif self.task == "query":
            embeddings = model.encode_query(list(documents))
        else:
            raise ValueError(f"Invalid task: {self.task!r}. Expected 'document' or 'query'.")

        return self._convert_to_sparse_vectors(embeddings)

    @staticmethod
    def _convert_to_sparse_vectors(embeddings: Any) -> SparseVectors:
        sparse_vectors: SparseVectors = []
        for vec in embeddings:
            if hasattr(vec, "to_dense"):
                vec_dense = vec.to_dense().numpy()
            else:
                vec_dense = vec.numpy() if hasattr(vec, "numpy") else np.array(vec)

            nz = np.where(vec_dense != 0)[0]
            indices = nz.tolist()
            values = vec_dense[nz].tolist()
            sparse_vectors.append(SparseVector.from_indices(indices, values))
        return sparse_vectors

    # ── Persistence ──────────────────────────────────────────────────

    @staticmethod
    def name() -> str:
        return "huggingface_sparse"

    def get_config(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "device": self.device,
            "task": self.task,
            "kwargs": self.kwargs,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> HuggingFaceSparseEmbeddingFunction:
        model_name = config.get("model_name", "prithivida/Splade_PP_en_v1")
        device = config.get("device", "cpu")
        task = config.get("task", "document")
        kwargs = config.get("kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, got {type(kwargs).__name__}")

        return HuggingFaceSparseEmbeddingFunction(
            model_name=model_name,
            device=device,
            task=task,
            **kwargs,
        )
