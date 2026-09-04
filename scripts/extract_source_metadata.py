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
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.audit_xml_corpus import source_desc_matches_title
from src.ingestion.parser import qn
from src.works import WORKS

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
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
