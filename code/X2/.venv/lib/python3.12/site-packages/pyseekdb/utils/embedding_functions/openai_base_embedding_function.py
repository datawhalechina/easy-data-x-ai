import os
from typing import Any

from pyseekdb.client.embedding_function import Documents, EmbeddingFunction, Embeddings


class OpenAIBaseEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Base embedding function for OpenAI-compatible embedding APIs.

    This class provides a common implementation for embedding functions that use
    OpenAI-compatible APIs. It uses the `openai` package to make API calls.

    Subclasses should override:
    - `_get_default_api_base()`: Return the default API base URL
    - `_get_default_api_key_env()`: Return the default API key environment variable name
    - `_get_model_dimensions()`: Return a dict mapping model names to their default dimensions
    - Optionally override `__init__` to set model-specific defaults

    Example:
    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import OpenAIBaseEmbeddingFunction

        class MyEmbeddingFunction(OpenAIBaseEmbeddingFunction):
            def _get_default_api_base(self):
                return "https://api.example.com/v1"

            def _get_default_api_key_env(self):
                return "MY_API_KEY"

            def _get_model_dimensions(self):
                return {"model-v1": 1536, "model-v2": 1024}
    """

    def __init__(
        self,
        model_name: str,
        api_key_env: str | None = None,
        api_base: str | None = None,
        dimensions: int | None = None,
        **kwargs: Any,
    ):
        """Initialize OpenAIBaseEmbeddingFunction.

        Args:
            model_name (str): Name of the embedding model.
            api_key_env (str, optional): Name of the environment variable containing the API key.
                Defaults to the value returned by `_get_default_api_key_env()`.
            api_base (str, optional): Base URL for the API endpoint.
                Defaults to the value returned by `_get_default_api_base()`.
            dimensions (int, optional): The number of dimensions the resulting embeddings should have.
                Can reduce dimensions from default for models that support it.
            **kwargs: Additional arguments to pass to the OpenAI client.
                Common options include:
                - timeout: Request timeout in seconds
                - max_retries: Maximum number of retries
                - See https://github.com/openai/openai-python for more options
        """
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ValueError(
                "The openai python package is not installed. Please install it with `pip install openai`"
            ) from exc

        # Set defaults
        if api_key_env is None:
            api_key_env = self._get_default_api_key_env()
        if api_base is None:
            api_base = self._get_default_api_base()

        # Validate that API key is available
        api_key = os.environ.get(api_key_env)
        if api_key is None:
            raise ValueError(
                f"API key environment variable '{api_key_env}' is not set. "
                f"Please set it before using {self.__class__.__name__}."
            )

        # Store configuration
        self.model_name = model_name
        self.api_key_env = api_key_env
        self.api_base = api_base
        self._dimensions_param = dimensions
        self._client_kwargs = kwargs

        # Initialize OpenAI client
        self._client = OpenAI(api_key=api_key, base_url=api_base, **kwargs)

        # Store original model name for dimension lookup
        self._model_name = model_name

    def _get_default_api_base(self) -> str:
        """Get the default API base URL for this provider.

        Subclasses should override this method.

        Returns:
            str: Default API base URL
        """
        raise NotImplementedError("Subclasses must implement _get_default_api_base()")

    def _get_default_api_key_env(self) -> str:
        """Get the default API key environment variable name for this provider.

        Subclasses should override this method.

        Returns:
            str: Default API key environment variable name
        """
        raise NotImplementedError("Subclasses must implement _get_default_api_key_env()")

    def _get_model_dimensions(self) -> dict[str, int]:
        """Get a dictionary mapping model names to their default dimensions.

        Subclasses should override this method.

        Returns:
            dict[str, int]: Dictionary mapping model names to dimensions
        """
        return {}

    @property
    def dimension(self) -> int:
        """Get the dimension of embeddings produced by this function.

        Returns the known dimension for models without making an API call.
        If the dimensions parameter is specified, that value is returned.
        Otherwise, the default dimension for the model is returned.

        If the model is not in the known dimensions list, falls back to calling
        the parent's dimension detection (which may make an API call).

        Returns:
            int: The dimension of embeddings for this model.
        """
        # If dimensions parameter is explicitly set, use it
        if self._dimensions_param is not None:
            return self._dimensions_param

        # Check if we know the dimension for this model
        model_dimensions = self._get_model_dimensions()
        if self._model_name in model_dimensions:
            return model_dimensions[self._model_name]

        # Fallback: make an API call to get the embedding and infer the dimension
        # This is done by actually generating an embedding for a dummy sentence
        test_input = "dimension probing"
        try:
            embeddings = self([test_input])
        except Exception as e:
            raise RuntimeError(f"Failed to determine embedding dimension via API call: {e}") from e
        if not embeddings or not isinstance(embeddings, list) or not isinstance(embeddings[0], list):
            raise RuntimeError("Could not get embedding dimension from API response")
        return len(embeddings[0])

    def __call__(self, documents: Documents) -> Embeddings:
        """Generate embeddings for the given documents.

        Args:
            documents: Documents to generate embeddings for. Can be a single string or list of strings.

        Returns:
            Embeddings for the documents as a list of lists of floats.
        """
        # Handle single string input
        if isinstance(documents, str):
            documents = [documents]

        # Handle empty input
        if not documents:
            return []

        # Prepare request parameters
        request_params = {
            "model": self.model_name,
            "input": documents,
        }

        # Add dimensions parameter if specified
        if self._dimensions_param is not None:
            request_params["dimensions"] = self._dimensions_param

        # Call OpenAI API
        response = self._client.embeddings.create(**request_params)

        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]

        # Validate that we got the expected number of embeddings
        if len(embeddings) != len(documents):
            raise ValueError(f"Expected {len(documents)} embeddings but got {len(embeddings)} from API")

        return embeddings

    def get_config(self) -> dict[str, Any]:
        """
        Get the configuration dictionary for the OpenAIBaseEmbeddingFunction.

        Subclasses should override the name() method to provide the correct name for routing.

        Returns:
            Dictionary containing configuration needed to restore this embedding function
        """
        return {
            "model_name": self.model_name,
            "api_key_env": self.api_key_env,
            "api_base": self.api_base,
            "dimensions": self._dimensions_param,
            "client_kwargs": self._client_kwargs,
        }
