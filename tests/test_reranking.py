"""Unit tests for src/retrieval/reranking.py.

Two things under test:
- Determinism: same query, same candidate set, same reranked output across
  repeated runs (no randomness anywhere in this path).
- A sanity/contrast case: the reranker must actually change RRF order when
  RRF rank and true query-passage relevance disagree — not just pass the
  candidate set through unchanged.

Uses the real bge-reranker-v2-m3 model (no mocking the reranker itself —
same discipline as tests/test_retrieval.py not mocking Qdrant), but does
not require a live Qdrant instance: RetrievedChunk fixtures are built by
hand so this suite can run standalone.
"""

from __future__ import annotations

import pytest

from src.retrieval.hybrid import RetrievedChunk
from src.retrieval.reranking import CrossEncoderReranker, rerank


def _chunk(chunk_id: str, score: float, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        score=score,
        work_id="1907_EC",
        chunk_id=chunk_id,
        section_id="s1",
        section_path="s1",
        paragraph_ids=["p1"],
        page_start={"display": "1"},
        page_end={"display": "1"},
        text=text,
    )


@pytest.fixture(scope="module")
def reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


QUERY = "Quel usage Bergson fait-il de l'image de la boule de neige ?"

# A real passage about the snowball image (strong true relevance) ranked
# below an unrelated passage by RRF (weaker rank) — and vice versa.
STRONG_RELEVANCE_WEAK_RRF = _chunk(
    "weak_rrf_strong_relevance",
    score=0.01,  # worse RRF rank
    text=(
        "Prenons l'image d'une boule de neige qui roule sur la pente couverte de neige de "
        "la montagne : elle grossit à mesure qu'elle avance, son volume s'accroît, en "
        "boule sur elle-même, sans cesse, comme tout état d'âme se modifie en s'épaississant."
    ),
)
WEAK_RELEVANCE_STRONG_RRF = _chunk(
    "strong_rrf_weak_relevance",
    score=0.5,  # better RRF rank
    text=(
        "Le chemin de fer relie les grandes villes de province, et les horaires des trains "
        "sont affichés dans chaque gare pour l'information des voyageurs."
    ),
)


def test_rerank_is_deterministic(reranker):
    chunks = [WEAK_RELEVANCE_STRONG_RRF, STRONG_RELEVANCE_WEAK_RRF]
    first = rerank(QUERY, chunks, reranker)
    second = rerank(QUERY, chunks, reranker)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.rerank_score for c in first] == [c.rerank_score for c in second]


def test_rerank_promotes_true_relevance_over_rrf_rank(reranker):
    """A chunk with a weaker RRF rank but stronger true query-passage
    relevance must be promoted above a chunk with a better RRF rank but
    weaker true relevance — confirms the reranker does more than preserve
    RRF order."""
    chunks = [WEAK_RELEVANCE_STRONG_RRF, STRONG_RELEVANCE_WEAK_RRF]
    assert chunks[0].score > chunks[1].score  # RRF order going in: weak-relevance first

    reranked = rerank(QUERY, chunks, reranker)

    assert reranked[0].chunk_id == "weak_rrf_strong_relevance"
    assert reranked[1].chunk_id == "strong_rrf_weak_relevance"
    assert reranked[0].rerank_score > reranked[1].rerank_score


def test_rerank_retains_original_rrf_score(reranker):
    chunks = [WEAK_RELEVANCE_STRONG_RRF, STRONG_RELEVANCE_WEAK_RRF]
    reranked = rerank(QUERY, chunks, reranker)
    rrf_scores_by_id = {c.chunk_id: c.rrf_score for c in reranked}
    assert rrf_scores_by_id["weak_rrf_strong_relevance"] == 0.01
    assert rrf_scores_by_id["strong_rrf_weak_relevance"] == 0.5


def test_rerank_empty_input_returns_empty(reranker):
    assert rerank(QUERY, [], reranker) == []
