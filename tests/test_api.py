"""Unit tests for src/api/main.py — Sprint 7 FastAPI + persistence
(docs/ROADMAP.md).

Same fixture discipline as tests/test_guardrail.py and
tests/test_chunk_judge.py: real gold-dataset queries/chunks (Q001, Q002,
Q004, Q007, and the Q005-derived "unrelated chunk" fixture), no synthetic
text. Skip marks are scoped per-test rather than module-wide, since several
tests here (malformed-body 422s, the provider-down 503 simulations) need
neither Qdrant nor a reachable LLM at all — only the tests that call the
real pipeline against real corpus content require them.

Persistence-specific coverage (the /generate <-> /judge-chunk round trip,
/evaluate via direct DB insertion, GET /turns and GET /conversations
assembly, 404s, and the chunk_judgments override rule) lives in
tests/test_persistence.py instead — this file keeps the per-endpoint
plumbing/422/503 coverage Sprint 7a established, updated for the request/
response shapes this branch (feat/api-persistence) changed.

Each test gets its own isolated in-memory SQLite DB (the `engine`/`client`
fixtures below) — `app.dependency_overrides[get_session]` swaps in a fresh
`StaticPool`-backed engine per test, so persisted rows from one test never
leak into another and never touch the real dev database
(`data/app.db`, src/api/db.py).
"""

from __future__ import annotations

import os

import litellm
import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.api.converters import chunk_input_to_generation_chunk
from src.api.db import get_session
from src.api.main import app
from src.api.models import Conversation, Generation, RetrievedChunkRow, Turn
from src.api.schemas import ChunkInput
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.generate import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    FALLBACK_MODEL_ENV_VAR,
    generate_from_chunks,
)
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME, point_id_for
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranking import CrossEncoderReranker, rerank

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
Q004_HALLUCINATED_ANSWER = (
    "Bergson affirme, en reprenant une thèse de Kant, que l'imagination poétique n'a "
    "structurellement aucun rapport avec la réalité et relève d'une faculté purement "
    f"arbitraire, indépendante de toute expérience vécue [{Q004_CHUNK_ID}]."
)

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

# Q009 (eval/gold_dataset.csv) — same confirmed, persistent retrieval miss
# as tests/test_guardrail.py's own Q009 case: the real hybrid_search +
# rerank pipeline never surfaces the correct gold chunk among its top
# candidates for this query, tops out at a "très faible" tier.
Q009_QUERY = "Quelle thèse Bergson explique-t-il en décrivant la grande chevauchée du vivant ?"


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

# GET /chunks/{chunk_id}/neighbors (docs/ROADMAP.md, Sprint 12
# `feat/chunk-neighbor-expansion`) needs both the indexed Qdrant collection
# (for chunk payloads) and the local chunks build artifact (for the
# paragraph_id -> chunk_id lookup, src/paragraph_chunk_map.py) — same
# discipline as tests/test_paragraph_chunk_map.py's own skip.
_neighbor_skip = pytest.mark.skipif(
    not _collection_populated() or not DEFAULT_CHUNKS_DIR.exists(),
    reason="Qdrant not reachable/empty, or data/processed/chunks not built — run "
    "`docker compose up qdrant`, scripts/run_ingestion.py, and scripts/build_index.py first",
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


@pytest.fixture(scope="module")
def reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


@pytest.fixture(scope="module")
def dense_embedder() -> DenseEmbedder:
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder() -> SparseEmbedder:
    return SparseEmbedder()


@pytest.fixture()
def engine():
    """A fresh, isolated in-memory SQLite DB per test — `StaticPool` so the
    single shared in-memory connection survives across the multiple
    `Session`s a request cycle opens (plain in-memory SQLite gives each new
    connection its own empty DB, which would silently lose everything
    written by a prior request in the same test)."""
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture()
def client(engine) -> TestClient:
    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


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


def _create_turn(
    engine,
    query: str,
    conversation_id: int | None = None,
    retrieved_chunks: list[tuple[str, float]] | None = None,
) -> int:
    """Direct DB insertion of a bare turn, bypassing /retrieve entirely —
    for tests that only need a valid turn_id to anchor a /generate,
    /judge-chunk, or /evaluate call, without exercising retrieval itself.
    `conversation_id` given reuses that conversation (else a new one is
    created); `retrieved_chunks` optionally seeds `retrieved_chunks` rows,
    mirroring what a real /retrieve call now persists for a turn
    (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix) — needed by tests that
    check /generate never touches that table."""
    with Session(engine) as session:
        if conversation_id is not None:
            conversation = session.get(Conversation, conversation_id)
        else:
            conversation = Conversation()
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
        turn = Turn(conversation_id=conversation.id, query=query)
        session.add(turn)
        session.commit()
        session.refresh(turn)
        for rank, (chunk_id, score) in enumerate(retrieved_chunks or []):
            session.add(
                RetrievedChunkRow(turn_id=turn.id, chunk_id=chunk_id, rank=rank, score=score)
            )
        session.commit()
        return turn.id


def _insert_generation(
    engine,
    turn_id: int,
    chunk_id: str,
    answer: str,
    model: str = "test-model",
    score: float = 1.0,
    retrieval_confidence_tier: str = "moyenne",
) -> int:
    """Direct DB insertion of a generation record, bypassing a live
    /generate call — this is /evaluate's new trust boundary (docs/ROADMAP.md):
    it looks the generation up by ID rather than trusting a client-submitted
    triple, so exercising it doesn't require actually running generation.
    `retrieval_confidence_tier` defaults to "moyenne" (a confident tier) so
    should_auto_expand's gating on it doesn't mask the faithfulness-only
    fixtures below; tests exercising confidence-tier behavior itself pass an
    explicit value."""
    with Session(engine) as session:
        session.add(RetrievedChunkRow(turn_id=turn_id, chunk_id=chunk_id, rank=0, score=score))
        generation = Generation(
            turn_id=turn_id,
            model=model,
            chunk_ids=[chunk_id],
            answer=answer,
            retrieval_confidence_tier=retrieval_confidence_tier,
        )
        session.add(generation)
        session.commit()
        session.refresh(generation)
        return generation.id


# --- /retrieve --------------------------------------------------------------


@_qdrant_skip
def test_retrieve_known_strong_query_returns_expected_chunk(client):
    response = client.post("/retrieve", json={"query": Q002_QUERY, "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    chunk_ids = {c["chunk_id"] for c in body["chunks"]}
    assert chunk_ids & Q002_GOLD_CHUNK_IDS


@_qdrant_skip
def test_retrieve_persists_turn_and_retrieved_chunks(client, engine):
    """docs/ROADMAP.md, Sprint 10 turn-lifecycle fix: /retrieve creates the
    turn (and a new conversation) immediately, and the chunk set it returns
    is already persisted — before any /generate call happens."""
    response = client.post("/retrieve", json={"query": Q002_QUERY, "top_k": 5})
    assert response.status_code == 200
    body = response.json()
    turn_id = body["turn_id"]
    conversation_id = body["conversation_id"]
    assert turn_id
    assert conversation_id

    with Session(engine) as session:
        turn = session.get(Turn, turn_id)
        assert turn is not None
        assert turn.query == Q002_QUERY
        assert turn.conversation_id == conversation_id
        rows = session.exec(
            select(RetrievedChunkRow).where(RetrievedChunkRow.turn_id == turn_id)
        ).all()
        assert {r.chunk_id for r in rows} == {c["chunk_id"] for c in body["chunks"]}


@_qdrant_skip
def test_retrieve_second_call_with_conversation_id_reuses_conversation(client, engine):
    first = client.post("/retrieve", json={"query": Q002_QUERY, "top_k": 3})
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/retrieve", json={"query": Q007_QUERY, "top_k": 3, "conversation_id": conversation_id}
    )
    assert second.status_code == 200
    body = second.json()
    assert body["conversation_id"] == conversation_id
    assert body["turn_id"] != first.json()["turn_id"]


def test_retrieve_unknown_conversation_id_returns_404(client):
    response = client.post("/retrieve", json={"query": Q002_QUERY, "conversation_id": 999999})
    assert response.status_code == 404


def test_retrieve_malformed_body_returns_422(client):
    assert client.post("/retrieve", json={"top_k": 5}).status_code == 422
    assert client.post("/retrieve", json={"query": 123}).status_code == 422


def test_retrieve_malformed_date_range_returns_422(client):
    """docs/ROADMAP.md, Sprint 11: `date_range.start > end` and an unknown
    `mode` are both rejected at the request-validation layer — full filtering
    semantics coverage lives in tests/test_filtering.py, this is just the
    endpoint-level plumbing check."""
    response = client.post(
        "/retrieve", json={"query": Q002_QUERY, "date_range": {"start": 2000, "end": 1000}}
    )
    assert response.status_code == 422
    response = client.post(
        "/retrieve",
        json={"query": Q002_QUERY, "date_range": {"start": 1900, "end": 2000, "mode": "bogus"}},
    )
    assert response.status_code == 422


@_qdrant_skip
def test_retrieve_applies_work_ids_and_date_range_filters(client):
    """docs/ROADMAP.md, Sprint 11: `/retrieve` threads `work_ids`/
    `date_range` through to `filtered_hybrid_search` — the endpoint-level
    plumbing check for the filtering logic tests/test_filtering.py covers in
    depth. 1907_EC (1907) is Q002's other gold work; the range [1900, 1910]
    includes it but excludes 1934_PM (1934), Q002's third gold work."""
    response = client.post(
        "/retrieve",
        json={
            "query": Q002_QUERY,
            "top_k": 5,
            "work_ids": ["1907_EC"],
            "date_range": {"start": 1900, "end": 1910, "mode": "publication"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"]
    assert {c["work_id"] for c in body["chunks"]} == {"1907_EC"}


@_qdrant_skip
def test_retrieve_echoes_and_persists_applied_filter(client):
    """docs/ROADMAP.md, Sprint 12 filter UI: `RetrieveResponse` and a later
    `GET /turns/{id}` both echo back exactly the work_ids/date_range that
    was applied to a turn — None for a call that set neither, matching
    `RetrieveRequest`'s own omitted-parameter contract exactly rather than
    an explicit "all works"/"full span" default, and the given values
    otherwise. This is what lets a reloaded page reconstruct which filter
    (if any) produced a turn's results, since retrieval itself has no
    other record of it (src/api/models.py's `Turn.work_ids`/`date_range`)."""
    unfiltered = client.post("/retrieve", json={"query": Q002_QUERY, "top_k": 3})
    assert unfiltered.status_code == 200
    unfiltered_body = unfiltered.json()
    assert unfiltered_body["work_ids"] is None
    assert unfiltered_body["date_range"] is None

    filtered = client.post(
        "/retrieve",
        json={
            "query": Q002_QUERY,
            "top_k": 3,
            "work_ids": ["1907_EC"],
            "date_range": {"start": 1900, "end": 1910, "mode": "publication"},
        },
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["work_ids"] == ["1907_EC"]
    assert filtered_body["date_range"] == {"start": 1900, "end": 1910, "mode": "publication"}

    # Persisted at turn creation (before retrieval itself runs) -- readable
    # back via GET /turns/{id}, independent of the live /retrieve response.
    turn_response = client.get(f"/turns/{filtered_body['turn_id']}")
    assert turn_response.status_code == 200
    turn_body = turn_response.json()
    assert turn_body["work_ids"] == ["1907_EC"]
    assert turn_body["date_range"] == {"start": 1900, "end": 1910, "mode": "publication"}

    unfiltered_turn = client.get(f"/turns/{unfiltered_body['turn_id']}")
    assert unfiltered_turn.status_code == 200
    assert unfiltered_turn.json()["work_ids"] is None
    assert unfiltered_turn.json()["date_range"] is None


# --- /generate ---------------------------------------------------------------


@_qdrant_skip
@_llm_skip
@pytest.mark.parametrize(
    ("query", "chunk_id"),
    [(Q001_QUERY, Q001_CHUNK_ID), (Q004_QUERY, Q004_CHUNK_ID)],
)
def test_generate_plumbing_produces_an_answer(client, qdrant_client, engine, query, chunk_id):
    """Confirms the endpoint plumbing end to end — not correctness of the
    generated content, that's /evaluate's job (docs/ROADMAP.md scope note).
    Also confirms the generation is persisted and its id, plus the turn's
    own (already-existing, per Sprint 10) turn_id/conversation_id, are
    returned. `turn_id` is created directly here (`_create_turn`), standing
    in for a prior /retrieve call — /generate no longer creates turns
    itself (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix)."""
    chunk = _load_chunk_input(qdrant_client, chunk_id)
    turn_id = _create_turn(engine, query)
    response = client.post("/generate", json={"turn_id": turn_id, "chunks": [chunk]})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip()
    assert body["model_used"]
    assert body["generation_id"]
    assert body["turn_id"] == turn_id
    assert body["conversation_id"]


def test_generate_malformed_body_returns_422(client, engine):
    turn_id = _create_turn(engine, Q001_QUERY)
    assert client.post("/generate", json={"turn_id": turn_id, "chunks": []}).status_code == 422
    assert (
        client.post("/generate", json={"chunks": [{"chunk_id": "x", "text": "y"}]}).status_code
        == 422
    )


@_qdrant_skip
def test_generate_unreachable_provider_returns_503(client, qdrant_client, engine, monkeypatch):
    def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "completion", _raise)
    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    turn_id = _create_turn(engine, Q001_QUERY)
    response = client.post("/generate", json={"turn_id": turn_id, "chunks": [chunk]})
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]
    assert "mistral" in response.json()["detail"]


@_qdrant_skip
def test_generate_unknown_turn_id_returns_404(client, qdrant_client):
    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    response = client.post("/generate", json={"chunks": [chunk], "turn_id": 999999})
    assert response.status_code == 404


# --- /confidence-preview -----------------------------------------------------


@_qdrant_skip
def test_confidence_preview_matches_q009_persistent_retrieval_miss(
    client, qdrant_client, dense_embedder, sparse_embedder, reranker
):
    """Q009 (eval/gold_dataset.csv) — the same real hybrid_search + rerank
    pipeline, and the same confirmed persistent retrieval miss, as
    tests/test_guardrail.py's own Q009 case: `generate_evaluation` used to
    compute a "très faible" tier internally for this exact chunk set/scores.
    /confidence-preview must return the same tier from the same (chunk_id,
    score) pairs, via the one shared computation
    (src.generation.signals.retrieval_confidence_tier) this endpoint and
    /generate both call — docs/ROADMAP.md, the retrieval-confidence-split
    correction."""
    candidates = hybrid_search(qdrant_client, Q009_QUERY, dense_embedder, sparse_embedder, limit=10)
    reranked = rerank(Q009_QUERY, candidates, reranker)[:5]
    assert reranked, "expected at least one retrieved chunk"

    response = client.post(
        "/confidence-preview",
        json={"chunks": [{"chunk_id": c.chunk_id, "score": c.rerank_score} for c in reranked]},
    )
    assert response.status_code == 200
    assert response.json()["retrieval_confidence_tier"] == "très faible"


def test_confidence_preview_malformed_body_returns_422(client):
    assert client.post("/confidence-preview", json={}).status_code == 422
    assert client.post("/confidence-preview", json={"chunks": []}).status_code == 422
    assert client.post("/confidence-preview", json={"chunks": [{"score": 0.5}]}).status_code == 422


@_qdrant_skip
@_llm_skip
def test_confidence_preview_and_generate_persisted_tier_agree(client, qdrant_client, engine):
    """Consistency check: the tier /confidence-preview shows the user
    pre-generation must match what /generate independently persists for the
    same chunk set — both endpoints call the one shared function
    (src.generation.signals.retrieval_confidence_tier), so they must never
    diverge (docs/ROADMAP.md, the retrieval-confidence-split correction)."""
    chunk = _load_chunk_input(qdrant_client, Q002_CHUNK_ID)

    preview_response = client.post(
        "/confidence-preview",
        json={"chunks": [{"chunk_id": chunk["chunk_id"], "score": chunk["score"]}]},
    )
    assert preview_response.status_code == 200
    preview_tier = preview_response.json()["retrieval_confidence_tier"]

    turn_id = _create_turn(engine, Q002_QUERY)
    generate_response = client.post("/generate", json={"turn_id": turn_id, "chunks": [chunk]})
    assert generate_response.status_code == 200
    generation_id = generate_response.json()["generation_id"]

    with Session(engine) as session:
        generation = session.get(Generation, generation_id)
        assert generation.retrieval_confidence_tier == preview_tier


# --- /evaluate -----------------------------------------------------------


@_qdrant_skip
@_judge_skip
@pytest.mark.parametrize(
    ("query", "chunk_id", "answer", "fabricated_term"),
    [
        (Q001_QUERY, Q001_CHUNK_ID, Q001_HALLUCINATED_ANSWER, "einstein"),
        (Q004_QUERY, Q004_CHUNK_ID, Q004_HALLUCINATED_ANSWER, "kant"),
    ],
)
def test_evaluate_flags_known_hallucination(
    client, engine, query, chunk_id, answer, fabricated_term
):
    """The real, gold-verified chunk text must be the cited evidence — a
    placeholder/synthetic context was found to let the local judge mark the
    fabricated claim as spuriously "supported" (this project's own judge
    fragility, tests/test_faithfulness.py), so this uses the same real
    indexed chunks tests/test_guardrail.py's Q001/Q004 cases do. The
    generation record is inserted directly (bypassing a live /generate
    call, docs/ROADMAP.md's Tests section) — see `_insert_generation`
    above."""
    turn_id = _create_turn(engine, query)
    generation_id = _insert_generation(engine, turn_id, chunk_id, answer)
    response = client.post("/evaluate", json={"generation_id": generation_id})
    assert response.status_code == 200
    body = response.json()
    unsupported = [c for c in body["faithfulness"]["claims"] if not c["supported"]]
    assert any(fabricated_term in c["statement"].lower() for c in unsupported), unsupported
    assert body["should_auto_expand"] is False


@_qdrant_skip
@_llm_skip
@_judge_skip
def test_evaluate_strong_case_auto_expands(client, qdrant_client, engine):
    """Real generate_from_chunks output at temperature=0, not a hand-crafted
    paraphrase — same discipline as tests/test_guardrail.py's own Q002 case
    (a hand-crafted near-verbatim paraphrase was found to reproducibly score
    faithfulness=0.0 against this project's local judge). The answer is
    produced by calling generate_from_chunks directly and then inserted as
    a generation record — /generate's own plumbing (turn/generation
    persistence, chunk_judgments auto-load) is already covered by
    test_generate_plumbing_produces_an_answer and tests/test_persistence.py,
    so this test's only job is to exercise /evaluate's new
    lookup-by-generation_id path."""
    chunk_input = _load_chunk_input(qdrant_client, Q002_CHUNK_ID)
    chunk = chunk_input_to_generation_chunk(ChunkInput(**chunk_input))
    result = generate_from_chunks(Q002_QUERY, [chunk], qdrant_client, temperature=0.0)

    turn_id = _create_turn(engine, Q002_QUERY)
    generation_id = _insert_generation(
        engine, turn_id, Q002_CHUNK_ID, result.answer, score=chunk_input["score"]
    )

    response = client.post("/evaluate", json={"generation_id": generation_id})
    assert response.status_code == 200
    assert response.json()["should_auto_expand"] is True


@_qdrant_skip
@_judge_skip
def test_evaluate_response_omits_retrieval_confidence_tier(client, engine):
    """docs/ROADMAP.md, the retrieval-confidence-split correction:
    /evaluate still uses the persisted retrieval confidence tier internally
    to gate should_auto_expand (test_evaluate_strong_case_auto_expands,
    test_evaluate_flags_known_hallucination above already exercise that),
    but must not re-surface the tier itself in the response — it was
    already shown to the user pre-generation via /confidence-preview.
    Explicit negative assertion, not just an absent check elsewhere."""
    turn_id = _create_turn(engine, Q001_QUERY)
    generation_id = _insert_generation(
        engine, turn_id, Q001_CHUNK_ID, f"une réponse [{Q001_CHUNK_ID}]."
    )
    response = client.post("/evaluate", json={"generation_id": generation_id})
    assert response.status_code == 200
    assert "retrieval_confidence_tier" not in response.json()


def test_evaluate_malformed_body_returns_422(client):
    assert client.post("/evaluate", json={}).status_code == 422
    assert client.post("/evaluate", json={"generation_id": "not-an-int"}).status_code == 422


def test_evaluate_unknown_generation_id_returns_404(client):
    response = client.post("/evaluate", json={"generation_id": 999999})
    assert response.status_code == 404


@_qdrant_skip
def test_evaluate_unreachable_provider_returns_503(client, engine, monkeypatch):
    """`generate_evaluation`'s only LLM call is the judge, made via
    langchain-litellm's `acompletion` (src/api/main.py's module docstring) —
    mocked directly here, same as before. Fetching the generation's chunk
    text back from Qdrant by chunk_id (src/api/converters.py) is new on this
    branch, so this now needs `_qdrant_skip` where it previously didn't."""

    async def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "acompletion", _raise)
    turn_id = _create_turn(engine, Q001_QUERY)
    generation_id = _insert_generation(
        engine, turn_id, Q001_CHUNK_ID, f"une réponse [{Q001_CHUNK_ID}]."
    )
    response = client.post("/evaluate", json={"generation_id": generation_id})
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]


# --- /judge-chunk ----------------------------------------------------------


@_qdrant_skip
@_judge_skip
def test_judge_chunk_pertinent_for_matching_chunk(client, qdrant_client, engine):
    chunk = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)
    turn_id = _create_turn(engine, Q007_QUERY)
    response = client.post(
        "/judge-chunk", json={"query": Q007_QUERY, "chunk": chunk, "turn_id": turn_id}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "pertinent"
    assert body["justification"].strip()


@_qdrant_skip
@_judge_skip
def test_judge_chunk_non_pertinent_for_unrelated_chunk(client, qdrant_client, engine):
    chunk = _load_chunk_input(qdrant_client, UNRELATED_CHUNK_ID)
    turn_id = _create_turn(engine, Q001_QUERY)
    response = client.post(
        "/judge-chunk", json={"query": Q001_QUERY, "chunk": chunk, "turn_id": turn_id}
    )
    assert response.status_code == 200
    assert response.json()["label"] == "non pertinent"


def test_judge_chunk_malformed_body_returns_422(client):
    assert client.post("/judge-chunk", json={"query": Q001_QUERY}).status_code == 422
    assert (
        client.post("/judge-chunk", json={"chunk": {"chunk_id": "x", "text": "y"}}).status_code
        == 422
    )
    # turn_id is now required (docs/ROADMAP.md) — omitting it 422s even
    # when query/chunk are otherwise well-formed.
    assert (
        client.post(
            "/judge-chunk",
            json={"query": Q001_QUERY, "chunk": {"chunk_id": "x", "text": "y"}},
        ).status_code
        == 422
    )


def test_judge_chunk_unreachable_provider_returns_503(client, engine, monkeypatch):
    def _raise(*args, **kwargs):
        raise litellm.exceptions.APIConnectionError(
            message="Connection refused", llm_provider="ollama_chat", model="mistral"
        )

    monkeypatch.setattr(litellm, "completion", _raise)
    turn_id = _create_turn(engine, "une question")
    chunk = {"chunk_id": "c1", "text": "Un extrait quelconque."}
    response = client.post(
        "/judge-chunk", json={"query": "une question", "chunk": chunk, "turn_id": turn_id}
    )
    assert response.status_code == 503
    assert "ollama_chat" in response.json()["detail"]


def test_judge_chunk_unknown_turn_id_returns_404(client):
    chunk = {"chunk_id": "c1", "text": "Un extrait quelconque."}
    response = client.post(
        "/judge-chunk", json={"query": "une question", "chunk": chunk, "turn_id": 999999}
    )
    assert response.status_code == 404


# --- GET /chunks/{chunk_id}/neighbors ----------------------------------------
#
# Fixtures below are real chunk_ids from 1934_PM's current chunking
# (data/processed/chunks/1934_PM.json), hand-verified against that file:
# section 1934_PM_s2 runs paragraphs 4-24 (chunks c4-c24), section
# 1934_PM_s3 starts right after at paragraph 25 (chunk c25) — a real,
# adjacent-paragraph, different-section pair, not a synthetic one.

# Mid-section: both paragraph_id-1 and +1 exist and stay inside 1934_PM_s2.
NEIGHBOR_MID_CHUNK_ID = "1934_PM_c5"
NEIGHBOR_MID_PREV_ID = "1934_PM_c4"
NEIGHBOR_MID_NEXT_ID = "1934_PM_c6"

# Last chunk of 1934_PM_s2: paragraph_id+1 (p25) exists but resolves to
# 1934_PM_c25, which belongs to the next section (1934_PM_s3) — the actual
# section-boundary regression case, not just "no more paragraphs".
NEIGHBOR_SECTION_LAST_CHUNK_ID = "1934_PM_c24"
NEIGHBOR_SECTION_LAST_PREV_ID = "1934_PM_c23"

# First chunk of 1934_PM_s3: paragraph_id-1 (p24) exists but resolves to
# 1934_PM_c24, which belongs to the previous section (1934_PM_s2).
NEIGHBOR_SECTION_FIRST_CHUNK_ID = "1934_PM_c25"
NEIGHBOR_SECTION_FIRST_NEXT_ID = "1934_PM_c26"


@_neighbor_skip
def test_chunk_neighbors_mid_section_returns_both_directions(client):
    response = client.get(f"/chunks/{NEIGHBOR_MID_CHUNK_ID}/neighbors")
    assert response.status_code == 200
    body = response.json()
    assert body["previous"]["chunk_id"] == NEIGHBOR_MID_PREV_ID
    assert body["next"]["chunk_id"] == NEIGHBOR_MID_NEXT_ID


@_neighbor_skip
def test_chunk_neighbors_at_section_end_has_no_next(client):
    """Last paragraph of a section: `next` resolves to a real chunk_id, but
    it's in the following section — must come back null, not that chunk."""
    response = client.get(f"/chunks/{NEIGHBOR_SECTION_LAST_CHUNK_ID}/neighbors")
    assert response.status_code == 200
    body = response.json()
    assert body["previous"]["chunk_id"] == NEIGHBOR_SECTION_LAST_PREV_ID
    assert body["next"] is None


@_neighbor_skip
def test_chunk_neighbors_at_section_start_has_no_previous(client):
    """First paragraph of a section: `previous` resolves to a real chunk_id
    in the preceding section — must come back null (the section-boundary
    regression test: an existing paragraph_id-1 is not enough on its own)."""
    response = client.get(f"/chunks/{NEIGHBOR_SECTION_FIRST_CHUNK_ID}/neighbors")
    assert response.status_code == 200
    body = response.json()
    assert body["previous"] is None
    assert body["next"]["chunk_id"] == NEIGHBOR_SECTION_FIRST_NEXT_ID


@_qdrant_skip
def test_chunk_neighbors_unknown_chunk_id_returns_404(client):
    response = client.get("/chunks/NOT_A_REAL_CHUNK_ID/neighbors")
    assert response.status_code == 404
