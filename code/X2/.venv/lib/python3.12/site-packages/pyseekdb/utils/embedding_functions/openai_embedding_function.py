from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known OpenAI embedding model dimensions
# Source: https://platform.openai.com/docs/guides/embeddings
_OPENAI_MODEL_DIMENSIONS = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class OpenAIEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for OpenAI embedding models.

    This class provides a simplified interface to OpenAI embedding models using the OpenAI API.

    For more information about OpenAI models, see https://platform.openai.com/docs/guides/embeddings

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import OpenAIEmbeddingFunction

        # Using default model (text-embedding-3-small)
        # Set OPENAI_API_KEY environment variable first
        ef = OpenAIEmbeddingFunction()

        # Using a specific OpenAI model
        ef = OpenAIEmbeddingFunction(model_name="text-embedding-3-small")

        # Using with additional parameters
        ef = OpenAIEmbeddingFunction(
            model_name="text-embedding-3-large",
            timeout=30,
            max_retries=3
        )

        # Using text-embedding-3 with custom dimensions
        ef = OpenAIEmbeddingFunction(
            model_name="text-embedding-3-small",
            dimensions=512  # Reduce from default 1536 to 512
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
        model_name: str = "text-embedding-3-small",
        api_key_env: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize OpenAIEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the OpenAI embedding model.
                Defaults to "text-embedding-3-small".
            api_key_env (str, optional): Name of the environment variable containing the OpenAI API key.
                Defaults to "OPENAI_API_KEY" if not provided.
            api_base (str, optional): Base URL for the API endpoint.
                Defaults to "https://api.openai.com/v1" if not provided.
                Useful for OpenAI-compatible proxies or custom endpoints.
            dimensions (int, optional): The number of dimensions the resulting embeddings should have.
                Only supported for text-embedding-3 models. Can reduce dimensions from
                default (1536 for text-embedding-3-small, 3072 for text-embedding-3-large).
            **kwargs: Additional arguments to pass to the OpenAI client.
                Common options include:
                - timeout: Request timeout in seconds
                - max_retries: Maximum number of retries
                - See https://github.com/openai/openai-python for more options
        """
        super().__init__(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        return "https://api.openai.com/v1"

    def _get_default_api_key_env(self) -> str:
        return "OPENAI_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        return _OPENAI_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        return "openai"

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "OpenAIEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        dimensions = config.get("dimensions")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return OpenAIEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **client_kwargs,
        )
