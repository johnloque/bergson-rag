"""FastAPI scaffold for Sprint 7 (docs/ROADMAP.md, Sprint 7 — "Backend API
and persistence"). Six endpoints: `/retrieve`, `/generate`, `/evaluate`,
`/judge-chunk`, `GET /turns/{id}`, `GET /conversations/{id}`. Each compute
endpoint still thin-wraps an existing, already-tested function
(`hybrid_search` + `rerank`, `generate_from_chunks`, `generate_evaluation` +
`should_auto_expand`, `judge_chunk`) — no retrieval, generation, evaluation,
or judging logic is reimplemented here. Persistence (SQLite via SQLModel,
`src/api/models.py`, `src/api/db.py`) is layered on top through
`src/api/persistence.py`'s helper functions, keeping this module's job
orchestration rather than raw session/query code.

## What this branch (feat/api-persistence) resolves

Sprint 7a shipped these endpoints with no persistence: every request was
self-contained, and two risks were explicitly flagged as deferred rather
than solved (docs/ROADMAP.md):

1. `/evaluate` trusted a client-submitted `(query, chunks, answer)` triple
   with no server-side proof it came from a real `/generate` call. Resolved
   here: `/evaluate` now takes `{generation_id}` and looks the generation up
   in the DB — `query`, `chunk_ids`, and `answer` all come from the stored
   record, not the client. The chunks' *text* is still re-fetched live from
   Qdrant by `chunk_id` (`src/api/converters.py:fetch_chunk_input`) rather
   than snapshotted — see `src/api/models.py`'s module docstring for that
   accepted limitation.
2. A user who left before `generate_evaluation` completed, or before a
   session persisted, never saw the final badge state (`should_auto_expand`,
   faithfulness annotations) — Sprint 6's flagged risk. Resolved here:
   `GET /turns/{turn_id}` reassembles a turn's full state (query, retrieved
   chunks, generation(s), evaluation(s), chunk judgments) purely from
   persisted rows — no Qdrant/LLM dependency — so a reloaded page recovers
   it even if the live session, or the retrieval/generation stack itself,
   is gone.

## `/generate`'s chunk_judgments auto-load rule

`chunk_judgments` omitted (or explicit `null`) AND `turn_id` given -> the
server auto-loads that turn's persisted judgments as the default, so a
plain "regenerate" click works without the client resending every judgment
it already made. Any explicit dict, including `{}`, is used as-is and
overrides the persisted default — this is what lets a client deliberately
regenerate with *no* judgments applied, distinct from "I have none to send
you, load what you have" (`src/api/schemas.py`'s `GenerateRequest` docstring).

## Error handling

`generate_from_chunks`, `generate_evaluation` (via `check_faithfulness`),
and `judge_chunk` all ultimately call out to an LLM through LiteLLM (or, for
the judge call inside `generate_evaluation`, through `langchain-litellm`,
which re-raises the same underlying LiteLLM/OpenAI-shaped exception after
its own retry budget is exhausted — reraise=True, confirmed in
`langchain_core.language_models.llms.create_base_retry_decorator`). Every
LiteLLM-raised error (timeout, connection refused, rate limit, auth
failure, ...) is a subclass of `openai.OpenAIError` and carries
`llm_provider`/`model` — a local Ollama server not running is the concrete,
expected case during development (docs/ROADMAP.md's own experience getting
Ollama running). `llm_provider_error_handler` below turns any such error
into a 503 naming the provider and model that failed, instead of an
unhandled 500. Unknown `turn_id`/`generation_id`/`conversation_id` surface
as 404s directly from `src/api/persistence.py` (FastAPI's own
`HTTPException` handling, no custom handler needed for that case).
"""

from __future__ import annotations

import math

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAIError
from sqlmodel import Session

from src.api import persistence
from src.api.converters import (
    chunk_input_to_generation_chunk,
    fetch_chunk_input,
    generation_chunk_to_result,
)
from src.api.db import get_session
from src.api.dependencies import (
    get_dense_embedder,
    get_qdrant_client,
    get_reranker,
    get_sparse_embedder,
)
from src.api.models import Evaluation
from src.api.schemas import (
    ClaimVerdictOut,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummaryOut,
    ConversationTurnOut,
    EvaluateRequest,
    EvaluateResponse,
    FaithfulnessOut,
    GenerateRequest,
    GenerateResponse,
    GenerationOut,
    JudgeChunkRequest,
    JudgeChunkResponse,
    PageRef,
    RenameConversationRequest,
    RetrievedChunkOut,
    RetrieveRequest,
    RetrieveResponse,
    StructuralCheckOut,
    TurnDetailResponse,
)
from src.generation.chunk_judge import judge_chunk
from src.generation.generate import generate_from_chunks
from src.generation.guardrail import EvaluationResult, generate_evaluation, should_auto_expand
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranking import DEFAULT_RERANK_CANDIDATES, rerank

# Sprint 8's frontend (a separate, later branch, docs/ROADMAP.md) is a Vite
# dev server on this default port. A single hardcoded local-dev origin is
# sufficient at this project's current stage — not a configurable allowlist.
FRONTEND_DEV_ORIGIN = "http://localhost:5173"

app = FastAPI(title="bergson-rag API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_DEV_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OpenAIError)
async def llm_provider_error_handler(request: Request, exc: OpenAIError) -> JSONResponse:
    provider = getattr(exc, "llm_provider", None) or "unknown"
    model = getattr(exc, "model", None) or "unknown"
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                f"LLM call failed (provider={provider}, model={model}): {exc}. "
                "If this is a local model, confirm Ollama is running and the model is pulled."
            )
        },
    )


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(body: RetrieveRequest) -> RetrieveResponse:
    """Hybrid retrieval + reranking, as-is (src/retrieval/hybrid.py,
    src/retrieval/reranking.py) — no new retrieval logic."""
    client = get_qdrant_client()
    candidate_limit = max(body.top_k, DEFAULT_RERANK_CANDIDATES)
    candidates = hybrid_search(
        client,
        body.query,
        dense_embedder=get_dense_embedder(),
        sparse_embedder=get_sparse_embedder(),
        limit=candidate_limit,
    )
    reranked = rerank(body.query, candidates, get_reranker())[: body.top_k]
    return RetrieveResponse(chunks=[generation_chunk_to_result(c) for c in reranked])


@app.post("/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest, session: Session = Depends(get_session)) -> GenerateResponse:
    """Wraps `generate_from_chunks` directly — no evaluation here (that's
    the separate `/evaluate` call, see module docstring) — plus turn/
    generation persistence (src/api/persistence.py). `turn_id` absent
    creates a new turn (and conversation, if `conversation_id` is also
    absent); `turn_id` present is a regeneration within that existing turn
    (404 if unknown)."""
    client = get_qdrant_client()
    turn = persistence.resolve_turn(session, body.conversation_id, body.turn_id, body.query)

    if body.chunk_judgments is not None:
        chunk_judgments = body.chunk_judgments
    elif body.turn_id is not None:
        chunk_judgments = persistence.load_chunk_judgments(session, turn.id) or None
    else:
        chunk_judgments = None

    chunks = [chunk_input_to_generation_chunk(c) for c in body.chunks]
    result = generate_from_chunks(
        body.query,
        chunks,
        client,
        model=body.model,
        chunk_judgments=chunk_judgments,
    )

    if body.turn_id is None:
        # Only the turn's initial /generate call establishes its retrieved-
        # chunk set — a regeneration's body.chunks is the client's included
        # subset (excluded chunks filtered out for the LLM call, useTurnController.ts's
        # regenerate()), and persisting that here would overwrite the turn's
        # full candidate set with just what survived exclusion, permanently
        # losing the excluded chunks from GET /turns/{id} on the next reload
        # (they'd vanish from the rail with no way back, contradicting the
        # rail's "excluded stays visible to re-include" contract).
        persistence.save_retrieved_chunks(session, turn.id, body.chunks)
    generation = persistence.save_generation(
        session,
        turn_id=turn.id,
        model=result.model,
        chunk_ids=[c.chunk_id for c in body.chunks],
        answer=result.answer,
        chunk_judgments_used=chunk_judgments,
    )
    return GenerateResponse(
        answer=result.answer,
        model_used=result.model,
        generation_id=generation.id,
        turn_id=turn.id,
        conversation_id=turn.conversation_id,
    )


def _evaluation_result_to_response(evaluation: EvaluationResult) -> EvaluateResponse:
    score = evaluation.faithfulness.score
    return EvaluateResponse(
        structural=StructuralCheckOut(
            citations=list(evaluation.structural.citations),
            unknown_citations=list(evaluation.structural.unknown_citations),
            has_citation=evaluation.structural.has_citation,
            passed=evaluation.structural.passed,
        ),
        faithfulness=FaithfulnessOut(
            score=None if math.isnan(score) else score,
            model=evaluation.faithfulness.model,
            claims=[
                ClaimVerdictOut(statement=c.statement, supported=c.supported, reason=c.reason)
                for c in evaluation.faithfulness.claims
            ],
        ),
        retrieval_confidence_tier=evaluation.retrieval_confidence,
        should_auto_expand=should_auto_expand(evaluation),
    )


def _evaluation_row_to_response(evaluation: Evaluation) -> EvaluateResponse:
    return EvaluateResponse(
        structural=StructuralCheckOut(**evaluation.structural_flags),
        faithfulness=FaithfulnessOut(**evaluation.faithfulness_annotations),
        retrieval_confidence_tier=evaluation.retrieval_confidence_tier,
        should_auto_expand=evaluation.should_auto_expand,
    )


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(body: EvaluateRequest, session: Session = Depends(get_session)) -> EvaluateResponse:
    """Wraps `generate_evaluation` + `should_auto_expand`. `query`, `chunks`,
    and `answer` all come from the stored `generations` record looked up by
    `generation_id` (404 if unknown) — closing the Sprint 7a trust gap (see
    module docstring): a client can no longer submit an arbitrary
    `(chunks, answer)` pairing that was never actually produced by
    `/generate`. Chunk text itself is re-fetched live from Qdrant by
    `chunk_id` (src/api/converters.py) — not snapshotted, see
    src/api/models.py's module docstring.

    Idempotent per `generation_id`: if a prior call already persisted an
    `Evaluation` row for it, that row is returned as-is instead of rerunning
    the RAGAS/LLM faithfulness check (~8-9s, src/generation/faithfulness.py).
    Without this, a page refresh or a second tab racing the first `/evaluate`
    call before it commits would each trigger their own full recheck."""
    generation = persistence.get_generation_or_404(session, body.generation_id)

    existing = persistence.get_evaluation_for_generation(session, generation.id)
    if existing is not None:
        return _evaluation_row_to_response(existing)

    turn = persistence.get_turn_or_404(session, generation.turn_id)
    scores = persistence.get_retrieved_chunk_scores(session, generation.turn_id)

    client = get_qdrant_client()
    chunk_inputs = [
        chunk_input
        for chunk_id in generation.chunk_ids
        if (chunk_input := fetch_chunk_input(client, chunk_id, scores.get(chunk_id))) is not None
    ]
    chunks = [chunk_input_to_generation_chunk(c) for c in chunk_inputs]

    evaluation = generate_evaluation(turn.query, chunks, generation.answer)
    response = _evaluation_result_to_response(evaluation)

    persistence.save_evaluation(
        session,
        generation_id=generation.id,
        structural_flags=response.structural.model_dump(),
        faithfulness_annotations=response.faithfulness.model_dump(),
        retrieval_confidence_tier=response.retrieval_confidence_tier,
        should_auto_expand=response.should_auto_expand,
    )
    return response


@app.post("/judge-chunk", response_model=JudgeChunkResponse)
def judge_chunk_endpoint(
    body: JudgeChunkRequest, session: Session = Depends(get_session)
) -> JudgeChunkResponse:
    """Wraps `judge_chunk` directly — one relevance judgment for one
    (query, chunk) pair — then persists it, upserted on (turn_id, chunk_id)
    (404 if `turn_id` is unknown)."""
    persistence.get_turn_or_404(session, body.turn_id)
    chunk = chunk_input_to_generation_chunk(body.chunk)
    judgment = judge_chunk(body.query, chunk, model=body.model)
    persistence.upsert_chunk_judgment(
        session,
        turn_id=body.turn_id,
        chunk_id=body.chunk.chunk_id,
        label=judgment["label"],
        justification=judgment["justification"],
        model=body.model,
    )
    return JudgeChunkResponse(label=judgment["label"], justification=judgment["justification"])


@app.get("/turns/{turn_id}", response_model=TurnDetailResponse)
def get_turn(turn_id: int, session: Session = Depends(get_session)) -> TurnDetailResponse:
    """Full turn state assembled from persisted rows — no Qdrant/LLM
    dependency for the turn/generation/evaluation/chunk_judgment state
    itself — so a reloaded page recovers a turn's final badge state even if
    the live session that produced it is gone (module docstring, the Sprint
    6 risk this resolves). Chunk *content* is the exception: like
    `/evaluate`, it's re-fetched live from Qdrant by chunk_id
    (`fetch_chunk_input`) since `retrieved_chunks` never stores text
    (src/api/schemas.py's `RetrievedChunkOut` docstring). 404 if `turn_id`
    is unknown."""
    turn = persistence.get_turn_or_404(session, turn_id)
    retrieved_chunks = persistence.get_retrieved_chunks(session, turn_id)
    generations = persistence.get_turn_generations(session, turn_id)
    chunk_judgments = persistence.load_chunk_judgments(session, turn_id)

    client = get_qdrant_client()
    retrieved_chunk_outs = []
    for row in retrieved_chunks:
        chunk_input = fetch_chunk_input(client, row.chunk_id, row.score)
        retrieved_chunk_outs.append(
            RetrievedChunkOut(
                chunk_id=row.chunk_id,
                rank=row.rank,
                score=row.score,
                text=chunk_input.text if chunk_input is not None else "",
                work_id=chunk_input.work_id if chunk_input is not None else "",
                section_path=chunk_input.section_path if chunk_input is not None else "",
                paragraph_ids=chunk_input.paragraph_ids if chunk_input is not None else [],
                page_start=chunk_input.page_start if chunk_input is not None else PageRef(),
                page_end=chunk_input.page_end if chunk_input is not None else PageRef(),
            )
        )

    generation_outs = []
    for generation in generations:
        evaluation = persistence.get_evaluation_for_generation(session, generation.id)
        evaluation_out = None if evaluation is None else _evaluation_row_to_response(evaluation)
        generation_outs.append(
            GenerationOut(
                generation_id=generation.id,
                model=generation.model,
                chunk_ids=generation.chunk_ids,
                answer=generation.answer,
                chunk_judgments_used=generation.chunk_judgments_used,
                created_at=generation.created_at,
                evaluation=evaluation_out,
            )
        )

    return TurnDetailResponse(
        turn_id=turn.id,
        conversation_id=turn.conversation_id,
        query=turn.query,
        created_at=turn.created_at,
        retrieved_chunks=retrieved_chunk_outs,
        generations=generation_outs,
        chunk_judgments=chunk_judgments,
    )


@app.get("/conversations", response_model=ConversationListResponse)
def list_conversations(session: Session = Depends(get_session)) -> ConversationListResponse:
    """Sprint 8 (frontend) addition: newest-first conversation summaries for
    the sidebar and the landing page's "last conversation" lookup (module
    docstring's "Sprint 8 additions" note) — Sprint 7 only shipped
    lookup-by-id."""
    conversations = persistence.list_conversations(session)
    return ConversationListResponse(
        conversations=[
            ConversationSummaryOut(
                conversation_id=c.id,
                created_at=c.created_at,
                title=c.title,
                first_query=persistence.get_first_turn_query(session, c.id),
            )
            for c in conversations
        ]
    )


@app.patch("/conversations/{conversation_id}", response_model=ConversationSummaryOut)
def rename_conversation(
    conversation_id: int, body: RenameConversationRequest, session: Session = Depends(get_session)
) -> ConversationSummaryOut:
    """Sprint 8 (frontend) addition: the sidebar's rename action. 404 if
    `conversation_id` is unknown."""
    conversation = persistence.rename_conversation(session, conversation_id, body.title)
    return ConversationSummaryOut(
        conversation_id=conversation.id,
        created_at=conversation.created_at,
        title=conversation.title,
        first_query=persistence.get_first_turn_query(session, conversation.id),
    )


@app.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, session: Session = Depends(get_session)) -> None:
    """Sprint 8 (frontend) addition: the sidebar's delete action, cascading
    through every child row (module docstring). 404 if `conversation_id` is
    unknown."""
    persistence.delete_conversation(session, conversation_id)


@app.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> ConversationDetailResponse:
    """The turns in a conversation (id, query, created_at) — enough for a
    history sidebar (Sprint 8); use `GET /turns/{id}` for full per-turn
    detail. 404 if `conversation_id` is unknown."""
    persistence.get_conversation_or_404(session, conversation_id)
    turns = persistence.get_conversation_turns(session, conversation_id)
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        turns=[
            ConversationTurnOut(turn_id=turn.id, query=turn.query, created_at=turn.created_at)
            for turn in turns
        ],
    )
