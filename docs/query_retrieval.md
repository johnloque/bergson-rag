# query_retrieval.py

Ad-hoc CLI (`scripts/query_retrieval.py`) for manually testing the
dense and sparse retrieval pipelines against a live Qdrant index. It
runs a single query and prints the top matches — for inspection during
development, not used by the ingestion or indexing pipelines.

## Prerequisites

- Qdrant running (`docker compose up qdrant`)
- The `bergson_chunks` collection already built (`scripts/build_index.py`)

## Usage

```
scripts/query_retrieval.py QUERY [options]
```

`QUERY` is any string, passed as a positional argument.

### Options

| Flag | Default | Description |
|---|---|---|
| `-m`, `--method {dense,sparse}` | `dense` | Retrieval pipeline to use. |
| `-k`, `--limit` | `10` | Number of results to return. |
| `--collection` | `bergson_chunks` | Qdrant collection name. |
| `--qdrant-url` | `http://localhost:6333` | Qdrant instance URL. |
| `--full` | off | Print each chunk's full text instead of a truncated snippet. |

### Method

- `dense`: embeds the query with the same BGE-M3 model used at
  indexing time and searches the `dense` named vector.
- `sparse`: stems the query with the same French Snowball stemmer used
  at indexing time, embeds it with the BM25 sparse embedder, and
  searches the `sparse` named vector.

## Examples

```
scripts/query_retrieval.py "De quel philosophe Bergson reconstitue-t-il la pensée à la manière d'une recette de cuisine ?" --method dense
scripts/query_retrieval.py "clou" -m sparse -k 5
```

## Output

For each match, in descending score order: rank, score, work ID,
section path, source page range, chunk ID, and the chunk text (snippet
or full, per `--full`).
