"""Static metadata for the corpus's fixed, closed set of 8 Bergson works
(docs/ROADMAP.md scope decision) — canonical title, alternate titles, and
publication year, keyed by `work_id`.

First built on `fix/title-year-grounding` for two consumers on that branch:
`src/generation/prompt.py` (title+year shown alongside `work_id` in the
generation prompt, so the model no longer has to recall them from its own
background knowledge) and `src/generation/guardrail.py` (Layer 1's
title+year pairing check, `check_title_year_mismatch`). It is also the
"static work_id -> year table" `docs/ROADMAP.md`'s Sprint 11 entry
anticipated for date-range retrieval filtering — this module is that table
(extended with title, which Sprint 11 didn't need but this branch does),
not a first draft to be superseded. **Sprint 11 should import and extend
this module, not build a second one.**

Hardcoded rather than read from `data/processed/works/*.json` (a gitignored
build artifact) — same reasoning as `KNOWN_WORK_TITLES` previously in
`src/generation/guardrail.py` (now derived from `WORKS` below instead of
independently hardcoded, to avoid two hand-maintained copies of the same 8
titles drifting apart): this module must work before any ingestion has run
(a fresh checkout, CI), and the corpus is a fixed, closed set that doesn't
need a data-driven lookup.

## Text-level dates (Sprint 11, `feat/backend-reference-data`)

Two of the 8 works, 1919_ES ("L'énergie spirituelle") and 1934_PM ("La
Pensée et le Mouvant"), are anthologies: each is a collection of
individually-dated articles/conferences/etc. (`<div>` `@type` one of
art/conf/discours/essai/notice), first published years apart from each
other and from the anthology's own publication date. `TEXTS` below records
each such text's own title, year, and paragraph_id range, so a paragraph
falling inside one resolves to *its* title/year rather than just the
enclosing work's — `resolve_paragraph_metadata` is the entry point.

This depends on a load-bearing structural assumption, verified (not just
inferred from the corpus-wide `docs/xml_audit_report.md` stat) specifically
for these two files' actual XML by `scripts/extract_text_metadata.py` and
by `tests/test_works.py::test_no_chunk_straddles_two_qualifying_divs`: no
qualifying `<div>` is nested inside another, so no chunk (which never
crosses a section/div boundary — `src/ingestion/chunking.py`) can ever
straddle two dated texts. If a future corpus update breaks this for either
file, `resolve_paragraph_metadata` must not be trusted without re-verifying
it.

`TEXTS` was extracted by `scripts/extract_text_metadata.py` (reusing
`src.ingestion.parser.parse_work` for paragraph numbering/traversal, not a
second XML-walking implementation) from `data/raw/corpus/raw/src`, printed
for manual review, and hand-transcribed here — same "script-generated but
committed as source" convention as `WORKS` above, for the same reason: this
module must work before `raw/src` has been fetched. Title is each
`<div>`'s `<head>` text; year is the single 4-digit token found in the
div's `@xml:id` (e.g. `ES_1902_EI` -> 1902) — searched, not assumed to sit
at a fixed position, and any div where that search doesn't resolve to
exactly one year is logged and excluded (falls back to work-level year)
rather than guessed. No div was excluded for either work in the current
corpus (see the script's output).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkMetadata:
    title: str
    alt_titles: tuple[str, ...]
    year: int


WORKS: dict[str, WorkMetadata] = {
    "1888_EDIC": WorkMetadata("Essai sur les données immédiates de la conscience", (), 1888),
    "1896_MM": WorkMetadata("Matière et mémoire", (), 1896),
    "1900_R": WorkMetadata("Le rire", ("Essai sur la signification du comique",), 1900),
    "1907_EC": WorkMetadata("L'Évolution créatrice", (), 1907),
    "1919_ES": WorkMetadata("L'énergie spirituelle", (), 1919),
    "1922_DS": WorkMetadata("Durée et simultanéité", ("A propos de la théorie d'Einstein",), 1922),
    "1932_2S": WorkMetadata("Les deux sources de la morale et de la religion", (), 1932),
    "1934_PM": WorkMetadata("La Pensée et le Mouvant", (), 1934),
}


def work_label(work_id: str) -> str:
    """`"{title} ({year})"` for display alongside `work_id` — the exact
    format `src/generation/prompt.py` shows in the generation prompt. Falls
    back to `work_id` alone for a work_id outside the known 8 (should not
    happen against this project's real corpus, but keeps hand-built test
    fixtures using an out-of-corpus id, e.g. tests exercising Layer 1's
    unknown-citation path, from raising)."""
    metadata = WORKS.get(work_id)
    if metadata is None:
        return work_id
    return f"{metadata.title} ({metadata.year})"


@dataclass(frozen=True)
class TextMetadata:
    """One individually-dated text within an anthology work — see the
    "Text-level dates" section above. `paragraph_start`/`paragraph_end` are
    the 1-based paragraph *index* (the trailing number in a paragraph_id
    like `1919_ES_p153` -> 153), inclusive on both ends."""

    title: str
    year: int
    paragraph_start: int
    paragraph_end: int


# Extracted by `scripts/extract_text_metadata.py` — re-run it and re-verify
# by hand before changing any entry below rather than hand-editing values
# directly. Each comment is the source `<div xml:id=...>` this entry came
# from, for traceability back to `data/raw/corpus/raw/src`.
TEXTS: dict[str, tuple[TextMetadata, ...]] = {
    "1919_ES": (
        TextMetadata("La conscience et la vie", 1911, 1, 27),  # ES_1911_CV
        TextMetadata("L'âme et le corps", 1912, 28, 47),  # ES_1912_AC
        # ES_1913_FVRP
        TextMetadata('"Fantômes de vivants" et "recherche psychique"', 1913, 48, 68),
        TextMetadata("Le rêve", 1901, 69, 100),  # ES_1901_R
        # ES_1908_SPFR
        TextMetadata("Le souvenir du présent et la fausse reconnaissance", 1908, 101, 152),
        TextMetadata("L'effort intellectuel", 1902, 153, 203),  # ES_1902_EI
        # ES_1904_CPIP
        TextMetadata("Le cerveau et la pensée : une illusion philosophique", 1904, 204, 230),
    ),
    "1934_PM": (
        TextMetadata("Introduction (première partie)", 1922, 4, 24),  # PM_1922_I1
        TextMetadata("Introduction (deuxième partie)", 1922, 25, 73),  # PM_1922_I2
        TextMetadata("Le possible et le réel", 1930, 74, 87),  # PM_1930_PR
        TextMetadata("L'intuition philosophique", 1911, 88, 112),  # PM_1911_IP
        TextMetadata("La perception du changement", 1911, 113, 129),  # PM_1911_PC1
        TextMetadata("Deuxième conférence", 1911, 130, 152),  # PM_1911_PC2
        TextMetadata("Introduction à la métaphysique", 1903, 153, 223),  # PM_1903_IM
        TextMetadata("La philosophie de Claude Bernard", 1913, 224, 232),  # PM_1913_PCB
        # PM_1911_PWJ
        TextMetadata("Sur le pragmatisme de William James. Vérité et réalité.", 1911, 233, 253),
        TextMetadata("La vie et l'œuvre de Ravaisson", 1904, 254, 311),  # PM_1904_VOR
    ),
}


@dataclass(frozen=True)
class ParagraphMetadata:
    """Resolution result for `resolve_paragraph_metadata` — `text_title`/
    `text_year` are None unless the paragraph falls inside an individually-
    dated text (`TEXTS`)."""

    work_title: str
    work_year: int | None
    text_title: str | None
    text_year: int | None


_PARAGRAPH_INDEX_PATTERN = re.compile(r"_p(\d+)$")


def _paragraph_index(paragraph_id: str) -> int:
    match = _PARAGRAPH_INDEX_PATTERN.search(paragraph_id)
    if match is None:
        raise ValueError(f"not a paragraph_id (expected a trailing '_p<n>'): {paragraph_id!r}")
    return int(match.group(1))


def resolve_paragraph_metadata(work_id: str, paragraph_id: str) -> ParagraphMetadata:
    """`{work_title, work_year, text_title, text_year}` for `paragraph_id`
    within `work_id` — the finer-grained resolution `src/generation/prompt.py`
    and Layer 1's title+year check (`src/generation/guardrail.py`) use going
    forward. `text_title`/`text_year` stay None for a paragraph in front/back
    matter, in one of the 6 non-anthology works (no `TEXTS` entry at all), or
    outside every recorded range for its work (should not happen against the
    real corpus, but not asserted against — falling back to work-level-only
    is always a safe, non-raising answer)."""
    metadata = WORKS.get(work_id)
    work_title = metadata.title if metadata is not None else work_id
    work_year = metadata.year if metadata is not None else None

    index = _paragraph_index(paragraph_id)
    for text in TEXTS.get(work_id, ()):
        if text.paragraph_start <= index <= text.paragraph_end:
            return ParagraphMetadata(work_title, work_year, text.title, text.year)

    return ParagraphMetadata(work_title, work_year, None, None)
