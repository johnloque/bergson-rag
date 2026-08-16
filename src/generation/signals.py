"""Evidence-conditioning signals computed from an input chunk selection
(docs/ROADMAP.md, Sprint 5 — "Evidence-conditioned prompt"). Three signals,
each a pure function of the chunks passed to `generate_from_chunks`; none
of this touches retrieval, reranking, or the gold dataset directly.

Thresholds below are generic, documented placeholders, not fit against
`eval/gold_dataset.csv` — at n=10 the dataset is far below the volume this
project already treats as a threshold for that kind of calibration
(docs/ROADMAP.md, Sprint 4 gold-dataset-volume note). Revisit once a larger
annotated set exists.
"""

from __future__ import annotations

import itertools
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from src.retrieval.hybrid import RetrievedChunk
from src.retrieval.reranking import RerankedChunk

GenerationChunk = RetrievedChunk | RerankedChunk

# Mean pairwise cosine similarity (dense/BGE-M3 space) at or above this is
# "convergent" evidence. Chosen from the real spread observed across this
# corpus's dense space (well above genuinely divergent pairs, well below
# a verified multi-work convergent case — see tests/test_generation.py),
# not fit to any gold-dataset threshold.
CONVERGENCE_THRESHOLD = 0.55

# Coefficient of variation (stdev / mean) of cross-encoder rerank scores
# at or above this counts as "confident" — the reranker meaningfully
# discriminates among the input chunks rather than scoring them all
# alike.
CONFIDENCE_CV_THRESHOLD = 1.0


@dataclass(frozen=True)
class EvidenceSignals:
    works: tuple[str, ...]
    convergence: float | None  # mean pairwise cosine sim; None if <2 chunks had a vector
    is_convergent: bool
    rerank_cv: float | None  # coefficient of variation of rerank_score; None if unavailable
    is_confident: bool

    @property
    def num_works(self) -> int:
        return len(self.works)

    @property
    def is_multi_work(self) -> bool:
        return self.num_works > 1


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def _mean_pairwise_cosine(vectors: list[list[float]]) -> float:
    sims = [_cosine(a, b) for a, b in itertools.combinations(vectors, 2)]
    return sum(sims) / len(sims)


def compute_signals(
    chunks: Sequence[GenerationChunk],
    dense_vectors: dict[str, list[float]],
) -> EvidenceSignals:
    """`dense_vectors` maps chunk_id -> the dense embedding already computed
    for that chunk at indexing time (see `fetch_dense_vectors` in
    src/generation/generate.py — read back from Qdrant, never recomputed
    here). A chunk_id missing from `dense_vectors` (e.g. a hand-built chunk
    that was never indexed) just drops out of the convergence computation
    rather than raising, so the other two signals still work standalone.

    Signals with insufficient data (fewer than two chunks, or no rerank
    scores at all) default to the non-branching side — "nothing to diverge
    from" / "no basis to be cautious about" — the same way a single chunk
    trivially reads as one work, not a missing multi-work signal.
    """
    works = tuple(sorted({chunk.work_id for chunk in chunks}))

    vectors = [dense_vectors[c.chunk_id] for c in chunks if c.chunk_id in dense_vectors]
    convergence = _mean_pairwise_cosine(vectors) if len(vectors) >= 2 else None
    is_convergent = convergence is None or convergence >= CONVERGENCE_THRESHOLD

    rerank_scores = [c.rerank_score for c in chunks if isinstance(c, RerankedChunk)]
    if len(rerank_scores) >= 2 and statistics.mean(rerank_scores) != 0:
        rerank_cv = statistics.pstdev(rerank_scores) / abs(statistics.mean(rerank_scores))
    else:
        rerank_cv = None
    is_confident = rerank_cv is None or rerank_cv >= CONFIDENCE_CV_THRESHOLD

    return EvidenceSignals(
        works=works,
        convergence=convergence,
        is_convergent=is_convergent,
        rerank_cv=rerank_cv,
        is_confident=is_confident,
    )
