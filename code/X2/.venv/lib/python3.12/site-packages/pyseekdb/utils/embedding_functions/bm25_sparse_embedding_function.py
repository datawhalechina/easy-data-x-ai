"""
BM25 sparse embedding function powered by bm25s.

Uses ``bm25s`` for tokenization (with optional PyStemmer stemming and stopword
filtering) and a pure-Python MurmurHash3 (x86_32) for mapping tokens to
dimension indices.  Computes BM25-style term-frequency scores as sparse vector
weights — the query-independent part of BM25 (no IDF), suitable for building
a sparse vector index.

Install:
    pip install "bm25s[full]"

    # Optional, for better stemming performance:
    pip install PyStemmer

Example:
    >>> from pyseekdb.utils.embedding_functions import BM25SparseEmbeddingFunction
    >>> ef = BM25SparseEmbeddingFunction()
    >>> sparse_vectors = ef(["machine learning algorithms", "python tutorial"])
"""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Iterable
from typing import Any

from pyseekdb.client.sparse_embedding_function import (
    Documents,
    SparseEmbeddingFunction,
    SparseVector,
    SparseVectors,
    register_sparse_embedding_function,
)

# ── BM25 defaults ────────────────────────────────────────────────────

DEFAULT_K = 1.2
DEFAULT_B = 0.75
DEFAULT_AVG_DOC_LENGTH = 256.0
DEFAULT_DIM = 250_000

# ── Hasher (pure-Python MurmurHash3 x86_32) ─────────────────────────

_U32 = 0xFFFFFFFF


def _murmurhash3_x86_32(data: bytes, seed: int = 0) -> int:
    """Pure-Python MurmurHash3 x86_32, matching the C reference implementation."""
    length = len(data)
    h1 = seed & _U32
    c1 = 0xCC9E2D51
    c2 = 0x1B873593
    nblocks = length // 4

    for i in range(nblocks):
        k1 = struct.unpack_from("<I", data, i * 4)[0]
        k1 = (k1 * c1) & _U32
        k1 = ((k1 << 15) | (k1 >> 17)) & _U32
        k1 = (k1 * c2) & _U32
        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & _U32
        h1 = (h1 * 5 + 0xE6546B64) & _U32

    tail_index = nblocks * 4
    tail = data[tail_index:]
    k1 = 0
    tail_len = length & 3
    if tail_len >= 3:
        k1 ^= tail[2] << 16
    if tail_len >= 2:
        k1 ^= tail[1] << 8
    if tail_len >= 1:
        k1 ^= tail[0]
        k1 = (k1 * c1) & _U32
        k1 = ((k1 << 15) | (k1 >> 17)) & _U32
        k1 = (k1 * c2) & _U32
        h1 ^= k1

    h1 ^= length
    h1 ^= h1 >> 16
    h1 = (h1 * 0x85EBCA6B) & _U32
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & _U32
    h1 ^= h1 >> 16

    return h1


class _Murmur3AbsHasher:
    """
    MurmurHash3 x86_32 hasher returning non-negative signed-32-bit values.

    The output matches ``abs(mmh3.hash(token, seed=seed))``.
    """

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    def hash(self, token: str) -> int:
        unsigned = _murmurhash3_x86_32(token.encode("utf-8"), self._seed)
        signed = struct.unpack("<i", struct.pack("<I", unsigned))[0]
        return abs(signed)


# ── BM25 Sparse Embedding Function ──────────────────────────────────


@register_sparse_embedding_function
class BM25SparseEmbeddingFunction(SparseEmbeddingFunction):
    """
    BM25 sparse embedding function powered by ``bm25s``.

    Tokenizes text via ``bm25s.tokenize()`` (lowercase, regex split, stopword
    removal, optional stemming with PyStemmer), hashes each token to a dimension
    index via MurmurHash3, and computes a BM25-style term frequency weight:

        score = tf * (k + 1) / (tf + k * (1 - b + b * doc_len / avg_doc_length))

    This is the *query-independent* part of BM25 (no IDF), suitable for building
    a sparse vector index.  The IDF component can be handled at search time by
    the database engine.

    Args:
        k: BM25 k1 parameter controlling term-frequency saturation. Default 1.2.
        b: BM25 b parameter controlling document-length normalization. Default 0.75.
        avg_doc_length: Assumed average document length in tokens. Default 256.0.
        dim: Maximum number of sparse-vector dimensions.  Hash values are reduced
            via ``hash % dim`` so every index falls in ``[0, dim)``.  Must not
            exceed the database engine's limit (seekdb supports up to 500 000).
            Default 250 000.
        language: Language for stopwords and stemming. Default ``"english"``.
            Supported values depend on bm25s (e.g. ``"english"``, ``"german"``,
            ``"french"``, etc.) and PyStemmer for stemming.
        stopwords: Custom stopword list.  ``None`` uses the built-in stopword
            list selected by *language*.

    Example:
        >>> ef = BM25SparseEmbeddingFunction(k=1.5, b=0.8)
        >>> vectors = ef(["machine learning algorithms"])
        >>> print(vectors[0])
        SparseVector(3 non-zero entries)
    """

    def __init__(
        self,
        k: float = DEFAULT_K,
        b: float = DEFAULT_B,
        avg_doc_length: float = DEFAULT_AVG_DOC_LENGTH,
        dim: int = DEFAULT_DIM,
        language: str = "english",
        stopwords: Iterable[str] | None = None,
    ) -> None:
        try:
            import bm25s  # noqa: F401
        except ImportError as exc:
            raise ValueError(
                "The bm25s package is not installed. Please install it with `pip install bm25s[full]`"
            ) from exc
        if k < 0:
            raise ValueError("k must be greater than or equal to 0")
        if float(avg_doc_length) <= 0:
            raise ValueError("avg_doc_length must be greater than 0")
        if int(dim) <= 0:
            raise ValueError("dim must be greater than 0")

        self.k = float(k)
        self.b = float(b)
        self.avg_doc_length = float(avg_doc_length)
        self.dim = int(dim)
        self.language = language

        if stopwords is not None:
            self.stopwords: list[str] | None = [str(w) for w in stopwords]
        else:
            self.stopwords = None

        self._stemmer = self._create_stemmer(language)
        self._hasher = _Murmur3AbsHasher()

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _create_stemmer(language: str) -> Any:
        """Return a PyStemmer ``Stemmer`` if available, else ``None``."""
        try:
            import Stemmer

            return Stemmer.Stemmer(language)
        except (ImportError, KeyError):
            return None

    def _tokenize(self, texts: list[str]) -> list[list[str]]:
        """Tokenize *texts* via bm25s, returning lists of (stemmed) token strings."""
        import bm25s

        sw = self.stopwords if self.stopwords is not None else self.language
        return bm25s.tokenize(
            texts,
            stopwords=sw,
            stemmer=self._stemmer,
            return_ids=False,
            show_progress=False,
        )

    def _score_tokens(self, tokens: list[str]) -> SparseVector:
        """Compute BM25 TF sparse vector from a list of tokens."""
        tokens = [t for t in tokens if t]

        if not tokens:
            return SparseVector.from_dict({0: 1e-6})

        doc_len = float(len(tokens))
        counts = Counter(tokens)

        dim_scores: dict[int, float] = {}
        for token, count in counts.items():
            tf = float(count)
            denominator = tf + self.k * (1 - self.b + (self.b * doc_len) / self.avg_doc_length)
            score = tf * (self.k + 1) / denominator
            idx = self._hasher.hash(token) % self.dim
            dim_scores[idx] = dim_scores.get(idx, 0.0) + score

        indices = sorted(dim_scores.keys())
        values = [dim_scores[i] for i in indices]

        return SparseVector.from_indices(indices, values)

    # ── Public API ────────────────────────────────────────────────────

    def __call__(self, documents: Documents) -> SparseVectors:
        if isinstance(documents, str):
            documents = [documents]
        token_lists = self._tokenize(list(documents))
        return [self._score_tokens(tokens) for tokens in token_lists]

    # ── Persistence ──────────────────────────────────────────────────

    @staticmethod
    def name() -> str:
        return "bm25"

    def get_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "k": self.k,
            "b": self.b,
            "avg_doc_length": self.avg_doc_length,
            "dim": self.dim,
            "language": self.language,
        }
        if self.stopwords is not None:
            config["stopwords"] = list(self.stopwords)
        return config

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> BM25SparseEmbeddingFunction:
        return BM25SparseEmbeddingFunction(
            k=config.get("k", DEFAULT_K),
            b=config.get("b", DEFAULT_B),
            avg_doc_length=config.get("avg_doc_length", DEFAULT_AVG_DOC_LENGTH),
            dim=config.get("dim", DEFAULT_DIM),
            language=config.get("language", "english"),
            stopwords=config.get("stopwords"),
        )
