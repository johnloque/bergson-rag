"""HTTP client for the native ml_service (feat/native-ml-service,
docs/dockerization.md), used by src/api/dependencies.py when
`ML_SERVICE_URL` is set.

Each wrapper below implements exactly the subset of `DenseEmbedder` /
`SparseEmbedder` / `CrossEncoderReranker`'s interface (src/indexing/embeddings.py,
src/retrieval/reranking.py) that `src/retrieval/hybrid.py` and
`src/retrieval/reranking.py` actually call at request time — `.embed()`,
`.embed_query()`, `.score()` — so `get_dense_embedder()` etc. in
dependencies.py can hand either the local, in-process model or this remote
stand-in to the same call sites with no branching downstream. Document-side
sparse embedding (`.embed`, plural-document TF weighting) is intentionally
not implemented here: indexing runs offline via `scripts/build_index.py`,
natively, never through `api` or this client (see src/ml_service/main.py's
module docstring).

## Connection reuse is not optional here

Each wrapper opens one `httpx.Client` in `__init__` and reuses it for every
call, instead of the module-level `httpx.post()` convenience function
(which opens a fresh connection per call). Verified live over
`host.docker.internal` (the default target, `docker-compose.yml`): a
single new connection through Docker Desktop's gateway/NAT took 25-40s to
establish on its own (occasionally more under concurrent connection
setup), dwarfing the actual native inference cost this whole branch exists
to get back (8.3s for reranking, per docs/dockerization.md) -- three fresh
connections per `/retrieve` call (dense, sparse, rerank) made the remote
path slower than the in-process fallback it was meant to replace, and
occasionally slow enough to blow past a naive timeout entirely.
`get_dense_embedder()` etc. (dependencies.py) hand out one `lru_cache`d
instance per process, so reusing the `httpx.Client` is enough to establish
each connection only once *if* it's also kept from being silently
recycled between calls -- httpx's own default `keepalive_expiry` (5s) is
far too short here: each wrapper's connection is only actually used once
per `/retrieve` call, and a full `/retrieve` call (dense + sparse + rerank
in sequence) already takes several seconds even natively, so the default
would force a fresh, 25-40s reconnect on every single request in practice,
not just the first. `_LIMITS` below disables that expiry entirely --
correct for a long-lived local connection to a private internal service,
never appropriate for an arbitrary/untrusted host. `_TIMEOUT` gives
connection establishment its own generous budget, separate from (and
larger than) the read budget, so a slow-but-eventually-successful Docker
Desktop reconnect doesn't get mistaken for a hung request.
"""

from __future__ import annotations

import httpx

_LIMITS = httpx.Limits(keepalive_expiry=None)
_TIMEOUT = httpx.Timeout(connect=60.0, read=120.0, write=30.0, pool=30.0)


class RemoteDenseEmbedder:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=_TIMEOUT, limits=_LIMITS)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post("/embed/dense", json={"texts": texts})
        response.raise_for_status()
        return response.json()["vectors"]


class RemoteSparseEmbedder:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=_TIMEOUT, limits=_LIMITS)

    def embed_query(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        response = self._client.post("/embed/sparse", json={"texts": texts})
        response.raise_for_status()
        body = response.json()
        return list(zip(body["indices"], body["values"], strict=True))


class RemoteCrossEncoderReranker:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=_TIMEOUT, limits=_LIMITS)

    def score(self, query: str, texts: list[str]) -> list[float]:
        response = self._client.post("/rerank", json={"query": query, "texts": texts})
        response.raise_for_status()
        return response.json()["scores"]
