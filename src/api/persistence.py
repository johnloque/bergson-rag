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
    """Replaces `turn_id`'s chunk set wholesale. Callers (src/api/main.py's
    `generate`) must only invoke this for a turn's *initial* `/generate`
    call — a regeneration's chunk list is the client's included subset with
    exclusions already filtered out, and saving that here would shrink the
    turn's persisted retrieved-chunk set to just the survivors, permanently
    losing the excluded chunks (they're tracked separately, correctly, per
    generation via `Generation.chunk_ids`)."""
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
    """404s if `turn_id` no longer exists — re-checked here (not just at
    `resolve_turn`, the start of `/generate`) because the conversation may
    have been deleted mid-request, while `generate_from_chunks` was
    running. Without this, since SQLite FKs aren't enforced (module
    docstring), the insert would silently succeed and leave an orphaned
    `Generation` row under a deleted turn."""
    if session.get(Turn, turn_id) is None:
        raise HTTPException(status_code=404, detail=f"turn_id {turn_id} not found")
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
    """404s if `generation_id` no longer exists — same rationale as
    `save_generation`'s check: the conversation may have been deleted
    mid-request, while `generate_evaluation` was running, and SQLite FKs
    aren't enforced here so an unchecked insert would silently orphan this
    row instead of surfacing the deletion.

    Upserts on `generation_id` (mirrors `upsert_chunk_judgment`'s
    (turn_id, chunk_id) upsert): `/evaluate` (src/api/main.py) already
    checks for an existing evaluation before rerunning the LLM check, but
    two concurrent `/evaluate` calls for the same `generation_id` could both
    pass that check before either commits — upserting here keeps that race
    from leaving duplicate rows for one generation."""
    if session.get(Generation, generation_id) is None:
        raise HTTPException(status_code=404, detail=f"generation_id {generation_id} not found")
    evaluation = get_evaluation_for_generation(session, generation_id)
    if evaluation is None:
        evaluation = Evaluation(generation_id=generation_id)
    evaluation.structural_flags = structural_flags
    evaluation.faithfulness_annotations = faithfulness_annotations
    evaluation.retrieval_confidence_tier = retrieval_confidence_tier
    evaluation.should_auto_expand = should_auto_expand
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


# --- Sprint 8 (frontend) additions ------------------------------------------
#
# The sidebar (docs/ROADMAP.md, Sprint 8, Screen 2) needs to enumerate
# conversations, rename them, and delete them — none of which Sprint 7
# exposed (it only shipped lookup-by-id). Added here rather than deferred to
# a client-side workaround since there is no other way to reconstruct "the
# list of conversations" or "the last conversation" from persisted state.


def list_conversations(session: Session) -> list[Conversation]:
    """Newest first — what both the sidebar list and the landing page's
    "last conversation" lookup need."""
    return list(session.exec(select(Conversation).order_by(Conversation.id.desc())).all())


def get_first_turn_query(session: Session, conversation_id: int) -> str | None:
    """The earliest turn's query in a conversation — the raw material for
    the sidebar's auto-generated title (truncation is a display concern,
    left to the frontend)."""
    turn = session.exec(
        select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.id).limit(1)
    ).first()
    return turn.query if turn is not None else None


def rename_conversation(session: Session, conversation_id: int, title: str) -> Conversation:
    conversation = get_conversation_or_404(session, conversation_id)
    conversation.title = title
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def delete_conversation(session: Session, conversation_id: int) -> None:
    """Cascades manually — SQLite foreign keys aren't enforced with
    `ON DELETE CASCADE` here (no migration system, `src/api/db.py`), so
    child rows across every table keyed by turn_id/generation_id are
    removed explicitly, deepest first."""
    conversation = get_conversation_or_404(session, conversation_id)
    turn_ids = [t.id for t in get_conversation_turns(session, conversation_id)]
    for turn_id in turn_ids:
        for generation in get_turn_generations(session, turn_id):
            for evaluation in session.exec(
                select(Evaluation).where(Evaluation.generation_id == generation.id)
            ).all():
                session.delete(evaluation)
            session.delete(generation)
        for row in get_retrieved_chunks(session, turn_id):
            session.delete(row)
        for row in session.exec(
            select(ChunkJudgmentRow).where(ChunkJudgmentRow.turn_id == turn_id)
        ).all():
            session.delete(row)
        session.delete(session.get(Turn, turn_id))
    session.delete(conversation)
    session.commit()
