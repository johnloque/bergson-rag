"""Unit tests for `scripts/extract_source_metadata.py` (Sprint 12, Sources
sub-page, `feat/presentation-and-guide-content`) — the publisher extraction
feeding `frontend/src/lib/sourceMetadata.ts`, and the `sourceDesc` guard
covering the known 1888_EDIC copy-paste error (`docs/xml_audit_report.md`
Sec. 5).
"""

from __future__ import annotations

import csv
import json
import re
from itertools import pairwise
from pathlib import Path

import pytest

import scripts.extract_source_metadata as extract_source_metadata
import scripts.extract_text_metadata as extract_text_metadata
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR
from src.works import TEXTS, WORKS, TextMetadata, resolve_paragraph_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"
SOURCE_METADATA_TS = REPO_ROOT / "frontend" / "src" / "lib" / "sourceMetadata.ts"

_corpus_skip = pytest.mark.skipif(
    not RAW_SRC_DIR.exists(), reason="corpus not fetched — run scripts/fetch_corpus.sh first"
)

_chunks_skip = pytest.mark.skipif(
    not DEFAULT_CHUNKS_DIR.exists() or not any(DEFAULT_CHUNKS_DIR.iterdir()),
    reason="data/processed/chunks not built — run the ingestion/chunking pipeline first",
)

KNOWN_SOURCE_DESC_MISMATCHES = ("1888_EDIC",)
ANTHOLOGY_WORK_IDS = ("1919_ES", "1934_PM")


@_corpus_skip
@pytest.mark.parametrize("work_id", list(WORKS))
def test_publisher_is_extracted_from_publicationstmt_not_hardcoded(work_id):
    """Reads `publicationStmt/publisher` straight out of the raw XML text —
    independently of `extract_publisher` — and checks the function's return
    value against it, so a hardcoded stub in the extraction function itself
    couldn't pass this test by coincidence."""
    raw = (RAW_SRC_DIR / f"{work_id}.xml").read_text(encoding="utf-8")
    match = re.search(r"<publicationStmt>.*?<publisher>(.*?)</publisher>", raw, re.S)
    assert match is not None, f"{work_id}: no publisher element in raw XML"
    assert extract_source_metadata.extract_publisher(work_id) == match.group(1).strip()


@_corpus_skip
def test_publisher_is_non_empty_for_all_eight_works():
    for work_id in WORKS:
        publisher = extract_source_metadata.extract_publisher(work_id)
        assert publisher, f"{work_id}: empty publisher"


@_corpus_skip
@pytest.mark.parametrize("work_id", KNOWN_SOURCE_DESC_MISMATCHES)
def test_known_source_desc_mismatch_still_raises(work_id):
    """Regression pin, not a one-off observation: `docs/xml_audit_report.md`
    flagged 1888_EDIC's `sourceDesc` as describing the wrong work. If
    bergson-synoptique ever fixes this upstream, this test starts failing —
    that's the intended signal to remove the work_id from
    `KNOWN_SOURCE_DESC_MISMATCHES` here and in `sourceMetadata.ts`, not to
    silence the test."""
    with pytest.raises(extract_source_metadata.SourceDescMismatch):
        extract_source_metadata.check_source_desc(work_id)


@_corpus_skip
@pytest.mark.parametrize("work_id", [w for w in WORKS if w not in KNOWN_SOURCE_DESC_MISMATCHES])
def test_other_works_source_desc_matches_their_own_title(work_id):
    """The guard isn't just always-raising — every other work's sourceDesc
    genuinely does mention its own title."""
    extract_source_metadata.check_source_desc(work_id)  # must not raise


@_corpus_skip
def test_source_metadata_ts_matches_fresh_extraction():
    """Ties the hand-transcribed `sourceMetadata.ts`'s `PUBLISHERS` back to
    a fresh extraction, so the two can't silently drift apart if the source
    XML ever changes — same discipline as
    `tests/test_works.py::test_texts_table_matches_fresh_extraction`."""
    ts_source = SOURCE_METADATA_TS.read_text(encoding="utf-8")
    match = re.search(r"PUBLISHERS:\s*Record<string,\s*string>\s*=\s*\{(.*?)\n\}", ts_source, re.S)
    assert match is not None, "PUBLISHERS table not found in sourceMetadata.ts"
    committed = dict(re.findall(r"'(\w+)':\s*'([^']*)'", match.group(1)))

    assert set(committed) == set(WORKS)
    for work_id, committed_publisher in committed.items():
        assert committed_publisher == extract_source_metadata.extract_publisher(work_id), (
            f"{work_id}: sourceMetadata.ts says {committed_publisher!r}, fresh extraction says "
            f"{extract_source_metadata.extract_publisher(work_id)!r} — re-run "
            "scripts/extract_source_metadata.py and update the committed table"
        )


def test_known_source_desc_mismatches_list_matches_ts_file():
    """`tests/test_source_metadata.py`'s own `KNOWN_SOURCE_DESC_MISMATCHES`
    and `sourceMetadata.ts`'s `KNOWN_SOURCE_DESC_MISMATCHES` must name the
    same work(s) — otherwise the frontend's explicit warning and this
    backend regression pin could silently drift apart."""
    ts_source = SOURCE_METADATA_TS.read_text(encoding="utf-8")
    match = re.search(
        r"KNOWN_SOURCE_DESC_MISMATCHES:\s*readonly string\[\]\s*=\s*\[(.*?)\]", ts_source, re.S
    )
    assert match is not None, "KNOWN_SOURCE_DESC_MISMATCHES not found in sourceMetadata.ts"
    ts_ids = tuple(re.findall(r"'(\w+)'", match.group(1)))
    assert ts_ids == KNOWN_SOURCE_DESC_MISMATCHES


# -- Citation codes (`feat/sources-citation-codes`) --------------------------


def _ts_work_codes() -> list[str]:
    ts_source = SOURCE_METADATA_TS.read_text(encoding="utf-8")
    match = re.search(r"WORK_CODES:\s*readonly string\[\]\s*=\s*\[(.*?)\]", ts_source, re.S)
    assert match is not None, "WORK_CODES not found in sourceMetadata.ts"
    return re.findall(r"'(\w+)'", match.group(1))


def _ts_text_ranges() -> dict[str, list[tuple[str, tuple[str, str] | None]]]:
    ts_source = SOURCE_METADATA_TS.read_text(encoding="utf-8")
    block = re.search(r"ANTHOLOGY_TEXT_RANGES:.*?=\s*\{(.*?)\n\}", ts_source, re.S)
    assert block is not None, "ANTHOLOGY_TEXT_RANGES not found in sourceMetadata.ts"
    ranges = {}
    for work_id, body in re.findall(r"'(\w+)':\s*\[(.*?)\n  \]", block.group(1), re.S):
        ranges[work_id] = [
            (title, (first, last) if first else None)
            for _, title, first, last in re.findall(
                r"title:\s*(['\"])(.*?)\1,\s*chunkRange:\s*"
                r"(?:\[\s*'([^']*)',\s*'([^']*)',?\s*\]|null)",
                body,
                re.S,
            )
        ]
    return ranges


def _chunk_number(chunk_id: str) -> int:
    return int(chunk_id.rsplit("_c", 1)[1])


def test_every_work_in_works_py_has_its_code_in_sources_data():
    assert _ts_work_codes() == list(WORKS)


@pytest.mark.parametrize("work_id", list(WORKS))
def test_work_code_is_the_work_id_resolve_paragraph_metadata_uses(work_id):
    """An unknown work_id falls back to itself as title, so a matching
    title/year shows the code is the key `resolve_paragraph_metadata` reads."""
    assert work_id in _ts_work_codes()
    resolved = resolve_paragraph_metadata(work_id, f"{work_id}_p1")
    assert (resolved.work_title, resolved.work_year) == (WORKS[work_id].title, WORKS[work_id].year)


def test_text_ranges_cover_exactly_the_texts_table():
    ranges = _ts_text_ranges()
    assert set(ranges) == set(ANTHOLOGY_WORK_IDS) == set(TEXTS)
    for work_id, entries in ranges.items():
        assert [title for title, r in entries if r is not None] == [t.title for t in TEXTS[work_id]]


@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_no_empty_or_placeholder_range(work_id):
    for title, chunk_range in _ts_text_ranges()[work_id]:
        if chunk_range is None:
            continue
        first, last = chunk_range
        for chunk_id in (first, last):
            assert re.fullmatch(rf"{work_id}_c\d+", chunk_id), (title, chunk_id)
        assert _chunk_number(first) <= _chunk_number(last), title


@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_text_ranges_within_an_anthology_do_not_overlap(work_id):
    spans = sorted(
        (_chunk_number(r[0]), _chunk_number(r[1])) for _, r in _ts_text_ranges()[work_id] if r
    )
    for (_, prev_end), (start, _) in pairwise(spans):
        assert start > prev_end


@_chunks_skip
def test_every_indexed_work_prefix_has_a_code():
    prefixes = set()
    for path in DEFAULT_CHUNKS_DIR.glob("*.json"):
        for chunk in json.loads(path.read_text(encoding="utf-8")):
            prefixes.add(chunk["chunk_id"].rsplit("_c", 1)[0])
    assert prefixes == set(_ts_work_codes())


@_chunks_skip
@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_range_endpoints_exist_and_resolve_to_their_text(work_id):
    chunks = {
        c["chunk_id"]: c
        for c in json.loads((DEFAULT_CHUNKS_DIR / f"{work_id}.json").read_text(encoding="utf-8"))
    }
    for title, chunk_range in _ts_text_ranges()[work_id]:
        if chunk_range is None:
            continue
        for chunk_id in chunk_range:
            assert chunk_id in chunks, f"{title}: {chunk_id} not in the index"
            for paragraph_id in chunks[chunk_id]["paragraph_ids"]:
                assert resolve_paragraph_metadata(work_id, paragraph_id).text_title == title


@_corpus_skip
@_chunks_skip
@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_text_ranges_match_fresh_computation(work_id):
    assert _ts_text_ranges()[work_id] == extract_source_metadata.anthology_text_ranges(work_id)


# Synthetic corpus/chunks for the range-building logic — fast, no real data.


def _write_corpus(tmp_path: Path, divs: list[tuple[str, str, int]]) -> None:
    """TESTWORK.xml with one `art` div per (xml_id, head, n_paragraphs)."""
    with (tmp_path / "metadata.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["id", "txmid", "textorder", "date", "title", "pages"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "TESTWORK",
                "txmid": "99",
                "textorder": "1",
                "date": "1900",
                "title": "Test Work",
                "pages": "10",
            }
        )
    body = "".join(
        f'<div type="art" xml:id="{xml_id}"><head>{head}</head>'
        + "".join(f"<p>Paragraph {i} of {head}.</p>" for i in range(n))
        + "</div>"
        for xml_id, head, n in divs
    )
    (tmp_path / "TESTWORK.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><TEI xmlns="http://www.tei-c.org/ns/1.0">'
        "<teiHeader><fileDesc><titleStmt><title>Test Work</title></titleStmt>"
        "<publicationStmt><date>1900</date></publicationStmt>"
        "<sourceDesc><p>Test source.</p></sourceDesc></fileDesc></teiHeader>"
        f"<text><body>{body}</body></text></TEI>",
        encoding="utf-8",
    )


def _write_chunks(chunks_dir: Path, paragraphs_per_chunk: list[list[int]]) -> Path:
    chunks_dir.mkdir()
    chunks = [
        {"chunk_id": f"TESTWORK_c{n}", "paragraph_ids": [f"TESTWORK_p{p}" for p in paragraphs]}
        for n, paragraphs in paragraphs_per_chunk
    ]
    (chunks_dir / "TESTWORK.json").write_text(json.dumps(chunks), encoding="utf-8")
    return chunks_dir


@pytest.fixture
def synthetic_anthology(tmp_path, monkeypatch):
    _write_corpus(
        tmp_path,
        [("TW_1901_A", "Dated A", 2), ("TW_NOYEAR", "Undated", 1), ("TW_1902_B", "Dated B", 2)],
    )
    monkeypatch.setattr(extract_text_metadata, "RAW_SRC_DIR", tmp_path)
    monkeypatch.setattr(
        extract_source_metadata,
        "TEXTS",
        {"TESTWORK": (TextMetadata("Dated A", 1901, 1, 2), TextMetadata("Dated B", 1902, 4, 5))},
    )
    return tmp_path


def test_excluded_text_is_listed_without_a_range(synthetic_anthology):
    chunks_dir = _write_chunks(
        synthetic_anthology / "chunks", [(1, [1]), (2, [2]), (3, [3]), (4, [4]), (5, [5])]
    )
    assert extract_source_metadata.anthology_text_ranges("TESTWORK", chunks_dir) == [
        ("Dated A", ("TESTWORK_c1", "TESTWORK_c2")),
        ("Undated", None),
        ("Dated B", ("TESTWORK_c4", "TESTWORK_c5")),
    ]


def test_non_contiguous_chunk_numbering_raises(synthetic_anthology):
    chunks_dir = _write_chunks(
        synthetic_anthology / "chunks", [(1, [1]), (3, [2]), (4, [3]), (5, [4]), (6, [5])]
    )
    with pytest.raises(extract_source_metadata.MisleadingChunkRange, match="Dated A"):
        extract_source_metadata.anthology_text_ranges("TESTWORK", chunks_dir)


def test_overlapping_text_ranges_raise(synthetic_anthology, monkeypatch):
    """A chunk holding paragraphs of two texts would make their ranges share it."""
    monkeypatch.setattr(
        extract_source_metadata,
        "TEXTS",
        {"TESTWORK": (TextMetadata("Dated A", 1901, 1, 2), TextMetadata("Dated B", 1902, 3, 5))},
    )
    _write_corpus(synthetic_anthology, [("TW_1901_A", "Dated A", 2), ("TW_1902_B", "Dated B", 3)])
    chunks_dir = _write_chunks(
        synthetic_anthology / "chunks", [(1, [1]), (2, [2, 3]), (3, [4]), (4, [5])]
    )
    with pytest.raises(extract_source_metadata.MisleadingChunkRange, match="share chunks"):
        extract_source_metadata.anthology_text_ranges("TESTWORK", chunks_dir)
