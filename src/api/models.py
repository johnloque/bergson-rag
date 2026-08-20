"""SQLModel table definitions for the Sprint 7b persistence layer
(docs/ROADMAP.md, Sprint 7 — "SQLite persistence").

SQLModel over raw sqlite3 or a heavier ORM: it pairs naturally with
FastAPI's existing Pydantic models (`src/api/schemas.py`) rather than
hand-rolling a second validation layer — same "reuse a fit-for-purpose
library" discipline as LiteLLM (`src/generation/generate.py`) or RAGAS
(`src/generation/faithfulness.py`).

## Known limitation: chunk text is not snapshotted

`retrieved_chunks` stores only `chunk_id`, `rank`, and `score` per turn —
never the chunk's text/work_id/section_path. If the corpus is later
reindexed, a historical turn's chunk references could point to content
that has since changed. `/evaluate` and `GET /turns/{id}` re-fetch chunk
content live from Qdrant by `chunk_id` when they need it
(`src/api/converters.py:fetch_chunk_input`) rather than reading a stored
snapshot. Accepted as a known limitation for this single-user local demo —
snapshotting full chunk text for every turn is unnecessary storage cost
here, not solved on this branch.

## Table <-> class naming

Table names are explicit (`__tablename__`) to match the plural names in
the schema design (docs/ROADMAP.md) rather than SQLModel's default
lowercased-singular-class-name convention.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from src.generation.chunk_judgment import ChunkJudgment


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)
    # Sprint 8 (frontend) addition: an explicit rename overrides the
    # sidebar's default first-query-derived title. None until the user
    # renames the conversation.
    title: str | None = Field(default=None)


class Turn(SQLModel, table=True):
    __tablename__ = "turns"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    query: str
    created_at: datetime = Field(default_factory=_utcnow)


class RetrievedChunkRow(SQLModel, table=True):
    """One row per chunk shown to the user for a turn — from `/retrieve` or
    the chunks the client passed into `/generate`. Composite primary key
    (turn_id, chunk_id): a turn's chunk set is replaced wholesale on each
    `/generate` call against that turn (`src/api/persistence.py`), not
    accumulated, since a regeneration may curate a different chunk
    selection than the initial generation."""

    __tablename__ = "retrieved_chunks"

    turn_id: int = Field(foreign_key="turns.id", primary_key=True)
    chunk_id: str = Field(primary_key=True)
    rank: int
    score: float


class Generation(SQLModel, table=True):
    __tablename__ = "generations"

    id: int | None = Field(default=None, primary_key=True)
    turn_id: int = Field(foreign_key="turns.id", index=True)
    model: str
    chunk_ids: list[str] = Field(sa_column=Column(JSON))
    answer: str
    # Snapshot of the chunk_judgments dict actually threaded into the
    # prompt for this generation (src/generation/prompt.py) — None when
    # none applied, distinct from an empty dict (see src/api/main.py's
    # /generate override-vs-auto-load rule).
    chunk_judgments_used: dict[str, ChunkJudgment] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=_utcnow)


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluations"

    id: int | None = Field(default=None, primary_key=True)
    generation_id: int = Field(foreign_key="generations.id", index=True)
    structural_flags: dict = Field(sa_column=Column(JSON))
    faithfulness_annotations: dict = Field(sa_column=Column(JSON))
    retrieval_confidence_tier: str
    should_auto_expand: bool
    created_at: datetime = Field(default_factory=_utcnow)


class ChunkJudgmentRow(SQLModel, table=True):
    """Composite primary key (turn_id, chunk_id) — upsert semantics
    (`src/api/persistence.py:upsert_chunk_judgment`): a chunk judged twice
    in the same turn overwrites the existing row, never accumulates
    duplicates."""

    __tablename__ = "chunk_judgments"

    turn_id: int = Field(foreign_key="turns.id", primary_key=True)
    chunk_id: str = Field(primary_key=True)
    # ChunkJudgmentLabel (src/generation/chunk_judgment.py) is a Literal —
    # SQLModel's column-type inference doesn't handle Literal (only Enum),
    # so this is plain str; validity of the three label values is already
    # enforced upstream by judge_chunk's own response parsing
    # (src/generation/chunk_judge.py:_parse_response).
    label: str
    justification: str
    model: str
    created_at: datetime = Field(default_factory=_utcnow)
