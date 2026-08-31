"""Unit tests for src/ingestion, run against the real corpus (raw/src) —
no synthetic XML fixtures. Requires the corpus to be fetched first via
scripts/fetch_corpus.sh.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.chunking import chunk_work
from src.ingestion.parser import load_metadata, parse_work

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"

pytestmark = pytest.mark.skipif(
    not RAW_SRC_DIR.exists(),
    reason="corpus not fetched — run scripts/fetch_corpus.sh first",
)


def _load(work_id: str):
    meta = load_metadata(RAW_SRC_DIR / "metadata.csv")
    return parse_work(RAW_SRC_DIR / f"{work_id}.xml", meta[work_id])


# -- Paragraph numbering ----------------------------------------------------


def test_paragraph_numbering_is_sequential_and_unique_per_work():
    work = _load("1900_R")
    ids = [p.paragraph_id for p in work.paragraphs]
    assert len(ids) == len(set(ids)), "paragraph IDs must be unique within a work"
    assert [p.index for p in work.paragraphs] == list(range(1, len(work.paragraphs) + 1))
    assert all(pid == f"1900_R_p{i}" for i, pid in enumerate(ids, start=1))


def test_paragraph_numbering_is_stable_across_reruns():
    """Re-running ingestion on an unchanged corpus must not renumber
    paragraphs (Sprint 1 requirement, docs/ROADMAP.md)."""
    first = _load("1907_EC")
    second = _load("1907_EC")
    assert [p.paragraph_id for p in first.paragraphs] == [p.paragraph_id for p in second.paragraphs]
    assert [p.text for p in first.paragraphs] == [p.text for p in second.paragraphs]


# -- Page tracking -----------------------------------------------------------


def test_page_start_end_across_unnumbered_pb():
    """1888_EDIC's front matter has two <pb> with no @n before the first
    numbered page — a genuinely unnumbered page, not an encoding gap.
    Its paragraphs must get a relational display string, never a
    fabricated page number."""
    work = _load("1888_EDIC")
    front_paragraphs = [
        p for p in work.paragraphs if p.paragraph_id in ("1888_EDIC_p1", "1888_EDIC_p2")
    ]
    assert len(front_paragraphs) == 2
    for p in front_paragraphs:
        assert p.page_start.number is None
        assert p.page_end.number is None
        assert p.page_start.display == "avant la p. 1"

    first_numbered = next(p for p in work.paragraphs if p.page_start.number is not None)
    assert first_numbered.page_start.number == 1
    assert first_numbered.page_start.display == "1"


def test_page_start_end_identical_when_paragraph_does_not_span_page_break():
    work = _load("1922_DS")
    non_spanning = [p for p in work.paragraphs if p.page_start.number == p.page_end.number]
    assert non_spanning
    for p in non_spanning[:5]:
        assert p.page_start == p.page_end


def test_paragraph_page_end_advances_when_a_pb_falls_inside_it():
    """1900_R has <pb n="2"/> in the middle of a <p> that starts on page
    1 — the paragraph must record page_start=1, page_end=2."""
    work = _load("1900_R")
    spanning = [p for p in work.paragraphs if p.page_start.number != p.page_end.number]
    assert spanning, "expected at least one paragraph spanning a page break"
    p = spanning[0]
    assert p.page_start.number is not None
    assert p.page_end.number is not None
    assert p.page_end.number > p.page_start.number


# -- Structural parsing / graceful @type handling ----------------------------


def test_div_with_missing_type_is_handled_gracefully():
    """1900_R's first body <div> (chapter 1 of Le Rire) has no @type —
    a known corpus inconsistency (docs/ROADMAP.md open issue). Parsing
    must not crash and must still attach its paragraphs to a section,
    falling back to the <head> text for the label."""
    work = _load("1900_R")
    untyped_body_sections = [s for s in work.sections if s.region == "body" and s.div_type is None]
    assert len(untyped_body_sections) == 1
    section = untyped_body_sections[0]
    assert section.paragraph_ids, "untyped div must still get its paragraphs"
    assert section.label.startswith("Du comique en général")


def test_all_sections_have_at_least_one_paragraph():
    for work_id in (
        "1888_EDIC",
        "1896_MM",
        "1900_R",
        "1907_EC",
        "1919_ES",
        "1922_DS",
        "1932_2S",
        "1934_PM",
    ):
        work = _load(work_id)
        assert all(s.paragraph_ids for s in work.sections)


# -- Chunking -----------------------------------------------------------------


def test_no_cross_section_chunk_merging():
    work = _load("1922_DS")
    section_by_paragraph = {p.paragraph_id: p.section_id for p in work.paragraphs}
    chunks = chunk_work(work)
    for chunk in chunks:
        section_ids = {section_by_paragraph[pid] for pid in chunk.paragraph_ids}
        assert section_ids == {
            chunk.section_id
        }, f"{chunk.chunk_id} mixes paragraphs across sections"


def test_each_chunk_maps_to_exactly_one_paragraph():
    work = _load("1934_PM")
    chunks = chunk_work(work)
    assert len(chunks) == len(work.paragraphs)
    for chunk, paragraph in zip(chunks, work.paragraphs, strict=False):
        assert chunk.paragraph_ids == [paragraph.paragraph_id]


def test_chunk_page_bounds_match_first_and_last_paragraph():
    work = _load("1900_R")
    paragraphs_by_id = {p.paragraph_id: p for p in work.paragraphs}
    chunks = chunk_work(work)
    for chunk in chunks:
        first = paragraphs_by_id[chunk.paragraph_ids[0]]
        last = paragraphs_by_id[chunk.paragraph_ids[-1]]
        assert chunk.page_start == first.page_start
        assert chunk.page_end == last.page_end


def test_chunk_word_count_matches_paragraph_sum():
    work = _load("1919_ES")
    paragraphs_by_id = {p.paragraph_id: p for p in work.paragraphs}
    chunks = chunk_work(work)
    for chunk in chunks:
        assert chunk.word_count == sum(
            paragraphs_by_id[pid].word_count for pid in chunk.paragraph_ids
        )
