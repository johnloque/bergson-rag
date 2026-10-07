"""`prompts_used` traceability columns (refactor/prompts-to-files,
docs/prompts.md): every new generations / evaluations / chunk_judgments row
records the prompt versions its LLM calls used; rows from before stay NULL.

Drives the real endpoints with the LLMs mocked (same capture approach as
tests/test_prompt_snapshots.py) and an in-memory SQLite DB — fast.
"""

from __future__ import annotations

from unittest import mock

import litellm
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.api.db import _sync_additive_columns, get_session
from src.api.main import app
from src.api.models import ChunkJudgmentRow, Conversation, Evaluation, Generation, Turn
from src.api.schemas import ChunkInput
from src.generation.chunk_judge import judge_chunk_prompts_used
from src.generation.faithfulness import faithfulness_prompts_used
from src.generation.prompt import generation_prompts_used
from src.prompts.loader import get_prompt_manifest
from tests.test_prompt_snapshots import _RecordingJudgeLLM

QUERY = "Quel usage Bergson fait-il de l'image de la boule de neige ?"
CHUNK = ChunkInput(
    chunk_id="1907_EC_c13",
    work_id="1907_EC",
    text="Le changement est ininterrompu, comme une boule de neige qui grossit.",
    section_path="body/Test",
    paragraph_ids=["1907_EC_p13"],
)
ANSWER = "Bergson compare le changement à une boule de neige [1907_EC_c13]."
TABLES = ("generations", "evaluations", "chunk_judgments")


def _reply(content: str) -> litellm.ModelResponse:
    return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": content}}])


@pytest.fixture()
def engine():
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    return test_engine


@pytest.fixture()
def client(engine):
    def _session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _session_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _create_turn(engine) -> int:
    with Session(engine) as session:
        conversation = Conversation()
        session.add(conversation)
        session.commit()
        turn = Turn(conversation_id=conversation.id, query=QUERY)
        session.add(turn)
        session.commit()
        return turn.id


def test_generate_evaluate_judge_record_prompts_used(engine, client):
    turn_id = _create_turn(engine)
    qdrant = mock.Mock()
    qdrant.retrieve.return_value = []
    claim = "Bergson compare le changement à une boule de neige."

    with (
        mock.patch("src.api.main.get_qdrant_client", return_value=qdrant),
        mock.patch("litellm.completion", return_value=_reply(ANSWER)),
    ):
        generated = client.post(
            "/generate", json={"turn_id": turn_id, "chunks": [CHUNK.model_dump()]}
        )
    assert generated.status_code == 200, generated.text
    generation_id = generated.json()["generation_id"]

    with (
        mock.patch("src.api.main.get_qdrant_client", return_value=qdrant),
        mock.patch("src.api.main.fetch_chunk_input", return_value=CHUNK),
        mock.patch(
            "src.generation.faithfulness.build_judge_llm", return_value=_RecordingJudgeLLM(claim)
        ),
    ):
        evaluated = client.post("/evaluate", json={"generation_id": generation_id})
    assert evaluated.status_code == 200, evaluated.text

    judge_reply = '{"label": "pertinent", "justification": "La boule de neige y figure."}'
    with mock.patch("litellm.completion", return_value=_reply(judge_reply)):
        judged = client.post(
            "/judge-chunk",
            json={"query": QUERY, "chunk": CHUNK.model_dump(), "turn_id": turn_id},
        )
    assert judged.status_code == 200, judged.text

    manifest = get_prompt_manifest()
    with Session(engine) as session:
        generation = session.get(Generation, generation_id)
        evaluation = session.exec(select(Evaluation)).one()
        judgment = session.exec(select(ChunkJudgmentRow)).one()

    assert generation.prompts_used == generation_prompts_used()
    assert set(generation.prompts_used) == {"generation.system", "generation.answer"}
    assert evaluation.prompts_used == faithfulness_prompts_used()
    assert set(evaluation.prompts_used) == {
        "faithfulness.segment_claims",
        "faithfulness.nli_verifier",
    }
    assert judgment.prompts_used == judge_chunk_prompts_used()
    assert set(judgment.prompts_used) == {
        "judge_chunk.system",
        "judge_chunk.relevance",
        "judge_chunk.retry",
    }
    for record in (generation.prompts_used, evaluation.prompts_used, judgment.prompts_used):
        for prompt_id, entry in record.items():
            assert entry["hash"] == manifest[prompt_id]["hash"]
            assert entry["version"] == manifest[prompt_id]["version"]
            assert entry["custom"] is False
    assert evaluation.prompts_used["faithfulness.nli_verifier"]["library"].startswith("ragas==")


def _legacy_engine(tmp_path):
    """A file DB in the pre-branch shape: all three tables without
    `prompts_used`, holding one row each written before the column existed."""
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN prompts_used"))
        conn.execute(text("INSERT INTO conversations (id, created_at) VALUES (1, '2026-01-01')"))
        conn.execute(
            text("INSERT INTO turns (id, conversation_id, query, created_at) "
                 "VALUES (1, 1, 'q', '2026-01-01')")
        )  # fmt: skip
        conn.execute(
            text("INSERT INTO generations (id, turn_id, model, chunk_ids, answer, "
                 "retrieval_confidence_tier, created_at) "
                 "VALUES (1, 1, 'm', '[\"c1\"]', 'a', 'moyenne', '2026-01-01')")
        )  # fmt: skip
        conn.execute(
            text("INSERT INTO evaluations (id, generation_id, structural_flags, "
                 "faithfulness_annotations, should_auto_expand, created_at) "
                 "VALUES (1, 1, '{}', '{}', 0, '2026-01-01')")
        )  # fmt: skip
        conn.execute(
            text("INSERT INTO chunk_judgments (turn_id, chunk_id, label, justification, model, "
                 "created_at) VALUES (1, 'c1', 'pertinent', 'j', 'm', '2026-01-01')")
        )  # fmt: skip
    return engine


def _columns(engine, table: str) -> list[str]:
    return [column["name"] for column in inspect(engine).get_columns(table)]


def test_add_column_step_is_idempotent_and_keeps_existing_rows_null(tmp_path):
    engine = _legacy_engine(tmp_path)
    assert all("prompts_used" not in _columns(engine, table) for table in TABLES)

    _sync_additive_columns(engine)
    after_first = {table: _columns(engine, table) for table in TABLES}
    _sync_additive_columns(engine)

    assert {table: _columns(engine, table) for table in TABLES} == after_first
    assert all(columns.count("prompts_used") == 1 for columns in after_first.values())
    with Session(engine) as session:
        assert session.get(Generation, 1).prompts_used is None
        assert session.exec(select(Evaluation)).one().prompts_used is None
        assert session.exec(select(ChunkJudgmentRow)).one().prompts_used is None
        assert session.get(Generation, 1).answer == "a"
