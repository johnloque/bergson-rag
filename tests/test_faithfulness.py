"""Unit tests for src/generation/faithfulness.py — the reusable
faithfulness-checking function both this sprint's RAGAS eval harness
(eval/scripts/run_ragas_eval.py) and Sprint 6's future anti-hallucination
guardrail will call (docs/ROADMAP.md).

Requires: Qdrant reachable at localhost:6333 with `bergson_chunks` populated
(scripts/build_index.py) — to read back a real chunk's text — and a
reachable judge LLM (Ollama running locally with the default model pulled,
or MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL set), same discipline as
tests/test_generation.py. Skipped cleanly otherwise.
"""

from __future__ import annotations

import math

import litellm
import pytest
from qdrant_client import QdrantClient

from src.generation.faithfulness import DEFAULT_JUDGE_MODEL, build_judge_llm, check_faithfulness
from src.generation.generate import generate_from_chunks
from src.indexing.qdrant_index import COLLECTION_NAME, PAYLOAD_FIELDS, point_id_for
from src.retrieval.hybrid import RetrievedChunk

QDRANT_URL = "http://localhost:6333"

# Q001 (eval/gold_dataset.csv) — a single, gold-verified chunk, real corpus
# text, not a synthetic fixture (same discipline as tests/test_generation.py).
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"


def _collection_populated() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(COLLECTION_NAME):
            return False
        return client.count(collection_name=COLLECTION_NAME).count > 0
    except Exception:
        return False


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


pytestmark = [
    pytest.mark.skipif(
        not _collection_populated(),
        reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
        "and scripts/build_index.py first",
    ),
    pytest.mark.skipif(
        not _model_reachable(DEFAULT_JUDGE_MODEL),
        reason=f"no reachable judge model ({DEFAULT_JUDGE_MODEL}) — start Ollama with the "
        "default model pulled, or set MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL",
    ),
]


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def q001_chunk(client: QdrantClient) -> RetrievedChunk:
    point = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(Q001_CHUNK_ID)], with_payload=True
    )[0]
    payload = point.payload or {}
    return RetrievedChunk(score=1.0, **{field: payload[field] for field in PAYLOAD_FIELDS})


@pytest.fixture(scope="module")
def generated_answer(client: QdrantClient, q001_chunk: RetrievedChunk) -> str:
    """A real `generate_from_chunks` output, grounded in `q001_chunk` by
    construction — matches Sprint 6's actual guardrail use case (scoring a
    generated answer) much more closely than a hand-written paraphrase would.

    A hand-written short paraphrase of the same underlying claim was tried
    first and found to reproducibly (confirmed via a determinism check, not
    a one-off) score faithfulness=0.0 against this chunk: `q001_chunk`'s real
    text is 4511 characters and the snowball passage sits ~2000 characters
    in, a needle-in-haystack case this project's 7B local judge apparently
    struggles with for a terse claim, even though the same chunk scores
    faithfulness=1.0 for `generate_from_chunks`' own (longer, more textually
    overlapping) answer — confirmed via eval/scripts/run_ragas_eval.py's
    real Q001 result. A real limitation of the cost-free default judge, and
    exactly why these tests score real generation output, not a synthetic
    string standing in for it."""
    return generate_from_chunks(Q001_QUERY, [q001_chunk], client, temperature=0.0).answer


def test_check_faithfulness_scores_generated_answer_high(q001_chunk, generated_answer):
    result = check_faithfulness(Q001_QUERY, generated_answer, [q001_chunk])
    assert not math.isnan(result.score)
    assert result.score >= 0.5


def test_check_faithfulness_scores_unsupported_claim_lower(q001_chunk, generated_answer):
    """A claim absent from (and contradicting the era of) the cited chunk
    must score lower than the real generated answer — a comparative
    assertion, not a fixed absolute threshold, since a 7B local judge's
    exact scores can vary run to run in ways a hard-coded number would be
    brittle against."""
    unfaithful_answer = (
        "Bergson utilise l'image de la boule de neige, qu'il a empruntée à "
        "Albert Einstein en 1950, pour illustrer la relativité du temps."
    )
    faithful_result = check_faithfulness(Q001_QUERY, generated_answer, [q001_chunk])
    unfaithful_result = check_faithfulness(Q001_QUERY, unfaithful_answer, [q001_chunk])
    assert unfaithful_result.score < faithful_result.score


def test_check_faithfulness_deterministic_at_temperature_zero(q001_chunk, generated_answer):
    first = check_faithfulness(Q001_QUERY, generated_answer, [q001_chunk])
    second = check_faithfulness(Q001_QUERY, generated_answer, [q001_chunk])
    assert first.score == second.score


def test_check_faithfulness_accepts_prebuilt_judge_llm_for_reuse(q001_chunk, generated_answer):
    """Batch callers (eval/scripts/run_ragas_eval.py) build one judge_llm and
    reuse it across many items rather than rebuilding one per call."""
    judge_llm = build_judge_llm()
    result = check_faithfulness(Q001_QUERY, generated_answer, [q001_chunk], judge_llm=judge_llm)
    assert result.model == DEFAULT_JUDGE_MODEL
    assert not math.isnan(result.score)
