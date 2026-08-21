"""SQLite engine/session for the Sprint 7b persistence layer
(docs/ROADMAP.md, Sprint 7).

A single local SQLite file (`data/app.db` by default), gitignored like
every other generated data artifact in this project (`.gitignore`) —
runtime state, not source. `BERGSON_DB_PATH` overrides the path; tests
point it at an isolated in-memory or tmp-file engine via
`app.dependency_overrides[get_session]` (see tests/test_persistence.py)
rather than touching the real dev database.

`get_engine` is process-wide, lazily built on first use — same
`lru_cache`-singleton convention as `src/api/dependencies.py`'s Qdrant
client and models. Tables are created on that same first access so
neither a production run nor a test needs a separate explicit migration
step.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Column, Connection, Engine, Table, inspect, text
from sqlmodel import Session, SQLModel, create_engine

# Imported for its side effect of registering table classes on
# SQLModel.metadata before create_all() runs below.
from src.api import models  # noqa: F401

DEFAULT_DB_PATH = "data/app.db"
DB_PATH_ENV_VAR = "BERGSON_DB_PATH"


def _db_url() -> str:
    path = os.environ.get(DB_PATH_ENV_VAR, DEFAULT_DB_PATH)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _backfill_generations_retrieval_confidence_tier(conn: Connection) -> None:
    """retrieval-confidence-split moved this column off `Evaluation` onto
    `Generation`. A pre-split dev DB still has the value sitting on the
    matching `evaluations` row (if that generation was ever evaluated) —
    reuse it there via `generations.id = evaluations.generation_id`.
    Generations that were never evaluated have no source value to reuse,
    so they're marked "unknown" rather than left NULL, since the model
    declares the column required.
    """
    conn.execute(
        text(
            """
            UPDATE generations
            SET retrieval_confidence_tier = (
                SELECT evaluations.retrieval_confidence_tier
                FROM evaluations
                WHERE evaluations.generation_id = generations.id
            )
            WHERE EXISTS (
                SELECT 1 FROM evaluations
                WHERE evaluations.generation_id = generations.id
            )
            """
        )
    )
    conn.execute(
        text(
            "UPDATE generations SET retrieval_confidence_tier = 'unknown' "
            "WHERE retrieval_confidence_tier IS NULL"
        )
    )


# Backfill for a *required* column that create_all() can't add on its own
# (see _sync_additive_columns). Keyed by (table, column); registered by
# hand alongside whatever model change introduced the column, since only
# that change's author knows where the old value should come from.
COLUMN_BACKFILLS: dict[tuple[str, str], Callable[[Connection], None]] = {
    ("generations", "retrieval_confidence_tier"): _backfill_generations_retrieval_confidence_tier,
}


def _add_column(conn: Connection, engine: Engine, table: Table, column: Column) -> None:
    col_type = column.type.compile(dialect=engine.dialect)
    ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
    if column.server_default is not None:
        ddl += f" DEFAULT {column.server_default.arg}"
    conn.execute(text(ddl))


def _sync_additive_columns(engine: Engine) -> None:
    """Add newly-declared columns to tables that already exist on disk.

    `create_all()` only creates missing tables — it never diffs an
    existing table against the current model, so a field added to a
    model (e.g. `Generation.retrieval_confidence_tier`) silently goes
    missing from an already-created dev DB and every query against it
    404s/500s with `no such column`. A column that's nullable or carries
    a SQL-level default is added as-is — existing rows just get NULL/the
    default. A required column with no default is only added if it has
    an entry in `COLUMN_BACKFILLS` to populate existing rows from;
    otherwise this fails loudly and tells the developer to delete the
    gitignored dev DB (`data/app.db`) rather than silently leaving rows
    with a required column undefined.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                if column.nullable or column.server_default is not None:
                    _add_column(conn, engine, table, column)
                    continue
                backfill = COLUMN_BACKFILLS.get((table.name, column.name))
                if backfill is None:
                    raise RuntimeError(
                        f"{table.name}.{column.name} is a new required column "
                        "with no default and no registered backfill in "
                        "COLUMN_BACKFILLS, so it can't be auto-migrated onto "
                        "existing rows. Delete the gitignored dev DB "
                        f"({_db_url()}) and let it recreate, or register a "
                        "backfill for it."
                    )
                _add_column(conn, engine, table, column)
                backfill(conn)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(_db_url(), connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    _sync_additive_columns(engine)
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
