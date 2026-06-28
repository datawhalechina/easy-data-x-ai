from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known Qwen embedding model dimensions
# Source: Qwen/DashScope documentation
_QWEN_MODEL_DIMENSIONS = {
    "text-embedding-v1": 1536,
    "text-embedding-v2": 1536,
    "text-embedding-v3": 1024,  # default and can be changed via dimensions parameter
    "text-embedding-v4": 1024,  # default and can be changed via dimensions parameter
}


class QwenEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for Qwen (Alibaba Cloud) embedding models.

    This class provides a simplified interface to Qwen embedding models using the OpenAI-compatible API.
    Qwen provides OpenAI-compatible API endpoints for embedding generation.

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import QwenEmbeddingFunction

        # Using Qwen embedding model
        # Set DASHSCOPE_API_KEY environment variable first
        ef = QwenEmbeddingFunction(
            model_name="text-embedding-v1"
        )

        # Using with custom api_key_env and additional parameters
        ef = QwenEmbeddingFunction(
            model_name="text-embedding-v1",
            api_key_env="DASHSCOPE_API_KEY",
            timeout=30
        )

        # Using with custom dimensions
        ef = QwenEmbeddingFunction(
            model_name="text-embedding-v3",
            dimensions=512  # Reduce from default 1024 to 512
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
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize QwenEmbeddingFunction.

        Args:
            model_name (str): Name of the Qwen embedding model.
                See Qwen documentation for available models.
            api_key_env (str, optional): Name of the environment variable containing the Qwen API key.
                Defaults to "DASHSCOPE_API_KEY" if not provided.
            api_base (str, optional): Base URL for the Qwen API endpoint.
                Defaults to "https://dashscope.aliyuncs.com/compatible-mode/v1" if not provided.
            dimensions (int, optional): The number of dimensions the resulting embeddings should have.
                Can reduce dimensions from default. You can check the Qwen official documentation for details.
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
        """Get the default API base URL for Qwen.

        Returns:
            str: Default Qwen API base URL
        """
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def _get_default_api_key_env(self) -> str:
        """Get the default API key environment variable name for Qwen.

        Returns:
            str: Default Qwen API key environment variable name
        """
        return "DASHSCOPE_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        """Get a dictionary mapping Qwen model names to their default dimensions.

        Returns:
            dict[str, int]: Dictionary mapping model names to dimensions
        """
        return _QWEN_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        """Get the unique name identifier for QwenEmbeddingFunction.

        Returns:
            The name identifier for this embedding function type
        """
        return "qwen"

    def get_config(self) -> dict[str, Any]:
        """Get the configuration dictionary for the QwenEmbeddingFunction.

        Returns:
            Dictionary containing configuration needed to restore this embedding function
        """
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "QwenEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        dimensions = config.get("dimensions")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return QwenEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **client_kwargs,
        )
