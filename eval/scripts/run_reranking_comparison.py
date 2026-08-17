#!/usr/bin/env python3
"""Cross-encoder reranking comparison against eval/gold_dataset.csv: hybrid
retrieval baseline (src/retrieval/hybrid.py, RRF fusion) vs. the same
baseline with cross-encoder reranking on top (src/retrieval/reranking.py).
Isolates the reranker's own contribution — same hybrid retrieval call
either way (via eval/scripts/run_eval.py's `retrieve()`), only the
post-processing differs (docs/ROADMAP.md, Sprint 4).

Both configs are run twice over the full gold set and compared exactly
before any table is computed; if the two runs of either config don't match,
this script fails loudly instead of reporting a comparison built on top of
a nondeterministic path (same discipline as run_hyperparam_sweep.py).

Per-item rank matrix (part B) is the primary output at the current gold
dataset size — see docs/gold_dataset_protocol.md for the n=50 target. The
aggregate/breakdown tables (part A) are exploratory at this n.

Usage: python3 -m eval.scripts.run_reranking_comparison [--limit 10]
    [--rerank-candidates 15]
Requires Qdrant running with the built index (scripts/build_index.py).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient

from eval.scripts.metrics import (
    BREAKDOWN_ATTRS,
    RECALL_KS,
    GoldItem,
    ItemResult,
    aggregate,
    breakdown_by,
    score_item,
)
from eval.scripts.run_eval import GOLD_DATASET_PATH, QDRANT_URL, print_gold_dataset_status, retrieve
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.retrieval.reranking import DEFAULT_RERANK_CANDIDATES, CrossEncoderReranker

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "eval" / "results"

CONFIG_NAMES = ["hybrid_only", "hybrid_rerank"]
CONFIG_LABELS = {
    "hybrid_only": "hybrid only (no rerank)",
    "hybrid_rerank": "+ cross-encoder rerank",
}

QUERY_PREVIEW_LEN = 60


def git_info() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            return "unknown"

    dirty = bool(run("status", "--porcelain"))
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": "yes (uncommitted changes present)" if dirty else "no",
    }


def run_both_configs(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    reranker: CrossEncoderReranker,
    limit: int,
    rerank_candidates: int,
) -> dict[str, dict[str, list[str]]]:
    return {
        "hybrid_only": retrieve(
            client, items, dense_embedder, sparse_embedder, limit=limit, rerank=False
        ),
        "hybrid_rerank": retrieve(
            client,
            items,
            dense_embedder,
            sparse_embedder,
            limit=limit,
            rerank=True,
            rerank_candidates=rerank_candidates,
            reranker=reranker,
        ),
    }


def check_determinism(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    reranker: CrossEncoderReranker,
    limit: int,
    rerank_candidates: int,
) -> dict[str, dict[str, list[str]]]:
    """Runs both configs twice over the full gold set and asserts the ranked
    chunk_id lists match exactly. Returns the first run's results for reuse
    by the report (no third pass), since equality with the second run is
    asserted before returning."""
    print("=== Determinism check (each config run twice, compared exactly) ===")
    first = run_both_configs(
        client, items, dense_embedder, sparse_embedder, reranker, limit, rerank_candidates
    )
    second = run_both_configs(
        client, items, dense_embedder, sparse_embedder, reranker, limit, rerank_candidates
    )

    failures = []
    for config_name in CONFIG_NAMES:
        for item in items:
            run1 = first[config_name][item.id]
            run2 = second[config_name][item.id]
            if run1 != run2:
                failures.append(f"{config_name} / {item.id}: run1={run1!r}  run2={run2!r}")

    if failures:
        print(
            "DETERMINISM CHECK FAILED — refusing to report a comparison built on top of "
            "non-deterministic retrieval:",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        sys.exit(1)

    print(
        f"OK — {len(CONFIG_NAMES)} configs x {len(items)} items, "
        "identical results across two runs.\n"
    )
    return first


@dataclass(frozen=True)
class MatrixRow:
    id: str
    query: str
    ranks: dict[str, int | None]  # config_name -> rank


def build_rank_matrix(
    items: list[GoldItem], results: dict[str, dict[str, list[str]]]
) -> list[MatrixRow]:
    return [
        MatrixRow(
            id=item.id,
            query=item.query,
            ranks={
                config_name: score_item(item, results[config_name][item.id]).rank
                for config_name in CONFIG_NAMES
            },
        )
        for item in items
    ]


def format_rank(rank: int | None, limit: int) -> str:
    return str(rank) if rank is not None else f">{limit}"


def format_delta(before: int | None, after: int | None, limit: int) -> str:
    """Positive means reranking moved the gold chunk to an earlier (better)
    rank. A rank of None (not found within `limit`) is treated as limit + 1
    for this comparison only — it does not appear in the rank columns
    themselves."""
    if before is None and after is None:
        return "="
    b = before if before is not None else limit + 1
    a = after if after is not None else limit + 1
    delta = b - a
    return f"+{delta}" if delta > 0 else str(delta)


def render_matrix_table(matrix: list[MatrixRow], limit: int) -> str:
    headers = ["id", "query", "hybrid_only", "hybrid_rerank", "delta"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in matrix:
        query_preview = row.query
        if len(query_preview) > QUERY_PREVIEW_LEN:
            query_preview = query_preview[:QUERY_PREVIEW_LEN].rstrip() + "…"
        query_preview = query_preview.replace("|", "\\|")
        before, after = row.ranks["hybrid_only"], row.ranks["hybrid_rerank"]
        cells = [
            row.id,
            query_preview,
            format_rank(before, limit),
            format_rank(after, limit),
            format_delta(before, after, limit),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _item_results(
    config_name: str, items: list[GoldItem], results: dict[str, dict[str, list[str]]]
) -> list[ItemResult]:
    return [
        ItemResult(item=item, rank=score_item(item, results[config_name][item.id]).rank)
        for item in items
    ]


def render_aggregate_table(items: list[GoldItem], results: dict[str, dict[str, list[str]]]) -> str:
    headers = ["config"] + [f"recall@{k}" for k in RECALL_KS] + ["mrr", "n"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for config_name in CONFIG_NAMES:
        metrics = aggregate(_item_results(config_name, items, results))
        cells = [CONFIG_LABELS[config_name]] + [f"{metrics[f'recall@{k}']:.3f}" for k in RECALL_KS]
        cells += [f"{metrics['mrr']:.3f}", str(metrics["n"])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_breakdown_table(
    attr: str, items: list[GoldItem], results: dict[str, dict[str, list[str]]]
) -> str:
    per_config = {
        config_name: breakdown_by(_item_results(config_name, items, results), attr)
        for config_name in CONFIG_NAMES
    }
    values = sorted({value for bd in per_config.values() for value in bd})

    headers = [attr, "config"] + [f"recall@{k}" for k in RECALL_KS] + ["mrr", "n"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for value in values:
        for config_name in CONFIG_NAMES:
            metrics = per_config[config_name].get(value)
            if metrics is None:
                continue
            cells = [value, CONFIG_LABELS[config_name]]
            cells += [f"{metrics[f'recall@{k}']:.3f}" for k in RECALL_KS]
            cells += [f"{metrics['mrr']:.3f}", str(metrics["n"])]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(
    items: list[GoldItem],
    results: dict[str, dict[str, list[str]]],
    limit: int,
    rerank_candidates: int,
    timestamp: str,
    git: dict[str, str],
) -> str:
    n = len(items)
    exploratory_banner = (
        f"> **EXPLORATORY — NOT STATISTICALLY MEANINGFUL AT n={n}.** "
        f"docs/gold_dataset_protocol.md targets n=50; this is a small-sample "
        "comparison only. Read the per-item rank matrix (part B) as the "
        "primary output — the aggregate/breakdown tables (part A) are "
        "included for convenience but recall/MRR deltas of one or two items "
        "are noise at this n."
    )
    breakdown_sections = "\n\n".join(
        f"### By {attr}\n\n{render_breakdown_table(attr, items, results)}"
        for attr in BREAKDOWN_ATTRS
    )
    retrieve_limit = max(limit, rerank_candidates)
    return f"""# Cross-encoder reranking eval — hybrid retrieval baseline vs. +rerank

- **Generated**: {timestamp}
- **Git commit**: `{git['commit']}` (branch `{git['branch']}`)
- **Working tree had uncommitted changes at run time**: {git['dirty']}
- **Gold dataset**: `eval/gold_dataset.csv`, n={n}
- **Command**: `python -m eval.scripts.run_reranking_comparison --limit {limit} \
--rerank-candidates {rerank_candidates}`

This file's name and the metadata above identify this as a small-n pass —
compare the `n=` value here against any later re-run before treating results
as comparable; a re-run at n=25+ is a materially different, more trustworthy
sample, not just "more of the same data."

{exploratory_banner}

## Determinism check

Both configs (`hybrid_only`, `hybrid_rerank`) were run twice over the full
gold set before any table was computed; ranked chunk_ids matched exactly
across both runs for each config (see script stdout for the full log). This
matches the automated determinism test in
`tests/test_reranking.py::test_rerank_is_deterministic`, which asserts the
same property at the unit level with a hand-built candidate set.

## Part B — per-item rank matrix (primary output at this n)

Rank of the first gold `chunk_id` for each item, per config. `>{limit}`
means the gold chunk did not appear in the top {limit} retrieved for that
config. `delta` = hybrid_only rank − hybrid_rerank rank, treating a missing
rank as {limit + 1} for this comparison only; positive means reranking moved
the gold chunk to an earlier (better) rank.

{render_matrix_table(build_rank_matrix(items, results), limit)}

## Part A — aggregate and breakdown tables (exploratory at n={n})

recall@k and MRR aggregated over all {n} gold items, and broken down by gold
item attribute. **Do not read small deltas here as a settled verdict on the
reranker at this sample size** — use part B to see which specific items
drive any difference.

### Overall

{render_aggregate_table(items, results)}

{breakdown_sections}

## Configs

- `hybrid_only`: `src/retrieval/hybrid.py` RRF fusion output, top-{limit},
  unmodified — the Sprint 3 baseline.
- `hybrid_rerank`: same hybrid retrieval call, retrieved at
  max(limit, rerank_candidates) = {retrieve_limit}, then reordered by
  `src/retrieval/reranking.py`'s `rerank()` (`bge-reranker-v2-m3`) and
  truncated back to {limit} before scoring.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=max(RECALL_KS), help="Top-k retrieved per query (default: 10)."
    )
    parser.add_argument(
        "--rerank-candidates",
        type=int,
        default=DEFAULT_RERANK_CANDIDATES,
        help=f"Candidate pool size passed to the reranker (default: {DEFAULT_RERANK_CANDIDATES}).",
    )
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .md path (default: eval/results/eval_reranking_n<N>_<timestamp>.md).",
    )
    args = parser.parse_args()

    items = print_gold_dataset_status(GOLD_DATASET_PATH)

    client = QdrantClient(url=args.qdrant_url)
    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()
    reranker = CrossEncoderReranker()

    results = check_determinism(
        client, items, dense_embedder, sparse_embedder, reranker, args.limit, args.rerank_candidates
    )

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    git = git_info()

    report = render_report(items, results, args.limit, args.rerank_candidates, timestamp, git)

    output_path = args.output
    if output_path is None:
        file_timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"eval_reranking_n{len(items)}_{file_timestamp}.md"

    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
