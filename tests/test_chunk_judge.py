"""Unit tests for src/generation/chunk_judge.py — `judge_chunk` (docs/ROADMAP.md,
Sprint 6 `chunk_judgments` interface; implemented on this branch,
feat/judge-chunks).

Real corpus chunks throughout, same discipline as tests/test_generation.py
and tests/test_guardrail.py — no synthetic chunk text. Justification-content
assertions check for terms hand-verified (by reading the real, indexed chunk
text) to be distinctive to that specific chunk and absent from the query
itself — so a match actually demonstrates the judge engaged with the
chunk's content, not just echoed the question back.

Requires: Qdrant reachable at localhost:6333 with `bergson_chunks` populated
(scripts/build_index.py) and a reachable judge LLM (Ollama running locally
with the default model pulled, or MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL
set) — same discipline as tests/test_faithfulness.py. Skipped cleanly
otherwise. The integration test additionally requires a reachable generation
LLM, same as tests/test_generation.py.
"""

from __future__ import annotations

import os

import litellm
import pytest
from qdrant_client import QdrantClient

from src.generation.chunk_judge import judge_chunk
from src.generation.chunk_judgment import ChunkJudgment
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.generate import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    FALLBACK_MODEL_ENV_VAR,
    generate_from_chunks,
)
from src.generation.prompt import CHUNK_JUDGMENT_INSTRUCTION
from src.indexing.qdrant_index import COLLECTION_NAME, PAYLOAD_FIELDS, point_id_for
from src.retrieval.hybrid import RetrievedChunk

QDRANT_URL = "http://localhost:6333"

# Q007 (eval/gold_dataset.csv), post-correction (docs/ROADMAP.md, Sprint 4) —
# real, manually verified gold chunks for a query about language's
# spatializing effect on philosophical problems.
Q007_QUERY = (
    "Selon Bergson, en quoi la structure du langage est-elle source de "
    "problèmes en philosophie ?"
)
Q007_CHUNK_IDS = ("1888_EDIC_c1", "1934_PM_c23", "1934_PM_c39")

# Read from the real, indexed chunk text (1888_EDIC_c1's full paragraph):
# it argues that spatialized language installs a "confusion" between duration
# and extension, succession and simultaneity, quality and quantity, at the
# root of the free-will problem specifically — these terms are concrete to
# that argument and absent from Q007_QUERY itself (which only says
# "langage"/"philosophie"/"problèmes"). Verified empirically (this branch)
# that judge_chunk(Q007_QUERY, this chunk) reliably (2/2 runs at
# temperature=0) returns "pertinent" against the local 7B judge — of Q007's
# three gold chunks, the other two (1934_PM_c23, 1934_PM_c39) were found to
# reliably score "partiellement pertinent" instead against this same judge:
# a real judge-leniency/strictness calibration finding (this local judge
# rarely commits to the extremes of its own label scale), not a bug in
# judge_chunk, so those two are not used as the "clearly pertinent" fixture
# here.
Q007_CHUNK_ID = "1888_EDIC_c1"
Q007_CHUNK_DISTINCTIVE_TERMS = (
    "liberté",
    "durée",
    "étendue",
    "succession",
    "simultanéité",
    "qualité",
    "quantité",
    "juxtapos",
    "discontinuité",
)

# Q001 (eval/gold_dataset.csv) — its own real gold chunk, about the
# continuous, self-renewing flux of inner psychological states (the "boule
# de neige" image itself). Used both as a second "pertinent" fixture (paired
# with its own query, Q001_QUERY) and to build the "non pertinent" fixture's
# query below — verified empirically to reliably (2/2 runs) return
# "pertinent" for Q001_QUERY.
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"
# "durée" is Bergson's own technical term for this chunk's claim, not part
# of Q001_QUERY's own wording ("perception du changement").
Q001_CHUNK_DISTINCTIVE_TERMS = ("durée",)

# Q005 (eval/gold_dataset.csv) — a real gold chunk about the 1906 San
# Francisco earthquake as a case study in how perception personifies
# catastrophe, topically unrelated to Q001's claim about the continuous
# flux of inner states: no shared vocabulary with Q001_QUERY. Verified
# empirically (2/2 runs) that judge_chunk(Q001_QUERY, this chunk) reliably
# returns "non pertinent".
UNRELATED_CHUNK_ID = "1932_2S_c62"
UNRELATED_CHUNK_DISTINCTIVE_TERMS = ("tremblement de terre", "san francisco")


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


pytestmark = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)

_judge_skip = pytest.mark.skipif(
    not _model_reachable(DEFAULT_JUDGE_MODEL),
    reason=f"no reachable judge model ({DEFAULT_JUDGE_MODEL}) — start Ollama with the "
    "default model pulled, or set MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL",
)

RESOLVED_FALLBACK_MODEL = os.environ.get(FALLBACK_MODEL_ENV_VAR, DEFAULT_FALLBACK_MODEL)

_llm_skip = pytest.mark.skipif(
    not (_model_reachable(DEFAULT_MODEL) or _model_reachable(RESOLVED_FALLBACK_MODEL)),
    reason="no reachable generation LLM — start Ollama with the default model pulled, or set "
    "MISTRAL_API_KEY for the default fallback, or set "
    f"{FALLBACK_MODEL_ENV_VAR} to a different LiteLLM model string with its provider "
    "API key configured",
)


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def _load_chunk(client: QdrantClient, chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    point = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(chunk_id)], with_payload=True
    )[0]
    payload = point.payload or {}
    return RetrievedChunk(score=score, **{field: payload[field] for field in PAYLOAD_FIELDS})


def _has_distinctive_term(justification: str, terms: tuple[str, ...]) -> bool:
    lowered = justification.lower()
    return any(term.lower() in lowered for term in terms)


# --- judge_chunk: label + justification specificity -----------------------


@_judge_skip
def test_judge_chunk_pertinent_for_matching_chunk(client):
    chunk = _load_chunk(client, Q007_CHUNK_ID)
    judgment: ChunkJudgment = judge_chunk(Q007_QUERY, chunk)

    assert judgment["label"] == "pertinent"
    assert judgment["justification"].strip()
    assert _has_distinctive_term(judgment["justification"], Q007_CHUNK_DISTINCTIVE_TERMS), judgment[
        "justification"
    ]


@_judge_skip
def test_judge_chunk_non_pertinent_for_unrelated_chunk(client):
    chunk = _load_chunk(client, UNRELATED_CHUNK_ID)
    judgment: ChunkJudgment = judge_chunk(Q001_QUERY, chunk)

    assert judgment["label"] == "non pertinent"
    assert judgment["justification"].strip()
    assert _has_distinctive_term(
        judgment["justification"], UNRELATED_CHUNK_DISTINCTIVE_TERMS
    ), judgment["justification"]


@_judge_skip
def test_judge_chunk_justification_is_not_generic_boilerplate(client):
    """Same specificity requirement, checked against a second, independent
    (query, chunk) pertinent pair (Q001's own gold chunk) — a single passing
    case above could coincidentally reuse a term from the prompt
    instructions rather than the chunk; this confirms it's not a one-off."""
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    judgment: ChunkJudgment = judge_chunk(Q001_QUERY, chunk)

    assert judgment["label"] == "pertinent"
    generic_phrases = (
        "cet extrait est pertinent",
        "ce passage est pertinent",
        "extrait pertinent par rapport à la question",
    )
    lowered = judgment["justification"].lower()
    assert not any(phrase in lowered for phrase in generic_phrases), judgment["justification"]
    assert _has_distinctive_term(judgment["justification"], Q001_CHUNK_DISTINCTIVE_TERMS), judgment[
        "justification"
    ]


# --- Integration: judge_chunk output feeding generate_from_chunks ---------


@_judge_skip
@_llm_skip
def test_judge_chunk_output_feeds_generate_from_chunks(client):
    """Simulates the future frontend's accumulation loop (Sprint 7,
    docs/ROADMAP.md): two real judge_chunk calls on two of Q007's three
    chunks, hand-assembled into a chunk_judgments dict, then passed to
    generate_from_chunks alongside all three chunks.

    Exercises generate_from_chunks' existing, unchanged contract (see
    src/generation/prompt.py's `_format_evidence`, which looks up each
    chunk's judgment via `chunk_judgments.get(chunk.chunk_id)`):
    - partial coverage tolerated: the third chunk (never judged) must still
      render normally, with no judgment annotation attached.
    - entries outside the current chunk selection are simply never looked
      up: an extra chunk_judgments entry keyed by a chunk_id absent from
      `chunks` must not surface anywhere in the prompt.
    """
    chunks = [_load_chunk(client, chunk_id) for chunk_id in Q007_CHUNK_IDS]
    judged_chunk_ids = Q007_CHUNK_IDS[:2]
    unjudged_chunk_id = Q007_CHUNK_IDS[2]

    chunk_judgments: dict[str, ChunkJudgment] = {
        chunk_id: judge_chunk(Q007_QUERY, _load_chunk(client, chunk_id))
        for chunk_id in judged_chunk_ids
    }
    # An entry for a chunk_id outside this call's `chunks` selection —
    # must be filtered out (never looked up) rather than erroring or
    # leaking into the prompt.
    chunk_judgments[UNRELATED_CHUNK_ID] = judge_chunk(
        Q007_QUERY, _load_chunk(client, UNRELATED_CHUNK_ID)
    )

    result = generate_from_chunks(
        Q007_QUERY, chunks, client, temperature=0.0, chunk_judgments=chunk_judgments
    )

    assert CHUNK_JUDGMENT_INSTRUCTION in result.prompt
    for chunk_id in judged_chunk_ids:
        assert chunk_judgments[chunk_id]["justification"] in result.prompt
        assert chunk_judgments[chunk_id]["label"] in result.prompt

    # The unjudged chunk's own text is present (it's still evidence)...
    assert unjudged_chunk_id in result.prompt
    # ...but the out-of-selection judgment never leaks into the prompt.
    assert chunk_judgments[UNRELATED_CHUNK_ID]["justification"] not in result.prompt

    assert result.answer.strip()
