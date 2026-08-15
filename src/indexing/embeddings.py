"""Dense and sparse embedding generation for the Qdrant hybrid index.

- Dense: BGE-M3 (`BAAI/bge-m3`), raw chunk text only — no title/section
  prefixing. Contextual enrichment was considered and deliberately
  deferred to the generation step (docs/ROADMAP.md, Sprint 4).
- Sparse: BM25 via FastEmbed's built-in `Qdrant/bm25` sparse embedder,
  rather than hand-rolled document-frequency/BM25-weighting code — a
  solved problem. FastEmbed's own stemming step is disabled: the caller
  (src/indexing/indexer.py) is expected to pass text already normalized
  by `src.indexing.normalize.normalize_text(...).bm25_text`, computed
  once per chunk rather than here, so stemming doesn't run twice for
  chunks whose stems are also persisted to disk.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from fastembed.sparse.bm25 import Bm25
from sentence_transformers import SentenceTransformer

DENSE_MODEL = "BAAI/bge-m3"
DENSE_DIM = 1024
SPARSE_MODEL = "Qdrant/bm25"
SPARSE_LANGUAGE = "french"

_PYPROJECT = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"


def _pinned_bge_m3_revision() -> str:
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return config["tool"]["bergson"]["model-versions"]["bge_m3_revision"]


class DenseEmbedder:
    def __init__(self) -> None:
        self._model = SentenceTransformer(DENSE_MODEL, revision=_pinned_bge_m3_revision())

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, show_progress_bar=False).tolist()


class SparseEmbedder:
    def __init__(self) -> None:
        self._model = Bm25(
            model_name=SPARSE_MODEL,
            language=SPARSE_LANGUAGE,
            disable_stemmer=True,
        )

    def embed(self, bm25_texts: list[str]) -> list[tuple[list[int], list[float]]]:
        """`bm25_texts` must already be normalized (e.g.
        `Normalization.bm25_text`) — this does not stem or lemmatize."""
        return [(e.indices.tolist(), e.values.tolist()) for e in self._model.embed(bm25_texts)]
