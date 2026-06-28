"""
Text2Vec embedding function for pyseekdb.

This module provides an embedding function using the text2vec library,
which is a powerful multilingual embedding model trained on HuggingFace.
"""

from typing import Any, ClassVar

from pyseekdb.client.embedding_function import (
    Documents,
    EmbeddingFunction,
    Embeddings,
)


class Text2VecEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    An embedding function using text2vec with a specific model.

    Text2Vec provides multilingual embeddings (supports 100+ languages) with
    various pretrained models.
    """

    # Class variable to cache loaded models
    # Key: (model_name, device, frozenset(kwargs.items()))
    models: ClassVar[dict[tuple[str, str, frozenset[tuple[str, Any]]], Any]] = {}

    def __init__(
        self,
        model_name: str = "shibing624/text2vec-base-chinese",
        device: str = "cpu",
        normalize_embeddings: bool = False,
        **kwargs: Any,
    ):
        """Initialize Text2VecEmbeddingFunction."""
        # Validate kwargs - only allow primitive types
        for key, value in kwargs.items():
            if not isinstance(value, (str, int, float, bool, list, dict, tuple)):
                raise TypeError(f"Keyword argument {key} is not a primitive type")

        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self.kwargs = kwargs
        self._cached_dimension: int | None = None
        self._model_instance: Any = None

    def _get_model(self) -> Any:
        """Get or initialize the text2vec model instance."""
        if self._model_instance is not None:
            return self._model_instance

        cache_key = (self.model_name, self.device, frozenset(self.kwargs.items()))
        if cache_key not in self.models:
            try:
                from text2vec import SentenceModel

                # Initialize the model
                self.models[cache_key] = SentenceModel(
                    model_name_or_path=self.model_name, device=self.device, **self.kwargs
                )
            except ImportError as exc:
                raise ImportError(
                    "The text2vec python package is not installed. Please install it with: `pip install text2vec`"
                ) from exc

        self._model_instance = self.models[cache_key]
        return self._model_instance

    @property
    def dimension(self) -> int:
        """Get the dimension of embeddings produced by this function."""
        if self._cached_dimension is None:
            # Get dimension from the model
            model = self._get_model()
            sample = model.encode("test", normalize_embeddings=self.normalize_embeddings)
            if hasattr(sample, "shape"):
                self._cached_dimension = int(sample.shape[0] if len(sample.shape) == 1 else sample.shape[1])
            else:
                self._cached_dimension = len(sample)
        return self._cached_dimension

    def __call__(self, documents: Documents) -> Embeddings:
        """Generate embeddings for given documents."""
        # Handle single string input
        if isinstance(documents, str):
            documents = [documents]

        # Handle empty input
        if not documents:
            return []

        # Generate embeddings using text2vec
        model = self._get_model()
        embeddings = model.encode(
            list(documents),
            normalize_embeddings=self.normalize_embeddings,
        )

        # Convert to list of lists
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return list(embeddings)

    @staticmethod
    def name() -> str:
        """Return the embedding function name identifier."""
        return "text2vec"

    def get_config(self) -> dict[str, Any]:
        """Get configuration dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "kwargs": self.kwargs,
        }

    @staticmethod
    def build_from_config(
        config: dict[str, Any],
    ) -> "Text2VecEmbeddingFunction":
        """Build Text2VecEmbeddingFunction from configuration dictionary."""
        model_name = config.get("model_name", "shibing624/text2vec-base-chinese")
        device = config.get("device", "cpu")
        normalize_embeddings = config.get("normalize_embeddings", False)
        kwargs = config.get("kwargs", {})

        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, but got {kwargs}")

        return Text2VecEmbeddingFunction(
            model_name=model_name,
            device=device,
            normalize_embeddings=normalize_embeddings,
            **kwargs,
        )
