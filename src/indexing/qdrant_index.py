"""Qdrant collection: one point per chunk, two named vectors (`dense`,
`sparse`) on the same point — not two separate collections.

Point IDs are UUID5s derived deterministically from `chunk_id`, so
re-indexing an unchanged corpus upserts the same points instead of
duplicating them (idempotency requirement, docs/ROADMAP.md Sprint 2).
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient, models

from src.indexing.embeddings import DENSE_DIM

COLLECTION_NAME = "bergson_chunks"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Fixed namespace so point IDs are stable across processes/machines.
_POINT_ID_NAMESPACE = uuid.UUID("6f6f9e2e-6b8b-4c1a-9c8e-3a1e9d2f5b7a")

PAYLOAD_FIELDS = (
    "work_id",
    "chunk_id",
    "section_id",
    "section_path",
    "paragraph_ids",
    "page_start",
    "page_end",
    "text",
)


def point_id_for(chunk_id: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, chunk_id))


def ensure_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            DENSE_VECTOR_NAME: models.VectorParams(size=DENSE_DIM, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: models.SparseVectorParams(),
        },
    )


def chunk_to_point(
    chunk: dict,
    dense_vector: list[float],
    sparse_vector: tuple[list[int], list[float]],
) -> models.PointStruct:
    indices, values = sparse_vector
    return models.PointStruct(
        id=point_id_for(chunk["chunk_id"]),
        vector={
            DENSE_VECTOR_NAME: dense_vector,
            SPARSE_VECTOR_NAME: models.SparseVector(indices=indices, values=values),
        },
        payload={field: chunk[field] for field in PAYLOAD_FIELDS},
    )


def upsert_points(client: QdrantClient, points: list[models.PointStruct]) -> None:
    client.upsert(collection_name=COLLECTION_NAME, points=points)
