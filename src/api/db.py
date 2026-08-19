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
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine
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


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(_db_url(), connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
