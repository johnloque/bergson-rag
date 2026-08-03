#!/usr/bin/env python3
"""Audit the Bergson XML corpus against docs/xml_audit_checklist.md.

Reads the paragraph-level source (raw/src) and word-level source
(tag/src), runs every check from the checklist, and writes the raw
results as JSON to docs/xml_audit_results.json. Run
scripts/generate_xml_audit_report.py afterwards to turn that JSON into
the Markdown report.

Usage: python3 scripts/audit_xml_corpus.py
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "data" / "raw" / "corpus"
RAW_DIR = CORPUS_DIR / "raw" / "src"
TAG_DIR = CORPUS_DIR / "tag" / "src"
RESULTS_PATH = REPO_ROOT / "docs" / "xml_audit_results.json"

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"


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
    tag_path: str
    metadata_pages: str = ""

    # 1. Tags and schema
    raw_tags: dict = field(default_factory=dict)
    tag_tags: dict = field(default_factory=dict)
    raw_attrs_by_tag: dict = field(default_factory=dict)
    tag_attrs_by_tag: dict = field(default_factory=dict)
    pos_values: dict = field(default_factory=dict)
    pos_suspicious: dict = field(default_factory=dict)

    # 2. Corpus size
    raw_paragraph_count: int = 0
    tag_paragraph_count: int = 0
    raw_word_count: int = 0
    tag_word_count: int = 0

    # 3. Structure above paragraph level
    div_types: dict = field(default_factory=dict)
    max_div_depth: int = 0
    app_div_count: int = 0

    # 4. Lemmatization quality
    lemma_total: int = 0
    lemma_nonempty: int = 0

    # 5. Encoding
    straight_apostrophes: int = 0
    curly_apostrophes: int = 0
    ligatures: dict = field(default_factory=dict)
    double_quotes: int = 0
    guillemets: int = 0

    # 6. Editorial content
    editorial_tags_found: dict = field(default_factory=dict)

    # 7. Cross-source alignment
    raw_p_has_id: bool = False
    tag_p_count: int = 0
    tag_p_ids_unique: bool = True

    # 8. Bibliographic metadata
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


def collect_tags_and_attrs(root: ET.Element) -> tuple[Counter, dict]:
    tags = Counter()
    attrs_by_tag: dict[str, set] = defaultdict(set)
    for el in root.iter():
        name = local_name(el.tag)
        tags[name] += 1
        for attr in el.attrib:
            attrs_by_tag[name].add(local_name(attr))
    return tags, attrs_by_tag


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


def audit_work(meta_row: dict, raw_id: str, tag_id: str) -> WorkAudit:
    raw_path = RAW_DIR / f"{raw_id}.xml"
    tag_path = TAG_DIR / f"{tag_id}.xml"

    w = WorkAudit(
        work_id=raw_id,
        title=meta_row["title"],
        first_pub_date=meta_row["date"],
        raw_path=str(raw_path.relative_to(REPO_ROOT)),
        tag_path=str(tag_path.relative_to(REPO_ROOT)),
        metadata_pages=meta_row.get("pages", ""),
    )

    raw_root = ET.parse(raw_path).getroot()
    tag_root = ET.parse(tag_path).getroot()

    # 1. Tags and schema
    raw_tags, raw_attrs = collect_tags_and_attrs(raw_root)
    tag_tags, tag_attrs = collect_tags_and_attrs(tag_root)
    w.raw_tags = dict(raw_tags)
    w.tag_tags = dict(tag_tags)
    w.raw_attrs_by_tag = {k: sorted(v) for k, v in raw_attrs.items()}
    w.tag_attrs_by_tag = {k: sorted(v) for k, v in tag_attrs.items()}

    pos_values = Counter()
    pos_suspicious = Counter()
    for wel in tag_root.iter(qn("w")):
        pos = wel.attrib.get("pos", "")
        pos_values[pos] += 1
        if pos in ("", "nan", "NaN", "None"):
            pos_suspicious[pos or "(empty)"] += 1
    w.pos_values = dict(pos_values)
    w.pos_suspicious = dict(pos_suspicious)

    # 2. Corpus size
    w.raw_paragraph_count = len(raw_root.findall(f".//{qn('p')}"))
    w.tag_paragraph_count = len(tag_root.findall(f".//{qn('p')}"))
    w.tag_word_count = len(tag_root.findall(f".//{qn('w')}"))
    raw_text = "".join(raw_root.itertext())
    w.raw_word_count = len(raw_text.split())

    # 3. Structure above paragraph level
    div_types, max_depth = div_depths(raw_root)
    w.div_types = dict(div_types)
    w.max_div_depth = max_depth
    w.app_div_count = sum(c for t, c in div_types.items() if t == "app")

    # 4. Lemmatization quality
    lemma_total = 0
    lemma_nonempty = 0
    for wel in tag_root.iter(qn("w")):
        lemma_total += 1
        if wel.attrib.get("lemma", "").strip():
            lemma_nonempty += 1
    w.lemma_total = lemma_total
    w.lemma_nonempty = lemma_nonempty

    # 5. Encoding
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

    # 6. Editorial content
    editorial_tags_found = {}
    for tag_name in ("note", "quote", "cit", "q", "bibl"):
        n = len(raw_root.findall(f".//{qn(tag_name)}"))
        if n:
            editorial_tags_found[tag_name] = n
    w.editorial_tags_found = editorial_tags_found

    # 7. Cross-source alignment
    raw_p_ids = [
        p.attrib.get(f"{{{XML_NS}}}id") or p.attrib.get("n")
        for p in raw_root.findall(f".//{qn('p')}")
    ]
    w.raw_p_has_id = any(raw_p_ids)
    tag_p_ids = [p.attrib.get("n") for p in tag_root.findall(f".//{qn('p')}")]
    w.tag_p_count = len(tag_p_ids)
    w.tag_p_ids_unique = len(tag_p_ids) == len(set(tag_p_ids))

    # 8. Bibliographic metadata
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
    """Compare raw/tag tag sets and per-tag attribute sets across works."""
    notes = []

    raw_tagsets = {w.work_id: frozenset(w.raw_tags) for w in works}
    common_raw = frozenset.intersection(*raw_tagsets.values())
    for wid, ts in raw_tagsets.items():
        extra = ts - common_raw
        if extra:
            notes.append(f"raw/{wid}: extra tags not in all works: {sorted(extra)}")

    tag_tagsets = {w.work_id: frozenset(w.tag_tags) for w in works}
    common_tag = frozenset.intersection(*tag_tagsets.values())
    for wid, ts in tag_tagsets.items():
        extra = ts - common_tag
        if extra:
            notes.append(f"tag/{wid}: extra tags not in all works: {sorted(extra)}")

    attr_union: dict[str, dict[str, set]] = defaultdict(dict)
    for w in works:
        for tag_name, attrs in w.raw_attrs_by_tag.items():
            attr_union[tag_name][w.work_id] = set(attrs)
    for tag_name, per_work in attr_union.items():
        all_attrs = set().union(*per_work.values())
        for wid, attrs in per_work.items():
            missing = all_attrs - attrs
            if missing and tag_name in common_raw:
                notes.append(f"raw/{wid}: <{tag_name}> missing attributes {sorted(missing)} seen elsewhere")

    return {
        "common_raw_tags": sorted(common_raw),
        "common_tag_tags": sorted(common_tag),
        "drift_notes": notes,
    }


def main() -> None:
    raw_meta = load_metadata(RAW_DIR / "metadata.csv")
    tag_meta = load_metadata(TAG_DIR / "metadata.csv")

    # tag/src ids are the raw id + "_w" suffix; pair them up in metadata.csv
    # order (== textorder), independent of filesystem listing order.
    raw_rows = sorted(raw_meta.values(), key=lambda r: int(r["textorder"]))

    works = []
    for row in raw_rows:
        raw_id = row["id"]
        tag_id = f"{raw_id}_w"
        assert tag_id in tag_meta, f"no tag/src metadata entry for {tag_id}"
        works.append(audit_work(row, raw_id, tag_id))

    results = {
        "works": [asdict(w) for w in works],
        "schema_consistency": schema_consistency(works),
    }

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH.relative_to(REPO_ROOT)} ({len(works)} works audited)")


if __name__ == "__main__":
    main()
