// docs/ROADMAP.md, Sprint 12: the chunk rail shows the top 15
// post-reranking chunks. Checked against the real backend rather than
// assumed: `RetrieveRequest.top_k` (src/api/schemas.py) defaults to
// `DEFAULT_TOP_K = 3` — lowered from 10 on `fix/faithfulness-citation-
// detection` to keep /generate and /evaluate's prompts from overflowing
// the judge's context window — and /retrieve's response is always exactly
// `top_k` chunks (`reranked[: body.top_k]`, src/api/main.py), reranked
// over `max(top_k, DEFAULT_RERANK_CANDIDATES)` candidates
// (`src/retrieval/reranking.py`'s `DEFAULT_RERANK_CANDIDATES = 15`). So
// the previously-omitted `top_k` (server default of 3) did not match the
// rail's 15-chunk target — this frontend now requests it explicitly.
//
// This is safe for the DEFAULT_TOP_K=3 context-window rationale above:
// /generate and /evaluate never see all `chunks` from /retrieve, only the
// client-curated `included` subset (state/turnUi.tsx), itself capped at
// MAX_INCLUDED_CHUNKS = 5 — retrieval breadth and generation-input size
// are decoupled by the rail's own selection mechanism.
export const CHUNK_RAIL_TOP_K = 15
