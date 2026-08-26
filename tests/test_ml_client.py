"""Unit tests for src/api/ml_client.py (feat/native-ml-service).

The underlying `httpx.Client.post` is mocked here (unlike
tests/test_ml_service.py, which deliberately does not mock the models) --
these tests are about the wrapper classes' request/response shape and
(critically -- see ml_client.py's "Connection reuse is not optional here"
docstring section) that each wrapper reuses one persistent `httpx.Client`
across calls rather than opening a fresh connection per request. Real
ml_service correctness is covered separately, against the real models, by
test_ml_service.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.api.ml_client import (
    _LIMITS,
    _TIMEOUT,
    RemoteCrossEncoderReranker,
    RemoteDenseEmbedder,
    RemoteSparseEmbedder,
)

BASE_URL = "http://localhost:8100"


def _mock_response(json_body: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_body
    response.raise_for_status.return_value = None
    return response


@patch("src.api.ml_client.httpx.Client")
def test_dense_embedder_posts_texts_and_returns_vectors(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.post.return_value = _mock_response({"vectors": [[0.1, 0.2], [0.3, 0.4]]})
    embedder = RemoteDenseEmbedder(BASE_URL)

    vectors = embedder.embed(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    mock_client_cls.assert_called_once_with(base_url=BASE_URL, timeout=_TIMEOUT, limits=_LIMITS)
    mock_client.post.assert_called_once_with("/embed/dense", json={"texts": ["a", "b"]})


@patch("src.api.ml_client.httpx.Client")
def test_sparse_embedder_zips_indices_and_values_into_tuples(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.post.return_value = _mock_response(
        {"indices": [[1, 2], [3]], "values": [[0.5, 0.6], [0.7]]}
    )
    embedder = RemoteSparseEmbedder(BASE_URL)

    pairs = embedder.embed_query(["a", "b"])

    assert pairs == [([1, 2], [0.5, 0.6]), ([3], [0.7])]
    mock_client.post.assert_called_once_with("/embed/sparse", json={"texts": ["a", "b"]})


@patch("src.api.ml_client.httpx.Client")
def test_reranker_posts_query_and_texts_and_returns_scores(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.post.return_value = _mock_response({"scores": [0.9, 0.1]})
    reranker = RemoteCrossEncoderReranker(BASE_URL)

    scores = reranker.score("query", ["a", "b"])

    assert scores == [0.9, 0.1]
    mock_client.post.assert_called_once_with(
        "/rerank", json={"query": "query", "texts": ["a", "b"]}
    )


@patch("src.api.ml_client.httpx.Client")
def test_dense_embedder_reuses_client_across_calls(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.post.return_value = _mock_response({"vectors": [[0.1]]})
    embedder = RemoteDenseEmbedder(BASE_URL)

    embedder.embed(["a"])
    embedder.embed(["b"])

    mock_client_cls.assert_called_once()  # one Client constructed, not one per call
    assert mock_client.post.call_count == 2


@patch("src.api.ml_client.httpx.Client")
def test_dense_embedder_raises_on_http_error(mock_client_cls):
    mock_client = mock_client_cls.return_value
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("boom")
    mock_client.post.return_value = response
    embedder = RemoteDenseEmbedder(BASE_URL)

    try:
        embedder.embed(["a"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected raise_for_status's error to propagate")
