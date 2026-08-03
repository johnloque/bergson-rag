# XML corpus audit checklist

Audit to run once on the corpus before any chunking code is written.
Covers both sources: paragraph-level (`raw/src`) and word-level
(`tag/src`).

## 1. Tags and schema

- [ ] List all XML tags present, per file
- [ ] List all POS values present, per file
- [ ] Check schema consistency across the 8 works (same tags, same
      attributes, same conventions) — corpora encoded at different times
      often drift slightly

## 2. Corpus size

- [ ] Paragraph count per text
- [ ] Word count per text

## 3. Structure above paragraph level

- [ ] Identify available structure levels above the paragraph (chapter,
      section, part) — needed for the parent context in hierarchical
      chunking

## 4. Lemmatization quality

- [ ] Lemmatization rate (share of tokens with a non-empty `lemma`
      attribute)

## 5. Encoding

- [ ] Detect suspicious encoding artifacts (ligatures, inconsistent
      typographic apostrophes, OCR residue if the corpus comes from a
      scan)

## 6. Editorial content

- [ ] Check for footnotes, quotations from other authors, or critical
      apparatus — decide whether to include, exclude, or index them
      separately (a chunk must never mix Bergson's text with an editor's
      note without flagging it)

## 7. Cross-source alignment

- [ ] Check presence and consistency of unique paragraph identifiers
      between the raw version and the tag version

## 8. Bibliographic metadata

- [ ] Confirm, per work: exact title, first publication date, source
      edition used for the encoding
- [ ] Check whether the source edition's pagination is encoded (useful
      for precise academic citation, expected by researchers)

## Expected output

A short report at `docs/xml_audit_report.md`, using comparative tables
across the 8 works wherever possible (e.g. one row per work, one column
per check).