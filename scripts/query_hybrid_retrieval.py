#!/usr/bin/env python3
"""Ad-hoc CLI to try the hybrid retrieval pipeline against a live Qdrant index.

Runs a single query through dense (BGE-M3) + sparse (BM25) prefetch,
fused via Qdrant-native RRF (src/retrieval/hybrid.py), and prints the
top matches. For manual testing/inspection only — not used by the
indexing or ingestion pipelines.

Usage:
    scripts/query_hybrid_retrieval.py "la duree et la memoire"
    scripts/query_hybrid_retrieval.py "duree memoire" -k 5 --prefetch-limit 100

Requires Qdrant running with the collection already built
(scripts/build_index.py).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient  # noqa: E402

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder  # noqa: E402
from src.indexing.qdrant_index import COLLECTION_NAME  # noqa: E402
from src.retrieval.hybrid import DEFAULT_PREFETCH_LIMIT, RetrievedChunk, hybrid_search  # noqa: E402

QDRANT_URL = "http://localhost:6333"
SNIPPET_LENGTH = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query the hybrid (dense + sparse, RRF-fused) retrieval pipeline."
    )
    parser.add_argument("query", help="Query text.")
    parser.add_argument(
        "-k", "--limit", type=int, default=10, help="Number of results to return (default: 10)."
    )
    parser.add_argument(
        "--prefetch-limit",
        type=int,
        default=DEFAULT_PREFETCH_LIMIT,
        help=(
            "Per-pipeline candidate pool size before RRF fusion "
            f"(default: {DEFAULT_PREFETCH_LIMIT})."
        ),
    )
    parser.add_argument(
        "--collection",
        default=COLLECTION_NAME,
        help=f"Collection name (default: {COLLECTION_NAME}).",
    )
    parser.add_argument(
        "--qdrant-url", default=QDRANT_URL, help=f"Qdrant URL (default: {QDRANT_URL})."
    )
    parser.add_argument(
        "--full", action="store_true", help="Print full chunk text instead of a snippet."
    )
    return parser.parse_args()


def format_page_range(page_start: dict, page_end: dict) -> str:
    start, end = page_start["display"], page_end["display"]
    return start if start == end else f"{start}-{end}"


def snippet(text: str, length: int = SNIPPET_LENGTH) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if len(collapsed) <= length else collapsed[:length].rstrip() + "..."


def print_results(chunks: list[RetrievedChunk], full: bool) -> None:
    if not chunks:
        print("No results.")
        return
    for rank, chunk in enumerate(chunks, start=1):
        pages = format_page_range(chunk.page_start, chunk.page_end)
        header = f"{chunk.work_id}  {chunk.section_path}  p. {pages}"
        print(f"[{rank}] score={chunk.score:.4f}  {header}")
        print(f"    chunk_id={chunk.chunk_id}")
        print(f"    {chunk.text if full else snippet(chunk.text)}")
        print()


def main() -> None:
    args = parse_args()
    client = QdrantClient(url=args.qdrant_url)
    chunks = hybrid_search(
        client,
        args.query,
        dense_embedder=DenseEmbedder(),
        sparse_embedder=SparseEmbedder(),
        limit=args.limit,
        prefetch_limit=args.prefetch_limit,
        collection_name=args.collection,
    )
    print_results(chunks, args.full)


if __name__ == "__main__":
    main()
