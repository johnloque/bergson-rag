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
"""

from __future__ import annotations

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
