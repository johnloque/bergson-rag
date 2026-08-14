"""Parse Bergson TEI XML (``raw/src``) into Work/Section/Paragraph objects.

Divs are flat (max nesting depth = 1, confirmed by
``docs/xml_audit_report.md``) — a single-level iteration over ``<div>``
is sufficient and should stay that way unless a future audit
contradicts this; do not add recursive nesting logic.

Front/back matter is not always ``<div>``-wrapped: some works put
loose ``<pb>``/``<head>``/``<p>`` directly under ``<front>``/``<back>``,
occasionally with more than one ``<head>`` marking separate implicit
sections in the same region (e.g. ``1900_R``'s back matter has two).
Both ``<div>``-wrapped and loose sections are handled uniformly below.

Verse quotations (``<lg>``/``<l>``) appear as direct siblings of
``<p>`` inside a div, not nested inside it — the corpus has no
``note``/``quote``/``cit``/``q``/``bibl`` tagging to distinguish quoted
material (see ``docs/xml_audit_report.md`` §4), so they are treated as
paragraph-like atomic units like any ``<p>``, to avoid silently
dropping text.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from pathlib import Path
from xml.etree import ElementTree as ET

from src.ingestion.models import PageRef, Paragraph, Section, Work

TEI_NS = "http://www.tei-c.org/ns/1.0"

REGIONS: tuple[str, ...] = ("front", "body", "back")

# @type -> French section-kind label, per docs/xml_audit_report.md's
# inventory of div/@type values found across the corpus.
DIV_TYPE_LABELS: dict[str, str] = {
    "chapter": "Chapitre",
    "art": "Article",
    "conf": "Conférence",
    "app": "Appendice",
    "conclusion": "Conclusion",
    "discours": "Discours",
    "essai": "Essai",
    "notice": "Notice",
    "preface": "Préface",
    "avant-propos": "Avant-propos",
}

# Elements that carry running text and are treated as atomic paragraph
# units. "p" is the normal case; "lg"/"l" are quoted verse (see module
# docstring).
PARAGRAPH_LIKE_TAGS = frozenset({"p", "lg", "l"})


def qn(tag: str) -> str:
    return f"{{{TEI_NS}}}{tag}"


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_metadata(metadata_csv: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with metadata_csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["id"]] = row
    return rows


def _resolve_page_refs(pbs: list[ET.Element]) -> dict[int, PageRef]:
    """Resolve each ``<pb>`` to a PageRef.

    Unnumbered pages (no ``@n``) get a relational display string
    derived from the nearest numbered pages on either side — never a
    fabricated number.
    """
    numbers: list[int | None] = []
    for pb in pbs:
        n = pb.attrib.get("n")
        numbers.append(int(n) if n and n.isdigit() else None)

    refs: dict[int, PageRef] = {}
    for i, (pb, number) in enumerate(zip(pbs, numbers, strict=True)):
        if number is not None:
            refs[id(pb)] = PageRef(number=number, display=str(number))
            continue

        before = next((numbers[j] for j in range(i - 1, -1, -1) if numbers[j] is not None), None)
        after = next(
            (numbers[j] for j in range(i + 1, len(numbers)) if numbers[j] is not None), None
        )

        if before is not None and after is not None:
            display = f"entre les p. {before} et {after}"
        elif after is not None:
            display = f"avant la p. {after}"
        elif before is not None:
            display = f"après la p. {before}"
        else:
            display = "page non numérotée"
        refs[id(pb)] = PageRef(number=None, display=display)

    return refs


def _region_blocks(region_el: ET.Element) -> list[tuple[str, list[ET.Element]]]:
    """Split a front/body/back region into section-like blocks.

    Yields ``("div", [div_element])`` for each ``<div>``, and
    ``("loose", [children...])`` for runs of un-wrapped content, split
    at each ``<head>`` that follows at least one paragraph-like element
    (a ``<pb>`` preceding the first ``<head>`` is a page marker for the
    section that follows, not a section of its own).
    """
    blocks: list[tuple[str, list[ET.Element]]] = []
    loose: list[ET.Element] = []
    loose_has_paragraph = False

    for child in region_el:
        tag = local_name(child.tag)
        if tag == "div":
            if loose:
                blocks.append(("loose", loose))
            blocks.append(("div", [child]))
            loose = []
            loose_has_paragraph = False
        elif tag == "head" and loose_has_paragraph:
            blocks.append(("loose", loose))
            loose = [child]
            loose_has_paragraph = False
        else:
            loose.append(child)
            if tag in PARAGRAPH_LIKE_TAGS:
                loose_has_paragraph = True

    if loose:
        blocks.append(("loose", loose))

    return blocks


def parse_work(xml_path: Path, meta_row: dict) -> Work:
    root = ET.parse(xml_path).getroot()
    text_el = root.find(qn("text"))
    if text_el is None:
        raise ValueError(f"{xml_path}: no <text> element")

    page_refs = _resolve_page_refs(list(text_el.iter(qn("pb"))))

    header = root.find(qn("teiHeader"))
    titles = [
        _clean_text("".join(t.itertext()))
        for t in header.findall(f".//{qn('titleStmt')}/{qn('title')}")
    ]
    date_el = header.find(f".//{qn('publicationStmt')}/{qn('date')}")
    source_edition_date = date_el.text.strip() if date_el is not None and date_el.text else ""
    src_p = header.find(f".//{qn('sourceDesc')}/{qn('p')}")
    source_desc = _clean_text("".join(src_p.itertext())) if src_p is not None else ""

    work = Work(
        work_id=meta_row["id"],
        title=titles[0] if titles else meta_row["title"],
        alt_titles=titles[1:],
        first_pub_date=meta_row["date"],
        source_edition_date=source_edition_date,
        source_desc=source_desc,
    )

    state = {"current_page": None, "para_counter": 0, "section_counter": 0, "type_counters": {}}

    def build_section(region: str, div_type: str | None, children: list[ET.Element]) -> Section:
        state["section_counter"] += 1
        section_index = state["section_counter"]

        head_el = next((c for c in children if local_name(c.tag) == "head"), None)
        head_text = _clean_text("".join(head_el.itertext())) if head_el is not None else ""

        if head_text:
            label = head_text
        elif div_type and div_type in DIV_TYPE_LABELS:
            counters = state["type_counters"]
            counters[div_type] = counters.get(div_type, 0) + 1
            label = f"{DIV_TYPE_LABELS[div_type]} {counters[div_type]}"
        else:
            label = f"Section {section_index}"

        section = Section(
            section_id=f"{work.work_id}_s{section_index}",
            work_id=work.work_id,
            region=region,
            div_type=div_type,
            label=label,
            index=section_index,
        )

        for child in children:
            tag = local_name(child.tag)
            if tag == "pb":
                state["current_page"] = page_refs[id(child)]
            elif tag in PARAGRAPH_LIKE_TAGS:
                page_start = state["current_page"]
                for nested_pb in child.iter(qn("pb")):
                    state["current_page"] = page_refs[id(nested_pb)]
                page_end = state["current_page"]

                if page_start is None:
                    page_start = (
                        page_end if page_end is not None else PageRef(None, "page non numérotée")
                    )
                if page_end is None:
                    page_end = page_start

                text = _clean_text("".join(child.itertext()))
                if not text:
                    continue

                state["para_counter"] += 1
                paragraph = Paragraph(
                    paragraph_id=f"{work.work_id}_p{state['para_counter']}",
                    work_id=work.work_id,
                    section_id=section.section_id,
                    index=state["para_counter"],
                    text=text,
                    word_count=len(text.split()),
                    page_start=page_start,
                    page_end=page_end,
                )
                work.paragraphs.append(paragraph)
                section.paragraph_ids.append(paragraph.paragraph_id)

        if section.paragraph_ids:
            paras_by_id = {p.paragraph_id: p for p in work.paragraphs}
            section.page_start = paras_by_id[section.paragraph_ids[0]].page_start
            section.page_end = paras_by_id[section.paragraph_ids[-1]].page_end

        return section

    for region in REGIONS:
        region_el = text_el.find(qn(region))
        if region_el is None:
            continue
        for kind, block_children in _region_blocks(region_el):
            div_type = block_children[0].attrib.get("type") if kind == "div" else None
            children = list(block_children[0]) if kind == "div" else block_children
            section = build_section(region, div_type, children)
            if section.paragraph_ids:
                work.sections.append(section)

    return work


def save_work(work: Work, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{work.work_id}.json"
    out_path.write_text(json.dumps(asdict(work), ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def save_paragraph_correspondence(work: Work, output_dir: Path) -> Path:
    """Export ``work``'s flat paragraph list for gold-dataset annotation.

    Paragraph IDs are assigned only at parse time (see module docstring
    in models.py), so this file is the lookup table annotators use to
    find the ``paragraph_id`` for a given passage of text.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{work.work_id}.json"
    records = [{"paragraph_id": p.paragraph_id, "text": p.text} for p in work.paragraphs]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def parse_corpus(raw_src_dir: Path) -> list[Work]:
    """Parse every work listed in ``metadata.csv`` under ``raw_src_dir``."""
    meta = load_metadata(raw_src_dir / "metadata.csv")
    rows = sorted(meta.values(), key=lambda r: int(r["textorder"]))
    return [parse_work(raw_src_dir / f"{row['id']}.xml", row) for row in rows]
