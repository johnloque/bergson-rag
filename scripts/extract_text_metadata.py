"""One-off extraction of individually-dated text metadata for 1919_ES and
1934_PM (Sprint 11, `feat/backend-reference-data`) — produced the
`TEXTS` table hand-transcribed into `src/works.py`. Not run at import time
or at runtime resolution (same reasoning as `src/works.py`'s own module
docstring: that module must work before `raw/src` has been fetched, and
this script's output is committed as source, not regenerated on every run).

Re-run this script only if the source XML for these two works changes
(re-verify the printed list against `src/works.py`'s `TEXTS` by hand before
committing any update — same discipline as `WORKS` itself).

Reuses `src.ingestion.parser.parse_work` for paragraph numbering and
section/div traversal — does not reimplement XML walking. The only new
logic here is (1) matching each parsed `Section` back to the raw `<div
xml:id=...>` it came from, by position (`div_type`-tagged sections appear
in the same document order as `<div>` elements, verified by an assertion
below — see docs/xml_audit_report.md: max div nesting depth is 1 for both
files, confirmed again here at nesting_divs==0 for every div, so this
straightforward positional zip is safe) and (2) robust year extraction from
`@xml:id`.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from src.ingestion.parser import load_metadata, parse_work, qn

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"

# @type values that mark an individually-dated text within these two
# anthology works (docs/xml_audit_report.md's per-work div/@type inventory).
QUALIFYING_DIV_TYPES = frozenset({"art", "conf", "discours", "essai", "notice"})

TARGET_WORK_IDS = ("1919_ES", "1934_PM")

_XML_ID_ATTR = "{http://www.w3.org/XML/1998/namespace}id"

# A plausible 4-digit year, searched anywhere in @xml:id rather than at a
# fixed position/split index — deliberately generous (1700-2099) since the
# goal is "does exactly one clean year token exist", not a tight range
# check.
_YEAR_TOKEN_PATTERN = re.compile(r"(?<!\d)(1[7-9]\d{2}|20\d{2})(?!\d)")


def extract_year_from_xml_id(xml_id: str) -> int | None:
    """The single 4-digit year token in `xml_id`, or None if zero or more
    than one is found — ambiguous cases are not guessed."""
    matches = _YEAR_TOKEN_PATTERN.findall(xml_id)
    if len(matches) != 1:
        return None
    return int(matches[0])


def _raw_divs(xml_path: Path) -> list[tuple[str | None, str | None]]:
    """`(xml_id, type)` for every `<div>` in `xml_path`, in document order."""
    root = ET.parse(xml_path).getroot()
    text_el = root.find(qn("text"))
    divs = []
    for div in text_el.iter(qn("div")):
        nested = len(list(div.iter(qn("div")))) - 1
        if nested != 0:
            raise AssertionError(
                f"{xml_path.name}: div {div.attrib.get(_XML_ID_ATTR)!r} has nested divs "
                f"(depth {nested}) — the flat single-level traversal this script relies on "
                "no longer holds for this file."
            )
        divs.append((div.attrib.get(_XML_ID_ATTR), div.attrib.get("type")))
    return divs


def extract_texts(work_id: str) -> list[dict]:
    xml_path = RAW_SRC_DIR / f"{work_id}.xml"
    meta = load_metadata(RAW_SRC_DIR / "metadata.csv")
    work = parse_work(xml_path, meta[work_id])

    raw_divs = _raw_divs(xml_path)
    div_sections = [s for s in work.sections if s.div_type is not None]

    if len(raw_divs) != len(div_sections):
        raise AssertionError(
            f"{work_id}: {len(raw_divs)} raw <div> elements but {len(div_sections)} "
            "div-derived sections — positional zip is unsafe, stop and investigate."
        )

    entries = []
    for (xml_id, div_type), section in zip(raw_divs, div_sections, strict=True):
        if div_type != section.div_type:
            raise AssertionError(
                f"{work_id}: div/@type {div_type!r} does not match section.div_type "
                f"{section.div_type!r} at the same position — positional zip is unsafe."
            )
        if div_type not in QUALIFYING_DIV_TYPES:
            continue

        if xml_id is None:
            logger.warning(
                "%s: div (type=%s, label=%r) has no @xml:id — excluded",
                work_id,
                div_type,
                section.label,
            )
            continue

        year = extract_year_from_xml_id(xml_id)
        if year is None:
            logger.warning(
                "%s: div %r has no unambiguous 4-digit year token — excluded, falls back to "
                "work-level year",
                work_id,
                xml_id,
            )
            continue

        entries.append(
            {
                "work_id": work_id,
                "xml_id": xml_id,
                "div_type": div_type,
                "title": section.label,
                "year": year,
                "paragraph_start": section.paragraph_ids[0],
                "paragraph_end": section.paragraph_ids[-1],
            }
        )

    return entries


def main() -> None:
    all_entries = []
    for work_id in TARGET_WORK_IDS:
        all_entries.extend(extract_texts(work_id))

    print(f"\n{len(all_entries)} individually-dated text(s) extracted for manual review:\n")
    for e in all_entries:
        print(
            f"{e['work_id']:10} {e['xml_id']:15} type={e['div_type']:10} year={e['year']} "
            f"[{e['paragraph_start']}..{e['paragraph_end']}]  {e['title']!r}"
        )


if __name__ == "__main__":
    main()
