"""One-off extraction of each work's publisher for the Sources sub-page
(Sprint 12, `feat/presentation-and-guide-content`) -- produces the
`PUBLISHERS` table hand-transcribed into
`frontend/src/lib/sourceMetadata.ts`. Not run at import time or at runtime
(same "committed as source" convention as `scripts/extract_text_metadata.py`
and `src/works.py` itself).

**Why `publicationStmt/publisher`, not `sourceDesc`, despite the sprint task
asking for the latter**: checked against the real XML rather than assumed --
`sourceDesc` only ever holds a free-text description of the *print edition
consulted for the encoding* (e.g. "144e édition de ... (1970), texte
conforme obtenu sur le site de l'UQAC ..."); it never names a publisher, for
any of the 8 works. The actual TEI field for a publisher name is
`publicationStmt/publisher` ("Félix Alcan" for all 8, correctly -- Bergson's
sole publisher throughout his lifetime, per `docs/xml_audit_report.md`'s own
bibliographic-metadata pass). That is what this script extracts and what
`sourceMetadata.ts` ships.

`sourceDesc` is still checked here, for the purpose it actually documents:
`scripts/audit_xml_corpus.py:source_desc_matches_title` (reused, not
reimplemented) is re-run per work as a hard gate. 1888_EDIC still fails it
as of this writing -- its `sourceDesc` still describes *L'Énergie
spirituelle* instead of *Essai sur les données immédiates de la
conscience*, unfixed upstream on bergson-synoptique
(`docs/xml_audit_report.md` Sec. 5) -- so `check_source_desc` raises for it
rather than this script silently treating that field as trustworthy.
`main()` catches that one raise to keep printing the rest of the table, but
surfaces it loudly (`logger.error`, non-zero exit) rather than swallowing
it.

**Citation codes (`feat/sources-citation-codes`)**: also prints
`WORK_CODES` (each work's `work_id`, the prefix of every inline citation
`[{work_id}_c{n}]`) and `ANTHOLOGY_TEXT_RANGES` (for 1919_ES and 1934_PM,
the first/last chunk_id each individual text covers), both transcribed into
`sourceMetadata.ts`. A text's range is its `src.works.TEXTS`
`paragraph_start`/`paragraph_end` converted through
`src.paragraph_chunk_map.resolve_chunk_id` against whatever chunking
`data/processed/chunks/` holds -- never recomputed from XML. Under today's
1 chunk = 1 paragraph chunking, c{n} == p{n}, but that is not assumed: a
range whose chunk numbers aren't contiguous, or that overlaps a sibling
text's, raises rather than printing a misleading range. A qualifying div
excluded from `TEXTS` (no extractable year) is listed by title with no
range. Citations carry no per-text identifier (no `xml:id` such as
`ES_1902_EI`, checked against real answers), so the range is the only way a
reader can attribute e.g. `1919_ES_c160` to a specific text. Re-run after
any re-chunking.
"""

from __future__ import annotations

import logging
import re
import sys
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.audit_xml_corpus import source_desc_matches_title
from scripts.extract_text_metadata import TARGET_WORK_IDS, extract_texts
from src.ingestion.parser import qn
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR, resolve_chunk_id
from src.works import TEXTS, WORKS, TextMetadata

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"


class SourceDescMismatch(RuntimeError):
    """A work's `sourceDesc` doesn't mention its own title -- the known
    1888_EDIC copy-paste error (`docs/xml_audit_report.md`), re-checked here
    rather than assumed still true (or already fixed)."""


def _source_desc_text(root: ET.Element) -> str:
    src_p = root.find(f".//{qn('sourceDesc')}/{qn('p')}")
    raw = "".join(src_p.itertext()).strip() if src_p is not None else ""
    return re.sub(r"\s+", " ", raw)


def check_source_desc(work_id: str) -> None:
    """Raises `SourceDescMismatch` if `work_id`'s `sourceDesc` doesn't
    mention its own title -- reuses the exact heuristic
    `docs/xml_audit_report.md` was generated with, not a second check."""
    root = ET.parse(RAW_SRC_DIR / f"{work_id}.xml").getroot()
    title = WORKS[work_id].title
    source_desc_text = _source_desc_text(root)
    if not source_desc_matches_title(source_desc_text, title):
        raise SourceDescMismatch(
            f"{work_id}: sourceDesc does not mention its own title ({title!r}) -- still the "
            f"known bergson-synoptique copy-paste error (docs/xml_audit_report.md); "
            f"got: {source_desc_text!r}"
        )


def extract_publisher(work_id: str) -> str:
    """The work's publisher, from `publicationStmt/publisher` -- see module
    docstring for why not `sourceDesc`. Does not itself check `sourceDesc`;
    call `check_source_desc` separately (`main()` does both)."""
    root = ET.parse(RAW_SRC_DIR / f"{work_id}.xml").getroot()
    publisher_el = root.find(f".//{qn('publicationStmt')}/{qn('publisher')}")
    if publisher_el is None or not (publisher_el.text or "").strip():
        raise RuntimeError(f"{work_id}: no publicationStmt/publisher text found")
    return publisher_el.text.strip()


class MisleadingChunkRange(RuntimeError):
    """A text's chunks aren't one contiguous run of chunk numbers, or
    overlap a sibling text's -- a `first–last` range would misattribute
    citations, so none is produced."""


_CHUNK_NUMBER_PATTERN = re.compile(r"_c(\d+)$")


def _chunk_number(chunk_id: str) -> int:
    match = _CHUNK_NUMBER_PATTERN.search(chunk_id)
    if match is None:
        raise ValueError(f"not a chunk_id (expected a trailing '_c<n>'): {chunk_id!r}")
    return int(match.group(1))


def text_chunk_range(
    work_id: str, text: TextMetadata, chunks_dir: Path = DEFAULT_CHUNKS_DIR
) -> tuple[str, str]:
    """(first, last) chunk_id covering `text`'s paragraph range. Raises
    `MisleadingChunkRange` if those chunks aren't numbered contiguously."""
    chunk_ids = list(
        dict.fromkeys(
            resolve_chunk_id(work_id, f"{work_id}_p{index}", chunks_dir)
            for index in range(text.paragraph_start, text.paragraph_end + 1)
        )
    )
    numbers = [_chunk_number(chunk_id) for chunk_id in chunk_ids]
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        raise MisleadingChunkRange(
            f"{work_id} {text.title!r}: chunks {chunk_ids} are not numbered contiguously"
        )
    return chunk_ids[0], chunk_ids[-1]


def anthology_text_ranges(
    work_id: str, chunks_dir: Path = DEFAULT_CHUNKS_DIR
) -> list[tuple[str, tuple[str, str] | None]]:
    """(title, (first, last) | None) per qualifying div of `work_id`, in
    document order -- None for a div excluded from `TEXTS`. Raises
    `MisleadingChunkRange` if two texts' ranges overlap."""
    included = {text.title: text for text in TEXTS[work_id]}
    entries: list[tuple[str, tuple[str, str] | None]] = []
    for div in extract_texts(work_id, include_excluded=True):
        if div["year"] is None:
            entries.append((div["title"], None))
            continue
        if div["title"] not in included:
            raise RuntimeError(
                f"{work_id}: dated div {div['title']!r} has no src.works.TEXTS entry -- "
                "re-run scripts/extract_text_metadata.py and update TEXTS first"
            )
        entries.append(
            (div["title"], text_chunk_range(work_id, included[div["title"]], chunks_dir))
        )

    ranges = sorted(
        (_chunk_number(r[0]), _chunk_number(r[1]), title) for title, r in entries if r is not None
    )
    for (_, prev_end, prev_title), (start, _, title) in pairwise(ranges):
        if start <= prev_end:
            raise MisleadingChunkRange(f"{work_id}: {prev_title!r} and {title!r} share chunks")
    return entries


def _ts_string(value: str) -> str:
    return f'"{value}"' if "'" in value else f"'{value}'"


def main() -> int:
    exit_code = 0
    print(f"{'work_id':10} {'publisher':15} sourceDesc check")
    for work_id in WORKS:
        publisher = extract_publisher(work_id)
        try:
            check_source_desc(work_id)
            status = "OK"
        except SourceDescMismatch as exc:
            logger.error(str(exc))
            status = (
                "MISMATCH -- see error above, publisher value above is still trustworthy "
                "(publicationStmt, not sourceDesc)"
            )
            exit_code = 1
        print(f"{work_id:10} {publisher:15} {status}")

    print("\nWORK_CODES:", ", ".join(_ts_string(work_id) for work_id in WORKS))
    print("\nANTHOLOGY_TEXT_RANGES:")
    for work_id in TARGET_WORK_IDS:
        print(f"  {_ts_string(work_id)}: [")
        for title, chunk_range in anthology_text_ranges(work_id):
            rendered = (
                "null" if chunk_range is None else f"['{chunk_range[0]}', '{chunk_range[1]}']"
            )
            print(f"    {{ title: {_ts_string(title)}, chunkRange: {rendered} }},")
        print("  ],")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
