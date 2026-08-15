# XML corpus audit checklist

Audit to run once on the corpus before ingestion (Sprint 1). Scoped to
`raw/src` only — the project no longer depends on `tag/src` (lemma/POS
are regenerated at indexing time, not read from the corpus repo).

## 1. Structure above paragraph level

- [ ] List structural tags present (`div`, `head`, `p`, etc.), per file
- [ ] Identify available structure levels above the paragraph (chapter,
      section, part) — needed for the parent context in hierarchical
      chunking
- [ ] Check tag/structure consistency across the 8 works

## 2. Corpus size

- [ ] Paragraph count per text

## 3. Encoding

- [ ] Detect suspicious encoding artifacts (ligatures, inconsistent
      typographic apostrophes, OCR residue if the corpus comes from a
      scan)

## 4. Editorial content

- [ ] Check for footnotes, quotations from other authors, or critical
      apparatus — decide whether to include, exclude, or index them
      separately (a chunk must never mix Bergson's text with an editor's
      note without flagging it)

## 5. Bibliographic metadata

- [ ] Confirm, per work: exact title, first publication date, source
      edition used for the encoding (`sourceDesc`)
- [ ] Check whether the source edition's pagination is encoded (useful
      for precise academic citation, expected by researchers)

## Removed from this checklist (no longer applicable)

- POS value inventory and lemmatization rate — were properties of
  `tag/src`, out of scope now that lemma/POS are regenerated at indexing
  time (spaCy + French stemmer), not sourced from the corpus repo.
- Cross-source paragraph alignment — moot with a single source; paragraph
  IDs are now assigned at ingestion, not read from either source.

## Expected output

A short report at `docs/xml_audit_report.md`, using comparative tables
across the 8 works wherever possible.
