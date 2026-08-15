# query_hybrid_retrieval.py

Ad-hoc CLI (`scripts/query_hybrid_retrieval.py`) for manually testing
the hybrid retrieval pipeline (`src/retrieval/hybrid.py`) against a
live Qdrant index. It runs a single query through dense (BGE-M3) +
sparse (BM25) prefetch, fused via Qdrant-native RRF, and prints the
top matches — for inspection during development, not used by the
ingestion or indexing pipelines.

## Prerequisites

- Qdrant running (`docker compose up qdrant`)
- The `bergson_chunks` collection already built (`scripts/build_index.py`)

## Usage

```
scripts/query_hybrid_retrieval.py QUERY [options]
```

`QUERY` is any string, passed as a positional argument.

### Options

| Flag | Default | Description |
|---|---|---|
| `-k`, `--limit` | `10` | Number of fused results to return. |
| `--prefetch-limit` | `50` | Per-pipeline (dense/sparse) candidate pool size before RRF fusion. |
| `--collection` | `bergson_chunks` | Qdrant collection name. |
| `--qdrant-url` | `http://localhost:6333` | Qdrant instance URL. |
| `--full` | off | Print each chunk's full text instead of a truncated snippet. |

## Examples

```
scripts/query_hybrid_retrieval.py "De quel philosophe Bergson reconstitue-t-il la pensée à la manière d'une recette de cuisine ?"
scripts/query_hybrid_retrieval.py "duree memoire" -k 5 --prefetch-limit 100
```

## Output

For each fused match, in descending RRF score order: rank, score, work
ID, section path, source page range, chunk ID, and the chunk text
(snippet or full, per `--full`).

See also `scripts/query_retrieval.py` / `docs/query_retrieval.md` to
test the dense and sparse pipelines individually.
