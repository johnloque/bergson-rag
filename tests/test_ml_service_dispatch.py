"""Unit test for src/api/dependencies.py's native-vs-remote dispatch
(feat/native-ml-service) -- confirms `get_dense_embedder()` /
`get_sparse_embedder()` / `get_reranker()` return the `Remote*` HTTP client
wrappers when `ML_SERVICE_URL` is set, without constructing (or
downloading) the real, heavyweight models -- that in-process path is
already exercised implicitly by every other test in this suite that hits
`/retrieve` with `ML_SERVICE_URL` unset (this repo's test-time default),
e.g. tests/test_api.py, tests/test_retrieval.py.

Each `lru_cache`-wrapped getter is explicitly cleared before and after
patching `ML_SERVICE_URL`, since these caches are process-wide singletons
shared with every other test module in the same pytest session -- leaving
a cached `Remote*` instance behind would silently break any later test
that expects the real, in-process model.
"""

from __future__ import annotations

import src.api.dependencies as deps


def _clear_caches() -> None:
    deps.get_dense_embedder.cache_clear()
    deps.get_sparse_embedder.cache_clear()
    deps.get_reranker.cache_clear()


def test_dispatches_to_remote_wrappers_when_ml_service_url_set(monkeypatch):
    monkeypatch.setattr(deps, "ML_SERVICE_URL", "http://localhost:8100")
    _clear_caches()
    try:
        dense = deps.get_dense_embedder()
        sparse = deps.get_sparse_embedder()
        reranker = deps.get_reranker()

        assert isinstance(dense, deps.RemoteDenseEmbedder)
        assert isinstance(sparse, deps.RemoteSparseEmbedder)
        assert isinstance(reranker, deps.RemoteCrossEncoderReranker)
    finally:
        _clear_caches()
