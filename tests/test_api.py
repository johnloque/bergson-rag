"""Unit tests for src/api/main.py — Sprint 7a FastAPI scaffold
(docs/ROADMAP.md).

Same fixture discipline as tests/test_guardrail.py and
tests/test_chunk_judge.py: real gold-dataset queries/chunks (Q001, Q002,
Q004, Q007, and the Q005-derived "unrelated chunk" fixture), no synthetic
text. Skip marks are scoped per-test rather than module-wide, since several
tests here (malformed-body 422s, the provider-down 503 simulations) need
neither Qdrant nor a reachable LLM at all — only the tests that call the
real pipeline against real corpus content require them.
"""

from __future__ import annotations

import os

import litellm
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from src.api.converters import chunk_input_to_generation_chunk
from src.api.main import app
from src.api.schemas import ChunkInput
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.generate import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    FALLBACK_MODEL_ENV_VAR,
    generate_from_chunks,
)
from src.indexing.qdrant_index import COLLECTION_NAME, point_id_for

QDRANT_URL = "http://localhost:6333"

# Q001 (eval/gold_dataset.csv) — real gold chunk + the same hand-crafted
# fabricated-attribution answer already used in tests/test_guardrail.py.
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"
Q001_HALLUCINATED_ANSWER = (
    "Bergson utilise l'image de la boule de neige, qu'il a empruntée à Albert Einstein "
    f"en 1950, pour illustrer la relativité du temps [{Q001_CHUNK_ID}]."
)

# Q004 (eval/gold_dataset.csv) — same discipline, second confirmed-
# hallucination fixture (tests/test_guardrail.py).
Q004_QUERY = "Quel rapport Bergson établit-il entre l'imagination poétique et la réalité ?"
Q004_CHUNK_ID = "1900_R_c49"

# Q002 (eval/gold_dataset.csv, ground_truth_type "multi") — the "known-
# strong query" case: any one of its three gold chunk_ids suffices as
# evidence (docs/ROADMAP.md, evaluation methodology). Same chunk used as
# the "strong case" in tests/test_guardrail.py.
Q002_QUERY = (
    "Quelle thèse Bergson explique-t-il à travers l'image de la fonte d'un morceau de "
    "sucre dans un verre d'eau ?"
)
Q002_GOLD_CHUNK_IDS = frozenset({"1907_EC_c9", "1907_EC_c163", "1934_PM_c6"})
Q002_CHUNK_ID = "1907_EC_c9"

# Q007 (eval/gold_dataset.csv) — "pertinent" fixture (tests/test_chunk_judge.py).
Q007_QUERY = (
    "Selon Bergson, en quoi la structure du langage est-elle source de problèmes en philosophie ?"
)
Q007_CHUNK_ID = "1888_EDIC_c1"

# Q005-derived "non pertinent" fixture, paired with Q001_QUERY (no shared
# vocabulary) — same pairing as tests/test_chunk_judge.py.
UNRELATED_CHUNK_ID = "1932_2S_c62"


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
            model=model, messages=[{"role": "user", "content": "ping"}], max_tokens=1, timeout=5
        )
        return True
    except Exception:
        return False


_qdrant_skip = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)

RESOLVED_FALLBACK_MODEL = os.environ.get(FALLBACK_MODEL_ENV_VAR, DEFAULT_FALLBACK_MODEL)

_llm_skip = pytest.mark.skipif(
    not (_model_reachable(DEFAULT_MODEL) or _model_reachable(RESOLVED_FALLBACK_MODEL)),
    reason="no reachable generation LLM — start Ollama with the default model pulled, or set "
    "MISTRAL_API_KEY for the default fallback, or set "
    f"{FALLBACK_MODEL_ENV_VAR} to a different LiteLLM model string with its provider "
    "API key configured",
)

_judge_skip = pytest.mark.skipif(
    not _model_reachable(DEFAULT_JUDGE_MODEL),
    reason=f"no reachable judge model ({DEFAULT_JUDGE_MODEL}) — start Ollama with the "
    "default model pulled, or set MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL",
)


@pytest.fixture(scope="module")
def qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _load_chunk_input(client: QdrantClient, chunk_id: str, score: float = 1.0) -> dict:
    point = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(chunk_id)], with_payload=True
    )[0]
    payload = point.payload or {}
    return {
        "chunk_id": payload["chunk_id"],
        "work_id": payload["work_id"],
        "section_path": payload["section_path"],
        "paragraph_ids": payload["paragraph_ids"],
        "page_start": payload["page_start"],
        "page_end": payload["page_end"],
        "text": payload["text"],
        "score": score,
    }


# --- /retrieve --------------------------------------------------------------


@_qdrant_skip
def test_retrieve_known_strong_query_returns_expected_chunk(client):
    response = client.post("/retrieve", json={"query": Q002_QUERY, "top_k": 5})
    assert response.status_code == 200
    chunk_ids = {c["chunk_id"] for c in response.json()["chunks"]}
    assert chunk_ids & Q002_GOLD_CHUNK_IDS


def test_retrieve_malformed_body_returns_422(client):
    assert client.post("/retrieve", json={"top_k": 5}).status_code == 422
    assert client.post("/retrieve", json={"query": 123}).status_code == 422


# --- /generate ---------------------------------------------------------------


@_qdrant_skip
@_llm_skip
@pytest.mark.parametrize(
    ("query", "chunk_id"),
    [(Q001_QUERY, Q001_CHUNK_ID), (Q004_QUERY, Q004_CHUNK_ID)],
)
def test_generate_plumbing_produces_an_answer(client, qdrant_client, query, chunk_id):
    """Confirms the endpoint plumbing end to end — not correctness of the
    generated content, that's /evaluate's job (docs/ROADMAP.md scope note)."""
    chunk = _load_chunk_input(qdrant_client, chunk_id)
    response = client.post("/generate", json={"query": query, "chunks": [chunk]})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip()
    assert body["model_used"]


def test_generate_malformed_body_returns_422(client):
    assert client.post("/generate", json={"query": Q001_QUERY, "chunks": []}).status_code == 422
    assert (
        client.post("/generate", json={"chunks": [{"chunk_id": "x", "text": "y"}]}).status_code
        == 422
    )


@_qdrant_skip
def test_generate_unreachable_provider_returns_503(client, qdrant_client, monkeypatch):
    def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "completion", _raise)
    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    response = client.post("/generate", json={"query": Q001_QUERY, "chunks": [chunk]})
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]
    assert "mistral" in response.json()["detail"]


# --- /evaluate -----------------------------------------------------------


@_qdrant_skip
@_judge_skip
def test_evaluate_flags_known_hallucination(client, qdrant_client):
    """The real, gold-verified chunk text must be the cited evidence — a
    placeholder/synthetic context was found to let the local judge mark the
    fabricated claim as spuriously "supported" (this project's own judge
    fragility, tests/test_faithfulness.py), so this uses the same real
    indexed chunk tests/test_guardrail.py's Q001 case does."""
    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    response = client.post(
        "/evaluate",
        json={"query": Q001_QUERY, "chunks": [chunk], "answer": Q001_HALLUCINATED_ANSWER},
    )
    assert response.status_code == 200
    body = response.json()
    unsupported = [c for c in body["faithfulness"]["claims"] if not c["supported"]]
    assert any("einstein" in c["statement"].lower() for c in unsupported), unsupported
    assert body["should_auto_expand"] is False


@_qdrant_skip
@_llm_skip
@_judge_skip
def test_evaluate_strong_case_auto_expands(client, qdrant_client):
    """Real generate_from_chunks output at temperature=0, not a hand-crafted
    paraphrase — same discipline as tests/test_guardrail.py's own Q002 case
    (a hand-crafted near-verbatim paraphrase was found to reproducibly score
    faithfulness=0.0 against this project's local judge). The answer is
    produced by calling generate_from_chunks directly rather than through
    POST /generate: /generate's request schema has no temperature field (by
    design — normal/interactive use has no reason to force greedy decoding,
    src/generation/generate.py), so provider-default sampling there is not
    reproducible enough for this specific assertion; /generate's own
    plumbing is already covered by test_generate_plumbing_produces_an_answer
    above, so this test's only job is to exercise /evaluate."""
    chunk_input = _load_chunk_input(qdrant_client, Q002_CHUNK_ID)
    chunk = chunk_input_to_generation_chunk(ChunkInput(**chunk_input))
    result = generate_from_chunks(Q002_QUERY, [chunk], qdrant_client, temperature=0.0)

    response = client.post(
        "/evaluate", json={"query": Q002_QUERY, "chunks": [chunk_input], "answer": result.answer}
    )
    assert response.status_code == 200
    assert response.json()["should_auto_expand"] is True


def test_evaluate_malformed_body_returns_422(client):
    assert client.post("/evaluate", json={"query": Q001_QUERY, "chunks": []}).status_code == 422
    assert (
        client.post("/evaluate", json={"query": Q001_QUERY, "chunks": [], "answer": ""}).status_code
        == 422
    )


def test_evaluate_unreachable_provider_returns_503(client, monkeypatch):
    """No Qdrant/LLM required at all: generate_evaluation never touches
    Qdrant, and the judge call is mocked directly at litellm.acompletion
    (langchain-litellm's ChatLiteLLM calls out through it, confirmed via
    `self.client.acompletion` where `self.client` is the `litellm` module
    itself — src/api/main.py's module docstring)."""

    async def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "acompletion", _raise)
    chunk = {
        "chunk_id": "c1",
        "work_id": "1907_EC",
        "section_path": "",
        "paragraph_ids": [],
        "text": "Un extrait quelconque.",
        "score": 1.0,
    }
    response = client.post(
        "/evaluate",
        json={"query": "une question", "chunks": [chunk], "answer": "une réponse [c1]."},
    )
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]


# --- /judge-chunk ----------------------------------------------------------


@_qdrant_skip
@_judge_skip
def test_judge_chunk_pertinent_for_matching_chunk(client, qdrant_client):
    chunk = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)
    response = client.post("/judge-chunk", json={"query": Q007_QUERY, "chunk": chunk})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "pertinent"
    assert body["justification"].strip()


@_qdrant_skip
@_judge_skip
def test_judge_chunk_non_pertinent_for_unrelated_chunk(client, qdrant_client):
    chunk = _load_chunk_input(qdrant_client, UNRELATED_CHUNK_ID)
    response = client.post("/judge-chunk", json={"query": Q001_QUERY, "chunk": chunk})
    assert response.status_code == 200
    assert response.json()["label"] == "non pertinent"


def test_judge_chunk_malformed_body_returns_422(client):
    assert client.post("/judge-chunk", json={"query": Q001_QUERY}).status_code == 422
    assert (
        client.post("/judge-chunk", json={"chunk": {"chunk_id": "x", "text": "y"}}).status_code
        == 422
    )


def test_judge_chunk_unreachable_provider_returns_503(client, monkeypatch):
    def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "completion", _raise)
    chunk = {"chunk_id": "c1", "text": "Un extrait quelconque."}
    response = client.post("/judge-chunk", json={"query": "une question", "chunk": chunk})
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]
