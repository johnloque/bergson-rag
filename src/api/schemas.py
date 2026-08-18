"""Pydantic request/response models for the Sprint 7a API (docs/ROADMAP.md).

No persistence, no session linkage: `ChunkInput` is how a caller resends
chunk content across the /retrieve -> /generate -> /evaluate boundary — each
call is self-contained, nothing is looked up server-side by ID. See
src/api/main.py's module docstring for the full known-simplification note.

`ChunkInput` mirrors `ChunkResult` (both shaped after
`src.ingestion.models.Chunk`) plus an optional `score` — the fused/reranked
score a prior /retrieve call attached to that chunk. When present, it's
threaded back into a `RerankedChunk` (src/api/converters.py) so
`retrieval_confidence_tier` (src/generation/signals.py) reflects the real
retrieval signal instead of falling back to its "insufficient data" default.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.generate import DEFAULT_MODEL
from src.generation.signals import RetrievalConfidenceTier

# Mirrors src.retrieval.hybrid.hybrid_search's own `limit: int = 10` default
# (also the default already used by scripts/query_retrieval.py and
# scripts/query_hybrid_retrieval.py) — not a new default introduced here.
DEFAULT_TOP_K = 10


class PageRef(BaseModel):
    number: int | None = None
    display: str = ""


class ChunkInput(BaseModel):
    """What a caller sends back into /generate, /evaluate, or /judge-chunk —
    typically the (possibly user-curated) `ChunkResult` output of a prior
    /retrieve call, resent verbatim. Only `chunk_id` and `text` are required;
    the rest default to empty so a hand-built minimal chunk still works, but
    `work_id`/`section_path`/`page_start`/`page_end` are what
    `generate_from_chunks`' prompt (src/generation/prompt.py) actually
    renders per chunk, so a real /retrieve chunk should be passed through in
    full."""

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    work_id: str = ""
    section_path: str = ""
    paragraph_ids: list[str] = Field(default_factory=list)
    page_start: PageRef = Field(default_factory=PageRef)
    page_end: PageRef = Field(default_factory=PageRef)
    score: float | None = None


class ChunkResult(BaseModel):
    """Mirrors `src.ingestion.models.Chunk`'s payload shape plus the
    fused (RRF) or reranked cross-encoder score, whichever this chunk
    carries coming out of /retrieve."""

    chunk_id: str
    work_id: str
    section_path: str
    paragraph_ids: list[str]
    page_start: PageRef
    page_end: PageRef
    text: str
    score: float


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=DEFAULT_TOP_K, gt=0)


class RetrieveResponse(BaseModel):
    chunks: list[ChunkResult]


class GenerateRequest(BaseModel):
    query: str = Field(min_length=1)
    chunks: list[ChunkInput] = Field(min_length=1)
    model: str = DEFAULT_MODEL
    chunk_judgments: dict[str, ChunkJudgment] | None = None


class GenerateResponse(BaseModel):
    answer: str
    model_used: str


class EvaluateRequest(BaseModel):
    query: str = Field(min_length=1)
    chunks: list[ChunkInput] = Field(min_length=1)
    answer: str = Field(min_length=1)


class ClaimVerdictOut(BaseModel):
    statement: str
    supported: bool
    reason: str


class StructuralCheckOut(BaseModel):
    citations: list[str]
    unknown_citations: list[str]
    has_citation: bool
    passed: bool


class FaithfulnessOut(BaseModel):
    # None when the answer yielded no claims (RAGAS's own NaN case,
    # src/generation/faithfulness.py) — NaN is not valid JSON, so it is
    # normalized to null before this model is built (src/api/main.py).
    score: float | None
    model: str
    claims: list[ClaimVerdictOut]


class EvaluateResponse(BaseModel):
    structural: StructuralCheckOut
    faithfulness: FaithfulnessOut
    retrieval_confidence_tier: RetrievalConfidenceTier
    should_auto_expand: bool


class JudgeChunkRequest(BaseModel):
    query: str = Field(min_length=1)
    chunk: ChunkInput
    model: str = DEFAULT_JUDGE_MODEL


class JudgeChunkResponse(BaseModel):
    label: str
    justification: str
