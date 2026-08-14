"""Unit tests for src/indexing, run against a live Qdrant instance and
the real processed corpus (data/processed/chunks) — no synthetic
fixtures, same discipline as tests/test_ingestion.py.

Requires: data/processed/chunks (scripts/run_ingestion.py) and Qdrant
reachable at localhost:6333 (docker compose up qdrant).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.indexer import index_chunks, load_chunks, normalize_chunks
from src.indexing.normalize import normalize_text
from src.indexing.qdrant_index import COLLECTION_NAME, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"
QDRANT_URL = "http://localhost:6333"
WORK_ID = "1888_EDIC"
KNOWN_CHUNK_ID = "1888_EDIC_c1"  # literally contains "juxtaposer dans l'espace"
ALL_WORK_IDS = (
    tuple(sorted(p.stem for p in CHUNKS_DIR.glob("*.json"))) if CHUNKS_DIR.exists() else ()
)


def _qdrant_available() -> bool:
    try:
        QdrantClient(url=QDRANT_URL).get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.glob("*.json")),
    reason="processed chunks not found — run scripts/run_ingestion.py first",
)


def _work_filter(work_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="work_id", match=models.MatchValue(value=work_id))]
    )


@pytest.fixture(scope="module")
def client():
    if not _qdrant_available():
        pytest.skip("Qdrant not reachable at localhost:6333 — run `docker compose up qdrant`")
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def dense_embedder():
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder():
    return SparseEmbedder()


@pytest.fixture(scope="module")
def indexed_work(client, dense_embedder, sparse_embedder):
    """Index WORK_ID once and reuse across this module's tests."""
    chunks = load_chunks(WORK_ID, CHUNKS_DIR)
    normalized = normalize_chunks(chunks)
    index_chunks(client, chunks, normalized, dense_embedder, sparse_embedder)
    return chunks


@pytest.mark.parametrize("work_id", ALL_WORK_IDS)
def test_point_count_matches_chunk_count_per_work(client, dense_embedder, sparse_embedder, work_id):
    """Catches silent drops during indexing (docs/ROADMAP.md Sprint 2),
    checked per work rather than on a corpus-wide total so a drop in one
    work can't be masked by a gain in another."""
    chunks = load_chunks(work_id, CHUNKS_DIR)
    normalized = normalize_chunks(chunks)
    index_chunks(client, chunks, normalized, dense_embedder, sparse_embedder)
    count = client.count(collection_name=COLLECTION_NAME, count_filter=_work_filter(work_id)).count
    assert count == len(chunks)


def test_reindexing_is_idempotent(client, dense_embedder, sparse_embedder, indexed_work):
    """Rerunning indexing on an unchanged corpus must not duplicate
    points — upsert by deterministic point ID, not auto-increment."""
    normalized = normalize_chunks(indexed_work)
    index_chunks(client, indexed_work, normalized, dense_embedder, sparse_embedder)
    count = client.count(collection_name=COLLECTION_NAME, count_filter=_work_filter(WORK_ID)).count
    assert count == len(indexed_work)


def test_dense_retrieval_finds_known_chunk(client, dense_embedder, indexed_work):
    """'juxtaposer dans l'espace' is a literal phrase in 1888_EDIC_c1
    (the "juxtaposer dans l'espace" passage referenced in the sprint
    scope)."""
    query_vector = dense_embedder.embed(["juxtaposer dans l'espace"])[0]
    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        using=DENSE_VECTOR_NAME,
        query=query_vector,
        query_filter=_work_filter(WORK_ID),
        limit=5,
    ).points
    assert any(hit.payload["chunk_id"] == KNOWN_CHUNK_ID for hit in hits)


def test_sparse_retrieval_finds_known_chunk_via_stem(client, sparse_embedder, indexed_work):
    """A different surface form of the same stem family ('juxtaposée'
    vs. the indexed chunk's 'juxtaposer') must still retrieve
    1888_EDIC_c1 via BM25-on-stems."""
    query_bm25_text = normalize_text("juxtaposée").bm25_text
    assert query_bm25_text == normalize_text("juxtaposer").bm25_text

    indices, values = sparse_embedder.embed([query_bm25_text])[0]
    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        using=SPARSE_VECTOR_NAME,
        query=models.SparseVector(indices=indices, values=values),
        query_filter=_work_filter(WORK_ID),
        limit=5,
    ).points
    assert any(hit.payload["chunk_id"] == KNOWN_CHUNK_ID for hit in hits)
