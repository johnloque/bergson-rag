#!/usr/bin/env python3
"""Sprint 3 retrieval-only evaluation: hybrid search (src/retrieval/hybrid.py)
against eval/gold_dataset.csv. Reports recall@{1,3,5,10} and MRR, overall
and broken down by category / vocabulary_type / difficulty / query_style.

Usage: python3 -m eval.scripts.run_eval [--limit 10]
Requires Qdrant running with the built index (scripts/build_index.py).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from eval.scripts.metrics import BREAKDOWN_ATTRS, RECALL_KS, GoldItem, full_report, score_item
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.retrieval.hybrid import hybrid_search

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


def load_gold_dataset(path: Path) -> list[GoldItem]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [
            GoldItem(
                id=row["id"],
                category=row["category"],
                query=row["query"],
                query_style=row["query_style"],
                ground_truth_type=row["ground_truth_type"],
                chunk_ids=tuple(c.strip() for c in row["chunk_ids"].split(",") if c.strip()),
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


def format_metrics(metrics: dict) -> str:
    parts = [f"recall@{k}={metrics[f'recall@{k}']:.3f}" for k in RECALL_KS]
    parts.append(f"mrr={metrics['mrr']:.3f}")
    parts.append(f"n={metrics['n']}")
    return "  ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=max(RECALL_KS), help="Top-k retrieved per query (default: 10)."
    )
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    args = parser.parse_args()

    items = print_gold_dataset_status(GOLD_DATASET_PATH)

    client = QdrantClient(url=args.qdrant_url)
    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()

    results = []
    for item in items:
        retrieved = hybrid_search(
            client, item.query, dense_embedder, sparse_embedder, limit=args.limit
        )
        results.append(score_item(item, [chunk.chunk_id for chunk in retrieved]))

    report = full_report(results)

    print("=== Overall ===")
    print(format_metrics(report["overall"]))
    for attr in BREAKDOWN_ATTRS:
        print(f"\n=== By {attr} ===")
        for value, metrics in report["by"][attr].items():
            print(f"{value:20s} {format_metrics(metrics)}")


if __name__ == "__main__":
    main()
