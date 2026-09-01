// Mirrors src/works.py's WORKS table (id -> title, year) — same manual-
// mirror convention as api/types.ts mirrors src/api/schemas.py (there is no
// shared build step between the Python backend and this Vite frontend).
// Keep this in sync by hand if src/works.py's 8-work set or any year ever
// changes; the year bounds below are derived from this list, not
// hardcoded, so a future corpus correction only needs one edit here.

export interface WorkOption {
  id: string
  title: string
  year: number
}

export const WORKS: WorkOption[] = [
  { id: '1888_EDIC', title: 'Essai sur les données immédiates de la conscience', year: 1888 },
  { id: '1896_MM', title: 'Matière et mémoire', year: 1896 },
  { id: '1900_R', title: 'Le rire', year: 1900 },
  { id: '1907_EC', title: "L'Évolution créatrice", year: 1907 },
  { id: '1919_ES', title: "L'énergie spirituelle", year: 1919 },
  { id: '1922_DS', title: 'Durée et simultanéité', year: 1922 },
  { id: '1932_2S', title: 'Les deux sources de la morale et de la religion', year: 1932 },
  { id: '1934_PM', title: 'La Pensée et le Mouvant', year: 1934 },
]

export const ALL_WORK_IDS = WORKS.map((w) => w.id)

// Real corpus span (earliest to latest work's publication year), derived
// from WORKS above rather than hardcoded — the chronological slider's
// min/max.
export const WORK_YEAR_RANGE = {
  min: Math.min(...WORKS.map((w) => w.year)),
  max: Math.max(...WORKS.map((w) => w.year)),
}

// The two anthology works whose individually-dated texts make "text" mode
// (vs. the default "publication" mode) actually change results — the other
// 6 works behave identically either way (docs/backend_api.md, Sprint 11).
export const ANTHOLOGY_WORK_IDS = ['1919_ES', '1934_PM']

export interface TextOption {
  title: string
  year: number
  // 1-based paragraph index range this text covers within its work
  // (inclusive both ends) — the trailing number in a paragraph_id like
  // `1919_ES_p153` -> 153. Added on `feat/chunk-rail-and-citations` for
  // `lib/citation.ts`'s `resolveParagraphMetadata`, mirroring
  // src/works.py's `TextMetadata.paragraph_start`/`paragraph_end` exactly
  // (same source values, see that module's TEXTS for provenance).
  paragraphStart: number
  paragraphEnd: number
}

// Mirrors src/works.py's TEXTS — same manual-mirror convention as WORKS
// above. Anthology works only (ANTHOLOGY_WORK_IDS above); keep in sync by
// hand alongside WORKS.
export const TEXTS: Record<string, TextOption[]> = {
  '1919_ES': [
    { title: 'La conscience et la vie', year: 1911, paragraphStart: 1, paragraphEnd: 27 },
    { title: "L'âme et le corps", year: 1912, paragraphStart: 28, paragraphEnd: 47 },
    {
      title: '"Fantômes de vivants" et "recherche psychique"',
      year: 1913,
      paragraphStart: 48,
      paragraphEnd: 68,
    },
    { title: 'Le rêve', year: 1901, paragraphStart: 69, paragraphEnd: 100 },
    {
      title: 'Le souvenir du présent et la fausse reconnaissance',
      year: 1908,
      paragraphStart: 101,
      paragraphEnd: 152,
    },
    { title: "L'effort intellectuel", year: 1902, paragraphStart: 153, paragraphEnd: 203 },
    {
      title: 'Le cerveau et la pensée : une illusion philosophique',
      year: 1904,
      paragraphStart: 204,
      paragraphEnd: 230,
    },
  ],
  '1934_PM': [
    { title: 'Introduction (première partie)', year: 1922, paragraphStart: 4, paragraphEnd: 24 },
    { title: 'Introduction (deuxième partie)', year: 1922, paragraphStart: 25, paragraphEnd: 73 },
    { title: 'Le possible et le réel', year: 1930, paragraphStart: 74, paragraphEnd: 87 },
    { title: "L'intuition philosophique", year: 1911, paragraphStart: 88, paragraphEnd: 112 },
    { title: 'La perception du changement', year: 1911, paragraphStart: 113, paragraphEnd: 129 },
    { title: 'Deuxième conférence', year: 1911, paragraphStart: 130, paragraphEnd: 152 },
    { title: 'Introduction à la métaphysique', year: 1903, paragraphStart: 153, paragraphEnd: 223 },
    { title: 'La philosophie de Claude Bernard', year: 1913, paragraphStart: 224, paragraphEnd: 232 },
    {
      title: 'Sur le pragmatisme de William James. Vérité et réalité.',
      year: 1911,
      paragraphStart: 233,
      paragraphEnd: 253,
    },
    { title: "La vie et l'œuvre de Ravaisson", year: 1904, paragraphStart: 254, paragraphEnd: 311 },
  ],
}
