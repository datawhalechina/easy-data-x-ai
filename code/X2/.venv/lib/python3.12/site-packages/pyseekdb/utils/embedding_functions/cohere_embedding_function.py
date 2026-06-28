import os
from typing import Any

from pyseekdb.utils.embedding_functions.litellm_base_embedding_function import (
    LiteLLMBaseEmbeddingFunction,
)

# Known Cohere embedding model dimensions
# Source: https://docs.cohere.com/docs/cohere-embed
_COHERE_MODEL_DIMENSIONS = {
    "embed-v4.0": 1536,
    "embed-english-v3.0": 1024,
    "embed-multilingual-v3.0": 1024,
    "embed-english-light-v3.0": 384,
    "embed-multilingual-light-v3.0": 384,
    "embed-english-v2.0": 4096,
    "embed-multilingual-v2.0": 768,
    "embed-english-light-v2.0": 1024,
    "embed-multilingual-light-v2.0": 384,
}

_DEFAULT_MODEL_NAME = "embed-english-v3.0"


class CohereEmbeddingFunction(LiteLLMBaseEmbeddingFunction):
    """
    A convenient embedding function for Cohere embedding models using LiteLLM.

    For more information about Cohere models, see https://docs.cohere.com/docs/cohere-embed

    For LiteLLM documentation, see https://docs.litellm.ai/docs/embedding/supported_embedding

    Example:
        pip install pyseekdb litellm

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import CohereEmbeddingFunction

        # Using Cohere embedding model
        # Set COHERE_API_KEY environment variable first
        ef = CohereEmbeddingFunction(
            model_name="embed-english-v3.0"
        )

        # Using multilingual model
        ef = CohereEmbeddingFunction(
            model_name="embed-multilingual-v3.0"
        )

        # Using with custom api_key_env
        ef = CohereEmbeddingFunction(
            model_name="embed-english-v3.0",
            api_key_env="COHERE_API_KEY"
        )

        # Using with input_type for better retrieval performance
        ef = CohereEmbeddingFunction(
            model_name="embed-english-v3.0",
            input_type="search_document"  # or "search_query" for queries
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
        model_name: str = _DEFAULT_MODEL_NAME,
        api_key_env: str | None = None,
        input_type: str | None = None,
        **kwargs: Any,
    ):
        """Initialize CohereEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Cohere embedding model.
                Defaults to "embed-english-v3.0".
                See Cohere documentation for available models: https://docs.cohere.com/docs/cohere-embed
            api_key_env (str, optional): Name of the environment variable containing the Cohere API key.
                Defaults to "COHERE_API_KEY" if not provided.
            input_type (str, optional): Type of the input text. Options: None, "search_document", "search_query".
                When set to "search_document" or "search_query", Cohere optimizes embeddings for
                retrieval/search tasks. Defaults to None.
            **kwargs: Additional arguments to pass to LiteLLM.
        See https://docs.litellm.ai/docs/providers/cohere#embedding for more information.
        """
        # Construct LiteLLM model name format: cohere/<model-name>
        litellm_model_name = f"cohere/{model_name}"

        self._client_kwargs = kwargs

        # Set default API key env if not provided
        if api_key_env is None:
            api_key_env = "COHERE_API_KEY"

        if not os.environ.get(api_key_env):
            raise ValueError(
                f"API key environment variable '{api_key_env}' is not set. Please set it before using {self.__class__.__name__}."
            )
        # Prepare kwargs for LiteLLM
        litellm_kwargs = {**kwargs}

        # Add input_type if provided
        if input_type is not None:
            litellm_kwargs["input_type"] = input_type

        # Initialize the base class
        super().__init__(
            model_name=litellm_model_name,
            api_key_env=api_key_env,
            **litellm_kwargs,
        )

        # Store additional configuration for get_config
        self._base_model_name = model_name  # Store original model name without prefix
        self.input_type = input_type

        # Store dimension for quick access (will be calculated if needed)
        model_dims = _COHERE_MODEL_DIMENSIONS
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
        """Get the unique name identifier for CohereEmbeddingFunction.

        Returns:
            The name identifier for this embedding function type
        """
        return "cohere"

    def get_config(self) -> dict[str, Any]:
        """Get the configuration dictionary for the CohereEmbeddingFunction.

        Returns:
            Dictionary containing configuration needed to restore this embedding function
        """

        return {
            "model_name": self._base_model_name,
            "api_key_env": self.api_key_env,
            "input_type": self.input_type,
            "client_kwargs": self._client_kwargs,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "CohereEmbeddingFunction":
        """Build a CohereEmbeddingFunction from its configuration dictionary.

        Args:
            config: Dictionary containing the embedding function's configuration

        Returns:
            Restored CohereEmbeddingFunction instance

        Raises:
            ValueError: If the configuration is invalid or missing required fields
        """
        model_name = config.get("model_name", _DEFAULT_MODEL_NAME)

        api_key_env = config.get("api_key_env", "COHERE_API_KEY")
        input_type = config.get("input_type")
        kwargs = config.get("client_kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, but got {kwargs}")

        return CohereEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            input_type=input_type,
            **kwargs,
        )
