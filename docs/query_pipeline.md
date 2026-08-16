# query_pipeline.py

Ad-hoc CLI (`scripts/query_pipeline.py`) for manually testing the full
retrieval + reranking + generation pipeline end-to-end, from a single query
string. It runs hybrid retrieval (`src/retrieval/hybrid.py`) through
cross-encoder reranking (`src/retrieval/reranking.py`) into evidence-
conditioned LLM synthesis (`src/generation/generate.py`), then prints the
retrieved evidence and the generated answer — for inspection during
development, not used by the retrieval or generation pipelines themselves.

## Prerequisites

- Qdrant running (`docker compose up qdrant`)
- The `bergson_chunks` collection already built (`scripts/build_index.py`)
- A reachable LLM: Ollama running locally with the default model pulled
  (`ollama pull mistral`), or `MISTRAL_API_KEY` set for the default hosted
  fallback, or `BERGSON_LLM_FALLBACK_MODEL` set to a different LiteLLM model
  string with its own provider API key configured — see
  `docs/generation_strategy.md`.

## Usage

```
scripts/query_pipeline.py QUERY [options]
```

`QUERY` is any string, passed as a positional argument.

### Options

| Flag | Default | Description |
|---|---|---|
| `-k`, `--limit` | `5` | Number of reranked chunks passed to the LLM as evidence. |
| `--prefetch-limit` | `50` | Per-pipeline (dense/sparse) candidate pool size before RRF fusion. |
| `--rerank-candidates` | `15` | Candidate pool size passed to the reranker. |
| `--no-rerank` | off | Skip reranking; generate directly from the hybrid retrieval output. |
| `--model` | `ollama_chat/mistral` | LiteLLM model string used for generation. |
| `--fallback-model` | `$BERGSON_LLM_FALLBACK_MODEL` or `mistral/mistral-small-latest` | LiteLLM model string used if `--model` fails. |
| `--collection` | `bergson_chunks` | Qdrant collection name. |
| `--qdrant-url` | `http://localhost:6333` | Qdrant instance URL. |
| `--full` | off | Print each evidence chunk's full text instead of a truncated snippet. |
| `--show-prompt` | off | Also print the full prompt sent to the LLM. |

### Pipeline

1. **Retrieval** — `hybrid_search`: dense (BGE-M3) + sparse (BM25) prefetch
   on the raw query, fused via Qdrant-native RRF. Retrieves
   `max(--limit, --rerank-candidates)` candidates (or just `--limit` with
   `--no-rerank`), so the reranker sees its full intended candidate pool.
2. **Reranking** — `rerank` (`bge-reranker-v2-m3`): reorders the candidates
   by cross-encoder relevance to the query, then truncates to `--limit`.
   Skipped with `--no-rerank`.
3. **Generation** — `generate_from_chunks`: computes the evidence-
   conditioning signals (work count, dense-vector convergence, reranking
   confidence — `src/generation/signals.py`), builds the evidence-
   conditioned prompt (`src/generation/prompt.py`), and calls the LLM via
   LiteLLM, falling back to `--fallback-model` if `--model` fails.

## Examples

```
scripts/query_pipeline.py "Qu'est-ce que la durée selon Bergson ?" -k 3
scripts/query_pipeline.py "duree memoire" --model mistral/mistral-small-latest --show-prompt
scripts/query_pipeline.py "clou" --no-rerank -k 5
```

## Output

- **Evidence**: for each chunk used, in descending score order: rank, score
  (rerank + RRF score, or just retrieval score with `--no-rerank`), work ID,
  section path, source page range, chunk ID, and the chunk text (snippet or
  full, per `--full`).
- **Prompt** (with `--show-prompt`): the exact prompt sent to the LLM.
- **Signals**: the evidence-conditioning signals computed from the final
  chunk selection (works covered, dense-vector convergence, reranking
  confidence).
- **Answer**: the generated answer, with the model that actually produced it
  (`--model`, or `--fallback-model`/its default if the primary call failed).

See also `scripts/query_retrieval.py` / `docs/query_retrieval.md` and
`scripts/query_hybrid_retrieval.py` / `docs/query_hybrid_retrieval.md` to
test the retrieval stages individually, without reranking or generation.
