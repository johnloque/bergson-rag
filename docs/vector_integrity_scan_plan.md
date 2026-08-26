# Vector integrity scan — not yet done, notes for whoever picks this up

Not implemented. This documents a real, unresolved finding from
`feat/native-ml-service`'s investigation into two failing
`tests/test_retrieval.py` tests, and what a proper scan/fix would need to
do. No script or branch for this exists yet — a prior attempt
(`chore/vector-integrity-scan`) was started and then explicitly abandoned
before completion, precisely so this would be picked up deliberately later
rather than left as half-finished, uncommitted work on a throwaway branch.

## The finding

`DenseEmbedder`/`CrossEncoderReranker` (`src/indexing/embeddings.py`,
`src/retrieval/reranking.py`) auto-select `mps` on this hardware — verified
directly (`torch.backends.mps.is_available()` → `True`, both models'
underlying `.device` → `mps:0`). This was initially suspected as the cause
of two `test_retrieval.py` failures (native MPS query embedding vs.
CPU-in-container corpus embedding). **That hypothesis is disconfirmed**:
embedding the same text on `cpu` vs. `mps` explicitly gives a max absolute
difference of `~1.97e-7` and cosine `1.0` between the two — device
selection does not meaningfully change the output.

The actual cause, found by re-embedding a chunk's own stored `text`
payload with the current `DenseEmbedder` and comparing to its own stored
dense vector in Qdrant:

- `1888_EDIC_c1` (the fixture chunk in
  `test_fusion_ranks_shared_chunk_at_least_as_high`): self-cosine `0.135`
  (should be `~1.0`).
- A quick, partial sample of 200/891 points in the `bergson_chunks`
  collection: **3 inconsistent (cosine < 0.9), 197 consistent** — roughly
  1.5%, not the whole collection.
- Ruled out a simple batch-misalignment/shuffle bug: a corrupted chunk's
  stored vector doesn't match any *other* nearby chunk's freshly computed
  text vector either — the corrupted vectors are not swapped with a
  neighbor's, they look like independent noise.
- Not yet determined: whether this is a batch-write bug in
  `src/indexing/indexer.py`, a partial/interrupted reindex, or corpus text
  edited after the vectors were originally computed (indexing embeds
  `c["text"]` directly, so a later edit to stored `text` without
  re-embedding would produce exactly this symptom).

This is unrelated to `feat/native-ml-service`, to CPU/MPS device
selection, and to the separate, already-understood `RRF_K=60→1` change
(`8af5c1c`) that explains the other failing test
(`test_hybrid_search_tie_break_is_deterministic`).

## What a real scan needs to do

1. **Scroll the whole `bergson_chunks` collection** (`COLLECTION_NAME`,
   `src/indexing/qdrant_index.py`), batched (e.g. 32-64 points at a time
   to keep `DenseEmbedder.embed` batches reasonably sized).
2. **For each point: re-embed its own stored `payload["text"]`** with the
   current `DenseEmbedder` and compare to `point.vector[DENSE_VECTOR_NAME]`
   by cosine similarity. Flag anything below a threshold (0.9 is a safe
   cut — genuine noise sits far below that, real matches sit at `~1.0`).
3. **Sparse vectors need a different check, not a naive re-embed-compare**:
   the collection's sparse field uses Qdrant's IDF `Modifier`
   (`SPARSE_VECTOR_NAME`, `src/indexing/qdrant_index.py`), which
   transforms stored values relative to `SparseEmbedder.embed`'s raw
   output — comparing raw output to stored values directly would flag
   every point, not just corrupted ones. Whoever picks this up needs to
   either read Qdrant's IDF modifier formula and reproduce it before
   comparing, or find another invariant to check (e.g., that indices are
   a subset of the query-time vocabulary, or that a document known not to
   contain a term never has it in its stored sparse indices).
4. **Output**: a per-chunk_id result set (JSON, so it can be consumed
   programmatically — e.g. by a test fixture picking a confirmed-clean
   `chunk_id`) plus a human-readable summary, following this repo's
   existing audit convention (`scripts/audit_xml_corpus.py` →
   `docs/xml_audit_results.json` → `scripts/generate_xml_audit_report.py`
   → `docs/xml_audit_report.md`).
5. **Root-cause, not just detect**: the scan above only detects the
   symptom. Actually explaining *why* ~1.5% of vectors are wrong (batch
   bug vs. partial reindex vs. post-hoc text edit) needs looking at
   `src/indexing/indexer.py`'s batching logic and, if available, whatever
   history exists of `data/raw/corpus` edits after the last
   `scripts/build_index.py` run.
6. **Remediation**: once root-caused, either a full `scripts/build_index.py`
   rebuild (simplest, safe, but redoes the entire collection) or a
   targeted re-embed of just the flagged `chunk_id`s (faster, but only
   correct if the corruption is confirmed isolated to embedding, not to
   stale/wrong `payload["text"]` too).

## What depends on this

- `tests/test_retrieval.py::test_fusion_ranks_shared_chunk_at_least_as_high`
  needs its fixture chunk (`1888_EDIC_c1`) swapped for one confirmed clean
  by a real scan, and confirmed to appear in both the dense and sparse
  top-k for whatever query fixture is chosen — not just "any clean chunk,"
  the same overlap condition the original test intended
  (`docs/dockerization.md`, `feat/native-ml-service` investigation notes).
  Do not hand-pick a `chunk_id` for this without a real scan backing it —
  the whole point of doing this as its own step is that "looks fine" isn't
  the same as "confirmed self-consistent."
- `tests/test_retrieval.py::test_hybrid_search_tie_break_is_deterministic`
  does **not** depend on this scan — its fixture just needs to be
  re-derived against the current `RRF_K=1` (`src/retrieval/hybrid.py`,
  changed from `60` in `8af5c1c`, a deliberate config, not a bug), an
  independent piece of work.
