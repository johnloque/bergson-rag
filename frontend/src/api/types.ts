// Mirrors src/api/schemas.py (Sprint 7/7b) plus the small Sprint 8 additions
// (list/rename/delete conversations) added alongside this frontend.

export interface PageRef {
  number: number | null
  display: string
}

export interface ChunkInput {
  chunk_id: string
  text: string
  work_id: string
  section_path: string
  paragraph_ids: string[]
  page_start: PageRef
  page_end: PageRef
  score: number | null
}

export interface ChunkResult {
  chunk_id: string
  work_id: string
  section_path: string
  paragraph_ids: string[]
  page_start: PageRef
  page_end: PageRef
  text: string
  score: number
}

export type ChunkJudgmentLabel = 'pertinent' | 'partiellement pertinent' | 'non pertinent'

export interface ChunkJudgment {
  label: ChunkJudgmentLabel
  justification: string
}

// docs/ROADMAP.md, Sprint 11 retrieval filtering: `mode` defaults to
// "publication" server-side, but the filter UI (Sprint 12) always sends it
// explicitly whenever date_range is sent at all — see
// state/retrievalFilter.ts.
export type DateRangeMode = 'publication' | 'text'

export interface DateRange {
  start: number
  end: number
  mode: DateRangeMode
}

export interface RetrieveRequest {
  query: string
  top_k?: number
  // None starts a brand-new conversation (and its first turn); given, must
  // name an existing conversation (docs/ROADMAP.md, Sprint 10 turn-
  // lifecycle fix).
  conversation_id?: number | null
  // Sprint 12 filter UI: both omitted by default, matching /retrieve's
  // unfiltered behavior exactly — never sent as an explicit "all 8 works" /
  // full-span list when the user hasn't deliberately narrowed anything
  // (state/retrievalFilter.ts, docs/frontend.md).
  work_ids?: string[]
  date_range?: DateRange
}

// turn_id/conversation_id (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix):
// submitting a query creates its turn — and persists the retrieved chunk
// set against it — immediately, before any generation happens. /generate
// attaches to this turn_id rather than creating a new one.
export interface RetrieveResponse {
  turn_id: number
  conversation_id: number
  chunks: ChunkResult[]
  // Echoes exactly what was persisted against this turn (Sprint 12 filter
  // UI, src/api/models.py's Turn.work_ids/date_range) — null means no
  // filter was applied. Not needed to drive the live-session display (the
  // client already knows what it just sent); this is what a reloaded
  // page's GET /turns/{id} call reads back instead (docs/frontend.md).
  work_ids: string[] | null
  date_range: DateRange | null
}

// turn_id is required (docs/ROADMAP.md, Sprint 10 turn-lifecycle fix):
// /retrieve always creates the turn first, so /generate — whether this is
// the turn's first, manually-triggered generation or a later regeneration —
// only ever attaches to an existing turn. `query` is not resent here
// either: the server reads it back from the persisted turn instead.
export interface GenerateRequest {
  turn_id: number
  chunks: ChunkInput[]
  model?: string
  chunk_judgments?: Record<string, ChunkJudgment> | null
}

export interface GenerateResponse {
  answer: string
  model_used: string
  generation_id: number
  turn_id: number
  conversation_id: number
}

export interface EvaluateRequest {
  generation_id: number
}

export interface ClaimVerdictOut {
  statement: string
  supported: boolean
  reason: string
  // Verbatim span of the answer this claim was grounded to, for highlighting
  // (see annotateAnswer.tsx); null when the judge's quote wasn't found
  // verbatim in the answer.
  quote: string | null
}

export interface TitleYearMismatchOut {
  title: string
  work_id: string
  correct_year: number
  claimed_years: number[]
}

export interface StructuralCheckOut {
  citations: string[]
  unknown_citations: string[]
  has_citation: boolean
  // Quoted work titles the answer names that don't match any of the
  // corpus's 8 real works (src/generation/guardrail.py, Sprint 10).
  fabricated_titles: string[]
  // A real, known title paired with the wrong publication year
  // (src/generation/guardrail.py's check_title_year_mismatch,
  // fix/title-year-grounding).
  title_year_mismatches: TitleYearMismatchOut[]
  passed: boolean
}

export interface FaithfulnessOut {
  score: number | null
  model: string
  claims: ClaimVerdictOut[]
}

export type RetrievalConfidenceTier = 'très faible' | 'faible' | 'moyenne' | 'élevée'

// No retrieval_confidence_tier field (docs/ROADMAP.md, the retrieval-
// confidence-split correction): the tier is shown to the user pre-
// generation via /confidence-preview (see ConfidencePreviewResponse below),
// not repeated here.
export interface EvaluateResponse {
  structural: StructuralCheckOut
  faithfulness: FaithfulnessOut
  should_auto_expand: boolean
}

export interface ConfidencePreviewChunk {
  chunk_id: string
  score: number | null
}

export interface ConfidencePreviewRequest {
  chunks: ConfidencePreviewChunk[]
}

export interface ConfidencePreviewResponse {
  retrieval_confidence_tier: RetrievalConfidenceTier
}

export interface JudgeChunkRequest {
  query: string
  chunk: ChunkInput
  turn_id: number
  model?: string
}

export interface JudgeChunkResponse {
  label: ChunkJudgmentLabel
  justification: string
}

export interface RetrievedChunkOut {
  chunk_id: string
  rank: number
  score: number
  text: string
  work_id: string
  section_path: string
  paragraph_ids: string[]
  page_start: PageRef
  page_end: PageRef
}

export interface GenerationOut {
  generation_id: number
  model: string
  chunk_ids: string[]
  answer: string
  chunk_judgments_used: Record<string, ChunkJudgment> | null
  created_at: string
  evaluation: EvaluateResponse | null
}

export interface TurnDetailResponse {
  turn_id: number
  conversation_id: number
  query: string
  created_at: string
  retrieved_chunks: RetrievedChunkOut[]
  generations: GenerationOut[]
  chunk_judgments: Record<string, ChunkJudgment>
  // Same persisted filter as RetrieveResponse's (Sprint 12 filter UI) —
  // null means no filter was applied to this turn. Read back here so a
  // reloaded page can reconstruct and display it (state/useTurnController.ts).
  work_ids: string[] | null
  date_range: DateRange | null
}

export interface ConversationTurnOut {
  turn_id: number
  query: string
  created_at: string
}

export interface ConversationDetailResponse {
  conversation_id: number
  turns: ConversationTurnOut[]
}

export interface ConversationSummaryOut {
  conversation_id: number
  created_at: string
  title: string | null
  first_query: string | null
}

export interface ConversationListResponse {
  conversations: ConversationSummaryOut[]
}
