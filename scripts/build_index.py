#!/usr/bin/env python3
"""Build the hybrid Qdrant index from data/processed/chunks/.

Usage: python3 scripts/build_index.py
Requires Qdrant running (docker compose up qdrant) and the corpus
already ingested (scripts/run_ingestion.py).
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.indexer import (
    index_chunks,
    load_chunks,
    normalize_chunks,
    save_lemmas,
    save_stems,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_DIR = REPO_ROOT / "data" / "processed" / "chunks"
LEMMAS_DIR = REPO_ROOT / "data" / "processed" / "lemmas"
STEMS_DIR = REPO_ROOT / "data" / "processed" / "stems"
QDRANT_URL = "http://localhost:6333"


def main() -> None:
    client = QdrantClient(url=QDRANT_URL)
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
