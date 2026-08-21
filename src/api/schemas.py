"""Pydantic request/response models for the Sprint 7 API (docs/ROADMAP.md).

`ChunkInput` is still how a caller resends chunk content into /generate,
/evaluate, and /judge-chunk (each call still carries its own chunk data in
the request body — /evaluate's chunks now come from the DB instead, see
below). See src/api/main.py's module docstring for the persistence model
this sprint (feat/api-persistence) adds on top of Sprint 7a's four
endpoints.

`ChunkInput` mirrors `ChunkResult` (both shaped after
`src.ingestion.models.Chunk`) plus an optional `score` — the fused/reranked
score a prior /retrieve call attached to that chunk. When present, it's
threaded back into a `RerankedChunk` (src/api/converters.py) so
`retrieval_confidence_tier` (src/generation/signals.py) reflects the real
retrieval signal instead of falling back to its "insufficient data" default.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.generate import DEFAULT_MODEL
from src.generation.signals import RetrievalConfidenceTier

# Was 10, mirroring src.retrieval.hybrid.hybrid_search's own `limit: int =
# 10` default (also the default used by scripts/query_retrieval.py and
# scripts/query_hybrid_retrieval.py). Lowered to 3: `/generate` and
# `/evaluate` both operate on however many chunks `/retrieve` handed back
# (neither has its own independent cap), so the old default of 10 chunks
# flowed straight into the faithfulness judge's prompt — reliably
# overflowing its context window (`JUDGE_NUM_CTX`,
# src/generation/faithfulness.py) and making `/evaluate` fail with an
# unhandled 500 on every turn that kept most of its retrieved chunks.
# Retrieval candidate breadth for reranking is unaffected — this only trims
# the final `[:top_k]` slice returned to the client (src/api/main.py's
# `retrieve`), not the `DEFAULT_RERANK_CANDIDATES` pool reranked over.
DEFAULT_TOP_K = 3


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
    # `None` (omitted, or explicit `null`) AND `turn_id` present -> the
    # server auto-loads that turn's persisted chunk_judgments as the
    # default (a plain "regenerate" click works without resending every
    # judgment already made). Any explicit dict, including `{}`, is used
    # as-is and overrides the persisted default (docs/ROADMAP.md).
    chunk_judgments: dict[str, ChunkJudgment] | None = None
    conversation_id: int | None = None
    turn_id: int | None = None


class GenerateResponse(BaseModel):
    answer: str
    model_used: str
    generation_id: int
    turn_id: int
    conversation_id: int


class EvaluateRequest(BaseModel):
    generation_id: int


class ClaimVerdictOut(BaseModel):
    statement: str
    supported: bool
    reason: str
    # Verbatim span of the answer this claim was grounded to (for UI
    # highlighting, src/generation/faithfulness.py:_ground_quote_in_answer);
    # None when the judge's quote couldn't be validated against the answer.
    quote: str | None = None


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
    turn_id: int
    model: str = DEFAULT_JUDGE_MODEL


class JudgeChunkResponse(BaseModel):
    label: str
    justification: str


# --- GET /turns/{id}, GET /conversations/{id} -------------------------------
#
# Assembled from persisted state (src/api/persistence.py) — turn/generation/
# evaluation/chunk_judgment rows never depend on Qdrant or an LLM, so a
# reloaded page can recover a turn's final badge state (should_auto_expand,
# faithfulness annotations) even if the live session that produced it, or
# the retrieval/generation stack itself, is gone (docs/ROADMAP.md, Sprint 6's
# flagged risk this resolves). Chunk *content* is the one exception: like
# `/evaluate`, `GET /turns/{id}` re-fetches it live from Qdrant by chunk_id
# (`src/api/converters.py:fetch_chunk_input`) since `retrieved_chunks`
# (src/api/models.py) stores only chunk_id/rank/score, never text — see that
# module's docstring for the accepted snapshot limitation this leaves (a
# reindexed/deleted chunk_id comes back empty rather than raising).


class RetrievedChunkOut(BaseModel):
    chunk_id: str
    rank: int
    score: float
    text: str
    work_id: str
    section_path: str
    paragraph_ids: list[str]
    page_start: PageRef
    page_end: PageRef


class GenerationOut(BaseModel):
    generation_id: int
    model: str
    chunk_ids: list[str]
    answer: str
    chunk_judgments_used: dict[str, ChunkJudgment] | None
    created_at: datetime
    evaluation: EvaluateResponse | None


class TurnDetailResponse(BaseModel):
    turn_id: int
    conversation_id: int
    query: str
    created_at: datetime
    retrieved_chunks: list[RetrievedChunkOut]
    generations: list[GenerationOut]
    chunk_judgments: dict[str, ChunkJudgment]


class ConversationTurnOut(BaseModel):
    turn_id: int
    query: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation_id: int
    turns: list[ConversationTurnOut]


# --- Sprint 8 (frontend) additions: list / rename / delete conversations ---
# Needed by the sidebar (docs/ROADMAP.md, Screen 2) and the landing page's
# "last conversation" lookup — Sprint 7 only shipped lookup-by-id.


class ConversationSummaryOut(BaseModel):
    conversation_id: int
    created_at: datetime
    title: str | None
    first_query: str | None


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryOut]


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1)
