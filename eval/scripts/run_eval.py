"""Retrieval building block shared by the eval report scripts: hybrid search
(src/retrieval/hybrid.py) against eval/gold_dataset.csv, with optional
cross-encoder reranking (src/retrieval/reranking.py) on top.

Pure functions only — embedding, hybrid_search, optional reranking, gold
dataset loading — no CLI, no printing beyond gold-dataset completeness
warnings, no file output. `retrieve()` returns results for callers to score
and report themselves.

`eval/gold_dataset.csv` expresses ground truth as `paragraph_ids`
(`fix/gold-dataset-paragraph-refs`), stable across re-chunking; `GoldItem`
still carries `chunk_ids`, resolved at load time via
`src.paragraph_chunk_map` against whatever chunking `CHUNKS_DIR` currently
holds, since that's what `/retrieve` results are scored against.

Consumers:
- eval/scripts/run_hyperparam_sweep.py — dense/sparse/hybrid_k sweep report
- eval/scripts/run_reranking_comparison.py — hybrid-only vs +rerank report

Requires Qdrant running with the built index (scripts/build_index.py).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from eval.scripts.metrics import RECALL_KS, GoldItem
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.paragraph_chunk_map import parse_paragraph_id, resolve_chunk_id
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranking import DEFAULT_RERANK_CANDIDATES, CrossEncoderReranker
from src.retrieval.reranking import rerank as apply_reranking

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DATASET_PATH = REPO_ROOT / "eval" / "gold_dataset.csv"
CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"
QDRANT_URL = "http://localhost:6333"

# docs/gold_dataset_protocol.md targets — used only to flag an
# incomplete/stale dataset, never to block a run: the breakdown logic is
# meant to be exercised now even on a small sample (docs/ROADMAP.md).
PROTOCOL_TARGET_N = 50
PROTOCOL_MIN_KEYWORD_STYLE = 8
PROTOCOL_MIN_FOOTNOTE_RELATED = 3


def _resolve_gold_paragraph_id(row_id: str, paragraph_id: str, chunks_dir: Path) -> str:
    """Current chunk_id for one gold `paragraph_id`, via
    `src.paragraph_chunk_map` (`feat/backend-reference-data`) — the only
    place gold paragraph_ids get parsed or resolved, so every eval script
    stays behind the same lookup. A paragraph_id resolves to exactly one
    chunk_id under any given chunking (non-overlapping paragraph groups,
    Sprint 1) — `resolve_chunk_id` asserts that rather than silently
    handling zero or multiple matches."""
    try:
        work_id, _ = parse_paragraph_id(paragraph_id)
    except ValueError as exc:
        raise ValueError(f"gold item {row_id}: {exc}") from exc
    return resolve_chunk_id(work_id, paragraph_id, chunks_dir)


def load_gold_dataset(path: Path, chunks_dir: Path = CHUNKS_DIR) -> list[GoldItem]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [
            GoldItem(
                id=row["id"],
                category=row["category"],
                query=row["query"],
                query_style=row["query_style"],
                ground_truth_type=row["ground_truth_type"],
                chunk_ids=tuple(
                    _resolve_gold_paragraph_id(row["id"], p.strip(), chunks_dir)
                    for p in row["paragraph_ids"].split(",")
                    if p.strip()
                ),
                expected_anwser=row["expected_anwser"],
                vocabulary_type=row["vocabulary_type"],
                difficulty=row["difficulty"],
                footnote_related=row["footnote_related"],
            )
            for row in reader
        ]


def check_gold_dataset(items: list[GoldItem]) -> list[str]:
    """Non-fatal completeness checks against the protocol's targets
    (docs/gold_dataset_protocol.md). The real, fully-annotated dataset is
    expected to live on a separate branch per the Sprint 3 task — this
    flags a dataset that looks like a stub/partial import instead of
    silently treating it as final."""
    warnings = []
    n = len(items)
    if n < PROTOCOL_TARGET_N:
        warnings.append(
            f"only {n} items (protocol targets {PROTOCOL_TARGET_N}) — "
            "results below are not statistically meaningful yet"
        )

    known_work_ids = {p.stem for p in CHUNKS_DIR.glob("*.json")} if CHUNKS_DIR.exists() else set()
    covered_work_ids = {
        chunk_id.rsplit("_c", 1)[0] for item in items for chunk_id in item.chunk_ids
    }
    missing_works = sorted(known_work_ids - covered_work_ids)
    if missing_works:
        warnings.append(f"no gold item covers: {', '.join(missing_works)}")

    keyword_count = sum(1 for item in items if item.query_style == "keyword")
    if keyword_count < PROTOCOL_MIN_KEYWORD_STYLE:
        warnings.append(
            f"only {keyword_count} query_style=keyword items "
            f"(protocol targets >= {PROTOCOL_MIN_KEYWORD_STYLE})"
        )

    footnote_count = sum(
        1 for item in items if item.footnote_related.lower() in ("oui", "yes", "true")
    )
    if footnote_count < PROTOCOL_MIN_FOOTNOTE_RELATED:
        warnings.append(
            f"only {footnote_count} footnote_related items "
            f"(protocol targets >= {PROTOCOL_MIN_FOOTNOTE_RELATED})"
        )

    return warnings


def print_gold_dataset_status(path: Path) -> list[GoldItem]:
    if not path.exists():
        print(
            f"gold dataset not found at {path} — the annotated gold dataset lives on a "
            "separate branch per Sprint 3 scope; merge/pull it before running this eval "
            "(refusing to evaluate on absent data).",
            file=sys.stderr,
        )
        sys.exit(1)

    items = load_gold_dataset(path)
    if not items:
        print(
            f"{path} exists but has 0 items — refusing to evaluate on empty data.", file=sys.stderr
        )
        sys.exit(1)

    warnings = check_gold_dataset(items)
    if warnings:
        print(f"WARNING: {path} looks incomplete relative to docs/gold_dataset_protocol.md:")
        for warning in warnings:
            print(f"  - {warning}")
        print("Proceeding anyway — see docs/gold_dataset_protocol.md for the full target set.\n")
    return items


def retrieve(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    *,
    limit: int = max(RECALL_KS),
    rerank: bool = False,
    rerank_candidates: int = DEFAULT_RERANK_CANDIDATES,
    reranker: CrossEncoderReranker | None = None,
) -> dict[str, list[str]]:
    """item.id -> ranked chunk_ids (length <= limit) from hybrid retrieval,
    optionally cross-encoder reranked on top of the same baseline.

    When `rerank` is set, retrieves `max(limit, rerank_candidates)` chunks so
    the reranker sees its full intended candidate pool, reorders them, then
    truncates to `limit` — same hybrid retrieval call either way, only the
    post-processing differs, so callers can isolate the reranker's
    contribution by calling this once with rerank=False and once with
    rerank=True over the same items.

    Pass `reranker` to reuse an already-loaded CrossEncoderReranker across
    calls; otherwise one is constructed when rerank=True.
    """
    active_reranker: CrossEncoderReranker | None = None
    if rerank:
        active_reranker = reranker or CrossEncoderReranker()
    retrieve_limit = max(limit, rerank_candidates) if rerank else limit

    results = {}
    for item in items:
        retrieved = hybrid_search(
            client, item.query, dense_embedder, sparse_embedder, limit=retrieve_limit
        )
        if active_reranker is not None:
            retrieved = apply_reranking(item.query, retrieved, active_reranker)
        results[item.id] = [chunk.chunk_id for chunk in retrieved[:limit]]
    return results
