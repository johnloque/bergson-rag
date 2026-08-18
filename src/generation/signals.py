"""Evidence-conditioning signals computed from an input chunk selection
(docs/ROADMAP.md, Sprint 5 — "Evidence-conditioned prompt"). Three signals,
each a pure function of the chunks passed to `generate_from_chunks`; none
of this touches retrieval, reranking, or the gold dataset directly.

Thresholds below are generic, documented placeholders, not fit against
`eval/gold_dataset.csv` — at n=10 the dataset is far below the volume this
project already treats as a threshold for that kind of calibration
(docs/ROADMAP.md, Sprint 4 gold-dataset-volume note). Revisit once a larger
annotated set exists.

## Retrieval confidence: one shared signal for Sprint 5 and Sprint 6

`retrieval_confidence_tier` below is used both by `EvidenceSignals.is_confident`
here (Sprint 5's soft, prompt-level caution sentence) and directly by
`src/generation/guardrail.py`'s `generate_evaluation`/`should_auto_expand`
(Sprint 6's auto-expand gate) — one definition, not two independently-tuned
ones. It was originally a coefficient of variation (stdev / mean) of the
input chunks' cross-encoder rerank scores, reused as-is (just re-bucketed)
for Sprint 6. That turned out to be the wrong shared primitive: CV is a
function of the *whole candidate set*'s composition, not of how good the
best evidence actually is — a genuine retrieval miss (near-zero scores
across the board) inflates CV because tiny absolute differences between
near-zero numbers balloon their *relative* spread, while a real relevant
cluster of scores sits close together in absolute terms and reads as *low*
CV. Sprint 6's guardrail needed the opposite polarity from Sprint 5's own
`CONFIDENCE_CV_THRESHOLD` to compensate — confusing for anyone reading both
call sites, and fragile precisely because it depended on how many (and how
irrelevant) other candidates happened to be in the set alongside the real
one.

The highest rerank score among `chunks` (not their spread) avoids both
problems: it doesn't need >= 2 chunks to be meaningful (works for a single
chunk, no `None`-defaulting need there), and it's close to invariant to weak
distractors sharing the set with a genuinely good passage (they don't move
the max). It answers what both sprints actually need — "how good is our
single best piece of evidence" — directly, instead of a relative-spread
proxy that only sometimes correlated with it. `retrieval_confidence_tier`
is the only public entry point for it; nothing outside this module needs
the raw score, only the tier bucketed from it.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

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

RetrievalConfidenceTier = Literal["très faible", "faible", "moyenne", "élevée"]

# Cut points on the best rerank score in a chunk selection
# (bge-reranker-v2-m3's own score scale, not a normalized probability),
# checked against real gold_dataset.csv items (tests/test_guardrail.py) —
# not fit as a formal sweep, same discipline as CONVERGENCE_THRESHOLD above:
#   - Genuinely correct, gold-verified chunk sets (Q002, Q007, Q008) score
#     max ~= 0.35-0.68.
#   - A verified persistent retrieval miss (Q009's real hybrid_search+rerank
#     top-5 output — the correct gold chunk 1907_EC_c130 is not among them)
#     tops out at ~0.24, even at its single best candidate.
_TIER_THRESHOLDS: tuple[tuple[float, RetrievalConfidenceTier], ...] = (
    (0.28, "très faible"),
    (0.42, "faible"),
    (0.55, "moyenne"),
)

# Tiers "moyenne" and "élevée" count as confident, for both consumers of
# this signal — Sprint 5's EvidenceSignals.is_confident and Sprint 6's
# should_auto_expand (src/generation/guardrail.py).
CONFIDENT_TIERS: frozenset[RetrievalConfidenceTier] = frozenset({"moyenne", "élevée"})


@dataclass(frozen=True)
class EvidenceSignals:
    works: tuple[str, ...]
    convergence: float | None  # mean pairwise cosine sim; None if <2 chunks had a vector
    is_convergent: bool
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


def _max_rerank_score(chunks: Sequence[GenerationChunk]) -> float | None:
    """The highest cross-encoder rerank score among `chunks`; None if none of
    them carry one (e.g. hand-built `RetrievedChunk`s that skipped
    reranking). Private: `retrieval_confidence_tier` below is the public
    entry point for this signal — nothing else in this project needs the raw
    score, only the tier bucketed from it."""
    scores = [c.rerank_score for c in chunks if isinstance(c, RerankedChunk)]
    return max(scores) if scores else None


def retrieval_confidence_tier(chunks: Sequence[GenerationChunk]) -> RetrievalConfidenceTier:
    """Discrete confidence tier from `chunks`' single best cross-encoder
    rerank score — see the module docstring and `_TIER_THRESHOLDS` above for
    why this replaced a coefficient-of-variation signal, and for the
    real-score calibration. A chunk selection with no rerank-scored chunks
    at all (e.g. a single hand-built `RetrievedChunk`) has nothing to
    measure — defaults to "moyenne", the same non-branching convention this
    module uses elsewhere for insufficient data (nothing to be confident or
    cautious about either way)."""
    score = _max_rerank_score(chunks)
    if score is None:
        return "moyenne"
    for threshold, tier in _TIER_THRESHOLDS:
        if score < threshold:
            return tier
    return "élevée"


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

    is_confident = retrieval_confidence_tier(chunks) in CONFIDENT_TIERS

    return EvidenceSignals(
        works=works,
        convergence=convergence,
        is_convergent=is_convergent,
        is_confident=is_confident,
    )
