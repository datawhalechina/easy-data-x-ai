from typing import Any, ClassVar

from pyseekdb.client.embedding_function import (
    Documents,
    EmbeddingFunction,
    Embeddings,
)


class SentenceTransformerEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    An embedding function using sentence-transformers with a specific model.

    Example:
        pip install pyseekdb sentence-transformers

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        db = pyseekdb.Client(
            path="./seekdb.db"
        )
        collection = db.create_collection(name="my_collection", embedding_function=ef)
        # Add documents
        collection.add(ids=["1", "2"], documents=["Hello world", "How are you?"], metadatas=[{"id": 1}, {"id": 2}])
        # Query using semantic search
        results = collection.query("How are you?", top_k=1)
        print(results)

    """

    # Since we do dynamic imports we have to type this as Any
    models: ClassVar[dict[str, Any]] = {}

    # for a full list of options: https://huggingface.co/sentence-transformers,
    # https://www.sbert.net/docs/pretrained_models.html
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        normalize_embeddings: bool = False,
        **kwargs: Any,
    ):
        """Initialize SentenceTransformerEmbeddingFunction.

        Args:
            model_name (str, optional): Identifier of the SentenceTransformer model, defaults to "all-MiniLM-L6-v2"
            device (str, optional): Device used for computation, defaults to "cpu"
            normalize_embeddings (bool, optional): Whether to normalize returned vectors, defaults to False
            **kwargs: Additional arguments to pass to the SentenceTransformer model.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ValueError(
                "The sentence-transformers python package is not installed. Please install it with `pip install sentence-transformers`"
            ) from exc

        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        for key, value in kwargs.items():
            if not isinstance(value, (str, int, float, bool, list, dict, tuple)):
                raise TypeError(f"Keyword argument {key} is not a primitive type")
        self.kwargs = kwargs

        if model_name not in self.models:
            self.models[model_name] = SentenceTransformer(model_name_or_path=model_name, device=device, **kwargs)
        self._model = self.models[model_name]

    def __call__(self, documents: Documents) -> Embeddings:
        embeddings = self._model.encode(
            list(documents),
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )

        return [embedding.tolist() for embedding in embeddings]

    @staticmethod
    def name() -> str:
        return "sentence_transformer"

    def get_config(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "kwargs": self.kwargs,
        }

    @staticmethod
    def build_from_config(
        config: dict[str, Any],
    ) -> "SentenceTransformerEmbeddingFunction":
        model_name = config.get("model_name", "all-MiniLM-L6-v2")
        device = config.get("device", "cpu")
        normalize_embeddings = config.get("normalize_embeddings", False)
        kwargs = config.get("kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, but got {kwargs}")

        return SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            device=device,
            normalize_embeddings=normalize_embeddings,
            **kwargs,
        )
