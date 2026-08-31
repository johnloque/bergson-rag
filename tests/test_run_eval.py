"""Unit tests for eval/scripts/run_eval.py's gold dataset loading —
paragraph_ids column parsing and paragraph_id -> chunk_id resolution via
src.paragraph_chunk_map (feat/backend-reference-data), plus malformed-value
handling (fix/gold-dataset-paragraph-refs).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.scripts.run_eval import CHUNKS_DIR, GOLD_DATASET_PATH, load_gold_dataset
from src.paragraph_chunk_map import parse_paragraph_id

GOLD_CSV_HEADER = (
    "id;category;query;query_style;ground_truth_type;paragraph_ids;"
    "expected_anwser;vocabulary_type;difficulty;footnote_related"
)


def _write_chunks(chunks_dir: Path, work_id: str, chunks: list[dict]) -> None:
    chunks_dir.mkdir(parents=True, exist_ok=True)
    (chunks_dir / f"{work_id}.json").write_text(json.dumps(chunks), encoding="utf-8")


def _write_gold_csv(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([GOLD_CSV_HEADER, *rows]) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    "paragraph_id,expected",
    [
        ("1934_PM_p1", ("1934_PM", 1)),
        ("1907_EC_p316", ("1907_EC", 316)),
        ("1888_EDIC_p1", ("1888_EDIC", 1)),
    ],
)
def test_parse_paragraph_id_splits_from_the_end(paragraph_id, expected):
    assert parse_paragraph_id(paragraph_id) == expected


@pytest.mark.parametrize(
    "paragraph_id",
    [
        "1907_EC-notaparagraph",  # missing "_p" separator
        "1907_EC_pXX",  # no digits after "_p"
        "1907_EC_p",  # "_p" with nothing after it
    ],
)
def test_parse_paragraph_id_raises_for_malformed_value(paragraph_id):
    with pytest.raises(ValueError):
        parse_paragraph_id(paragraph_id)


def test_header_rename_loads_every_row(tmp_path):
    chunks_dir = tmp_path / "chunks"
    _write_chunks(
        chunks_dir,
        "1907_EC",
        [{"chunk_id": "1907_EC_c5", "paragraph_ids": ["1907_EC_p12", "1907_EC_p13"]}],
    )
    csv_path = tmp_path / "gold_dataset.csv"
    _write_gold_csv(
        csv_path, ["Q001;factuel;q;framed;single;1907_EC_p13;answer;bergsonien;facile;non"]
    )

    items = load_gold_dataset(csv_path, chunks_dir=chunks_dir)

    assert len(items) == 1
    assert items[0].chunk_ids == ("1907_EC_c5",)


def test_malformed_paragraph_id_missing_p_separator_is_flagged(tmp_path):
    csv_path = tmp_path / "gold_dataset.csv"
    _write_gold_csv(
        csv_path,
        ["Q001;factuel;q;framed;single;1907_EC-notaparagraph;answer;bergsonien;facile;non"],
    )

    with pytest.raises(ValueError, match="Q001"):
        load_gold_dataset(csv_path, chunks_dir=tmp_path / "chunks")


def test_malformed_paragraph_id_no_digits_after_p_is_flagged(tmp_path):
    csv_path = tmp_path / "gold_dataset.csv"
    _write_gold_csv(
        csv_path, ["Q001;factuel;q;framed;single;1907_EC_pXX;answer;bergsonien;facile;non"]
    )

    with pytest.raises(ValueError, match="Q001"):
        load_gold_dataset(csv_path, chunks_dir=tmp_path / "chunks")


def test_multi_ground_truth_paragraph_ids_resolve_independently(tmp_path):
    chunks_dir = tmp_path / "chunks"
    _write_chunks(
        chunks_dir, "1888_EDIC", [{"chunk_id": "1888_EDIC_c1", "paragraph_ids": ["1888_EDIC_p1"]}]
    )
    _write_chunks(
        chunks_dir,
        "1934_PM",
        [
            {"chunk_id": "1934_PM_c23", "paragraph_ids": ["1934_PM_p45"]},
            {"chunk_id": "1934_PM_c33", "paragraph_ids": ["1934_PM_p60"]},
        ],
    )
    csv_path = tmp_path / "gold_dataset.csv"
    _write_gold_csv(
        csv_path,
        [
            "Q007;définitionnel;q;framed;multi;1888_EDIC_p1,1934_PM_p45,1934_PM_p60;"
            "answer;mixte;facile;non"
        ],
    )

    items = load_gold_dataset(csv_path, chunks_dir=chunks_dir)

    assert items[0].chunk_ids == ("1888_EDIC_c1", "1934_PM_c23", "1934_PM_c33")


def test_same_paragraph_id_resolves_differently_under_different_chunking(tmp_path):
    """Portability check: re-chunking data/processed/chunks (a different
    TARGET_WORDS/MAX_STANDALONE_WORDS run) changes which chunk_id a
    paragraph_id resolves to, without touching the gold dataset itself —
    the actual benefit motivating this change."""
    csv_path = tmp_path / "gold_dataset.csv"
    _write_gold_csv(
        csv_path, ["Q001;factuel;q;framed;single;1907_EC_p13;answer;bergsonien;facile;non"]
    )

    coarse_dir = tmp_path / "chunks_coarse"
    _write_chunks(
        coarse_dir,
        "1907_EC",
        [{"chunk_id": "1907_EC_c5", "paragraph_ids": ["1907_EC_p12", "1907_EC_p13"]}],
    )
    fine_dir = tmp_path / "chunks_fine"
    _write_chunks(
        fine_dir, "1907_EC", [{"chunk_id": "1907_EC_c9", "paragraph_ids": ["1907_EC_p13"]}]
    )

    coarse_items = load_gold_dataset(csv_path, chunks_dir=coarse_dir)
    fine_items = load_gold_dataset(csv_path, chunks_dir=fine_dir)

    assert coarse_items[0].chunk_ids == ("1907_EC_c5",)
    assert fine_items[0].chunk_ids == ("1907_EC_c9",)
    assert coarse_items[0].chunk_ids != fine_items[0].chunk_ids


pytestmark_real_data = pytest.mark.skipif(
    not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.iterdir()),
    reason="data/processed/chunks not built — run the ingestion/chunking pipeline first",
)


@pytestmark_real_data
def test_known_items_resolve_to_prior_gold_chunk_ids():
    """Regression check against the real, currently-committed gold dataset
    and chunking: Q001, Q004, Q007's new paragraph_ids resolve to the same
    chunk_ids used in prior evaluation runs (cross-checked by hand in
    tests/test_paragraph_chunk_map.py at commit 5da96d6)."""
    items = {item.id: item for item in load_gold_dataset(GOLD_DATASET_PATH)}

    assert items["Q001"].chunk_ids == ("1907_EC_c5",)
    assert items["Q004"].chunk_ids == ("1900_R_c49",)
    assert items["Q007"].chunk_ids == (
        "1888_EDIC_c1",
        "1934_PM_c23",
        "1934_PM_c33",
        "1934_PM_c39",
    )
