"""Unit tests for src/retrieval/hybrid.py, run against a live Qdrant
instance with the collection already built (scripts/build_index.py) —
no synthetic fixtures, same discipline as tests/test_indexing.py.
Retrieval is read-only here; this suite does not (re)index the corpus.

Requires: Qdrant reachable at localhost:6333 with the `bergson_chunks`
collection populated.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient, models

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from src.retrieval.hybrid import hybrid_search

QDRANT_URL = "http://localhost:6333"

# "juxtaposer dans l'espace" is a literal phrase in 1888_EDIC_c1 (also
# used in tests/test_indexing.py): dense-only ranks it #1, sparse-only
# ranks it #4 on this corpus — a real overlap case for the fusion
# sanity check below, not a synthetic one.
QUERY = "juxtaposer dans l'espace"
KNOWN_CHUNK_ID = "1888_EDIC_c1"


def _collection_populated() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(COLLECTION_NAME):
            return False
        return client.count(collection_name=COLLECTION_NAME).count > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)


@pytest.fixture(scope="module")
def client():
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def dense_embedder():
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder():
    return SparseEmbedder()


def _single_channel_rank(client, using: str, query, chunk_id: str, limit: int = 50) -> int | None:
    hits = client.query_points(
        collection_name=COLLECTION_NAME, using=using, query=query, limit=limit, with_payload=True
    ).points
    for rank, hit in enumerate(hits, start=1):
        if hit.payload["chunk_id"] == chunk_id:
            return rank
    return None


def test_fusion_ranks_shared_chunk_at_least_as_high(client, dense_embedder, sparse_embedder):
    """A chunk present in both the dense and sparse top-k must not rank
    worse after RRF fusion than its best single-channel rank — the
    fusion mechanism itself, not retrieval quality, is under test."""
    from src.indexing.normalize import normalize_text

    dense_vector = dense_embedder.embed([QUERY])[0]
    bm25_text = normalize_text(QUERY).bm25_text
    sparse_indices, sparse_values = sparse_embedder.embed_query([bm25_text])[0]

    dense_rank = _single_channel_rank(client, DENSE_VECTOR_NAME, dense_vector, KNOWN_CHUNK_ID)
    sparse_rank = _single_channel_rank(
        client,
        SPARSE_VECTOR_NAME,
        models.SparseVector(indices=sparse_indices, values=sparse_values),
        KNOWN_CHUNK_ID,
    )
    assert (
        dense_rank is not None and sparse_rank is not None
    ), "fixture query/chunk must appear in both channels for this sanity check to be meaningful"

    fused = hybrid_search(client, QUERY, dense_embedder, sparse_embedder, limit=50)
    fused_rank = next(
        (rank for rank, chunk in enumerate(fused, start=1) if chunk.chunk_id == KNOWN_CHUNK_ID),
        None,
    )
    assert fused_rank is not None
    assert fused_rank <= min(dense_rank, sparse_rank)


def test_hybrid_search_is_deterministic(client, dense_embedder, sparse_embedder):
    """Same query against an unchanged index must return the same
    ranked chunk_ids and scores — no randomness anywhere in this path."""
    first = hybrid_search(client, QUERY, dense_embedder, sparse_embedder, limit=10)
    second = hybrid_search(client, QUERY, dense_embedder, sparse_embedder, limit=10)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.score for c in first] == [c.score for c in second]
