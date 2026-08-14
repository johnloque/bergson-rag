#!/usr/bin/env python3
"""Audit the Bergson XML corpus against docs/xml_audit_checklist.md.

Reads the paragraph-level source (raw/src), runs every check from the
checklist, and writes the raw results as JSON to
docs/xml_audit_results.json. Run scripts/generate_xml_audit_report.py
afterwards to turn that JSON into the Markdown report.

Usage: python3 scripts/audit_xml_corpus.py
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "data" / "raw" / "corpus"
RAW_DIR = CORPUS_DIR / "raw" / "src"
RESULTS_PATH = REPO_ROOT / "docs" / "xml_audit_results.json"

TEI_NS = "http://www.tei-c.org/ns/1.0"


def qn(tag: str) -> str:
    """Qualify a bare TEI tag name with the TEI namespace."""
    return f"{{{TEI_NS}}}{tag}"


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


@dataclass
class WorkAudit:
    work_id: str
    title: str
    first_pub_date: str
    raw_path: str
    metadata_pages: str = ""

    # 1. Structure above paragraph level
    raw_tags: dict = field(default_factory=dict)
    div_types: dict = field(default_factory=dict)
    max_div_depth: int = 0

    # 2. Corpus size
    raw_paragraph_count: int = 0
    raw_word_count: int = 0

    # 3. Encoding
    straight_apostrophes: int = 0
    curly_apostrophes: int = 0
    ligatures: dict = field(default_factory=dict)
    double_quotes: int = 0
    guillemets: int = 0

    # 4. Editorial content
    editorial_tags_found: dict = field(default_factory=dict)
    app_div_count: int = 0

    # 5. Bibliographic metadata
    pub_stmt_date: str = ""
    source_desc_text: str = ""
    source_desc_title_match: bool = True
    pb_total: int = 0
    pb_with_n: int = 0


def load_metadata(csv_path: Path) -> dict[str, dict]:
    rows = {}
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows[row["id"]] = row
    return rows


def collect_tags(root: ET.Element) -> Counter:
    tags = Counter()
    for el in root.iter():
        tags[local_name(el.tag)] += 1
    return tags


def div_depths(root: ET.Element) -> tuple[Counter, int]:
    types = Counter()
    max_depth = 0

    def walk(el: ET.Element, depth: int) -> None:
        nonlocal max_depth
        for child in el:
            if local_name(child.tag) == "div":
                depth_here = depth + 1
                max_depth = max(max_depth, depth_here)
                types[child.attrib.get("type", "(untyped)")] += 1
                walk(child, depth_here)
            else:
                walk(child, depth)

    walk(root, 0)
    return types, max_depth


TITLE_STOPWORDS = {"le", "la", "les", "de", "des", "du", "et", "sur", "en", "l", "un", "une"}


def source_desc_matches_title(source_desc: str, title: str) -> bool:
    """Heuristic: at least one significant title word should appear in the
    descriptive part of sourceDesc (before the URL), to catch copy-paste
    errors between works."""
    descriptive_part = source_desc.split("http")[0]
    norm_desc = strip_accents(descriptive_part).lower()
    words = re.findall(r"[a-zA-Zàâäéèêëïîôöùûüç]+", strip_accents(title).lower())
    significant = [w for w in words if len(w) > 3 and w not in TITLE_STOPWORDS]
    if not significant:
        return True
    return any(w in norm_desc for w in significant)


def audit_work(meta_row: dict, raw_id: str) -> WorkAudit:
    raw_path = RAW_DIR / f"{raw_id}.xml"

    w = WorkAudit(
        work_id=raw_id,
        title=meta_row["title"],
        first_pub_date=meta_row["date"],
        raw_path=str(raw_path.relative_to(REPO_ROOT)),
        metadata_pages=meta_row.get("pages", ""),
    )

    raw_root = ET.parse(raw_path).getroot()

    # 1. Structure above paragraph level
    w.raw_tags = dict(collect_tags(raw_root))
    div_types, max_depth = div_depths(raw_root)
    w.div_types = dict(div_types)
    w.max_div_depth = max_depth

    # 2. Corpus size
    raw_text = "".join(raw_root.itertext())
    w.raw_paragraph_count = len(raw_root.findall(f".//{qn('p')}"))
    w.raw_word_count = len(raw_text.split())

    # 3. Encoding
    w.straight_apostrophes = raw_text.count("'")
    w.curly_apostrophes = raw_text.count("’")
    ligatures = Counter()
    for lig in ("œ", "æ", "Œ", "Æ"):  # oe/ae ligatures, lower/upper
        c = raw_text.count(lig)
        if c:
            ligatures[lig] += c
    w.ligatures = dict(ligatures)
    w.double_quotes = raw_text.count('"')
    w.guillemets = raw_text.count("«") + raw_text.count("»")

    # 4. Editorial content
    editorial_tags_found = {}
    for tag_name in ("note", "quote", "cit", "q", "bibl"):
        n = len(raw_root.findall(f".//{qn(tag_name)}"))
        if n:
            editorial_tags_found[tag_name] = n
    w.editorial_tags_found = editorial_tags_found
    w.app_div_count = sum(c for t, c in div_types.items() if t == "app")

    # 5. Bibliographic metadata
    date_el = raw_root.find(f".//{qn('publicationStmt')}/{qn('date')}")
    w.pub_stmt_date = date_el.text.strip() if date_el is not None and date_el.text else ""
    src_p = raw_root.find(f".//{qn('sourceDesc')}/{qn('p')}")
    source_desc_text = "".join(src_p.itertext()).strip() if src_p is not None else ""
    w.source_desc_text = re.sub(r"\s+", " ", source_desc_text)
    w.source_desc_title_match = source_desc_matches_title(w.source_desc_text, w.title)

    pbs = raw_root.findall(f".//{qn('pb')}")
    w.pb_total = len(pbs)
    w.pb_with_n = sum(1 for pb in pbs if pb.attrib.get("n"))

    return w


def schema_consistency(works: list[WorkAudit]) -> dict:
    """Compare raw/src tag sets across works."""
    notes = []

    raw_tagsets = {w.work_id: frozenset(w.raw_tags) for w in works}
    common_raw = frozenset.intersection(*raw_tagsets.values())
    for wid, ts in raw_tagsets.items():
        extra = ts - common_raw
        if extra:
            notes.append(f"{wid}: extra tags not in all works: {sorted(extra)}")

    return {
        "common_raw_tags": sorted(common_raw),
        "drift_notes": notes,
    }


def main() -> None:
    raw_meta = load_metadata(RAW_DIR / "metadata.csv")
    raw_rows = sorted(raw_meta.values(), key=lambda r: int(r["textorder"]))

    works = [audit_work(row, row["id"]) for row in raw_rows]

    results = {
        "works": [asdict(w) for w in works],
        "schema_consistency": schema_consistency(works),
    }

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH.relative_to(REPO_ROOT)} ({len(works)} works audited)")


if __name__ == "__main__":
    main()
