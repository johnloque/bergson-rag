"""Hybrid retrieval over the Sprint 2 Qdrant collection: dense (BGE-M3)
+ sparse (BM25-on-stems) prefetch, fused with Qdrant's native
Reciprocal Rank Fusion.

The query is used as-is, raw — no reformulation, no rewriting, no
decomposition. This is a deliberate Sprint 3 scope decision, not a
placeholder: query reformulation was dropped from this project's scope
entirely and remains a documented `exp/` candidate only, deferred
pending a larger gold dataset (docs/ROADMAP.md). Two related ideas are
likewise considered and intentionally not built this sprint, for the
same reason:
- BM25-on-stems vs. BM25-on-lemmas comparison (src/indexing/normalize.py
  already isolates this behind `Normalization.bm25_text` for later).
- Keyword-extraction / discourse-framing-noise filtering for dense
  queries — a possible future `exp/` once query_style-stratified recall
  data exists (eval/scripts/metrics.py breakdown), not hand-built now.

Fusion note: Qdrant's plain `FusionQuery(fusion=Fusion.RRF)` shortcut
silently uses an internal default constant (k=2) meant for local/testing
parity, not the literature value. The parameterized `RrfQuery(rrf=Rrf(k=...))`
form is what actually lets the server compute `1 / (k + rank)` with the
requested k — verified empirically against a live collection before
picking this form.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.normalize import normalize_text
from src.indexing.qdrant_index import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    PAYLOAD_FIELDS,
    SPARSE_VECTOR_NAME,
)

RRF_K = 60  # Cormack et al. 2009 standard value — no project-specific tuning.
DEFAULT_PREFETCH_LIMIT = 50


@dataclass(frozen=True)
class RetrievedChunk:
    score: float
    work_id: str
    chunk_id: str
    section_id: str
    section_path: str
    paragraph_ids: list[str]
    page_start: dict
    page_end: dict
    text: str


def _point_to_chunk(point: models.ScoredPoint) -> RetrievedChunk:
    payload = point.payload or {}
    return RetrievedChunk(score=point.score, **{field: payload[field] for field in PAYLOAD_FIELDS})


def hybrid_search(
    client: QdrantClient,
    query: str,
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    limit: int = 10,
    prefetch_limit: int = DEFAULT_PREFETCH_LIMIT,
    collection_name: str = COLLECTION_NAME,
) -> list[RetrievedChunk]:
    """Dense + sparse prefetch on `query`, fused via Qdrant-native RRF
    (k=60). Deterministic given a fixed query and an unchanged index —
    both embedders and the fusion itself are non-random.
    """
    dense_vector = dense_embedder.embed([query])[0]
    bm25_text = normalize_text(query).bm25_text
    sparse_indices, sparse_values = sparse_embedder.embed_query([bm25_text])[0]

    response = client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(query=dense_vector, using=DENSE_VECTOR_NAME, limit=prefetch_limit),
            models.Prefetch(
                query=models.SparseVector(indices=sparse_indices, values=sparse_values),
                using=SPARSE_VECTOR_NAME,
                limit=prefetch_limit,
            ),
        ],
        query=models.RrfQuery(rrf=models.Rrf(k=RRF_K)),
        limit=limit,
        with_payload=True,
    )
    return [_point_to_chunk(point) for point in response.points]
