from typing import Any

from pyseekdb.client.embedding_function import Documents, Embeddings
from pyseekdb.utils.embedding_functions.openai_base_embedding_function import (
    OpenAIBaseEmbeddingFunction,
)

# Known Mistral embedding model dimensions
# Source: https://docs.mistral.ai/capabilities/embeddings/text_embeddings
_MISTRAL_MODEL_DIMENSIONS = {
    "mistral-embed": 1024,
}


class MistralEmbeddingFunction(OpenAIBaseEmbeddingFunction):
    """
    A convenient embedding function for Mistral text embedding models.

    This class provides a simplified interface to Mistral text embeddings using the
    OpenAI-compatible API.

    Note: The embeddings API only accepts the model name and input texts.

    For more information about Mistral embeddings, see:
    https://docs.mistral.ai/capabilities/embeddings/text_embeddings

    Example:
        pip install pyseekdb openai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import MistralEmbeddingFunction

        # Using Mistral text embedding model
        # Set MISTRAL_API_KEY environment variable first
        ef = MistralEmbeddingFunction(model_name="mistral-embed")

        # Using with additional parameters
        ef = MistralEmbeddingFunction(
            model_name="mistral-embed",
            timeout=30,
            max_retries=3
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
        model_name: str = "mistral-embed",
        api_key_env: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ):
        """Initialize MistralEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Mistral embedding model.
                Defaults to "mistral-embed".
            api_key_env (str, optional): Name of the environment variable containing the Mistral API key.
                Defaults to "MISTRAL_API_KEY" if not provided.
            api_base (str, optional): Base URL for the Mistral API endpoint.
                Defaults to "https://api.mistral.ai/v1" if not provided.
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
            **kwargs,
        )

    def _get_default_api_base(self) -> str:
        return "https://api.mistral.ai/v1"

    def _get_default_api_key_env(self) -> str:
        return "MISTRAL_API_KEY"

    def _get_model_dimensions(self) -> dict[str, int]:
        return _MISTRAL_MODEL_DIMENSIONS

    @staticmethod
    def name() -> str:
        return "mistral"

    def __call__(self, documents: Documents) -> Embeddings:
        """Generate embeddings for the given documents using Mistral's input parameter."""
        if isinstance(documents, str):
            documents = [documents]

        if not documents:
            return []

        request_params = {
            "model": self.model_name,
            "input": documents,
        }

        response = self._client.embeddings.create(**request_params)
        embeddings = [item.embedding for item in response.data]

        if len(embeddings) != len(documents):
            raise ValueError(f"Expected {len(documents)} embeddings but got {len(embeddings)} from API")

        return embeddings

    def get_config(self) -> dict[str, Any]:
        return super().get_config()

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "MistralEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env")
        api_base = config.get("api_base")
        client_kwargs = config.get("client_kwargs", {})
        if not isinstance(client_kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {client_kwargs}")

        return MistralEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            api_base=api_base,
            **client_kwargs,
        )
