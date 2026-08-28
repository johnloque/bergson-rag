"""Unit tests for src/paragraph_chunk_map.py (Sprint 11,
`feat/backend-reference-data`) — run against the real, currently-indexed
chunking under `data/processed/chunks/` (a gitignored build artifact, same
discipline as tests/test_ingestion.py's `raw/src` dependency).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR, resolve_chunk_id, resolve_chunk_ids

pytestmark = pytest.mark.skipif(
    not DEFAULT_CHUNKS_DIR.exists() or not any(DEFAULT_CHUNKS_DIR.iterdir()),
    reason="data/processed/chunks not built — run the ingestion/chunking pipeline first",
)

# Known, already-verified gold_dataset.csv mappings (eval/gold_dataset.csv,
# commit 5da96d6 "paragraph ids instead of chunk ids"), cross-checked by
# hand against the current data/processed/chunks/*.json at the time this
# test was written — Q001 (mono, single-chunk match), Q004 (mono), and Q007
# (multi-work, four paragraph_ids across two works).
Q001_WORK_ID = "1907_EC"
Q001_PARAGRAPH_ID = "1907_EC_p13"
Q001_CHUNK_ID = "1907_EC_c5"

Q004_WORK_ID = "1900_R"
Q004_PARAGRAPH_ID = "1900_R_p169"
Q004_CHUNK_ID = "1900_R_c49"

Q007_MAPPINGS = (
    ("1888_EDIC", "1888_EDIC_p1", "1888_EDIC_c1"),
    ("1934_PM", "1934_PM_p45", "1934_PM_c23"),
    ("1934_PM", "1934_PM_p60", "1934_PM_c33"),
    ("1934_PM", "1934_PM_p68", "1934_PM_c39"),
)


def test_q001_paragraph_resolves_to_gold_chunk():
    assert resolve_chunk_id(Q001_WORK_ID, Q001_PARAGRAPH_ID) == Q001_CHUNK_ID


def test_q004_paragraph_resolves_to_gold_chunk():
    assert resolve_chunk_id(Q004_WORK_ID, Q004_PARAGRAPH_ID) == Q004_CHUNK_ID


@pytest.mark.parametrize("work_id,paragraph_id,expected_chunk_id", Q007_MAPPINGS)
def test_q007_paragraphs_resolve_to_gold_chunks(work_id, paragraph_id, expected_chunk_id):
    assert resolve_chunk_id(work_id, paragraph_id) == expected_chunk_id


def test_resolve_chunk_ids_returns_tuple_for_matching_paragraph():
    assert resolve_chunk_ids(Q001_WORK_ID, Q001_PARAGRAPH_ID) == (Q001_CHUNK_ID,)


def test_resolve_chunk_ids_returns_empty_tuple_for_unknown_paragraph():
    assert resolve_chunk_ids(Q001_WORK_ID, "1907_EC_p999999") == ()


def test_resolve_chunk_id_raises_for_unknown_paragraph():
    with pytest.raises(ValueError):
        resolve_chunk_id(Q001_WORK_ID, "1907_EC_p999999")


def test_resolve_chunk_ids_raises_for_missing_work_chunk_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_chunk_ids("NOT_A_REAL_WORK", "NOT_A_REAL_WORK_p1", chunks_dir=tmp_path)


def test_every_paragraph_in_a_chunk_resolves_back_to_that_same_chunk():
    """Round-trip sanity check, not just the three hand-picked gold items:
    for every chunk in 1907_EC's current chunking, every paragraph_id it
    lists must resolve (uniquely) back to that same chunk_id."""
    import json

    chunks = json.loads((DEFAULT_CHUNKS_DIR / "1907_EC.json").read_text(encoding="utf-8"))
    for chunk in chunks:
        for paragraph_id in chunk["paragraph_ids"]:
            assert resolve_chunk_id("1907_EC", paragraph_id) == chunk["chunk_id"]
