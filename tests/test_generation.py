"""Unit tests for src/generation — two distinct kinds, per docs/ROADMAP.md
Sprint 5's testing-approach note (kept reusable for future generation work,
not a one-off for this sprint):

- Test A ("isolated prompt-branch tests"): hand-fixed chunk sets, no
  retrieval involved, asserting the evidence-conditioned prompt actually
  contains the expected conditioning instructions for each branch (per-work
  attribution, mono-work continuity, convergent-synthesis vs.
  divergent-separate-presentation). Split into two tiers here:
    - `test_signals_*` / `test_prompt_*`: exercise `compute_signals` +
      `build_prompt` directly. These only need chunks' already-indexed
      dense vectors (read from Qdrant, same discipline as
      tests/test_retrieval.py — real data, no synthetic vectors), so they
      run without any LLM and give fast, LLM-independent regression
      coverage of the conditioning logic itself.
    - `test_generate_from_chunks_*`: call `generate_from_chunks` end to
      end (the literal Test A ask), asserting on `GenerationResult.prompt`.
      Skipped when no LLM is reachable — same discipline as this repo's
      Qdrant-dependent suites skipping instead of mocking the model.
- Test B ("pipeline-realistic tests"): run the real retrieve+rerank
  pipeline for a few real gold_dataset.csv queries and feed whatever it
  returns (potentially a mediocre distractor alongside a good chunk) into
  `generate_from_chunks` — the realistic, not hand-curated, candidate set.
  Also skipped when no LLM is reachable.

Requires: Qdrant reachable at localhost:6333 with `bergson_chunks`
populated (scripts/build_index.py). The `test_generate_from_chunks_*` and
Test B cases additionally require a reachable LLM — either Ollama running
locally with the default model pulled, or `MISTRAL_API_KEY` set for the
default fallback (Mistral's free hosted tier), or `BERGSON_LLM_FALLBACK_MODEL`
set to a different LiteLLM model string with its own provider API key
configured in the environment.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import litellm
import pytest
from qdrant_client import QdrantClient

from src.generation.generate import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    FALLBACK_MODEL_ENV_VAR,
    fetch_dense_vectors,
    generate_from_chunks,
)
from src.generation.prompt import (
    CAUTION_INSTRUCTION,
    CITATION_INSTRUCTION,
    CONVERGENT_INSTRUCTION,
    DIVERGENT_INSTRUCTION,
    INTERPRETIVE_FRAMING_INSTRUCTION,
    MONO_WORK_INSTRUCTION,
    build_prompt,
)
from src.generation.signals import compute_signals
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME, PAYLOAD_FIELDS, point_id_for
from src.retrieval.hybrid import RetrievedChunk, hybrid_search
from src.retrieval.reranking import CrossEncoderReranker, rerank
from src.works import WORKS

QDRANT_URL = "http://localhost:6333"
REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_DATASET_PATH = REPO_ROOT / "eval" / "gold_dataset.csv"

# Q007 (eval/gold_dataset.csv), post-correction (docs/ROADMAP.md, Sprint 4:
# "Fix Q007 gold annotation") — a real, manually verified multi-work
# convergent case: two distinct works, both genuinely bearing on the same
# specific claim about language's spatializing effect on thought.
Q007_QUERY = (
    "Selon Bergson, en quoi la structure du langage est-elle source de "
    "problèmes en philosophie ?"
)
Q007_CHUNK_IDS = ("1888_EDIC_c1", "1934_PM_c23", "1934_PM_c39")

# Q001 (eval/gold_dataset.csv) — a single, mono-work, gold-verified chunk.
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"

# Synthetic, deliberately constructed divergent-evidence case — NOT a gold
# dataset item. Two real chunks from the same work (1888_EDIC, "Essai sur
# les données immédiates de la conscience"), both plausible hits for a
# broad "le moi et la durée" theme (topically related), but answering
# different specific claims (free will vs. the difficulty of representing
# pure duration) — confirmed via their real, already-indexed dense vectors
# to have low mutual cosine similarity (~0.47, well under
# src.generation.signals.CONVERGENCE_THRESHOLD=0.55) against a verified
# convergent case (Q007's trio sits at ~0.60-0.65). Real examples of
# contested/divergent evidence are scarce now that comparative/contested
# questions are out of scope (docs/ROADMAP.md), hence the construction.
DIVERGENT_QUERY = "Que dit Bergson sur le moi et la durée ?"
DIVERGENT_CHUNK_IDS = ("1888_EDIC_c56", "1888_EDIC_c36")


def _collection_populated() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(COLLECTION_NAME):
            return False
        return client.count(collection_name=COLLECTION_NAME).count > 0
    except Exception:
        return False


# The resolved fallback candidate mirrors generate_from_chunks' own default
# resolution (BERGSON_LLM_FALLBACK_MODEL override, else Mistral's free
# hosted tier) so the reachability probes below test exactly what a real
# call would use.
RESOLVED_FALLBACK_MODEL = os.environ.get(FALLBACK_MODEL_ENV_VAR, DEFAULT_FALLBACK_MODEL)


def _model_reachable(model: str) -> bool:
    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=5,
        )
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)

_llm_skip = pytest.mark.skipif(
    not (_model_reachable(DEFAULT_MODEL) or _model_reachable(RESOLVED_FALLBACK_MODEL)),
    reason="no reachable LLM — start Ollama with the default model pulled, or set "
    "MISTRAL_API_KEY for the default fallback, or set "
    f"{FALLBACK_MODEL_ENV_VAR} to a different LiteLLM model string with its provider "
    "API key configured",
)

_fallback_skip = pytest.mark.skipif(
    not _model_reachable(RESOLVED_FALLBACK_MODEL),
    reason=f"fallback model {RESOLVED_FALLBACK_MODEL!r} not reachable — set MISTRAL_API_KEY "
    f"(default fallback) or {FALLBACK_MODEL_ENV_VAR} plus its provider API key",
)


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def dense_embedder() -> DenseEmbedder:
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder() -> SparseEmbedder:
    return SparseEmbedder()


@pytest.fixture(scope="module")
def reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


def _load_chunk(client: QdrantClient, chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    point = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(chunk_id)], with_payload=True
    )[0]
    payload = point.payload or {}
    return RetrievedChunk(score=score, **{field: payload[field] for field in PAYLOAD_FIELDS})


def _prepared_chunks(client, reranker, query: str, chunk_ids: tuple[str, ...]):
    """Hand-fixed chunk set (real, verified chunk_ids — not retrieval
    output) run through the real cross-encoder, then paired with the
    chunks' already-indexed dense vectors — mirrors what generate_from_chunks
    itself does internally, minus the LLM call, so these helpers can back
    both the LLM-independent signal/prompt tests and the full
    generate_from_chunks tests below without duplicating logic."""
    candidates = [_load_chunk(client, chunk_id) for chunk_id in chunk_ids]
    reranked = rerank(query, candidates, reranker)
    dense_vectors = fetch_dense_vectors(client, [c.chunk_id for c in reranked])
    signals = compute_signals(reranked, dense_vectors)
    return reranked, signals


# --- Test A, tier 1: signals + prompt, no LLM required -----------------


def test_signals_multi_work_convergent(client, reranker):
    _, signals = _prepared_chunks(client, reranker, Q007_QUERY, Q007_CHUNK_IDS)
    assert signals.works == ("1888_EDIC", "1934_PM")
    assert signals.is_multi_work
    assert signals.is_convergent


def test_prompt_multi_work_has_attribution_language(client, reranker):
    chunks, signals = _prepared_chunks(client, reranker, Q007_QUERY, Q007_CHUNK_IDS)
    prompt = build_prompt(Q007_QUERY, chunks, signals)
    assert "1888_EDIC" in prompt and "1934_PM" in prompt
    assert "attribue explicitement chaque affirmation à l'œuvre" in prompt
    assert MONO_WORK_INSTRUCTION not in prompt
    assert CITATION_INSTRUCTION in prompt
    assert INTERPRETIVE_FRAMING_INSTRUCTION in prompt
    # Signal 3 (reranking confidence) is independent of signals 1/2 above —
    # whatever the real cross-encoder scores say for this candidate set,
    # the caution instruction's presence must track signals.is_confident.
    assert (CAUTION_INSTRUCTION in prompt) == (not signals.is_confident)


def test_prompt_multi_work_shows_title_and_year_per_work(client, reranker):
    """`fix/title-year-grounding`: the model must be shown the real title and
    publication year for each represented work, not just work_id — see
    docs/generation_strategy.md's "Title/year grounding" note. Additive, not
    a replacement: work_id must still be present too (Layer 1 and the
    citation format both key on it)."""
    chunks, signals = _prepared_chunks(client, reranker, Q007_QUERY, Q007_CHUNK_IDS)
    prompt = build_prompt(Q007_QUERY, chunks, signals)
    assert signals.works == ("1888_EDIC", "1934_PM")
    for work_id in signals.works:
        metadata = WORKS[work_id]
        assert metadata.title in prompt, f"expected title for {work_id} in prompt"
        assert str(metadata.year) in prompt, f"expected year for {work_id} in prompt"
        assert work_id in prompt, f"expected work_id {work_id} still present alongside title/year"


def test_signals_mono_work_single_chunk(client, reranker):
    _, signals = _prepared_chunks(client, reranker, Q001_QUERY, (Q001_CHUNK_ID,))
    assert signals.works == ("1907_EC",)
    assert not signals.is_multi_work
    assert signals.is_convergent  # trivial: nothing to diverge from


def test_prompt_mono_work_has_continuous_presentation_language(client, reranker):
    chunks, signals = _prepared_chunks(client, reranker, Q001_QUERY, (Q001_CHUNK_ID,))
    prompt = build_prompt(Q001_QUERY, chunks, signals)
    assert MONO_WORK_INSTRUCTION in prompt
    assert "attribue explicitement chaque affirmation à l'œuvre" not in prompt
    assert CITATION_INSTRUCTION in prompt
    # fix/title-year-grounding: real title/year shown even in the mono-work
    # branch, not just the multi-work attribution case.
    metadata = WORKS["1907_EC"]
    assert metadata.title in prompt
    assert str(metadata.year) in prompt


def test_signals_synthetic_divergent_case(client, reranker):
    _, signals = _prepared_chunks(client, reranker, DIVERGENT_QUERY, DIVERGENT_CHUNK_IDS)
    assert signals.convergence is not None
    assert not signals.is_convergent, (
        f"expected the constructed pair's mean cosine similarity "
        f"({signals.convergence:.3f}) below CONVERGENCE_THRESHOLD"
    )


def test_prompt_divergent_case_has_separate_presentation_language(client, reranker):
    chunks, signals = _prepared_chunks(client, reranker, DIVERGENT_QUERY, DIVERGENT_CHUNK_IDS)
    prompt = build_prompt(DIVERGENT_QUERY, chunks, signals)
    assert DIVERGENT_INSTRUCTION in prompt
    assert CONVERGENT_INSTRUCTION not in prompt
    assert "ne présente jamais la réponse comme un consensus" in prompt


# --- Test A, tier 2: generate_from_chunks end to end, requires an LLM --


@_llm_skip
def test_generate_from_chunks_multi_work(client, reranker):
    chunks, _ = _prepared_chunks(client, reranker, Q007_QUERY, Q007_CHUNK_IDS)
    result = generate_from_chunks(Q007_QUERY, chunks, client)
    assert result.signals.is_multi_work
    assert "attribue explicitement chaque affirmation à l'œuvre" in result.prompt
    assert result.answer.strip()


@_llm_skip
def test_generate_from_chunks_mono_work(client, reranker):
    chunks, _ = _prepared_chunks(client, reranker, Q001_QUERY, (Q001_CHUNK_ID,))
    result = generate_from_chunks(Q001_QUERY, chunks, client)
    assert not result.signals.is_multi_work
    assert MONO_WORK_INSTRUCTION in result.prompt
    assert result.answer.strip()


@_llm_skip
def test_generate_from_chunks_divergent(client, reranker):
    chunks, _ = _prepared_chunks(client, reranker, DIVERGENT_QUERY, DIVERGENT_CHUNK_IDS)
    result = generate_from_chunks(DIVERGENT_QUERY, chunks, client)
    assert not result.signals.is_convergent
    assert DIVERGENT_INSTRUCTION in result.prompt
    assert result.answer.strip()


@_fallback_skip
def test_generate_from_chunks_model_is_a_call_parameter(client, reranker):
    """The same query/chunks must be callable with different models without
    touching any other code path — model is a per-call parameter, not a
    global setting (docs/ROADMAP.md, Sprint 5)."""
    chunks, _ = _prepared_chunks(client, reranker, Q001_QUERY, (Q001_CHUNK_ID,))
    result = generate_from_chunks(Q001_QUERY, chunks, client, model=RESOLVED_FALLBACK_MODEL)
    assert result.model == RESOLVED_FALLBACK_MODEL


# --- Test B: pipeline-realistic, non-curated candidate sets -------------


def _load_gold_queries(n: int) -> list[tuple[str, str]]:
    with GOLD_DATASET_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)[:n]
    return [(row["id"], row["query"]) for row in rows]


_GOLD_QUERIES = _load_gold_queries(3) if GOLD_DATASET_PATH.exists() else []


@_llm_skip
@pytest.mark.parametrize("gold_id,query", _GOLD_QUERIES)
def test_generate_from_chunks_on_real_pipeline_output(
    client, dense_embedder, sparse_embedder, reranker, gold_id, query
):
    """Whatever retrieve+rerank actually returns for a real gold query —
    not the curated gold chunk_ids — including any mediocre distractor
    alongside a good chunk. No guardrail exists yet (Sprint 6) to filter
    this, so this only checks generate_from_chunks runs end to end and
    still carries the mandatory citation instruction, not that the answer
    is faithful — RAGAS faithfulness is a separate, later evaluation.
    """
    candidates = hybrid_search(client, query, dense_embedder, sparse_embedder, limit=10)
    reranked = rerank(query, candidates, reranker)[:3]
    assert reranked, f"{gold_id}: expected at least one retrieved chunk"

    result = generate_from_chunks(query, reranked, client)
    assert result.answer.strip()
    assert CITATION_INSTRUCTION in result.prompt
    assert result.signals.works
