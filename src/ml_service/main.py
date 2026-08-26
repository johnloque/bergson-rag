"""Native ML service (feat/native-ml-service, docs/dockerization.md).

The finding this branch acts on: Docker Desktop on Apple Silicon has no
Metal passthrough into its Linux VM, so any of this project's three
`sentence-transformers`-backed models (`DenseEmbedder`, `SparseEmbedder`,
`CrossEncoderReranker` — src/indexing/embeddings.py,
src/retrieval/reranking.py) running inside a container falls back to
CPU-only, silently and with no error. Measured directly for the
cross-encoder reranker alone: 8.3s native (MPS) vs 258s containerized
(CPU) for the same 15-candidate batch, ~31x — see docs/dockerization.md's
"`/retrieve` reranking, reproduced in isolation" section. This is the same
root cause `fix/ollama-native-default` already fixed for generation; this
service applies the identical native-by-default, containerized-opt-in
split to the other three models.

This app is meant to run directly on the host (`scripts/setup_ml_service.sh`
/ `make setup-ml-service`), never inside `docker-compose.yml` — there is no
service block for it there, unlike Ollama's opt-in `with-ollama` profile:
a fully-containerized stack is still possible, it just means not running
this script and leaving `ML_SERVICE_URL` unset (src/api/dependencies.py),
which falls back to the pre-existing in-process model loading in `api`.

All three models are loaded once at process startup (FastAPI `lifespan`,
stored on `app.state`) rather than lazily per-request — this process's
only job is serving these models, so there is no "maybe never needed"
case to defer construction for, unlike `api`'s `lru_cache`-based lazy
singletons (src/api/dependencies.py), which stay lazy because `api` also
has to start up (and pass its healthcheck) even before Qdrant has data or
a request has ever asked for a model.

## Sparse embedding: query-side only

`/embed/sparse` calls `SparseEmbedder.embed_query`, not `.embed`
(src/indexing/embeddings.py — the two differ: flat presence weighting for
queries vs. TF/length-saturation weighting for indexed documents). This
service is only ever called from `api`'s `/retrieve` handler
(src/retrieval/hybrid.py's `hybrid_search`, which only calls
`sparse_embedder.embed_query`) — per this project's architecture, `/retrieve`
is the only endpoint that talks to these three models at request time.
Document-side sparse embedding happens once, offline, during indexing
(`scripts/build_index.py`, `src/indexing/indexer.py`), which already runs
natively via `uv run` and never goes through `api` or this service at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.ml_service.schemas import (
    DenseEmbedRequest,
    DenseEmbedResponse,
    RerankRequest,
    RerankResponse,
    SparseEmbedRequest,
    SparseEmbedResponse,
)
from src.retrieval.reranking import CrossEncoderReranker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.dense_embedder = DenseEmbedder()
    app.state.sparse_embedder = SparseEmbedder()
    app.state.reranker = CrossEncoderReranker()
    yield


app = FastAPI(title="bergson-rag ML service", lifespan=lifespan)


@app.post("/embed/dense", response_model=DenseEmbedResponse)
def embed_dense(body: DenseEmbedRequest, request: Request) -> DenseEmbedResponse:
    vectors = request.app.state.dense_embedder.embed(body.texts)
    return DenseEmbedResponse(vectors=vectors)


@app.post("/embed/sparse", response_model=SparseEmbedResponse)
def embed_sparse(body: SparseEmbedRequest, request: Request) -> SparseEmbedResponse:
    # Query-side (embed_query), not document-side -- see module docstring.
    pairs = request.app.state.sparse_embedder.embed_query(body.texts)
    return SparseEmbedResponse(
        indices=[indices for indices, _values in pairs],
        values=[values for _indices, values in pairs],
    )


@app.post("/rerank", response_model=RerankResponse)
def rerank_endpoint(body: RerankRequest, request: Request) -> RerankResponse:
    if not body.texts:
        # Mirrors src.retrieval.reranking.rerank's own empty-input guard --
        # CrossEncoder.predict is not guaranteed to handle an empty batch.
        return RerankResponse(scores=[])
    scores = request.app.state.reranker.score(body.query, body.texts)
    return RerankResponse(scores=scores)
