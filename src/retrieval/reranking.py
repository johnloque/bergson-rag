"""Cross-encoder reranking (bge-reranker-v2-m3) over hybrid retrieval's
RRF-fused candidates (docs/ROADMAP.md, Sprint 4 — "Scoring": cross-encoder
reranker as the default, always-on relevance score).

Deferred, not implemented: BGE-M3 multi-vector (ColBERT-style) reranking
was considered as an alternative/comparison point and explicitly not built
this sprint — gated on two unmet conditions, tracked in docs/ROADMAP.md:
(1) a feasibility check of extracting multi-vector (colbert) representations
in this stack, which likely requires the separate FlagEmbedding library
rather than the FastEmbed/sentence-transformers already in use here, and
(2) a larger gold dataset, needed for a reranker-vs-reranker comparison to
be meaningful.

This module is deliberately decoupled from src/retrieval/hybrid.py: `rerank`
takes a query and an already-retrieved list of chunks, so it can be
exercised in isolation (fixing the candidate set, varying only the
reranker) for the eventual reranker comparison noted above.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from sentence_transformers import CrossEncoder

from src.retrieval.hybrid import RetrievedChunk

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# Matches the candidate-pool size used in prior manual debugging sessions
# for this project; exposed as a parameter (not hardcoded downstream) so it
# can be tuned later without code changes.
DEFAULT_RERANK_CANDIDATES = 15

_PYPROJECT = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"


def _pinned_reranker_revision() -> str:
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return config["tool"]["bergson"]["model-versions"]["bge_reranker_v2_m3_revision"]


@dataclass(frozen=True)
class RerankedChunk:
    rerank_score: float
    rrf_score: float
    work_id: str
    chunk_id: str
    section_id: str
    section_path: str
    paragraph_ids: list[str]
    page_start: dict
    page_end: dict
    text: str


class CrossEncoderReranker:
    """Thin wrapper around sentence-transformers' CrossEncoder, mirroring
    DenseEmbedder/SparseEmbedder in src/indexing/embeddings.py. CrossEncoder
    runs in eval mode with no dropout, so `.predict` is deterministic for a
    fixed model revision and input."""

    def __init__(self) -> None:
        self._model = CrossEncoder(RERANKER_MODEL, revision=_pinned_reranker_revision())

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.predict([(query, text) for text in texts])]


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    reranker: CrossEncoderReranker,
) -> list[RerankedChunk]:
    """Reorder `chunks` (typically the top `rerank_candidates` chunks from
    hybrid_search) by cross-encoder relevance to `query`, descending.

    Both the cross-encoder score and each chunk's original RRF-fused score
    are retained on the output — the RRF score is not discarded, since it's
    useful for debugging and for the eventual reranker-vs-reranker
    comparison (docs/ROADMAP.md).

    Callable independently of the hybrid retrieval pipeline: takes any
    already-retrieved list of chunks, not just hybrid_search's own output,
    so the candidate set can be held fixed while comparing rerankers.
    """
    if not chunks:
        return []
    scores = reranker.score(query, [chunk.text for chunk in chunks])
    reranked = [
        RerankedChunk(
            rerank_score=score,
            rrf_score=chunk.score,
            work_id=chunk.work_id,
            chunk_id=chunk.chunk_id,
            section_id=chunk.section_id,
            section_path=chunk.section_path,
            paragraph_ids=chunk.paragraph_ids,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            text=chunk.text,
        )
        for chunk, score in zip(chunks, scores, strict=True)
    ]
    # Deterministic tie-break (chunk_id asc) on top of the cross-encoder
    # score, same discipline as hybrid_search's RRF tie-break
    # (src/retrieval/hybrid.py) — CrossEncoder scores are floats and can
    # coincide, especially on near-duplicate passages.
    return sorted(reranked, key=lambda c: (-c.rerank_score, c.chunk_id))
