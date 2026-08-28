"""paragraph_id -> chunk_id(s) lookup over already-chunked data (Sprint 11,
`feat/backend-reference-data`).

Paragraph IDs are stable across re-chunking (assigned once at ingestion —
`src/ingestion/parser.py`); chunk_ids are not (`src/ingestion/chunking.py`
renumbers `{work_id}_c{n}` from scratch on every chunking run, and a
different `TARGET_WORDS`/`MAX_STANDALONE_WORDS` changes chunk boundaries
entirely). `docs/gold_dataset_protocol.md` expresses ground truth directly
in `chunk_ids` scraped by hand from the chunk correspondence export at
annotation time — every re-chunking event (Sprint 14's chunk-size
experiments) invalidates all of those by-hand lookups. This module resolves
a `(work_id, paragraph_id)` pair against *whatever chunking
`data/processed/chunks/` currently holds* — no new XML parsing, just a
lookup over `Chunk.paragraph_ids` (`src/ingestion/models.py`), already
produced by ingestion.

A reusable function, not a one-off script: intended to be called
repeatedly, for many paragraph_ids at a time, whenever the gold dataset
needs remapping after a re-chunking event — see `resolve_chunk_ids` below.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"


@cache
def _load_chunks(work_id: str, chunks_dir: Path) -> tuple[dict, ...]:
    """`{chunk_id, paragraph_ids, ...}` records for `work_id`, cached per
    `(work_id, chunks_dir)` — this module is meant to be called once per
    paragraph_id in a batch (a gold-dataset remap), not to re-read the same
    work's chunk file from disk on every call."""
    path = chunks_dir / f"{work_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"no chunk file for work_id {work_id!r} at {path} — has "
            "`python scripts/run_ingestion.py` (or equivalent chunking step) been run?"
        )
    return tuple(json.loads(path.read_text(encoding="utf-8")))


def resolve_chunk_ids(
    work_id: str, paragraph_id: str, chunks_dir: Path = DEFAULT_CHUNKS_DIR
) -> tuple[str, ...]:
    """chunk_id(s) in `chunks_dir` whose `paragraph_ids` currently include
    `paragraph_id`. Chunking never splits a paragraph across chunks and
    never merges paragraphs from different sections into one chunk in a way
    that would let the same paragraph appear in two chunks
    (`src/ingestion/chunking.py`), so this is normally exactly one chunk_id
    — returned as a tuple regardless, rather than assuming uniqueness, since
    this function's whole point is to stay correct across chunking schemes
    it doesn't control."""
    chunks = _load_chunks(work_id, chunks_dir)
    return tuple(chunk["chunk_id"] for chunk in chunks if paragraph_id in chunk["paragraph_ids"])


def resolve_chunk_id(work_id: str, paragraph_id: str, chunks_dir: Path = DEFAULT_CHUNKS_DIR) -> str:
    """Convenience wrapper for the common case of a single expected match —
    raises if `paragraph_id` resolves to zero or more than one chunk_id,
    rather than silently picking one."""
    matches = resolve_chunk_ids(work_id, paragraph_id, chunks_dir)
    if len(matches) != 1:
        raise ValueError(
            f"{work_id}/{paragraph_id} resolved to {len(matches)} chunk_ids {matches!r}, "
            "expected exactly one — use resolve_chunk_ids directly if that's expected"
        )
    return matches[0]
