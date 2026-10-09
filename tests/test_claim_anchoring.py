"""Unit tests for the pure, no-LLM parts of src/generation/faithfulness.py:
anchoring judge-extracted claims to answer segments (`_anchor_claims`),
turning one per-claim NLI response into a `ClaimVerdict` (`_claim_verdict`),
and scoring (`_score`). The LLM-backed end-to-end path is covered by
tests/test_faithfulness.py (slow)."""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

from ragas.metrics._faithfulness import NLIStatementOutput, StatementFaithfulnessAnswer

from src.generation.faithfulness import (
    ClaimVerdict,
    SegmentClaims,
    SegmentedClaimsOutput,
    _anchor_claims,
    _claim_verdict,
    _context_for_judge,
    _score,
    _text_for_judge,
)
from src.generation.segmentation import Segment, segment_answer

SEGMENTS = segment_answer("Voici la réponse. Bergson oppose la durée au temps. Il le juge spatial.")


def _nli(*verdicts: int) -> NLIStatementOutput:
    return NLIStatementOutput(
        statements=[
            StatementFaithfulnessAnswer(statement="echo", reason=f"r{i}", verdict=v)
            for i, v in enumerate(verdicts)
        ]
    )


def test_anchor_claims_keeps_judge_attribution_and_drops_unknown_ids_and_blanks():
    output = SegmentedClaimsOutput(
        segments=[
            SegmentClaims(segment_id=0, claims=[]),
            SegmentClaims(segment_id=1, claims=["Bergson oppose la durée au temps.", "  "]),
            SegmentClaims(segment_id=2, claims=["Bergson juge le temps spatial."]),
            SegmentClaims(segment_id=7, claims=["Inventé."]),
        ]
    )
    assert _anchor_claims(SEGMENTS, output) == [
        (1, "Bergson oppose la durée au temps."),
        (2, "Bergson juge le temps spatial."),
    ]


def test_claim_verdict_keeps_the_claim_text_not_the_judge_echo():
    """Each NLI call judges one claim, so its single verdict belongs to that
    claim by construction — the echoed statement text is never used."""
    assert _claim_verdict(2, "A.", _nli(1)) == ClaimVerdict(
        statement="A.", supported=True, reason="r0", segment_id=2
    )
    assert _claim_verdict(2, "A.", _nli(0)).supported is False


def test_claim_verdict_is_not_evaluated_without_exactly_one_verdict():
    for output in (None, _nli(), _nli(1, 0)):
        verdict = _claim_verdict(1, "A.", output)
        assert verdict == ClaimVerdict(statement="A.", supported=None, reason=None, segment_id=1)


def test_score_counts_only_evaluated_claims():
    claims = [
        ClaimVerdict(statement="a", supported=True, reason="r", segment_id=0),
        ClaimVerdict(statement="b", supported=False, reason="r", segment_id=0),
        ClaimVerdict(statement="c", supported=None, reason=None, segment_id=1),
    ]
    assert _score(claims) == 0.5
    assert math.isnan(_score(claims[2:]))
    assert math.isnan(_score([]))


def test_text_for_judge_drops_citations_the_judge_could_mistake_for_segment_ids():
    text = "La durée [1889_DI_c3, 1907_EC_c5], dit-il. Oui [1907_EC_c9]."
    segment = Segment(id=0, text=text, start=0, end=len(text))
    assert _text_for_judge(segment) == "La durée, dit-il. Oui."


def _chunk(text: str, work_id: str = "", paragraph_ids: tuple[str, ...] = ()) -> Any:
    return SimpleNamespace(text=text, work_id=work_id, paragraph_ids=list(paragraph_ids))


def test_judge_context_puts_each_chunk_under_its_source_header():
    """The judge sees the same title/year as the generation prompt, the
    anthology's own text included, so it can check a title claim against
    the context instead of its memory."""
    context = _context_for_judge(
        [
            _chunk("Premier passage.", "1907_EC", ("1907_EC_p40",)),
            _chunk("Second passage.", "1934_PM", ("1934_PM_p6",)),
        ]
    )
    assert context == (
        "[1907_EC — L'Évolution créatrice (1907)]\nPremier passage.\n\n"
        "[1934_PM — La Pensée et le Mouvant (1934) › Introduction (première partie) (1922)]"
        "\nSecond passage."
    )


def test_judge_context_without_work_id_or_paragraphs_degrades_gracefully():
    assert _context_for_judge([_chunk("Passage.")]) == "Passage."
    assert _context_for_judge([_chunk("Passage.", "1919_ES")]) == (
        "[1919_ES — L'énergie spirituelle (1919)]\nPassage."
    )
