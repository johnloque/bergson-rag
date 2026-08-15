"""Orchestrates Sprint 2 indexing for one work's chunks at a time:
normalize each chunk exactly once (lemma+POS and stem, both persisted),
then embed (dense on raw text, sparse on the normalized BM25 text) and
upsert into the single Qdrant collection.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from qdrant_client import QdrantClient

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.normalize import Normalization, normalize_text
from src.indexing.qdrant_index import chunk_to_point, ensure_collection, upsert_points

BATCH_SIZE = 32


def load_chunks(work_id: str, chunks_dir: Path) -> list[dict]:
    return json.loads((chunks_dir / f"{work_id}.json").read_text(encoding="utf-8"))


def normalize_chunks(chunks: list[dict]) -> list[Normalization]:
    """Lemma+POS and stem for each chunk's text, computed once and
    reused for both persistence (save_lemmas/save_stems) and sparse
    embedding (index_chunks) — stemming in particular must not run
    twice per chunk."""
    return [normalize_text(chunk["text"]) for chunk in chunks]


def save_lemmas(
    work_id: str, chunks: list[dict], normalized: list[Normalization], output_dir: Path
) -> Path:
    """spaCy lemma+POS per chunk. Not used for BM25 this sprint (see
    src/indexing/normalize.py) — stored for other consumers (MCP
    exact-lemma lookup, the companion lexicon-graph project)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{work_id}.json"
    records = [
        {"chunk_id": chunk["chunk_id"], "tokens": [asdict(t) for t in norm.lemmas]}
        for chunk, norm in zip(chunks, normalized, strict=True)
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def save_stems(
    work_id: str, chunks: list[dict], normalized: list[Normalization], output_dir: Path
) -> Path:
    """French Snowball stem per chunk — the BM25 sparse index input
    this sprint. Stored for debugging/inspection; the index itself only
    holds the resulting sparse vector, not these token lists."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{work_id}.json"
    records = [
        {"chunk_id": chunk["chunk_id"], "tokens": [asdict(t) for t in norm.stems]}
        for chunk, norm in zip(chunks, normalized, strict=True)
    ]
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def index_chunks(
    client: QdrantClient,
    chunks: list[dict],
    normalized: list[Normalization],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Embed and upsert `chunks`. Upsert is by deterministic point ID
    (src.indexing.qdrant_index.point_id_for), so calling this again on
    unchanged chunks does not duplicate points."""
    ensure_collection(client)
    indexed = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_norm = normalized[i : i + batch_size]
        dense_vectors = dense_embedder.embed([c["text"] for c in batch])
        sparse_vectors = sparse_embedder.embed([n.bm25_text for n in batch_norm])
        points = [
            chunk_to_point(chunk, dense_vec, sparse_vec)
            for chunk, dense_vec, sparse_vec in zip(
                batch, dense_vectors, sparse_vectors, strict=True
            )
        ]
        upsert_points(client, points)
        indexed += len(points)
    return indexed
