#!/usr/bin/env python3
"""Exploratory hyperparameter sweep against eval/gold_dataset.csv: dense-only
vs. sparse-only vs. hybrid at RRF k in {1, 5, 10, 20, 40, 60}.

This is NOT the Sprint 3 evaluation (that's eval/scripts/run_eval.py, fixed
at the production hybrid config). This script exists to compare retrieval
methods/hyperparameters against each other, not to certify any one of them.

At the current gold dataset size (n=10 as of writing; protocol target is 50,
see docs/gold_dataset_protocol.md), the per-item rank matrix (part B of the
output) is the thing worth reading — individual items flipping ranks across
configs is a real signal at this n. The aggregate table (part A) is included
for convenience but is explicitly exploratory: recall/MRR deltas of one or
two items are within noise at n=10 and must not be read as "config X beats
config Y."

Before any of that: the same retrieval config is run twice over the full
gold set and compared exactly (chunk_ids and scores). If the two runs don't
match, this script fails loudly instead of reporting a sweep built on top of
a nondeterministic retrieval path (relevant given the recent RRF tie-break
fix, commit ea548d0 on this branch's ancestry).

Usage: python3 -m eval.scripts.run_hyperparam_sweep [--matrix-limit 50]
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

from eval.scripts.metrics import RECALL_KS, GoldItem, ItemResult, aggregate, score_item
from eval.scripts.run_eval import print_gold_dataset_status
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.retrieval.hybrid import (
    DEFAULT_PREFETCH_LIMIT,
    RetrievedChunk,
    dense_search,
    hybrid_search,
    sparse_search,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DATASET_PATH = REPO_ROOT / "eval" / "gold_dataset.csv"
DOCS_DIR = REPO_ROOT / "docs"
QDRANT_URL = "http://localhost:6333"

RRF_K_VALUES = (1, 5, 10, 20, 40, 60)
CONFIG_NAMES = ["dense", "sparse"] + [f"hybrid_k{k}" for k in RRF_K_VALUES]

# Depth searched to establish each item's "true rank" per config. Recall@10
# is unaffected by searching deeper than 10 (a rank <=10 is the same rank
# regardless of how far past it we also looked), but MRR here counts hits
# found between rank 11 and this limit too — so MRR figures below can differ
# slightly from eval/scripts/run_eval.py, which truncates hybrid retrieval
# at top-10. This is called out again next to the aggregate table.
DEFAULT_MATRIX_LIMIT = 50

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


def run_config(
    client: QdrantClient,
    config_name: str,
    query: str,
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    limit: int,
) -> list[RetrievedChunk]:
    if config_name == "dense":
        return dense_search(client, query, dense_embedder, limit=limit)
    if config_name == "sparse":
        return sparse_search(client, query, sparse_embedder, limit=limit)
    rrf_k = int(config_name.removeprefix("hybrid_k"))
    # hybrid_search's client-side tie-break (score desc, chunk_id asc) only
    # protects the final truncation to `limit` if Qdrant's own fused-result
    # request (internally sized to `prefetch_limit`) is asked for strictly
    # more than `limit` — otherwise the *server-side* window is the one
    # hitting the tie-at-cutoff nondeterminism the tie-break was built to
    # avoid (confirmed here: calling with prefetch_limit==limit==50 failed
    # the determinism check below on several hybrid_k configs). Request
    # generous headroom so the client-side sort is the one that decides.
    return hybrid_search(
        client,
        query,
        dense_embedder,
        sparse_embedder,
        limit=limit,
        prefetch_limit=max(DEFAULT_PREFETCH_LIMIT, limit * 4),
        rrf_k=rrf_k,
    )


def run_all_configs(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    limit: int,
) -> dict[str, dict[str, list[str]]]:
    """config_name -> item.id -> ranked chunk_ids (length <= limit)."""
    return {
        config_name: {
            item.id: [
                c.chunk_id
                for c in run_config(
                    client, config_name, item.query, dense_embedder, sparse_embedder, limit
                )
            ]
            for item in items
        }
        for config_name in CONFIG_NAMES
    }


def check_determinism(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    limit: int,
) -> dict[str, dict[str, list[str]]]:
    """Runs every config twice over the full gold set and asserts the
    ranked chunk_id lists match exactly. Returns the first run's results
    for reuse by the sweep proper (no third pass), since equality with the
    second run is asserted before returning."""
    print("=== Determinism check (each config run twice, compared exactly) ===")
    first = run_all_configs(client, items, dense_embedder, sparse_embedder, limit)
    second = run_all_configs(client, items, dense_embedder, sparse_embedder, limit)

    failures = []
    for config_name in CONFIG_NAMES:
        for item in items:
            run1 = first[config_name][item.id]
            run2 = second[config_name][item.id]
            if run1 != run2:
                failures.append(f"{config_name} / {item.id}: run1={run1!r}  run2={run2!r}")

    if failures:
        print(
            "DETERMINISM CHECK FAILED — refusing to run the sweep on top of "
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


def render_matrix_table(matrix: list[MatrixRow], limit: int) -> str:
    headers = ["id", "query"] + CONFIG_NAMES
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in matrix:
        query_preview = row.query
        if len(query_preview) > QUERY_PREVIEW_LEN:
            query_preview = query_preview[:QUERY_PREVIEW_LEN].rstrip() + "…"
        query_preview = query_preview.replace("|", "\\|")
        cells = [row.id, query_preview] + [format_rank(row.ranks[c], limit) for c in CONFIG_NAMES]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_aggregate_table(items: list[GoldItem], results: dict[str, dict[str, list[str]]]) -> str:
    headers = ["config"] + [f"recall@{k}" for k in RECALL_KS] + ["mrr", "n"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for config_name in CONFIG_NAMES:
        item_results = [
            ItemResult(item=item, rank=score_item(item, results[config_name][item.id]).rank)
            for item in items
        ]
        metrics = aggregate(item_results)
        cells = [config_name] + [f"{metrics[f'recall@{k}']:.3f}" for k in RECALL_KS]
        cells += [f"{metrics['mrr']:.3f}", str(metrics["n"])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(
    items: list[GoldItem],
    results: dict[str, dict[str, list[str]]],
    matrix_limit: int,
    timestamp: str,
    git: dict[str, str],
) -> str:
    n = len(items)
    exploratory_banner = (
        f"> **EXPLORATORY — NOT STATISTICALLY MEANINGFUL AT n={n}.** "
        f"docs/gold_dataset_protocol.md targets n=50; this pass is a small-sample "
        "smoke comparison only. Read the per-item rank matrix (part B) as the "
        "primary output — the aggregate table (part A) is included for "
        "convenience but recall/MRR deltas of one or two items are noise at this n."
    )
    return f"""# Retrieval hyperparameter sweep — exploratory

- **Generated**: {timestamp}
- **Git commit**: `{git['commit']}` (branch `{git['branch']}`)
- **Working tree had uncommitted changes at run time**: {git['dirty']}
- **Gold dataset**: `eval/gold_dataset.csv`, n={n}
- **Matrix search depth**: top-{matrix_limit} per config (see note under part A)

This file's name and the metadata above identify this as a small-n pass —
compare the `n=` value here against any later re-run before treating results
as comparable; a re-run at n=25+ is a materially different, more trustworthy
sample, not just "more of the same data."

{exploratory_banner}

## Determinism check

Every config below was run twice over the full gold set before any table was
computed; ranked chunk_ids and scores matched exactly across both runs (see
script stdout for the full log). The sweep tables reuse that verified first
run rather than a third, unverified pass.

## Part B — per-item rank matrix (primary output at this n)

Rank of the first gold `chunk_id` for each item, per config. `>{matrix_limit}`
means the gold chunk did not appear in the top {matrix_limit} retrieved for
that config — not necessarily "never retrievable," just outside the depth
searched here.

{render_matrix_table(build_rank_matrix(items, results), matrix_limit)}

## Part A — aggregate table (exploratory / not statistically meaningful at n={n})

recall@k and MRR per configuration, aggregated over all {n} gold items.
**Do not read small deltas between configs here as a real ranking of
methods at this sample size** — use part B to see which specific items
drive any difference. MRR is computed over the same top-{matrix_limit}
retrieval depth as the rank matrix, so it may differ slightly from
`eval/scripts/run_eval.py`'s production config, which truncates hybrid
retrieval at top-10.

{render_aggregate_table(items, results)}

## Configs

- `dense`: BGE-M3 dense-only, no fusion.
- `sparse`: BM25-on-stems sparse-only, no fusion.
- `hybrid_k{{1,5,10,20,40,60}}`: dense + sparse, Qdrant-native RRF fusion at
  the given `k` (`src/retrieval/hybrid.py`). Project default is k=60
  (Cormack et al. 2009 standard value, see `RRF_K` in that module) —
  the rest of this sweep is what motivates whether that default should
  ever be revisited, not a claim that it should.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-limit",
        type=int,
        default=DEFAULT_MATRIX_LIMIT,
        help=f"Search depth per config for the rank matrix (default: {DEFAULT_MATRIX_LIMIT}).",
    )
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .md path (default: docs/eval_hyperparam_sweep_n<N>_<timestamp>.md).",
    )
    args = parser.parse_args()

    items = print_gold_dataset_status(GOLD_DATASET_PATH)

    client = QdrantClient(url=args.qdrant_url)
    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()

    results = check_determinism(client, items, dense_embedder, sparse_embedder, args.matrix_limit)

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    git = git_info()

    report = render_report(items, results, args.matrix_limit, timestamp, git)

    output_path = args.output
    if output_path is None:
        file_timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DOCS_DIR / f"eval_hyperparam_sweep_n{len(items)}_{file_timestamp}.md"

    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
