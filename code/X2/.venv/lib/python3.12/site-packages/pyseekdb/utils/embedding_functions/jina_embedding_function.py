import os
from typing import Any

from pyseekdb.utils.embedding_functions.litellm_base_embedding_function import (
    LiteLLMBaseEmbeddingFunction,
)

# Known Jina AI embedding model dimensions
# Source: https://api.jina.ai/scalar#tag/search-foundation-models/POST/v1/embeddings
# Note: Most Jina v2 models have 768 dimensions
_JINA_MODEL_DIMENSIONS = {
    "jina-embeddings-v3": 1024,
    "jina-embeddings-v4": 2048,
    "jina-clip-v2": 1024,
    "jina-colbert-v2": 128,
    "jina-embeddings-v2-base-en": 768,
    "jina-embeddings-v2-base-zh": 768,
    "jina-embeddings-v2-base-es": 768,
    "jina-embeddings-v2-base-de": 768,
    "jina-embeddings-v2-base-code": 768,
    "jina-embeddings-v2-base-multilingual": 768,
    "jina-embeddings-v2-small-en": 512,
    "jina-embeddings-v2-small-zh": 512,
    "jina-embeddings-v2-small-es": 512,
    "jina-embeddings-v2-small-de": 512,
    "jina-embeddings-v2-small-code": 512,
    "jina-embeddings-v2-small-multilingual": 512,
}


class JinaEmbeddingFunction(LiteLLMBaseEmbeddingFunction):
    """
    A convenient embedding function for Jina AI embedding models.

    This class provides a simplified interface to Jina AI embedding models using LiteLLM.

    For more information about Jina AI models, see https://jina.ai/embeddings

    For LiteLLM documentation, see https://docs.litellm.ai/docs/embedding/supported_embedding

    Example:
        pip install pyseekdb litellm

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import JinaEmbeddingFunction

        # Using Jina AI embedding model
        # Set JINA_API_KEY environment variable first
        ef = JinaEmbeddingFunction(
            model_name="jina-embeddings-v2-base-en"
        )

        # Using multilingual model
        ef = JinaEmbeddingFunction(
            model_name="jina-embeddings-v2-base-multilingual"
        )

        # Using with custom api_key_env
        ef = JinaEmbeddingFunction(
            model_name="jina-embeddings-v2-base-en",
            api_key_env="JINA_API_KEY"
        )

        db = pyseekdb.Client(path="./seekdb.db")
        collection = db.create_collection(name="my_collection", embedding_function=ef)
        # Add documents
        collection.add(ids=["1", "2"], documents=["Hello world", "How are you?"], metadatas=[{"id": 1}, {"id": 2}])
        # Query using semantic search
        results = collection.query("How are you?", n_results=1)
        print(results)

    """

    def __init__(
        self,
        model_name: str = "jina-embeddings-v3",
        api_key_env: str | None = None,
        **kwargs: Any,
    ):
        """Initialize JinaEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Jina AI embedding model.
                Defaults to "jina-embeddings-v3".
                See Jina AI documentation for all available models: https://jina.ai/embeddings
            api_key_env (str, optional): Name of the environment variable containing the Jina AI API key.
                Defaults to "JINA_AI_API_KEY" if not provided.
            **kwargs: Additional arguments to pass to LiteLLM.
            See https://docs.litellm.ai/docs/providers/jina_ai#sample-usage---embedding for more information.
        """
        # Construct LiteLLM model name format: jina/<model-name>
        litellm_model_name = f"jina_ai/{model_name}"
        self._client_kwargs = kwargs

        # Set default API key env if not provided
        if api_key_env is None:
            api_key_env = "JINA_AI_API_KEY"
        if not os.environ.get(api_key_env):
            raise ValueError(
                f"API key environment variable '{api_key_env}' is not set. Please set it before using {self.__class__.__name__}."
            )

        # Initialize the base class
        super().__init__(
            model_name=litellm_model_name,
            api_key_env=api_key_env,
            **kwargs,
        )

        # Store additional configuration for get_config
        self._base_model_name = model_name  # Store original model name without prefix

        # Store dimension for quick access (will be calculated if needed)
        model_dims = _JINA_MODEL_DIMENSIONS
        if model_name in model_dims:
            self._dimension = model_dims[model_name]
        else:
            # Will be calculated on first access via dimension property
            self._dimension = None

    @property
    def dimension(self) -> int:
        """Get the dimension of embeddings produced by this function.

        Returns the known dimension for models without making an API call.
        If the model is in the known dimensions list, that value is returned.

        If the model is not in the known dimensions list, falls back to making
        an API call to get the embedding and infer the dimension.

        Returns:
            int: The dimension of embeddings for this model.
        """
        # If dimension is known, return it
        if self._dimension is not None:
            return self._dimension

        # Fallback: make an API call to get the embedding and infer the dimension
        # This is done by actually generating an embedding for a dummy sentence
        test_input = "dimension probing"
        try:
            embeddings = self([test_input])
        except Exception as e:
            raise RuntimeError("Failed to determine embedding dimension via API call") from e
        if not embeddings or not isinstance(embeddings, list) or not isinstance(embeddings[0], list):
            raise RuntimeError("Could not get embedding dimension from API response")

        # Cache the dimension for future use
        self._dimension = len(embeddings[0])
        return self._dimension

    @staticmethod
    def name() -> str:
        """Get the unique name identifier for JinaEmbeddingFunction.

        Returns:
            The name identifier for this embedding function type
        """
        return "jina"

    def get_config(self) -> dict[str, Any]:
        """Get the configuration dictionary for the JinaEmbeddingFunction.

        Returns:
            Dictionary containing configuration needed to restore this embedding function
        """
        # Add Jina specific configuration
        return {
            "model_name": self._base_model_name,
            "api_key_env": self.api_key_env,
            "client_kwargs": self._client_kwargs,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "JinaEmbeddingFunction":
        """Build a JinaEmbeddingFunction from its configuration dictionary.

        Args:
            config: Dictionary containing the embedding function's configuration

        Returns:
            Restored JinaEmbeddingFunction instance

        Raises:
            ValueError: If the configuration is invalid or missing required fields
        """
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env", "JINA_AI_API_KEY")
        kwargs = config.get("client_kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, but got {kwargs}")

        return JinaEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            **kwargs,
        )
