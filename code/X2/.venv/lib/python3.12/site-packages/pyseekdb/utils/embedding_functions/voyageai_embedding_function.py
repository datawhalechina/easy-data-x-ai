import os
from typing import Any

from pyseekdb.client.embedding_function import (
    Documents,
    EmbeddingFunction,
    Embeddings,
)

# Known Voyage AI embedding model dimensions
# Source: https://docs.voyageai.com/docs/embeddings
# Note: Many models support flexible dimensions (256, 512, 1024, 2048)
# Default dimensions are listed below
_VOYAGEAI_MODEL_DIMENSIONS = {
    # Latest models (voyage-4 series)
    "voyage-4-large": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-4": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-4-lite": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-code-3": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-finance-2": 1024,
    "voyage-law-2": 1024,
    "voyage-code-2": 1536,
    # Previous generation models
    "voyage-3-large": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-3.5": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-3.5-lite": 1024,  # default, supports 256, 512, 1024, 2048
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-multilingual-2": 1024,
    # Open models
    "voyage-4-nano": 1024,  # default, supports 256, 512, 1024, 2048
}


class VoyageaiEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    A convenient embedding function for Voyage AI embedding models.

    This class provides a simplified interface to Voyage AI embedding models using the voyageai package.

    For more information about Voyage AI models, see https://docs.voyageai.com/docs/embeddings

    Example:
        pip install pyseekdb voyageai

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import VoyageaiEmbeddingFunction

        # Using Voyage AI embedding model
        # Set VOYAGE_API_KEY environment variable first
        ef = VoyageaiEmbeddingFunction(
            model_name="voyage-4-large"
        )

        # Using with input_type for better retrieval performance
        ef = VoyageaiEmbeddingFunction(
            model_name="voyage-4-large",
            input_type="document"  # or "query" for queries
        )

        # Using with custom output_dimension
        ef = VoyageaiEmbeddingFunction(
            model_name="voyage-4-large",
            output_dimension=512  # Reduce from default 1024 to 512
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
        model_name: str = "voyage-4-large",
        api_key_env: str | None = None,
        input_type: str | None = None,
        truncation: bool | None = None,
        output_dimension: int | None = None,
        **kwargs: Any,
    ):
        """Initialize VoyageaiEmbeddingFunction.

        Args:
            model_name (str, optional): Name of the Voyage AI embedding model.
                Defaults to "voyage-4-large".
                See Voyage AI documentation for all available models
            api_key_env (str, optional): Name of the environment variable containing the Voyage AI API key.
                Defaults to "VOYAGE_API_KEY" if not provided.
            input_type (str, optional): Type of the input text. Options: None, "query", "document".
                When set to "query" or "document", Voyage AI prepends a prompt to optimize
                embeddings for retrieval/search tasks. Defaults to None.
            truncation (bool, optional): Whether to truncate input texts to fit within context length.
                If True, over-length texts will be truncated. If False, an error will be raised
                for over-length texts. Defaults to None (uses Voyage AI default, which is True).
            output_dimension (int, optional): The number of dimensions for resulting embeddings.
                Supported values depend on the model. For voyage-4 series, voyage-3-large, voyage-3.5,
                voyage-3.5-lite, and voyage-code-3: 256, 512, 1024 (default), 2048.
                If None, uses the model's default dimension.
            **kwargs: Additional arguments (currently not used, reserved for future use).
        """
        try:
            import voyageai
        except ImportError as error:
            raise ValueError(
                "The voyageai python package is not installed. Please install it with `pip install voyageai`"
            ) from error

        # Get API key from environment variable
        if api_key_env is None:
            api_key_env = "VOYAGE_API_KEY"
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise ValueError(f"Voyage AI API key not found. Please set the '{api_key_env}' environment variable.")

        # Store configuration
        self.model_name = model_name
        self.api_key_env = api_key_env
        self.input_type = input_type
        self.truncation = truncation
        self.output_dimension = output_dimension
        self.kwargs = kwargs

        # Initialize Voyage AI client
        self._client = voyageai.Client(api_key=api_key)

        # Store dimension for quick access (will be calculated if needed)
        self._dimension = output_dimension
        if self._dimension is None:
            # Use default dimension from model dimensions dict if known
            model_dims = _VOYAGEAI_MODEL_DIMENSIONS
            if model_name in model_dims:
                self._dimension = model_dims[model_name]
            else:
                # Will be calculated on first access via dimension property
                self._dimension = None

    @property
    def dimension(self) -> int:
        # If output_dimension is explicitly set, use it
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

    def __call__(self, documents: Documents) -> Embeddings:
        # Handle single string input
        if isinstance(documents, str):
            documents = [documents]

        # Handle empty input
        if not documents:
            return []

        # Prepare parameters for voyageai.Client.embed()
        embed_params = {
            "texts": documents,
            "model": self.model_name,
            "output_dtype": "float",  # Always use float
        }

        # Add optional parameters
        if self.input_type is not None:
            embed_params["input_type"] = self.input_type
        if self.truncation is not None:
            embed_params["truncation"] = self.truncation
        if self.output_dimension is not None:
            embed_params["output_dimension"] = self.output_dimension

        # Call Voyage AI API
        result = self._client.embed(**embed_params)

        # Extract embeddings from result
        embeddings = result.embeddings

        # Validate that we got the expected number of embeddings
        if len(embeddings) != len(documents):
            raise ValueError(f"Expected {len(documents)} embeddings but got {len(embeddings)} from API")

        # Convert to list of lists (in case voyageai returns numpy arrays or other formats)
        return embeddings

    @staticmethod
    def name() -> str:
        return "voyageai"

    def get_config(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "api_key_env": self.api_key_env,
            "input_type": self.input_type,
            "truncation": self.truncation,
            "output_dimension": self.output_dimension,
            "client_kwargs": self.kwargs,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "VoyageaiEmbeddingFunction":
        model_name = config.get("model_name")
        if model_name is None:
            raise ValueError("Missing required field 'model_name' in configuration")

        api_key_env = config.get("api_key_env", "VOYAGE_API_KEY")
        input_type = config.get("input_type")
        truncation = config.get("truncation")
        output_dimension = config.get("output_dimension")
        kwargs = config.get("client_kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"client_kwargs must be a dictionary, but got {kwargs}")

        return VoyageaiEmbeddingFunction(
            model_name=model_name,
            api_key_env=api_key_env,
            input_type=input_type,
            truncation=truncation,
            output_dimension=output_dimension,
            **kwargs,
        )
