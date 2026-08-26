"""Unit tests for src/ml_service/main.py (feat/native-ml-service).

Uses the real DenseEmbedder/SparseEmbedder/CrossEncoderReranker models --
same discipline as tests/test_reranking.py and tests/test_retrieval.py not
mocking the models themselves. `client` is module-scoped (via the `with
TestClient(app)` context manager, which drives the FastAPI `lifespan` --
src/ml_service/main.py loads all three models once at startup, not per
request) so the whole file pays the model-loading cost once.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.indexing.embeddings import DENSE_DIM
from src.ml_service.main import app

QUERY = "Que signifie la duree chez Bergson ?"
RELEVANT_TEXT = (
    "La duree est le fondement de la vie interieure : elle est succession "
    "sans exteriorite, une multiplicite qualitative que l'espace ne saurait "
    "representer."
)
UNRELATED_TEXT = "Le chemin de fer relie les grandes villes de province."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_embed_dense_returns_one_vector_per_text(client):
    response = client.post("/embed/dense", json={"texts": [RELEVANT_TEXT, UNRELATED_TEXT]})
    assert response.status_code == 200
    vectors = response.json()["vectors"]
    assert len(vectors) == 2
    assert len(vectors[0]) == DENSE_DIM
    assert len(vectors[1]) == DENSE_DIM


def test_embed_dense_empty_input_returns_empty(client):
    response = client.post("/embed/dense", json={"texts": []})
    assert response.status_code == 200
    assert response.json()["vectors"] == []


def test_embed_sparse_returns_matching_indices_and_values_per_text(client):
    response = client.post("/embed/sparse", json={"texts": [RELEVANT_TEXT, UNRELATED_TEXT]})
    assert response.status_code == 200
    body = response.json()
    assert len(body["indices"]) == 2
    assert len(body["values"]) == 2
    for indices, values in zip(body["indices"], body["values"], strict=True):
        assert len(indices) == len(values)
        assert len(indices) > 0


def test_rerank_promotes_true_relevance(client):
    response = client.post(
        "/rerank", json={"query": QUERY, "texts": [UNRELATED_TEXT, RELEVANT_TEXT]}
    )
    assert response.status_code == 200
    scores = response.json()["scores"]
    assert len(scores) == 2
    assert scores[1] > scores[0]  # RELEVANT_TEXT scores higher than UNRELATED_TEXT


def test_rerank_empty_texts_returns_empty_scores(client):
    response = client.post("/rerank", json={"query": QUERY, "texts": []})
    assert response.status_code == 200
    assert response.json()["scores"] == []
