"""Unit tests for src/works.py's Sprint 11 extension (`feat/backend-reference-data`)
— text-level dates for the two anthology works (1919_ES, 1934_PM) and
`resolve_paragraph_metadata`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import scripts.extract_text_metadata as extract_text_metadata
from src.works import TEXTS, WORKS, resolve_paragraph_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"
CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"

_corpus_skip = pytest.mark.skipif(
    not RAW_SRC_DIR.exists(), reason="corpus not fetched — run scripts/fetch_corpus.sh first"
)
_chunks_skip = pytest.mark.skipif(
    not CHUNKS_DIR.exists() or not any(CHUNKS_DIR.iterdir()),
    reason="data/processed/chunks not built — run the ingestion/chunking pipeline first",
)

ANTHOLOGY_WORK_IDS = ("1919_ES", "1934_PM")
NON_ANTHOLOGY_WORK_IDS = tuple(w for w in WORKS if w not in ANTHOLOGY_WORK_IDS)


# -- resolve_paragraph_metadata: dated-text case -----------------------------


def test_known_example_es_1902_ei():
    """The example named in this branch's task description: ES_1902_EI ->
    "L'effort intellectuel", 1902 — extracted end to end."""
    result = resolve_paragraph_metadata("1919_ES", "1919_ES_p153")
    assert result.text_title == "L'effort intellectuel"
    assert result.text_year == 1902
    assert result.work_title == "L'énergie spirituelle"
    assert result.work_year == 1919


def test_dated_text_paragraph_returns_text_year_not_work_year():
    """A paragraph inside a dated text must resolve to *that text's* year,
    not the enclosing anthology's own publication year — the two are
    genuinely different here (1902 vs. 1919)."""
    result = resolve_paragraph_metadata("1919_ES", "1919_ES_p153")
    assert result.text_year != result.work_year


def test_dated_text_range_boundaries_are_inclusive():
    # ES_1902_EI spans 1919_ES_p153..1919_ES_p203 (script output).
    first = resolve_paragraph_metadata("1919_ES", "1919_ES_p153")
    last = resolve_paragraph_metadata("1919_ES", "1919_ES_p203")
    next_text_start = resolve_paragraph_metadata("1919_ES", "1919_ES_p204")
    assert first.text_title == last.text_title == "L'effort intellectuel"
    assert next_text_start.text_title == "Le cerveau et la pensée : une illusion philosophique"


# -- resolve_paragraph_metadata: fallback cases ------------------------------


def test_front_matter_paragraph_falls_back_to_work_level_only():
    # 1934_PM's first dated text (PM_1922_I1) starts at p4 — p1..p3 precede it.
    result = resolve_paragraph_metadata("1934_PM", "1934_PM_p1")
    assert result.text_title is None
    assert result.text_year is None
    assert result.work_title == "La Pensée et le Mouvant"
    assert result.work_year == 1934


@pytest.mark.parametrize("work_id", NON_ANTHOLOGY_WORK_IDS)
def test_non_anthology_work_falls_back_to_work_level_only(work_id):
    result = resolve_paragraph_metadata(work_id, f"{work_id}_p1")
    assert result.text_title is None
    assert result.text_year is None
    assert result.work_title == WORKS[work_id].title
    assert result.work_year == WORKS[work_id].year


def test_non_anthology_works_have_no_texts_entries():
    for work_id in NON_ANTHOLOGY_WORK_IDS:
        assert work_id not in TEXTS


# -- Nesting-depth / no-straddling load-bearing assumption -------------------


@_chunks_skip
@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_no_chunk_straddles_two_qualifying_divs(work_id):
    """The load-bearing assumption `resolve_paragraph_metadata` depends on:
    no chunk's paragraph_ids span two different dated texts (or a dated
    text and undated front matter). Verified programmatically against the
    real, currently-indexed chunking, not just inferred from the
    corpus-wide max-nesting-depth stat."""
    chunks = json.loads((CHUNKS_DIR / f"{work_id}.json").read_text(encoding="utf-8"))
    for chunk in chunks:
        text_titles = {
            resolve_paragraph_metadata(work_id, pid).text_title for pid in chunk["paragraph_ids"]
        }
        assert (
            len(text_titles) == 1
        ), f"{chunk['chunk_id']} straddles multiple texts/front-matter: {text_titles}"


@_corpus_skip
@pytest.mark.parametrize("work_id,expected_div_count", [("1919_ES", 7), ("1934_PM", 10)])
def test_no_qualifying_div_is_nested_in_another(work_id, expected_div_count):
    """Verified directly against these two files' actual XML structure (not
    inferred from the corpus-wide stat in docs/xml_audit_report.md):
    `_raw_divs` itself raises `AssertionError` the moment it finds a <div>
    with a nested <div> inside it (`nested != 0`), so completing without
    raising *is* the nesting-depth-0 proof — the count check below just
    confirms it didn't also (incorrectly) short-circuit early."""
    xml_path = RAW_SRC_DIR / f"{work_id}.xml"
    divs = extract_text_metadata._raw_divs(xml_path)
    assert len(divs) == expected_div_count


# -- Robust year extraction from @xml:id -------------------------------------


@pytest.mark.parametrize(
    "xml_id,expected_year",
    [
        ("ES_1902_EI", 1902),
        ("PM_1911_PC2", 1911),
        ("ES_1913_FVRP", 1913),
    ],
)
def test_extract_year_from_xml_id_finds_the_single_year_token(xml_id, expected_year):
    assert extract_text_metadata.extract_year_from_xml_id(xml_id) == expected_year


@pytest.mark.parametrize(
    "xml_id",
    [
        "NOYEAR_ABC",  # no 4-digit token at all
        "X_1900_1955",  # two 4-digit tokens — ambiguous
        "X_99",  # not 4 digits
    ],
)
def test_extract_year_from_xml_id_returns_none_for_ambiguous_or_missing_year(xml_id):
    assert extract_text_metadata.extract_year_from_xml_id(xml_id) is None


def test_ambiguous_year_div_is_logged_and_excluded_not_defaulted(tmp_path, monkeypatch, caplog):
    """End-to-end: a div whose @xml:id has no unambiguous year must be
    logged and excluded from the extracted entries — never silently
    defaulted to the work-level year or to a guessed value. Exercised
    against a synthetic corpus (real 1919_ES/1934_PM currently has no such
    div — see the extraction script's docstring) via a monkeypatched
    RAW_SRC_DIR, not the real corpus."""
    metadata_csv = tmp_path / "metadata.csv"
    with metadata_csv.open("w", newline="", encoding="utf-8") as fh:
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

    xml_path = tmp_path / "TESTWORK.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Test Work</title></titleStmt>
      <publicationStmt><date>1900</date></publicationStmt>
      <sourceDesc><p>Test source.</p></sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <div type="art" xml:id="TW_1955_OK">
        <head>A good entry</head>
        <p>Some paragraph text here.</p>
      </div>
      <div type="art" xml:id="TW_BADID">
        <head>An entry with no year</head>
        <p>Another paragraph of text.</p>
      </div>
    </body>
  </text>
</TEI>
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(extract_text_metadata, "RAW_SRC_DIR", tmp_path)
    import logging

    with caplog.at_level(logging.WARNING, logger=extract_text_metadata.logger.name):
        entries = extract_text_metadata.extract_texts("TESTWORK")

    titles = [e["title"] for e in entries]
    assert titles == ["A good entry"]
    assert "TW_BADID" in caplog.text
    assert "excluded" in caplog.text


# -- Regression: TEXTS matches a fresh extraction ----------------------------


@_corpus_skip
@pytest.mark.parametrize("work_id", ANTHOLOGY_WORK_IDS)
def test_texts_table_matches_fresh_extraction(work_id):
    """Ties the hand-transcribed `works.TEXTS` back to
    `scripts/extract_text_metadata.py`'s output, so the two can't silently
    drift apart if the source XML ever changes."""
    fresh = extract_text_metadata.extract_texts(work_id)
    expected = [
        {
            "title": text.title,
            "year": text.year,
            "paragraph_start": f"{work_id}_p{text.paragraph_start}",
            "paragraph_end": f"{work_id}_p{text.paragraph_end}",
        }
        for text in TEXTS[work_id]
    ]
    actual = [
        {
            "title": e["title"],
            "year": e["year"],
            "paragraph_start": e["paragraph_start"],
            "paragraph_end": e["paragraph_end"],
        }
        for e in fresh
    ]
    assert actual == expected
