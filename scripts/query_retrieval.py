#!/usr/bin/env python3
"""Ad-hoc CLI to try the retrieval pipelines against a live Qdrant index.

Runs a single dense (BGE-M3) or sparse (BM25) query against the
`bergson_chunks` collection and prints the top matches. For manual
testing/inspection only — not used by the indexing or ingestion
pipelines.

Usage:
    scripts/query_retrieval.py "la duree et la memoire" --method dense
    scripts/query_retrieval.py "duree memoire" -m sparse -k 5
Requires Qdrant running with the collection already built
(scripts/build_index.py).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient, models  # noqa: E402

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder  # noqa: E402
from src.indexing.normalize import stem  # noqa: E402
from src.indexing.qdrant_index import (  # noqa: E402
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)

QDRANT_URL = "http://localhost:6333"
SNIPPET_LENGTH = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the hybrid Qdrant retrieval index.")
    parser.add_argument("query", help="Query text.")
    parser.add_argument(
        "-m",
        "--method",
        choices=["dense", "sparse"],
        default="dense",
        help="Retrieval pipeline to use (default: dense).",
    )
    parser.add_argument(
        "-k", "--limit", type=int, default=10, help="Number of results to return (default: 10)."
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


def build_query(method: str, text: str) -> tuple[models.QueryInterface, str]:
    if method == "dense":
        vector = DenseEmbedder().embed([text])[0]
        return vector, DENSE_VECTOR_NAME

    bm25_text = " ".join(t.stem for t in stem(text))
    indices, values = SparseEmbedder().embed([bm25_text])[0]
    return models.SparseVector(indices=indices, values=values), SPARSE_VECTOR_NAME


def format_page_range(page_start: dict, page_end: dict) -> str:
    start, end = page_start["display"], page_end["display"]
    return start if start == end else f"{start}-{end}"


def snippet(text: str, length: int = SNIPPET_LENGTH) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if len(collapsed) <= length else collapsed[:length].rstrip() + "..."


def print_results(points: list[models.ScoredPoint], full: bool) -> None:
    if not points:
        print("No results.")
        return
    for rank, point in enumerate(points, start=1):
        payload = point.payload or {}
        pages = format_page_range(payload["page_start"], payload["page_end"])
        header = f"{payload['work_id']}  {payload['section_path']}  p. {pages}"
        print(f"[{rank}] score={point.score:.4f}  {header}")
        print(f"    chunk_id={payload['chunk_id']}")
        print(f"    {payload['text'] if full else snippet(payload['text'])}")
        print()


def main() -> None:
    args = parse_args()
    client = QdrantClient(url=args.qdrant_url)
    query, using = build_query(args.method, args.query)
    response = client.query_points(
        collection_name=args.collection,
        query=query,
        using=using,
        limit=args.limit,
        with_payload=True,
    )
    print_results(response.points, args.full)


if __name__ == "__main__":
    main()
