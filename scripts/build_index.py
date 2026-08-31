#!/usr/bin/env python3
"""Build the hybrid Qdrant index from data/processed/chunks/.

Usage: python3 scripts/build_index.py [--rebuild]
Requires Qdrant running (docker compose up qdrant) and the corpus
already ingested (scripts/run_ingestion.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qdrant_client import QdrantClient  # noqa: E402

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder  # noqa: E402
from src.indexing.indexer import (  # noqa: E402
    index_chunks,
    load_chunks,
    normalize_chunks,
    save_lemmas,
    save_stems,
)
from src.indexing.qdrant_index import COLLECTION_NAME  # noqa: E402

CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"
LEMMAS_DIR = REPO_ROOT / "data" / "processed" / "lemmas"
STEMS_DIR = REPO_ROOT / "data" / "processed" / "stems"
QDRANT_URL = "http://localhost:6333"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            f"Delete the existing '{COLLECTION_NAME}' collection before indexing, "
            "instead of upserting into it. Required after a chunking-strategy "
            "change (chunk_id no longer refers to the same paragraphs), since "
            "upserting alone would mix stale and fresh points."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = QdrantClient(url=QDRANT_URL)

    if args.rebuild and client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing '{COLLECTION_NAME}' collection.")

    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()

    for chunks_path in sorted(CHUNKS_DIR.glob("*.json")):
        work_id = chunks_path.stem
        chunks = load_chunks(work_id, CHUNKS_DIR)
        normalized = normalize_chunks(chunks)
        save_lemmas(work_id, chunks, normalized, LEMMAS_DIR)
        save_stems(work_id, chunks, normalized, STEMS_DIR)
        indexed = index_chunks(client, chunks, normalized, dense_embedder, sparse_embedder)
        print(f"{work_id}: {len(chunks)} chunks, {indexed} points indexed")


if __name__ == "__main__":
    main()
