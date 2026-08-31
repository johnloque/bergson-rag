# Ingestion & indexing

Two sequential steps turn the raw TEI-XML corpus into a queryable Qdrant
collection: **ingestion** (parse + chunk, writes `data/processed/`) and
**indexing** (embed + upsert, writes to Qdrant). `make build-index` runs
both.

```
make build-index
# equivalent to:
uv run python3 scripts/run_ingestion.py
uv run python3 scripts/build_index.py
```

Requires the corpus fetched (`scripts/fetch_corpus.sh` / `make
fetch-data`) and Qdrant running (`docker compose up qdrant`).

Run both scripts through `uv run` (as the Makefile does), not a bare
`python3` — the `src` package is only importable inside the project's
`uv` environment/root, and a bare `python3 scripts/run_ingestion.py`
fails with `ModuleNotFoundError: No module named 'src'`.

## Ingestion — `scripts/run_ingestion.py`

For each work in `data/raw/corpus/raw/src`:

1. `parse_corpus` parses the TEI-XML into a `Work` (sections, paragraphs).
   Paragraph IDs (`{work_id}_p{n}`) are assigned sequentially at parse
   time and are stable across reruns — they don't exist in the source
   XML (`src/ingestion/models.py`).
2. `chunk_work` (`src/ingestion/chunking.py`) turns the work's paragraphs
   into chunks. **One chunk = one paragraph**: chunk and paragraph
   boundaries are identical, and a section boundary is always a chunk
   boundary too (a chunk never spans two sections). `chunk_id` is
   `{work_id}_c{n}`, renumbered from scratch on every run — it is **not**
   stable the way `paragraph_id` is.
3. Output is written to `data/processed/{works,paragraphs,chunks}/`.

Because `chunk_id` isn't stable across chunking-strategy changes, ground
truth (e.g. `eval/gold_dataset.csv`) is keyed on `paragraph_id` instead
and resolved to whatever `chunk_id` currently holds it via
`src/paragraph_chunk_map.py::resolve_chunk_ids`.

## Indexing — `scripts/build_index.py`

For each `data/processed/chunks/{work_id}.json`:

1. Normalize each chunk's text once (lemma+POS and French Snowball stem —
   `src/indexing/normalize.py`), persisted to
   `data/processed/{lemmas,stems}/`.
2. Embed: dense vector on raw text (`DenseEmbedder`), sparse vector on
   the stemmed BM25 text (`SparseEmbedder`).
3. Upsert into the single Qdrant collection `bergson_chunks`
   (`src/indexing/qdrant_index.py`) — one point per chunk, two named
   vectors (`dense`, `sparse`) on the same point. Point IDs are UUID5s
   derived deterministically from `chunk_id`
   (`point_id_for`), so re-running on an unchanged corpus re-upserts the
   same points rather than duplicating them.

```
uv run python3 scripts/build_index.py [--rebuild]
```

### `--rebuild`

Deletes the existing `bergson_chunks` collection before indexing,
instead of upserting into it. `ensure_collection` then recreates it from
scratch on the first batch.

**When to use it:** any time the chunking strategy changes (e.g. the
target chunk size, or the switch to one-chunk-per-paragraph). Because
`chunk_id` is `{work_id}_c{n}` and is renumbered from `n=1` on every
`run_ingestion.py` run, a chunking change doesn't just change what `n`
*contains* — it changes how many chunks a section produces. A plain
upsert (no `--rebuild`) would then:

- overwrite points for `chunk_id`s that still exist, with the new
  chunking's text/vectors — fine for those,
- but leave **orphaned points** in the collection for any `chunk_id`
  that existed under the old chunking but not the new one, silently
  polluting retrieval with stale text.

Without `--rebuild`, upserting is safe only when the chunking logic
itself hasn't changed (e.g. re-running after a corpus text fix). Plain
`make build-index` does not pass `--rebuild` — it stays a safe
incremental upsert by default.

Full re-chunking workflow:

```
uv run python3 scripts/run_ingestion.py
uv run python3 scripts/build_index.py --rebuild
```
