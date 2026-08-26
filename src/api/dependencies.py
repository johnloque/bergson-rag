"""FastAPI dependencies: process-wide singletons for the Qdrant client and
the three models this API loads (dense embedder, sparse embedder,
cross-encoder reranker) — each is expensive to construct (model weights) and
stateless/thread-safe to reuse across requests, same convention as the
`scope="module"` fixtures in tests/test_guardrail.py and
tests/test_chunk_judge.py. `lru_cache` gives one instance per process,
built lazily on first request rather than at import time.

## Native ml_service, containerized opt-in (feat/native-ml-service)

The three model singletons below are either loaded in-process (as before)
or replaced with a thin HTTP client to the native `ml_service`
(src/ml_service/main.py) depending on `ML_SERVICE_URL` — the same
native-by-default, containerized-opt-in split `fix/ollama-native-default`
already applied to generation, now applied to dense/sparse embedding and
cross-encoder reranking (docs/dockerization.md's measured ~31x
CPU-in-container slowdown on reranking specifically). Empty/unset (the
default for a plain `uv run uvicorn` dev process, and this module's own
default) keeps today's behavior — models loaded directly into this
process. Set (`docker-compose.yml`'s `api` service default:
`http://host.docker.internal:8100`) calls the native service instead,
started via `make setup-ml-service` / `scripts/setup_ml_service.sh`. Either
way, `src/retrieval/hybrid.py` and `src/retrieval/reranking.py` call the
exact same `.embed()` / `.embed_query()` / `.score()` methods — see
src/api/ml_client.py's module docstring for why the remote wrapper classes
need implement only that subset.
"""

from __future__ import annotations

import os
from functools import lru_cache

from qdrant_client import QdrantClient

from src.api.ml_client import RemoteCrossEncoderReranker, RemoteDenseEmbedder, RemoteSparseEmbedder
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME
from src.retrieval.reranking import CrossEncoderReranker

# Overridable so the api container can reach Qdrant by its internal Docker
# service name (QDRANT_URL=http://qdrant:6333, docker-compose.yml) --
# "localhost" inside that container would mean the api container itself,
# not the qdrant one. Defaults to the non-Docker dev setup (docker-compose
# up qdrant, published on the host's localhost).
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# See this module's "Native ml_service, containerized opt-in" docstring
# section above. Empty by default -- deliberately NOT defaulted to
# http://host.docker.internal:8100 here, unlike docker-compose.yml's `api`
# service environment: that default belongs to the containerized profile,
# not to this module, so a plain host `uv run uvicorn` dev process (no
# Docker involved at all) keeps today's in-process behavior unless someone
# opts in explicitly.
ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "")


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@lru_cache(maxsize=1)
def get_dense_embedder() -> DenseEmbedder | RemoteDenseEmbedder:
    if ML_SERVICE_URL:
        return RemoteDenseEmbedder(ML_SERVICE_URL)
    return DenseEmbedder()


@lru_cache(maxsize=1)
def get_sparse_embedder() -> SparseEmbedder | RemoteSparseEmbedder:
    if ML_SERVICE_URL:
        return RemoteSparseEmbedder(ML_SERVICE_URL)
    return SparseEmbedder()


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoderReranker | RemoteCrossEncoderReranker:
    if ML_SERVICE_URL:
        return RemoteCrossEncoderReranker(ML_SERVICE_URL)
    return CrossEncoderReranker()


__all__ = [
    "COLLECTION_NAME",
    "get_dense_embedder",
    "get_qdrant_client",
    "get_reranker",
    "get_sparse_embedder",
]
