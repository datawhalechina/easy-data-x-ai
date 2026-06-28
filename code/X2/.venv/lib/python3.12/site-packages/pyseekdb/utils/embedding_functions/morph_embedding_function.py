import logging
from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known Morph embedding model dimensions
# Source: https://docs.morphllm.com/api-reference/endpoint/embedding
_MORPH_MODEL_DIMENSIONS = {
    "morph-embedding-v4": 1536,
}

logger = logging.getLogger(__name__)


class MorphEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for Morph embedding models.

    This class provides a simplified interface to Morph embedding models using the
    OpenAI-compatible API.

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import MorphEmbeddingFunction

        # Using Morph embedding model
        # Set MORPH_API_KEY environment variable first
        ef = MorphEmbeddingFunction(
            model_name="morph-embedding-v4"
        )

        # Using with custom api_key_env
        ef = MorphEmbeddingFunction(
            model_name="morph-embedding-v4",
            api_key_env="MORPH_API_KEY"
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
        model_name: str,
        api_key_env: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ):
        """Initialize MorphEmbeddingFunction.

        Args:
            model_name (str): Name of the Morph embedding model.
            api_key_env (str, optional): Name of the environment variable containing the Morph API key.
                Defaults to "MORPH_API_KEY" if not provided.
            api_base (str, optional): Base URL for the Morph API endpoint.
                Defaults to "https://api.morphllm.com/v1" if not provided.
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
            dimensions=None,
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        """Get the default API base URL for Morph.

        Returns:
            str: Default Morph API base URL
        """
        return "https://api.morphllm.com/v1"

    def _get_default_api_key_env(self) -> str:
        """Get the default API key environment variable name for Morph.

        Returns:
            str: Default Morph API key environment variable name
        """
        return "MORPH_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        """Get a dictionary mapping Morph model names to their default dimensions.

        Returns:
            dict[str, int]: Dictionary mapping model names to dimensions
        """
        return _MORPH_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        """Get the unique name identifier for MorphEmbeddingFunction.

        Returns:
            The name identifier for this embedding function type
        """
        return "morph"

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "MorphEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        dimensions = config.get("dimensions")
        if dimensions is not None:
            logger.warning("Ignoring unsupported 'dimensions' for MorphEmbeddingFunction")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return MorphEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            **client_kwargs,
        )
