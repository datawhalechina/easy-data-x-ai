import warnings
from typing import Any

from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known Tencent Hunyuan embedding model dimensions
# Source: https://cloud.tencent.com/document/product/1729/111007
# Note: The embedding interface currently only supports input and model parameters.
# Model is fixed as hunyuan-embedding, dimensions is fixed at 1024.
_TENCENT_HUNYUAN_MODEL_DIMENSIONS = {
    "hunyuan-embedding": 1024,
}


class TencentHunyuanEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for Tencent Hunyuan embedding models.

    This class provides a simplified interface to Tencent Hunyuan embedding models using the OpenAI-compatible API.
    Tencent Hunyuan provides OpenAI-compatible API endpoints for embedding generation.

    For more information about Tencent Hunyuan models, see https://cloud.tencent.com/document/product/1729/111007

    Note: The embedding interface currently only supports `input` and `model` parameters.
    The model is fixed as `hunyuan-embedding` and dimensions are fixed at 1024.

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import TencentHunyuanEmbeddingFunction

        # Using Tencent Hunyuan embedding model
        # Set HUNYUAN_API_KEY environment variable first
        ef = TencentHunyuanEmbeddingFunction()

        # Using with custom api_key_env and additional parameters
        ef = TencentHunyuanEmbeddingFunction(
            api_key_env="HUNYUAN_API_KEY",
            timeout=30
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
        model_name: str = "hunyuan-embedding",
        api_key_env: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize TencentHunyuanEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Tencent Hunyuan embedding model.
                Defaults to "hunyuan-embedding". Currently, this is the only supported model.
            api_key_env (str, optional): Name of the environment variable containing the Tencent Hunyuan API key.
                Defaults to "HUNYUAN_API_KEY" if not provided.
            api_base (str, optional): Base URL for the Tencent Hunyuan API endpoint.
                Defaults to "https://api.hunyuan.cloud.tencent.com/v1" if not provided.
            dimensions (int, optional): This parameter is not supported by the Tencent Hunyuan API.
                Dimensions are fixed at 1024. If provided, a warning will be issued and the parameter will be ignored.
            **kwargs: Additional arguments to pass to the OpenAI client.
                Common options include:
                - timeout: Request timeout in seconds
                - max_retries: Maximum number of retries
                - See https://github.com/openai/openai-python for more options
        """
        # Warn if dimensions parameter is provided since it's not supported
        if dimensions is not None:
            warnings.warn(
                "The dimensions parameter is not supported by Tencent Hunyuan API. "
                "Dimensions are fixed at 1024. The provided dimensions parameter will be ignored.",
                UserWarning,
                stacklevel=2,
            )

        # Warn if model_name is not the default
        if model_name != "hunyuan-embedding":
            warnings.warn(
                f"Model '{model_name}' may not be supported. "
                "Tencent Hunyuan embedding API currently only supports 'hunyuan-embedding'.",
                UserWarning,
                stacklevel=2,
            )

        super().__init__(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=None,  # Always None since API doesn't support it
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        return "https://api.hunyuan.cloud.tencent.com/v1"

    def _get_default_api_key_env(self) -> str:
        return "HUNYUAN_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        return _TENCENT_HUNYUAN_MODEL_DIMENSIONS

    @property
    def dimension(self) -> int:
        return 1024

    @staticmethod
    def name() -> str:
        return "tencent_hunyuan"

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "TencentHunyuanEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        # dimensions is ignored since API doesn't support it
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return TencentHunyuanEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            dimensions=None,  # Always None for Tencent Hunyuan
            **client_kwargs,
        )
