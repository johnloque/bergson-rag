"""FastAPI scaffold for Sprint 7a (docs/ROADMAP.md, Sprint 7 — "Backend API").

Four compute endpoints, no persistence: `/retrieve`, `/generate`,
`/evaluate`, `/judge-chunk`. Each thin-wraps an existing, already-tested
function (`hybrid_search` + `rerank`, `generate_from_chunks`,
`generate_evaluation` + `should_auto_expand`, `judge_chunk`) — no retrieval,
generation, evaluation, or judging logic is reimplemented here.

## Known simplification: /evaluate trusts its input

`/evaluate` takes `(query, chunks, answer)` straight from the request body
and runs `generate_evaluation` on exactly that triple — there is no
server-side record of a prior `/generate` call to check the submitted
`answer` and `chunks` against. A client could submit any `answer` alongside
any `chunks` and get back a faithfulness evaluation of that claimed pairing,
whether or not it was ever actually produced by `/generate` from those
chunks. This is a deliberate, documented scope boundary for this branch
(`feat/api-endpoints`), not an oversight: linking a `/generate` call to its
later `/evaluate` call requires persisting the generation (or at least a
signed/opaque reference to it) somewhere the server can check against, which
is exactly what `feat/api-persistence` (docs/ROADMAP.md, Sprint 7) adds.
Nothing here should be patched around this ahead of that branch — the two-
call pattern itself (`/generate` then, separately, `/evaluate`) is
intentional (see the Sprint 6 collapsed-by-default / auto-expand-on-good-
evaluation UI behavior it exists to support), the missing link is only the
verification step.

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
unhandled 500.
"""

from __future__ import annotations

import math

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAIError

from src.api.converters import chunk_input_to_generation_chunk, generation_chunk_to_result
from src.api.dependencies import (
    get_dense_embedder,
    get_qdrant_client,
    get_reranker,
    get_sparse_embedder,
)
from src.api.schemas import (
    ClaimVerdictOut,
    EvaluateRequest,
    EvaluateResponse,
    FaithfulnessOut,
    GenerateRequest,
    GenerateResponse,
    JudgeChunkRequest,
    JudgeChunkResponse,
    RetrieveRequest,
    RetrieveResponse,
    StructuralCheckOut,
)
from src.generation.chunk_judge import judge_chunk
from src.generation.generate import generate_from_chunks
from src.generation.guardrail import generate_evaluation, should_auto_expand
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranking import DEFAULT_RERANK_CANDIDATES, rerank

# Sprint 7's frontend (a separate, later branch, docs/ROADMAP.md) is a Vite
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
def generate(body: GenerateRequest) -> GenerateResponse:
    """Wraps `generate_from_chunks` directly — no evaluation here (that's
    the separate `/evaluate` call, see module docstring)."""
    client = get_qdrant_client()
    chunks = [chunk_input_to_generation_chunk(c) for c in body.chunks]
    result = generate_from_chunks(
        body.query,
        chunks,
        client,
        model=body.model,
        chunk_judgments=body.chunk_judgments,
    )
    return GenerateResponse(answer=result.answer, model_used=result.model)


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(body: EvaluateRequest) -> EvaluateResponse:
    """Wraps `generate_evaluation` + `should_auto_expand` directly. See the
    module docstring for the known simplification: `(chunks, answer)` are
    trusted as submitted, with no server-side check that `answer` actually
    came from a prior `/generate` call on these exact `chunks`."""
    chunks = [chunk_input_to_generation_chunk(c) for c in body.chunks]
    evaluation = generate_evaluation(body.query, chunks, body.answer)

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


@app.post("/judge-chunk", response_model=JudgeChunkResponse)
def judge_chunk_endpoint(body: JudgeChunkRequest) -> JudgeChunkResponse:
    """Wraps `judge_chunk` directly — one relevance judgment for one
    (query, chunk) pair."""
    chunk = chunk_input_to_generation_chunk(body.chunk)
    judgment = judge_chunk(body.query, chunk, model=body.model)
    return JudgeChunkResponse(label=judgment["label"], justification=judgment["justification"])
