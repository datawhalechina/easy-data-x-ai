import importlib
import json
from typing import Any

from pyseekdb.client.embedding_function import (
    Documents,
    EmbeddingFunction,
    Embeddings,
)

# Known Amazon Bedrock embedding model dimensions
# Source: https://docs.aws.amazon.com/bedrock/
_AMAZON_BEDROCK_MODEL_DIMENSIONS = {
    "amazon.titan-embed-text-v1": 1536,
    "amazon.titan-embed-text-v2": 1024,
    "amazon.titan-embed-g1-text-02": 1024,
    "amazon.titan-embed-text-v2:0": 1024,
}

_DEFAULT_MODEL_NAME = "amazon.titan-embed-text-v2"


class AmazonBedrockEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    A convenient embedding function for Amazon Bedrock embedding models using boto3.

    For more information about Amazon Bedrock models, see
    https://docs.aws.amazon.com/bedrock/

    This embedding function runs remotely on Amazon Bedrock's servers, and requires AWS credentials configured via boto3.

    Example:
        pip install pyseekdb boto3

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import AmazonBedrockEmbeddingFunction

        # Using Amazon Bedrock embedding model
        # Set up AWS credentials first (see Authentication section above)
        import boto3
        session = boto3.Session()
        ef = AmazonBedrockEmbeddingFunction(
            session=session,
            model_name="amazon.titan-embed-text-v2"
        )

        # Using with a custom boto3 session
        import boto3
        session = boto3.Session(region_name="us-east-1")
        ef = AmazonBedrockEmbeddingFunction(
            model_name="amazon.titan-embed-text-v2",
            session=session
        )

        # Using with AWS profile name via session
        import boto3
        session = boto3.Session(profile_name="my-profile")
        ef = AmazonBedrockEmbeddingFunction(
            model_name="amazon.titan-embed-text-v2",
            session=session
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
        session: Any,
        model_name: str = _DEFAULT_MODEL_NAME,
        **kwargs: Any,
    ):
        """Initialize AmazonBedrockEmbeddingFunction.

        Args:
            session (boto3.Session): A boto3 Session object to use.
                The session should be configured with appropriate credentials and region.
                region_name and profile_name will be extracted from the session for config storage.
            model_name (str, optional): Name of the Amazon Bedrock embedding model.
                Defaults to "amazon.titan-embed-text-v2".
                See Amazon Bedrock documentation for all available models
            **kwargs: Additional arguments passed to boto3.client().
                Common options include:
                - endpoint_url: Custom endpoint URL (for testing or custom deployments)
                - config: boto3 Config object for advanced configuration
                - See boto3 documentation for more options
        """
        if not importlib.util.find_spec("boto3"):
            raise ValueError("The boto3 python package is not installed. Please install it with `pip install boto3`")

        for key, value in kwargs.items():
            if not isinstance(value, (str, int, float, bool, list, dict, tuple)):
                raise TypeError(f"Keyword argument {key} is not a primitive type: {type(value)!s}")

        # Extract region_name and profile_name from the session for config storage
        self._session_args = {}
        if hasattr(session, "region_name") and session.region_name:
            self._session_args["region_name"] = session.region_name
        if hasattr(session, "profile_name") and session.profile_name:
            self._session_args["profile_name"] = session.profile_name

        # Store configuration (for get_config, but NOT credentials)
        self.model_name = model_name
        self._client_kwargs = kwargs

        # Initialize boto3 Bedrock Runtime client from session
        self._client = session.client("bedrock-runtime", **kwargs)

        # Store dimension for quick access (will be calculated if needed)
        model_dims = _AMAZON_BEDROCK_MODEL_DIMENSIONS
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

        accept = "application/json"
        content_type = "application/json"

        embeddings = []
        for text in documents:
            # Prepare request body for Bedrock API
            # Format depends on the model, but for Titan models it's:
            request_body = {"inputText": text}

            # Invoke the model
            response = self._client.invoke_model(
                modelId=self.model_name,
                body=json.dumps(request_body),
                accept=accept,
                contentType=content_type,
            )

            # Parse response
            # The response body is a StreamingBody, so we need to read it
            response_body = json.loads(response["body"].read())

            # Extract embedding from response
            # For Titan models, the embedding is in the "embedding" field
            embedding = response_body.get("embedding")
            if embedding is None:
                raise ValueError(f"Unexpected response format from Bedrock API: {response_body}")

            embeddings.append(embedding)

        return embeddings

    @staticmethod
    def name() -> str:
        return "amazon_bedrock"

    def get_config(self) -> dict[str, Any]:
        """Get the configuration dictionary for the AmazonBedrockEmbeddingFunction.

        Returns:
            Dictionary containing configuration needed to restore this embedding function.
            Note: AWS credentials are NOT stored in the config for security reasons.
            Credentials should be provided via environment variables, IAM roles, or
            passed as parameters when restoring.
        """
        # Never store credentials in config for security reasons
        # Users should use environment variables, IAM roles, or pass credentials
        # when restoring from config
        config = {
            "model_name": self.model_name,
            "client_kwargs": self._client_kwargs,
            "session_args": self._session_args,
        }

        return config

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "AmazonBedrockEmbeddingFunction":
        """Build an AmazonBedrockEmbeddingFunction from its configuration dictionary.

        Args:
            config: Dictionary containing the embedding function's configuration.
                Note: AWS credentials are NOT stored in config for security reasons.
                Credentials should be provided via environment variables, IAM roles,
                or passed as additional parameters.

        Returns:
            Restored AmazonBedrockEmbeddingFunction instance

        Raises:
            ValueError: If the configuration is invalid or missing required fields
        """
        model_name = config.get("model_name", _DEFAULT_MODEL_NAME)

        kwargs = config.get("client_kwargs", {})
        if not isinstance(kwargs, dict):
            raise TypeError(f"kwargs must be a dictionary, but got {kwargs}")

        # Credentials are not stored in config for security reasons
        # They should be provided via environment variables, IAM roles, or
        # passed as additional parameters when calling build_from_config
        # Create a session with region_name and profile_name if they were stored
        try:
            import boto3
        except ImportError as error:
            raise ValueError(
                "The boto3 python package is not installed. Please install it with `pip install boto3`"
            ) from error

        session_args = config.get("session_args")
        session = boto3.Session(**session_args) if session_args else boto3.Session()

        return AmazonBedrockEmbeddingFunction(
            session=session,
            model_name=model_name,
            **kwargs,
        )
