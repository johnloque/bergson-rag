// Publisher per work, for the Sources sub-page (`routes/Sources.tsx`,
// Sprint 12). Extracted by `scripts/extract_source_metadata.py` from
// `data/raw/corpus/raw/src/*.xml`'s `publicationStmt/publisher` — printed
// for manual review, hand-transcribed here, same "generated but committed
// as source" convention `lib/works.ts`/`src/works.py` use. Re-run that
// script and re-verify by hand before changing any entry below.
//
// Not `sourceDesc`, despite that being the field this page was originally
// asked to read the publisher from: checked against the real XML,
// `sourceDesc` only ever holds a free-text note on the *print edition
// consulted for the encoding* (e.g. "144e édition de ... (1970), texte
// conforme obtenu sur le site de l'UQAC ...") — it never names a publisher,
// for any of the 8 works. `publicationStmt/publisher` is the actual TEI
// field for that, and gives the same value, "Félix Alcan", for all 8 —
// correctly: he was Bergson's sole publisher throughout his lifetime
// (`docs/xml_audit_report.md`'s bibliographic-metadata pass). This is a
// coincidence worth flagging (it matches this feature's own design-mockup
// placeholder text) but is the genuinely extracted value, not a leftover
// stand-in — see the extraction script's own docstring and
// `tests/test_source_metadata.py` for the verification.
//
// `sourceDesc` is used for what it actually documents: a per-work
// consistency check (does it mention the work's own title), reusing
// `scripts/audit_xml_corpus.py:source_desc_matches_title`. 1888_EDIC still
// fails that check as of this table's last extraction — its `sourceDesc`
// still describes *L'Énergie spirituelle* instead of *Essai sur les
// données immédiates de la conscience*, a known copy-paste error
// (`docs/xml_audit_report.md` Sec. 5) not yet fixed upstream on
// bergson-synoptique. Its `PUBLISHERS` entry below is unaffected (sourced
// from `publicationStmt`, not `sourceDesc`), but the mismatch itself is
// real and open — do not assume it's been corrected without re-running the
// extraction script.
export const PUBLISHERS: Record<string, string> = {
  '1888_EDIC': 'Félix Alcan',
  '1896_MM': 'Félix Alcan',
  '1900_R': 'Félix Alcan',
  '1907_EC': 'Félix Alcan',
  '1919_ES': 'Félix Alcan',
  '1922_DS': 'Félix Alcan',
  '1932_2S': 'Félix Alcan',
  '1934_PM': 'Félix Alcan',
}

// 1888_EDIC's still-open sourceDesc/title mismatch (see above) — imported
// by `routes/Sources.tsx` to log a loud, explicit console warning rather
// than silently rendering as if the corpus were clean, and by
// `routes/Sources.test.tsx` to assert that warning fires.
export const KNOWN_SOURCE_DESC_MISMATCHES: readonly string[] = ['1888_EDIC']
