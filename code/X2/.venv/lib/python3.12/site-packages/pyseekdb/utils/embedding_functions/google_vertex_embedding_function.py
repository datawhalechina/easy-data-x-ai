import os
from typing import Any

from pyseekdb.client.embedding_function import Documents, EmbeddingFunction, Embeddings

_DEFAULT_MODEL_NAME = "textembedding-gecko"


class GoogleVertexEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    A convenient embedding function for Google Vertex AI embedding models.

    For more information about Google Vertex AI models, see
    https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/text-embeddings-api

    Example:
        pip install pyseekdb google-cloud-aiplatform

    .. code-block:: python
        import pyseekdb
        from pyseekdb.utils.embedding_functions import GoogleVertexEmbeddingFunction

        # Using Google Vertex AI embedding model
        # Set up authentication first (see Authentication section above)
        ef = GoogleVertexEmbeddingFunction(
            project_id="your-project-id",
            model_name="textembedding-gecko"
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
        model_name: str = _DEFAULT_MODEL_NAME,
        project_id: str = "cloud-large-language-models",
        region: str = "us-central1",
        api_key_env: str | None = "GOOGLE_VERTEX_API_KEY",
    ):
        """
        Initialize the GoogleVertexEmbeddingFunction.

        Args:
            api_key_env (str, optional): Environment variable name that contains your API key for the Google Vertex AI API.
                Defaults to "GOOGLE_VERTEX_API_KEY".
            model_name (str, optional): The name of the model to use for text embeddings.
                Defaults to "textembedding-gecko".
            project_id (str, optional): The Google Cloud project ID.
                Defaults to "cloud-large-language-models".
            region (str, optional): The Google Cloud region.
                Defaults to "us-central1".
        """
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel
        except ImportError as error:
            raise ValueError(
                "The vertexai python package is not installed. Please install it with `pip install google-cloud-aiplatform`"
            ) from error

        self.api_key_env = api_key_env
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"The {api_key_env} environment variable is not set.")

        self.model_name = model_name
        self.project_id = project_id
        self.region = region

        vertexai.init(project=project_id, location=region)
        self._model = TextEmbeddingModel.from_pretrained(model_name)

    def __call__(self, documents: Documents) -> Embeddings:
        """
        Generate embeddings for the given documents.

        Args:
            documents: Documents or images to generate embeddings for.

        Returns:
            Embeddings for the documents.
        """
        if not documents:
            return []
        if isinstance(documents, str):
            documents = [documents]

        # Google Vertex only works with text documents
        if not all(isinstance(item, str) for item in documents):
            raise ValueError("Google Vertex only supports text documents")

        embeddings_response = self._model.get_embeddings(documents)
        embeddings_list = [embedding.values for embedding in embeddings_response]
        return embeddings_list

    @staticmethod
    def name() -> str:
        return "google_vertex"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "GoogleVertexEmbeddingFunction":
        api_key_env = config.get("api_key_env")
        model_name = config.get("model_name")
        project_id = config.get("project_id")
        region = config.get("region")

        if api_key_env is None or model_name is None or project_id is None or region is None:
            raise ValueError("Missing required configuration")

        return GoogleVertexEmbeddingFunction(
            api_key_env=api_key_env,
            model_name=model_name,
            project_id=project_id,
            region=region,
        )

    def get_config(self) -> dict[str, Any]:
        return {
            "api_key_env": self.api_key_env,
            "model_name": self.model_name,
            "project_id": self.project_id,
            "region": self.region,
        }
