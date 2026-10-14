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

// Citation codes for the Sources page (`feat/sources-citation-codes`),
// printed by `scripts/extract_source_metadata.py` and hand-transcribed here
// like `PUBLISHERS` above. Display-only: no identifier is renamed anywhere.
//
// `WORK_CODES`: each work's `work_id` from `src/works.py`, in its order —
// the prefix of every inline citation `[{work_id}_c{n}]` in an answer.
export const WORK_CODES: readonly string[] = [
  '1888_EDIC',
  '1896_MM',
  '1900_R',
  '1907_EC',
  '1919_ES',
  '1922_DS',
  '1932_2S',
  '1934_PM',
]

export interface TextCitationRange {
  title: string
  // First and last chunk_id the text covers (inclusive), from its
  // `src/works.py` TEXTS paragraph range through
  // `src/paragraph_chunk_map.py:resolve_chunk_id`. null for a text excluded
  // from TEXTS (no extractable year): listed, but with no range.
  chunkRange: readonly [string, string] | null
}

// Per anthology, one entry per individual text in document order — citations
// carry no per-text identifier, so this range is how a reader attributes
// e.g. 1919_ES_c160 to "L'effort intellectuel". Front matter (1934_PM_c1–c3,
// the Avant-propos) is not a text and has no entry. Re-run the extraction
// script after any re-chunking: chunk numbers are not stable across chunkings.
export const ANTHOLOGY_TEXT_RANGES: Record<string, readonly TextCitationRange[]> = {
  '1919_ES': [
    { title: 'La conscience et la vie', chunkRange: ['1919_ES_c1', '1919_ES_c27'] },
    { title: "L'âme et le corps", chunkRange: ['1919_ES_c28', '1919_ES_c47'] },
    {
      title: '"Fantômes de vivants" et "recherche psychique"',
      chunkRange: ['1919_ES_c48', '1919_ES_c68'],
    },
    { title: 'Le rêve', chunkRange: ['1919_ES_c69', '1919_ES_c100'] },
    {
      title: 'Le souvenir du présent et la fausse reconnaissance',
      chunkRange: ['1919_ES_c101', '1919_ES_c152'],
    },
    { title: "L'effort intellectuel", chunkRange: ['1919_ES_c153', '1919_ES_c203'] },
    {
      title: 'Le cerveau et la pensée : une illusion philosophique',
      chunkRange: ['1919_ES_c204', '1919_ES_c230'],
    },
  ],
  '1934_PM': [
    { title: 'Introduction (première partie)', chunkRange: ['1934_PM_c4', '1934_PM_c24'] },
    { title: 'Introduction (deuxième partie)', chunkRange: ['1934_PM_c25', '1934_PM_c73'] },
    { title: 'Le possible et le réel', chunkRange: ['1934_PM_c74', '1934_PM_c87'] },
    { title: "L'intuition philosophique", chunkRange: ['1934_PM_c88', '1934_PM_c112'] },
    { title: 'La perception du changement', chunkRange: ['1934_PM_c113', '1934_PM_c129'] },
    { title: 'Deuxième conférence', chunkRange: ['1934_PM_c130', '1934_PM_c152'] },
    { title: 'Introduction à la métaphysique', chunkRange: ['1934_PM_c153', '1934_PM_c223'] },
    { title: 'La philosophie de Claude Bernard', chunkRange: ['1934_PM_c224', '1934_PM_c232'] },
    {
      title: 'Sur le pragmatisme de William James. Vérité et réalité.',
      chunkRange: ['1934_PM_c233', '1934_PM_c253'],
    },
    { title: "La vie et l'œuvre de Ravaisson", chunkRange: ['1934_PM_c254', '1934_PM_c311'] },
  ],
}

// "1919_ES_c153 à 1919_ES_c203": both endpoints as full chunk_ids, exactly as
// they appear in citations.
export function formatChunkRange([first, last]: readonly [string, string]): string {
  if (first === last) return first
  return `${first} à ${last}`
}
