"""Pydantic request/response models for the ml_service API
(feat/native-ml-service, docs/dockerization.md).

Deliberately minimal — three endpoints, one request/response pair each — no
persistence, no auth, no shapes shared with src/api/schemas.py: this service
has nothing in common with the api service beyond the model classes it
wraps (src/indexing/embeddings.py, src/retrieval/reranking.py).
"""

from __future__ import annotations

from pydantic import BaseModel


class DenseEmbedRequest(BaseModel):
    texts: list[str]


class DenseEmbedResponse(BaseModel):
    vectors: list[list[float]]


class SparseEmbedRequest(BaseModel):
    texts: list[str]


class SparseEmbedResponse(BaseModel):
    indices: list[list[int]]
    values: list[list[float]]


class RerankRequest(BaseModel):
    query: str
    texts: list[str]


class RerankResponse(BaseModel):
    scores: list[float]
