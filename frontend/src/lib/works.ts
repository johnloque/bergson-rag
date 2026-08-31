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
}

// Mirrors src/works.py's TEXTS — title/year only, no paragraph_start/end,
// since the frontend only needs this for lib/retrievalScope.ts's "which
// sources were actually considered" summary, never for paragraph
// resolution. Anthology works only (ANTHOLOGY_WORK_IDS above); keep in
// sync by hand alongside WORKS.
export const TEXTS: Record<string, TextOption[]> = {
  '1919_ES': [
    { title: 'La conscience et la vie', year: 1911 },
    { title: "L'âme et le corps", year: 1912 },
    { title: '"Fantômes de vivants" et "recherche psychique"', year: 1913 },
    { title: 'Le rêve', year: 1901 },
    { title: 'Le souvenir du présent et la fausse reconnaissance', year: 1908 },
    { title: "L'effort intellectuel", year: 1902 },
    { title: 'Le cerveau et la pensée : une illusion philosophique', year: 1904 },
  ],
  '1934_PM': [
    { title: 'Introduction (première partie)', year: 1922 },
    { title: 'Introduction (deuxième partie)', year: 1922 },
    { title: 'Le possible et le réel', year: 1930 },
    { title: "L'intuition philosophique", year: 1911 },
    { title: 'La perception du changement', year: 1911 },
    { title: 'Deuxième conférence', year: 1911 },
    { title: 'Introduction à la métaphysique', year: 1903 },
    { title: 'La philosophie de Claude Bernard', year: 1913 },
    { title: 'Sur le pragmatisme de William James. Vérité et réalité.', year: 1911 },
    { title: "La vie et l'œuvre de Ravaisson", year: 1904 },
  ],
}
