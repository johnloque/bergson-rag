"""Unit tests for `scripts/extract_source_metadata.py` (Sprint 12, Sources
sub-page, `feat/presentation-and-guide-content`) — the publisher extraction
feeding `frontend/src/lib/sourceMetadata.ts`, and the `sourceDesc` guard
covering the known 1888_EDIC copy-paste error (`docs/xml_audit_report.md`
Sec. 5).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import scripts.extract_source_metadata as extract_source_metadata
from src.works import WORKS

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"
SOURCE_METADATA_TS = REPO_ROOT / "frontend" / "src" / "lib" / "sourceMetadata.ts"

_corpus_skip = pytest.mark.skipif(
    not RAW_SRC_DIR.exists(), reason="corpus not fetched — run scripts/fetch_corpus.sh first"
)

KNOWN_SOURCE_DESC_MISMATCHES = ("1888_EDIC",)


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
