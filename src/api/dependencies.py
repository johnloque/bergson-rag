"""FastAPI dependencies: process-wide singletons for the Qdrant client and
the three models this API loads (dense embedder, sparse embedder,
cross-encoder reranker) — each is expensive to construct (model weights) and
stateless/thread-safe to reuse across requests, same convention as the
`scope="module"` fixtures in tests/test_guardrail.py and
tests/test_chunk_judge.py. `lru_cache` gives one instance per process,
built lazily on first request rather than at import time.
"""

from __future__ import annotations

import os
from functools import lru_cache

from qdrant_client import QdrantClient

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME
from src.retrieval.reranking import CrossEncoderReranker

# Overridable so the api container can reach Qdrant by its internal Docker
# service name (QDRANT_URL=http://qdrant:6333, docker-compose.yml) --
# "localhost" inside that container would mean the api container itself,
# not the qdrant one. Defaults to the non-Docker dev setup (docker-compose
# up qdrant, published on the host's localhost).
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@lru_cache(maxsize=1)
def get_dense_embedder() -> DenseEmbedder:
    return DenseEmbedder()


@lru_cache(maxsize=1)
def get_sparse_embedder() -> SparseEmbedder:
    return SparseEmbedder()


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


__all__ = [
    "COLLECTION_NAME",
    "get_dense_embedder",
    "get_qdrant_client",
    "get_reranker",
    "get_sparse_embedder",
]
