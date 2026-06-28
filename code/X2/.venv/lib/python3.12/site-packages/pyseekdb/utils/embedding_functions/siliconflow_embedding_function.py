from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known SiliconFlow embedding model dimensions
# Source: https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings
_SILICONFLOW_MODEL_DIMENSIONS = {
    "BAAI/bge-large-zh-v1.5": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
    "netease-youdao/bce-embedding-base_v1": 768,
    "BAAI/bge-m3": 1024,
    "Pro/BAAI/bge-m3": 1024,
    # Qwen models support variable dimensions, default values listed below
    "Qwen/Qwen3-Embedding-8B": 4096,  # default, supports [64,128,256,512,768,1024,1536,2048,2560,4096]
    "Qwen/Qwen3-Embedding-4B": 2560,  # default, supports [64,128,256,512,768,1024,1536,2048,2560]
    "Qwen/Qwen3-Embedding-0.6B": 1024,  # default, supports [64,128,256,512,768,1024]
}


class SiliconflowEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for SiliconFlow embedding models.

    This class provides a simplified interface to SiliconFlow embedding models using the OpenAI-compatible API.
    SiliconFlow provides OpenAI-compatible API endpoints for embedding generation.

    For more information about SiliconFlow models, see https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import SiliconflowEmbeddingFunction

        # Using SiliconFlow embedding model
        # Set SILICONFLOW_API_KEY environment variable first
        ef = SiliconflowEmbeddingFunction(
            model_name="BAAI/bge-large-zh-v1.5"
        )

        # Using with custom api_key_env and additional parameters
        ef = SiliconflowEmbeddingFunction(
            model_name="BAAI/bge-m3",
            api_key_env="SILICONFLOW_API_KEY",
            timeout=30
        )

        # Using Qwen models with custom dimensions
        ef = SiliconflowEmbeddingFunction(
            model_name="Qwen/Qwen3-Embedding-8B",
            dimensions=1024  # Reduce from default 4096 to 1024
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
        model_name: str = "BAAI/bge-large-zh-v1.5",
        api_key_env: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize SiliconflowEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the SiliconFlow embedding model.
                Defaults to "BAAI/bge-large-zh-v1.5".
                See SiliconFlow documentation for available models: https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings
            api_key_env (str, optional): Name of the environment variable containing the SiliconFlow API key.
                Defaults to "SILICONFLOW_API_KEY" if not provided.
            api_base (str, optional): Base URL for the SiliconFlow API endpoint.
                Defaults to "https://api.siliconflow.cn/v1" if not provided.
            dimensions (int, optional): The number of dimensions the resulting embeddings should have.
                See SiliconFlow documentation for available models: https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings
            **kwargs: Additional arguments to pass to the OpenAI client.
                See https://github.com/openai/openai-python for more information.
        """
        super().__init__(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        return "https://api.siliconflow.cn/v1"

    def _get_default_api_key_env(self) -> str:
        return "SILICONFLOW_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        return _SILICONFLOW_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        return "siliconflow"

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "SiliconflowEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        dimensions = config.get("dimensions")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return SiliconflowEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=dimensions,
            **client_kwargs,
        )
