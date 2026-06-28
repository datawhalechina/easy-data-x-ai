import os
from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known Ollama embedding model dimensions
# Source: https://docs.ollama.com/capabilities/embeddings
_OLLAMA_MODEL_DIMENSIONS = {
    "nomic-embed-text": 768,
    "all-minilm": 384,
}


class OllamaEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for Ollama embedding models.

    This class provides a simplified interface to Ollama embedding models using the OpenAI-compatible API.
    Ollama provides OpenAI-compatible API endpoints for embedding generation.

    For more information about Ollama, see https://docs.ollama.com/

    Note: Before using a model, you need to pull it locally using `ollama pull <model_name>`.

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import OllamaEmbeddingFunction

        # First, pull the model locally: ollama pull nomic-embed-text
        # Using Ollama embedding model
        # API key is required but ignored by Ollama, can be set to "ollama" or any value
        # Set OLLAMA_API_KEY environment variable first (or it will default to "ollama")
        ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text"
        )

        # Using with custom api_base (for remote Ollama server)
        ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            api_base="http://remote-server:11434/v1",
            timeout=30
        )

        # Using with custom dimensions (if supported by the model)
        ef = OllamaEmbeddingFunction(
            model_name="nomic-embed-text",
            dimensions=512
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
        model_name: str = "nomic-embed-text",
        api_key_env: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize OllamaEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Ollama embedding model.
                Defaults to "nomic-embed-text".
                See Ollama documentation for available models: https://docs.ollama.com/capabilities/embeddings
                Note: Models must be pulled locally first using `ollama pull <model_name>`
            api_key_env (str, optional): Name of the environment variable containing the Ollama API key.
                Defaults to "OLLAMA_API_KEY" if not provided.
                Note: The API key is required but ignored by Ollama. You can set it to "ollama" or any value.
                If the environment variable is not set, it will default to "ollama".
            api_base (str, optional): Base URL for the Ollama API endpoint.
                Defaults to "http://localhost:11434/v1" if not provided.
                For remote Ollama servers, use the appropriate URL.
            dimensions (int, optional): The number of dimensions the resulting embeddings should have.
                Supported if the model supports it. Check model documentation for supported dimensions.
            **kwargs: Additional arguments to pass to the OpenAI client.
                See https://github.com/openai/openai-python for more information.
        """
        # Set default API key env if not provided
        if api_key_env is None:
            api_key_env = self._get_default_api_key_env()

        # Handle the case where API key env var is not set (Ollama ignores the key anyway)
        # We'll set a default value of "ollama" if not found
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            # Set a default API key since Ollama requires it but ignores it
            os.environ[api_key_env] = "ollama"

        super().__init__(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        """Get the default API base URL for Ollama.

        Returns:
            str: Default Ollama API base URL
        """
        return "http://localhost:11434/v1"

    def _get_default_api_key_env(self) -> str:
        """Get the default API key environment variable name for Ollama.

        Returns:
            str: Default Ollama API key environment variable name
        """
        return "OLLAMA_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        """Get a dictionary mapping Ollama model names to their default dimensions.

        Returns:
            dict[str, int]: Dictionary mapping model names to dimensions
        """
        return _OLLAMA_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        """Get the unique name identifier for OllamaEmbeddingFunction.

        Returns:
            The name identifier for this embedding function type
        """
        return "ollama"

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "OllamaEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        dimensions = config.get("dimensions")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return OllamaEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **client_kwargs,
        )
