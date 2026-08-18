"""`generate_from_chunks` — synthesis from a caller-provided chunk
selection (docs/ROADMAP.md, Sprint 5). Does not call retrieval itself:
chunks are always passed in explicitly, so this works standalone with a
hand-constructed chunk list as well as with real retrieve+rerank output —
required for the isolated prompt-branch tests in tests/test_generation.py.

Multi-provider model access goes through LiteLLM rather than hand-rolled
provider-switching (`model` is a LiteLLM model string, e.g.
`"ollama_chat/mistral"` or `"anthropic/claude-haiku-4-5"`). `model` is a
parameter on this call, not a global setting, so the same query/chunks can
be regenerated with a different model without touching any other code
path.

The default API fallback provider is Mistral's hosted API
(`mistral/mistral-small-latest`, LiteLLM reads `MISTRAL_API_KEY` from the
environment) — chosen over a paid provider (Anthropic, OpenAI) to keep
this project's default configuration cost-free on Mistral's free tier.
`BERGSON_LLM_FALLBACK_MODEL` overrides it with any other LiteLLM model
string; that provider's own API key is then optional/user-supplied, not
activated by default.

`chunk_judgments` (docs/ROADMAP.md, Sprint 6) carries prior relevance
judgments — keyed by chunk_id, shape `src.generation.chunk_judgment.ChunkJudgment`
— for chunks still present in `chunks`. Populated on a user-triggered manual
regeneration after a (future, separate-branch) `judge_chunks` call; `None`
for an initial generation. `generate_from_chunks` never filters `chunks`
based on it — that's the caller's job, already done before this call — it
only threads the judgment text into the prompt as extra signal
(src/generation/prompt.py).

Deliberately out of scope this sprint still (docs/ROADMAP.md, Sprint 6 vs.
7): no hard refusal anywhere in this function regardless of evidence
strength or `chunk_judgments` content — `generate_from_chunks` always
generates and returns an answer. Post-generation faithfulness/structural
validation is a separate function, `generate_evaluation`
(src/generation/guardrail.py), not run inside this one (this function stays
generation-only and fast). `judge_chunks` itself remains unstubbed, its own
later branch.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import litellm
from litellm import ModelResponse
from qdrant_client import QdrantClient

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.prompt import SYSTEM_PROMPT, build_prompt
from src.generation.signals import EvidenceSignals, GenerationChunk, compute_signals
from src.indexing.qdrant_index import COLLECTION_NAME, DENSE_VECTOR_NAME, point_id_for

DEFAULT_MODEL = "ollama_chat/mistral"
DEFAULT_FALLBACK_MODEL = "mistral/mistral-small-latest"
FALLBACK_MODEL_ENV_VAR = "BERGSON_LLM_FALLBACK_MODEL"


@dataclass(frozen=True)
class GenerationResult:
    answer: str
    model: str
    prompt: str
    signals: EvidenceSignals


def fetch_dense_vectors(client: QdrantClient, chunk_ids: list[str]) -> dict[str, list[float]]:
    """The dense (BGE-M3) vectors already computed for these chunks at
    indexing time, read back from Qdrant — the evidence-convergence signal
    reuses them rather than issuing a new embedding call."""
    if not chunk_ids:
        return {}
    points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id_for(chunk_id) for chunk_id in chunk_ids],
        with_vectors=[DENSE_VECTOR_NAME],
        with_payload=["chunk_id"],
    )
    vectors: dict[str, list[float]] = {}
    for point in points:
        payload = point.payload or {}
        named_vectors = point.vector if isinstance(point.vector, dict) else {}
        dense_vector = named_vectors.get(DENSE_VECTOR_NAME)
        is_flat_vector = isinstance(dense_vector, list) and (
            not dense_vector or isinstance(dense_vector[0], float)
        )
        if is_flat_vector:
            vectors[payload["chunk_id"]] = cast(list[float], dense_vector)
    return vectors


def generate_from_chunks(
    query: str,
    chunks: Sequence[GenerationChunk],
    client: QdrantClient,
    model: str = DEFAULT_MODEL,
    fallback_model: str | None = None,
    temperature: float | None = None,
    chunk_judgments: Mapping[str, ChunkJudgment] | None = None,
    **extra_params: Any,
) -> GenerationResult:
    """Synthesize an answer to `query` from `chunks` only.

    `client` is used exclusively to read back each chunk's already-indexed
    dense vector (for the convergence signal) — this function never
    performs retrieval or reranking itself.

    `fallback_model` defaults to `os.environ[BERGSON_LLM_FALLBACK_MODEL]` when
    set, else `DEFAULT_FALLBACK_MODEL` (Mistral's free hosted tier). If the
    primary `model` call fails, the fallback is attempted regardless — a
    missing `MISTRAL_API_KEY` (or whichever key the resolved fallback model
    needs) simply surfaces as that call's own error.

    `chunk_judgments` (docs/ROADMAP.md, Sprint 6): optional prior relevance
    judgments, keyed by chunk_id, rendered inline with the matching chunk's
    evidence text in the prompt (src/generation/prompt.py). `None` for an
    initial generation; a caller re-generating after judging some chunks
    passes them here — this never filters `chunks` itself, that's the
    caller's job before this call.

    `temperature` is left unset (provider default sampling) unless given —
    eval/scripts/run_ragas_eval.py passes 0 explicitly, since RAGAS scoring
    needs a reproducible answer to score, but normal/interactive use has no
    reason to force greedy decoding.

    `**extra_params` are forwarded to `litellm.completion` as-is (e.g.
    `num_ctx` for an Ollama model) — eval/scripts/run_ragas_eval.py passes
    the same `num_ctx` used for judging, so generation and judging never
    disagree on Ollama's context-window size: a size change on every call
    forces Ollama to reload the model, observed to add tens of seconds per
    call when generation and judging alternated with different context
    sizes on the same local server. Forwarded to `fallback_model` too, so a
    provider-specific param (like `num_ctx`) that the resolved fallback
    doesn't support surfaces as that call's own error, same as any other
    fallback failure mode here — caller's responsibility to keep
    `extra_params` valid for both when a cross-provider fallback is in play.
    """
    if fallback_model is None:
        fallback_model = os.environ.get(FALLBACK_MODEL_ENV_VAR, DEFAULT_FALLBACK_MODEL)

    dense_vectors = fetch_dense_vectors(client, [chunk.chunk_id for chunk in chunks])
    signals = compute_signals(chunks, dense_vectors)
    prompt = build_prompt(query, chunks, signals, chunk_judgments)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    def complete(completion_model: str) -> ModelResponse:
        response = litellm.completion(
            model=completion_model, messages=messages, temperature=temperature, **extra_params
        )
        # Never called with stream=True, so litellm always returns a
        # ModelResponse here, not a CustomStreamWrapper.
        assert isinstance(response, ModelResponse)
        return response

    used_model = model
    try:
        response = complete(model)
    except Exception:
        if not fallback_model:
            raise
        used_model = fallback_model
        response = complete(fallback_model)
    return GenerationResult(
        answer=response.choices[0].message.content or "",
        model=used_model,
        prompt=prompt,
        signals=signals,
    )
