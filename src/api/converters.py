"""Conversions between the API's Pydantic schemas (src/api/schemas.py) and
this project's existing retrieval/generation dataclasses
(`src.retrieval.hybrid.RetrievedChunk`, `src.retrieval.reranking.RerankedChunk`).

No new chunk representation is introduced here — the API reuses the same
`GenerationChunk` union (`src.generation.signals.GenerationChunk`) every
other consumer of `generate_from_chunks`/`generate_evaluation` already uses,
so this module is pure adaptation, not new business logic.
"""

from __future__ import annotations

from qdrant_client import QdrantClient

from src.api.schemas import ChunkInput, ChunkResult, ConfidencePreviewChunk, PageRef
from src.generation.signals import GenerationChunk
from src.indexing.qdrant_index import COLLECTION_NAME, point_id_for
from src.retrieval.hybrid import RetrievedChunk
from src.retrieval.reranking import RerankedChunk


def chunk_input_to_generation_chunk(chunk: ChunkInput) -> GenerationChunk:
    """A client-submitted `ChunkInput` never carries a `section_id` (not
    used anywhere downstream of retrieval — see src/api/schemas.py) or the
    type identity of a real `RerankedChunk`/`RetrievedChunk`, so it is
    rebuilt here rather than passed through as-is.

    When `chunk.score` is present (the caller resent a prior /retrieve
    chunk's fused/reranked score), it's rebuilt as a `RerankedChunk` so
    `retrieval_confidence_tier` (src/generation/signals.py) reads the real
    signal. When absent (a hand-curated chunk with no retrieval score), it's
    built as a plain `RetrievedChunk` — the same "insufficient data" case
    that module already documents and defaults to the "moyenne" tier for.
    """
    page_start = chunk.page_start.model_dump()
    page_end = chunk.page_end.model_dump()
    if chunk.score is None:
        return RetrievedChunk(
            score=0.0,
            work_id=chunk.work_id,
            chunk_id=chunk.chunk_id,
            section_id="",
            section_path=chunk.section_path,
            paragraph_ids=chunk.paragraph_ids,
            page_start=page_start,
            page_end=page_end,
            text=chunk.text,
        )
    return RerankedChunk(
        rerank_score=chunk.score,
        rrf_score=chunk.score,
        work_id=chunk.work_id,
        chunk_id=chunk.chunk_id,
        section_id="",
        section_path=chunk.section_path,
        paragraph_ids=chunk.paragraph_ids,
        page_start=page_start,
        page_end=page_end,
        text=chunk.text,
    )


def confidence_preview_chunk_to_generation_chunk(chunk: ConfidencePreviewChunk) -> GenerationChunk:
    """Same `RerankedChunk`-when-scored / `RetrievedChunk`-when-not rebuild
    rule as `chunk_input_to_generation_chunk`, pared down to what
    `retrieval_confidence_tier` (src/generation/signals.py) actually reads —
    `chunk_id` and the rerank score. Every other field is irrelevant to that
    computation, so it's left empty rather than requiring the caller to
    resend a full chunk's text/work_id/section_path just to get a tier back
    (docs/ROADMAP.md, the retrieval-confidence-split correction)."""
    if chunk.score is None:
        return RetrievedChunk(
            score=0.0,
            work_id="",
            chunk_id=chunk.chunk_id,
            section_id="",
            section_path="",
            paragraph_ids=[],
            page_start={},
            page_end={},
            text="",
        )
    return RerankedChunk(
        rerank_score=chunk.score,
        rrf_score=chunk.score,
        work_id="",
        chunk_id=chunk.chunk_id,
        section_id="",
        section_path="",
        paragraph_ids=[],
        page_start={},
        page_end={},
        text="",
    )


def fetch_chunk_input(
    client: QdrantClient, chunk_id: str, score: float | None
) -> ChunkInput | None:
    """Rebuilds a `ChunkInput` by reading `chunk_id`'s current payload back
    from Qdrant — used by `/evaluate` and `GET /turns/{id}` (`src/api/main.py`)
    to reconstruct full chunk content for a persisted turn, since
    `retrieved_chunks` (`src/api/models.py`) stores only `chunk_id`/`rank`/
    `score`, never chunk text. `score` comes from the caller's own
    persisted `retrieved_chunks` row, not from Qdrant.

    Returns `None` if `chunk_id` is no longer indexed (e.g. a reindex
    since this turn was recorded) — the known, documented limitation
    (`src/api/models.py`'s module docstring) rather than a hard failure:
    the caller drops it from the reconstructed chunk set instead of
    crashing on a stale reference.
    """
    points = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(chunk_id)], with_payload=True
    )
    if not points:
        return None
    payload = points[0].payload or {}
    return ChunkInput(
        chunk_id=payload["chunk_id"],
        work_id=payload["work_id"],
        section_path=payload["section_path"],
        paragraph_ids=payload["paragraph_ids"],
        page_start=payload["page_start"],
        page_end=payload["page_end"],
        text=payload["text"],
        score=score,
    )


def generation_chunk_to_result(chunk: GenerationChunk) -> ChunkResult:
    """The `/retrieve` response's per-chunk score is the reranked
    cross-encoder score when `chunk` was reranked, else the raw RRF-fused
    score — whichever this chunk actually carries."""
    score = chunk.rerank_score if isinstance(chunk, RerankedChunk) else chunk.score
    return ChunkResult(
        chunk_id=chunk.chunk_id,
        work_id=chunk.work_id,
        section_path=chunk.section_path,
        paragraph_ids=chunk.paragraph_ids,
        page_start=PageRef(**chunk.page_start),
        page_end=PageRef(**chunk.page_end),
        text=chunk.text,
        score=score,
    )
