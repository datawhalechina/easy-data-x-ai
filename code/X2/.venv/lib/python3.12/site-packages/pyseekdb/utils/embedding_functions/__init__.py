"""
Embedding function implementations for pyseekdb.

This module provides various embedding function implementations that can be used
with pyseekdb collections.
"""

from .amazon_bedrock_embedding_function import AmazonBedrockEmbeddingFunction
from .bm25_sparse_embedding_function import BM25SparseEmbeddingFunction
from .cohere_embedding_function import CohereEmbeddingFunction
from .google_vertex_embedding_function import GoogleVertexEmbeddingFunction
from .huggingface_sparse_embedding_function import (
    HuggingFaceSparseEmbeddingFunction,
)
from .jina_embedding_function import JinaEmbeddingFunction
from .litellm_base_embedding_function import LiteLLMBaseEmbeddingFunction
from .mistral_embedding_function import MistralEmbeddingFunction
from .morph_embedding_function import MorphEmbeddingFunction
from .ollama_embedding_function import OllamaEmbeddingFunction
from .onnx_embedding_function import OnnxEmbeddingFunction
from .openai_base_embedding_function import OpenAIBaseEmbeddingFunction
from .openai_embedding_function import OpenAIEmbeddingFunction
from .qwen_embedding_function import QwenEmbeddingFunction
from .sentence_transformer_embedding_function import (
    SentenceTransformerEmbeddingFunction,
)
from .siliconflow_embedding_function import SiliconflowEmbeddingFunction
from .tencent_hunyuan_embedding_function import TencentHunyuanEmbeddingFunction
from .text2vec_embedding_function import Text2VecEmbeddingFunction
from .voyageai_embedding_function import VoyageaiEmbeddingFunction

__all__ = [
    "AmazonBedrockEmbeddingFunction",
    "BM25SparseEmbeddingFunction",
    "CohereEmbeddingFunction",
    "GoogleVertexEmbeddingFunction",
    "HuggingFaceSparseEmbeddingFunction",
    "JinaEmbeddingFunction",
    "LiteLLMBaseEmbeddingFunction",
    "MistralEmbeddingFunction",
    "MorphEmbeddingFunction",
    "OllamaEmbeddingFunction",
    "OnnxEmbeddingFunction",
    "OpenAIBaseEmbeddingFunction",
    "OpenAIEmbeddingFunction",
    "QwenEmbeddingFunction",
    "SentenceTransformerEmbeddingFunction",
    "SiliconflowEmbeddingFunction",
    "TencentHunyuanEmbeddingFunction",
    "Text2VecEmbeddingFunction",
    "VoyageaiEmbeddingFunction",
]
