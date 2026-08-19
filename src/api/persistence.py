"""DB-facing helper functions for the Sprint 7b API (docs/ROADMAP.md,
Sprint 7). `src/api/main.py` orchestrates; this module is where the actual
SQLModel session operations live, keeping the endpoint functions thin —
same "thin wrapper around an already-tested function" discipline Sprint 7a
established for the compute endpoints, applied here to persistence instead.

Every "not found" case (unknown turn_id, generation_id, conversation_id)
raises `fastapi.HTTPException(404, ...)` directly from here rather than
via a sentinel return value the caller has to check — the same
"endpoint-shaped errors surface immediately" discipline `src/api/main.py`
already uses for provider failures (its `OpenAIError` -> 503 handler).
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException
from sqlmodel import Session, select

from src.api.models import (
    ChunkJudgmentRow,
    Conversation,
    Evaluation,
    Generation,
    RetrievedChunkRow,
    Turn,
)
from src.api.schemas import ChunkInput
from src.generation.chunk_judgment import ChunkJudgment


def resolve_turn(
    session: Session,
    conversation_id: int | None,
    turn_id: int | None,
    query: str,
) -> Turn:
    """`/generate`'s turn-resolution rule (docs/ROADMAP.md):
    - `turn_id` given: this is a regeneration within that existing turn —
      looked up as-is (404 if unknown), `query` is not used.
    - `turn_id` absent, `conversation_id` given: a new turn in that
      existing conversation (404 if `conversation_id` is unknown).
    - both absent: a brand new conversation and its first turn.
    """
    if turn_id is not None:
        turn = session.get(Turn, turn_id)
        if turn is None:
            raise HTTPException(status_code=404, detail=f"turn_id {turn_id} not found")
        return turn

    if conversation_id is not None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=404, detail=f"conversation_id {conversation_id} not found"
            )
    else:
        conversation = Conversation()
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

    turn = Turn(conversation_id=conversation.id, query=query)
    session.add(turn)
    session.commit()
    session.refresh(turn)
    return turn


def save_retrieved_chunks(session: Session, turn_id: int, chunks: Sequence[ChunkInput]) -> None:
    """Replaces `turn_id`'s chunk set wholesale — not accumulated — since a
    regeneration may pass a differently curated chunk selection than the
    turn's initial `/generate` call, and `retrieved_chunks` should reflect
    what was actually shown/used most recently, not a growing history."""
    existing = session.exec(
        select(RetrievedChunkRow).where(RetrievedChunkRow.turn_id == turn_id)
    ).all()
    for row in existing:
        session.delete(row)
    for rank, chunk in enumerate(chunks):
        score = chunk.score if chunk.score is not None else 0.0
        session.add(
            RetrievedChunkRow(turn_id=turn_id, chunk_id=chunk.chunk_id, rank=rank, score=score)
        )
    session.commit()


def load_chunk_judgments(session: Session, turn_id: int) -> dict[str, ChunkJudgment]:
    rows = session.exec(select(ChunkJudgmentRow).where(ChunkJudgmentRow.turn_id == turn_id)).all()
    return {
        row.chunk_id: ChunkJudgment(label=row.label, justification=row.justification)
        for row in rows
    }


def upsert_chunk_judgment(
    session: Session,
    turn_id: int,
    chunk_id: str,
    label: str,
    justification: str,
    model: str,
) -> ChunkJudgmentRow:
    """A chunk judged twice in the same turn overwrites, never accumulates
    duplicate rows (docs/ROADMAP.md's `chunk_judgments` schema note)."""
    if session.get(Turn, turn_id) is None:
        raise HTTPException(status_code=404, detail=f"turn_id {turn_id} not found")

    row = session.get(ChunkJudgmentRow, (turn_id, chunk_id))
    if row is None:
        row = ChunkJudgmentRow(turn_id=turn_id, chunk_id=chunk_id)
    row.label = label
    row.justification = justification
    row.model = model
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def save_generation(
    session: Session,
    turn_id: int,
    model: str,
    chunk_ids: list[str],
    answer: str,
    chunk_judgments_used: dict[str, ChunkJudgment] | None,
) -> Generation:
    generation = Generation(
        turn_id=turn_id,
        model=model,
        chunk_ids=chunk_ids,
        answer=answer,
        chunk_judgments_used=chunk_judgments_used,
    )
    session.add(generation)
    session.commit()
    session.refresh(generation)
    return generation


def get_generation_or_404(session: Session, generation_id: int) -> Generation:
    generation = session.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status_code=404, detail=f"generation_id {generation_id} not found")
    return generation


def get_retrieved_chunk_scores(session: Session, turn_id: int) -> dict[str, float]:
    rows = session.exec(select(RetrievedChunkRow).where(RetrievedChunkRow.turn_id == turn_id)).all()
    return {row.chunk_id: row.score for row in rows}


def save_evaluation(
    session: Session,
    generation_id: int,
    structural_flags: dict,
    faithfulness_annotations: dict,
    retrieval_confidence_tier: str,
    should_auto_expand: bool,
) -> Evaluation:
    evaluation = Evaluation(
        generation_id=generation_id,
        structural_flags=structural_flags,
        faithfulness_annotations=faithfulness_annotations,
        retrieval_confidence_tier=retrieval_confidence_tier,
        should_auto_expand=should_auto_expand,
    )
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)
    return evaluation


def get_turn_or_404(session: Session, turn_id: int) -> Turn:
    turn = session.get(Turn, turn_id)
    if turn is None:
        raise HTTPException(status_code=404, detail=f"turn_id {turn_id} not found")
    return turn


def get_turn_generations(session: Session, turn_id: int) -> list[Generation]:
    return list(
        session.exec(
            select(Generation).where(Generation.turn_id == turn_id).order_by(Generation.id)
        ).all()
    )


def get_evaluation_for_generation(session: Session, generation_id: int) -> Evaluation | None:
    return session.exec(select(Evaluation).where(Evaluation.generation_id == generation_id)).first()


def get_retrieved_chunks(session: Session, turn_id: int) -> list[RetrievedChunkRow]:
    return list(
        session.exec(
            select(RetrievedChunkRow)
            .where(RetrievedChunkRow.turn_id == turn_id)
            .order_by(RetrievedChunkRow.rank)
        ).all()
    )


def get_conversation_or_404(session: Session, conversation_id: int) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"conversation_id {conversation_id} not found")
    return conversation


def get_conversation_turns(session: Session, conversation_id: int) -> list[Turn]:
    return list(
        session.exec(
            select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.id)
        ).all()
    )
