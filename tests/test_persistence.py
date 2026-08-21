"""Persistence-specific tests for src/api/ (docs/ROADMAP.md, Sprint 7 —
"SQLite persistence", feat/api-persistence). Endpoint plumbing/422/503
coverage lives in tests/test_api.py; this file covers what only exists
because requests are now persisted:

- the /generate -> /judge-chunk -> /generate round trip (a persisted
  judgment auto-loaded into a regeneration's prompt)
- the chunk_judgments override rule (an explicit, even empty, dict in the
  request beats the persisted default)
- /evaluate looked up by generation_id via direct DB insertion (Q001/Q004
  confirmed-hallucination fixtures, bypassing a live /generate call so this
  stays fast and independent of model output variance)
- GET /turns/{id} and GET /conversations/{id} assembling persisted state
  correctly after a full generate -> evaluate -> judge-chunk sequence
- 404s on every id-keyed lookup

Same real-corpus fixture discipline as tests/test_api.py: Q001 and Q007
(eval/gold_dataset.csv), no synthetic chunk text where a real judge call is
involved. Each test gets its own isolated in-memory SQLite DB (the
`engine`/`client` fixtures below), same pattern as tests/test_api.py.
"""

from __future__ import annotations

import litellm
import pytest
from fastapi.testclient import TestClient
from litellm import ModelResponse
from qdrant_client import QdrantClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.api.converters import chunk_input_to_generation_chunk
from src.api.db import get_session
from src.api.main import app
from src.api.models import Conversation, Generation, RetrievedChunkRow, Turn
from src.api.schemas import ChunkInput
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL
from src.generation.prompt import CHUNK_JUDGMENT_INSTRUCTION
from src.generation.signals import retrieval_confidence_tier
from src.indexing.qdrant_index import COLLECTION_NAME, point_id_for

QDRANT_URL = "http://localhost:6333"

# Captured before any monkeypatching so tests that fake litellm.completion
# for /generate can still restore the real one around a /judge-chunk call
# in the same test — /judge-chunk needs a real, reachable judge model
# (_judge_skip), and it calls litellm.completion internally
# (src/generation/chunk_judge.py) through the very same module-level name
# a naive whole-test monkeypatch would otherwise also intercept.
_REAL_LITELLM_COMPLETION = litellm.completion

# Q001 (eval/gold_dataset.csv) — real gold chunk + confirmed-hallucination
# fixture, same as tests/test_api.py and tests/test_guardrail.py.
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"
Q001_HALLUCINATED_ANSWER = (
    "Bergson utilise l'image de la boule de neige, qu'il a empruntée à Albert Einstein "
    f"en 1950, pour illustrer la relativité du temps [{Q001_CHUNK_ID}]."
)

# Q004 (eval/gold_dataset.csv) — second confirmed-hallucination fixture.
Q004_QUERY = "Quel rapport Bergson établit-il entre l'imagination poétique et la réalité ?"
Q004_CHUNK_ID = "1900_R_c49"
Q004_HALLUCINATED_ANSWER = (
    "Bergson affirme, en reprenant une thèse de Kant, que l'imagination poétique n'a "
    "structurellement aucun rapport avec la réalité et relève d'une faculté purement "
    f"arbitraire, indépendante de toute expérience vécue [{Q004_CHUNK_ID}]."
)

# Q007 (eval/gold_dataset.csv) — "pertinent" fixture (tests/test_chunk_judge.py),
# used for the /generate -> /judge-chunk -> /generate round trip.
Q007_QUERY = (
    "Selon Bergson, en quoi la structure du langage est-elle source de problèmes en philosophie ?"
)
Q007_CHUNK_ID = "1888_EDIC_c1"


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

_judge_skip = pytest.mark.skipif(
    not _model_reachable(DEFAULT_JUDGE_MODEL),
    reason=f"no reachable judge model ({DEFAULT_JUDGE_MODEL}) — start Ollama with the "
    "default model pulled, or set MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL",
)


@pytest.fixture(scope="module")
def qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture()
def engine():
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


def _create_turn(engine, query: str) -> int:
    with Session(engine) as session:
        conversation = Conversation()
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        turn = Turn(conversation_id=conversation.id, query=query)
        session.add(turn)
        session.commit()
        session.refresh(turn)
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
    """Direct DB insertion of a generation record, bypassing a live LLM
    call — used for the /evaluate tests below so they stay fast and
    independent of model output variance (docs/ROADMAP.md's Tests section).
    `retrieval_confidence_tier` defaults to "moyenne" (a confident tier) —
    /evaluate now reads it back from this persisted field instead of
    recomputing it from chunks."""
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


def _fake_completion(captured: list, chunk_id: str = Q007_CHUNK_ID) -> object:
    """A `litellm.completion` stand-in that records the `messages` it was
    called with (so the real prompt built by `build_prompt`,
    src/generation/prompt.py, can be inspected — same "prompt inspection"
    discipline tests/test_generation.py established for chunk_judgments,
    applied here through the API layer instead of calling
    generate_from_chunks directly) and returns a canned answer citing
    `chunk_id`, so the round trip completes without a live generation LLM."""

    def _completion(*, model, messages, **kwargs):
        captured.append(messages)
        return ModelResponse(
            choices=[
                {
                    "message": {"role": "assistant", "content": f"Réponse [{chunk_id}]."},
                    "finish_reason": "stop",
                    "index": 0,
                }
            ]
        )

    return _completion


# --- round trip: /generate -> /judge-chunk -> /generate --------------------


@_qdrant_skip
@_judge_skip
def test_persisted_chunk_judgment_auto_loaded_into_regeneration_prompt(
    client, qdrant_client, monkeypatch
):
    """A chunk judged via /judge-chunk on a turn is auto-loaded into that
    turn's next /generate call when chunk_judgments is omitted — and its
    justification actually appears in the constructed prompt, not just in
    the generation's persisted chunk_judgments_used snapshot."""
    captured: list = []
    monkeypatch.setattr(litellm, "completion", _fake_completion(captured))

    chunk = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)

    first = client.post("/generate", json={"query": Q007_QUERY, "chunks": [chunk]})
    assert first.status_code == 200
    turn_id = first.json()["turn_id"]
    # No chunk_judgments applied yet.
    assert CHUNK_JUDGMENT_INSTRUCTION not in captured[-1][-1]["content"]

    # Restore the real litellm.completion for the /judge-chunk call itself —
    # it needs the real, reachable judge model (_judge_skip), not the fake
    # /generate stand-in above.
    monkeypatch.setattr(litellm, "completion", _REAL_LITELLM_COMPLETION)
    judge_response = client.post(
        "/judge-chunk", json={"query": Q007_QUERY, "chunk": chunk, "turn_id": turn_id}
    )
    assert judge_response.status_code == 200
    justification = judge_response.json()["justification"]

    monkeypatch.setattr(litellm, "completion", _fake_completion(captured))
    second = client.post(
        "/generate", json={"query": Q007_QUERY, "chunks": [chunk], "turn_id": turn_id}
    )
    assert second.status_code == 200

    prompt_content = captured[-1][-1]["content"]
    assert CHUNK_JUDGMENT_INSTRUCTION in prompt_content
    assert justification in prompt_content


@_qdrant_skip
@_judge_skip
def test_generate_explicit_chunk_judgments_overrides_persisted_default(
    client, qdrant_client, monkeypatch
):
    """A turn with a persisted judgment for chunk A, then a /generate call
    on that turn_id with an explicit (even empty) chunk_judgments — the
    persisted judgment for A is NOT auto-applied: explicit request body
    wins over the persisted default (docs/ROADMAP.md)."""
    captured: list = []
    monkeypatch.setattr(litellm, "completion", _fake_completion(captured))

    chunk = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)
    first = client.post("/generate", json={"query": Q007_QUERY, "chunks": [chunk]})
    turn_id = first.json()["turn_id"]

    monkeypatch.setattr(litellm, "completion", _REAL_LITELLM_COMPLETION)
    client.post("/judge-chunk", json={"query": Q007_QUERY, "chunk": chunk, "turn_id": turn_id})

    monkeypatch.setattr(litellm, "completion", _fake_completion(captured))
    second = client.post(
        "/generate",
        json={
            "query": Q007_QUERY,
            "chunks": [chunk],
            "turn_id": turn_id,
            "chunk_judgments": {},
        },
    )
    assert second.status_code == 200
    assert CHUNK_JUDGMENT_INSTRUCTION not in captured[-1][-1]["content"]


# --- /generate: server-side retrieval confidence persistence ---------------


@_qdrant_skip
def test_generate_persists_correct_retrieval_confidence_tier(
    client, qdrant_client, engine, monkeypatch
):
    """/generate computes the retrieval confidence tier server-side
    (src.generation.signals.retrieval_confidence_tier) over the chunks it
    was actually given, and persists it on the generations row — never a
    client-submitted value (docs/ROADMAP.md, the retrieval-confidence-split
    correction). Verified via a direct DB read, not just that the call
    succeeds. `litellm.completion` is faked (`_fake_completion`) so this
    doesn't need a reachable generation LLM — /generate's own answer
    content is irrelevant here, only the persisted tier is under test."""
    chunk = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)
    expected_tier = retrieval_confidence_tier(
        [chunk_input_to_generation_chunk(ChunkInput(**chunk))]
    )

    monkeypatch.setattr(litellm, "completion", _fake_completion([], chunk_id=Q007_CHUNK_ID))
    response = client.post("/generate", json={"query": Q007_QUERY, "chunks": [chunk]})
    assert response.status_code == 200
    generation_id = response.json()["generation_id"]

    with Session(engine) as session:
        generation = session.get(Generation, generation_id)
        assert generation.retrieval_confidence_tier == expected_tier


# --- /evaluate via generation_id, direct DB insertion -----------------------


@_qdrant_skip
@_judge_skip
@pytest.mark.parametrize(
    ("query", "chunk_id", "answer", "fabricated_term"),
    [
        (Q001_QUERY, Q001_CHUNK_ID, Q001_HALLUCINATED_ANSWER, "einstein"),
        (Q004_QUERY, Q004_CHUNK_ID, Q004_HALLUCINATED_ANSWER, "kant"),
    ],
)
def test_evaluate_via_generation_id_flags_known_hallucination(
    client, engine, query, chunk_id, answer, fabricated_term
):
    turn_id = _create_turn(engine, query)
    generation_id = _insert_generation(engine, turn_id, chunk_id, answer)

    response = client.post("/evaluate", json={"generation_id": generation_id})
    assert response.status_code == 200
    body = response.json()
    unsupported = [c for c in body["faithfulness"]["claims"] if not c["supported"]]
    assert any(fabricated_term in c["statement"].lower() for c in unsupported), unsupported
    assert body["should_auto_expand"] is False


# --- GET /turns/{id} ---------------------------------------------------------


@_qdrant_skip
@_judge_skip
def test_get_turn_assembles_full_state_after_generate_evaluate_judge(
    client, qdrant_client, monkeypatch
):
    """The "user returns later" scenario (docs/ROADMAP.md, Sprint 6's
    flagged risk this branch resolves): after a full generate -> evaluate
    -> judge-chunk sequence, GET /turns/{id} must return all of it
    correctly assembled, not just satisfy a schema check."""
    monkeypatch.setattr(litellm, "completion", _fake_completion([], chunk_id=Q001_CHUNK_ID))

    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    generate_response = client.post("/generate", json={"query": Q001_QUERY, "chunks": [chunk]})
    assert generate_response.status_code == 200
    generate_body = generate_response.json()
    turn_id = generate_body["turn_id"]
    generation_id = generate_body["generation_id"]

    evaluate_response = client.post("/evaluate", json={"generation_id": generation_id})
    assert evaluate_response.status_code == 200
    evaluate_body = evaluate_response.json()

    monkeypatch.setattr(litellm, "completion", _REAL_LITELLM_COMPLETION)
    judge_response = client.post(
        "/judge-chunk", json={"query": Q001_QUERY, "chunk": chunk, "turn_id": turn_id}
    )
    assert judge_response.status_code == 200
    judgment = judge_response.json()

    turn_response = client.get(f"/turns/{turn_id}")
    assert turn_response.status_code == 200
    body = turn_response.json()

    assert body["turn_id"] == turn_id
    assert body["conversation_id"] == generate_body["conversation_id"]
    assert body["query"] == Q001_QUERY
    assert [c["chunk_id"] for c in body["retrieved_chunks"]] == [Q001_CHUNK_ID]

    assert len(body["generations"]) == 1
    generation_out = body["generations"][0]
    assert generation_out["generation_id"] == generation_id
    assert generation_out["chunk_ids"] == [Q001_CHUNK_ID]
    assert generation_out["answer"] == generate_body["answer"]
    assert generation_out["evaluation"] is not None
    assert generation_out["evaluation"]["should_auto_expand"] == evaluate_body["should_auto_expand"]
    # retrieval_confidence_tier is no longer part of EvaluateResponse
    # (docs/ROADMAP.md, the retrieval-confidence-split correction) — it was
    # already shown to the user pre-generation via /confidence-preview.
    assert "retrieval_confidence_tier" not in evaluate_body
    assert "retrieval_confidence_tier" not in generation_out["evaluation"]

    assert body["chunk_judgments"] == {
        Q001_CHUNK_ID: {"label": judgment["label"], "justification": judgment["justification"]}
    }


@_qdrant_skip
def test_regenerate_with_excluded_chunk_keeps_it_in_retrieved_chunks(
    client, qdrant_client, monkeypatch
):
    """Regression: excluding a chunk in the UI (frontend/src/state/turnUi.tsx)
    filters it out of the *regeneration's* /generate call, but that chunk
    must still come back from GET /turns/{id} afterwards — the chunk rail's
    "excluded stays visible to re-include" contract (frontend/src/components/
    ChunkRail.tsx) depends on the turn's persisted retrieved_chunks set never
    shrinking to just whatever the most recent generation used."""
    monkeypatch.setattr(litellm, "completion", _fake_completion([], chunk_id=Q001_CHUNK_ID))

    chunk_a = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)
    chunk_b = _load_chunk_input(qdrant_client, Q007_CHUNK_ID)

    first = client.post("/generate", json={"query": Q001_QUERY, "chunks": [chunk_a, chunk_b]})
    assert first.status_code == 200
    turn_id = first.json()["turn_id"]

    # Regenerate with chunk_b excluded — mirrors useTurnController.ts's
    # regenerate() sending only turnUi-included chunks.
    second = client.post(
        "/generate", json={"query": Q001_QUERY, "chunks": [chunk_a], "turn_id": turn_id}
    )
    assert second.status_code == 200

    turn_response = client.get(f"/turns/{turn_id}")
    assert turn_response.status_code == 200
    retrieved_ids = {c["chunk_id"] for c in turn_response.json()["retrieved_chunks"]}
    assert retrieved_ids == {Q001_CHUNK_ID, Q007_CHUNK_ID}

    # The exclusion is still reflected in what that specific generation used.
    generations = turn_response.json()["generations"]
    assert generations[-1]["chunk_ids"] == [Q001_CHUNK_ID]


def test_get_turn_unknown_id_returns_404(client):
    assert client.get("/turns/999999").status_code == 404


# --- GET /conversations/{id} -------------------------------------------------


@_qdrant_skip
def test_get_conversation_lists_its_turns(client, qdrant_client, monkeypatch):
    monkeypatch.setattr(litellm, "completion", _fake_completion([]))
    chunk = _load_chunk_input(qdrant_client, Q001_CHUNK_ID)

    first = client.post("/generate", json={"query": Q001_QUERY, "chunks": [chunk]})
    conversation_id = first.json()["conversation_id"]
    second = client.post(
        "/generate",
        json={"query": Q007_QUERY, "chunks": [chunk], "conversation_id": conversation_id},
    )
    assert second.status_code == 200

    response = client.get(f"/conversations/{conversation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    queries = [t["query"] for t in body["turns"]]
    assert queries == [Q001_QUERY, Q007_QUERY]


def test_get_conversation_unknown_id_returns_404(client):
    assert client.get("/conversations/999999").status_code == 404
