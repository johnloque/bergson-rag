"""Unit tests for src/generation/guardrail.py — Sprint 6 anti-hallucination
guardrail (docs/ROADMAP.md).

Two kinds of fixture, deliberately not one:
- Hand-crafted answers (Q001/Q004 hallucination fixtures, the Layer 1
  unknown-citation case, the chunk_judgments prompt-content check) — used
  wherever the test needs a deterministic, specific claim to assert against.
  A hand-crafted *paraphrase* of real chunk content was tried first for the
  "strong case" (Q002) and found to reproducibly score faithfulness=0.0
  against this project's local 7B judge even when near-verbatim — the same
  needle-in-haystack-adjacent judge fragility documented in
  tests/test_faithfulness.py, not something this module can fix. Real
  `generate_from_chunks` output does not have this problem (confirmed
  empirically), so it's used instead wherever the test needs a genuinely
  faithful answer (Q002, Q008, Q009, the manual-regeneration path).
- Real `generate_from_chunks` / real retrieve+rerank output — used wherever
  the test's actual point is that generation and evaluation run together,
  unmodified, regardless of retrieval confidence (Q008, Q009) or of whether
  `chunk_judgments` was populated (the manual-regeneration test).

`should_auto_expand` does not gate on `EvaluationResult.structural`
(Layer 1) — see `src/generation/guardrail.py`'s module docstring: the local
generation model was found, empirically, to often omit `[chunk_id]`
citations even from well-grounded answers, which would make the "moyenne
and above" gate practically unreachable if citation presence were required.
The Layer 1 test below therefore uses a fixture where the unknown citation
is paired with a claim that Layer 2 also independently flags — the same
mechanism already exercised by the Q001/Q004 tests, not a separate one.

Requires: Qdrant reachable at localhost:6333 with `bergson_chunks` populated
(scripts/build_index.py), same discipline as tests/test_generation.py and
tests/test_faithfulness.py. Tests that call `generate_from_chunks` also need
a reachable generation LLM; tests that call `generate_evaluation` also need
a reachable judge LLM (both default to local Ollama). Skipped cleanly
otherwise.
"""

from __future__ import annotations

import os

import litellm
import pytest
from qdrant_client import QdrantClient

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL, FaithfulnessResult, build_judge_llm
from src.generation.generate import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    FALLBACK_MODEL_ENV_VAR,
    generate_from_chunks,
)
from src.generation.guardrail import (
    EvaluationResult,
    check_structure,
    check_title_fabrication,
    check_title_year_mismatch,
    generate_evaluation,
    should_auto_expand,
)
from src.generation.prompt import CHUNK_JUDGMENT_INSTRUCTION
from src.generation.signals import retrieval_confidence_tier
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME, PAYLOAD_FIELDS, point_id_for
from src.retrieval.hybrid import RetrievedChunk, hybrid_search
from src.retrieval.reranking import CrossEncoderReranker, rerank

QDRANT_URL = "http://localhost:6333"

# Q001 (eval/gold_dataset.csv) — real, gold-verified chunk; a hand-crafted
# hallucinated answer, same fabricated Einstein/1950 attribution already
# used as the "unsupported" comparison case in tests/test_faithfulness.py,
# with a citation added so the structural check has something to inspect.
Q001_QUERY = (
    "Quel usage Bergson fait-il de l'image de la boule de neige pour "
    "illustrer la perception du changement ?"
)
Q001_CHUNK_ID = "1907_EC_c5"
Q001_HALLUCINATED_ANSWER = (
    "Bergson utilise l'image de la boule de neige, qu'il a empruntée à Albert Einstein "
    f"en 1950, pour illustrer la relativité du temps [{Q001_CHUNK_ID}]."
)

# Q004 (eval/gold_dataset.csv) — same discipline: real gold chunk, a
# fabricated attribution (to Kant) not present in, and not entailed by, the
# cited chunk's real content.
Q004_QUERY = "Quel rapport Bergson établit-il entre l'imagination poétique et la réalité ?"
Q004_CHUNK_ID = "1900_R_c49"
Q004_HALLUCINATED_ANSWER = (
    "Bergson affirme, en reprenant une thèse de Kant, que l'imagination poétique n'a "
    "structurellement aucun rapport avec la réalité et relève d'une faculté purement "
    f"arbitraire, indépendante de toute expérience vécue [{Q004_CHUNK_ID}]."
)

# Q008 (eval/gold_dataset.csv) — real multi-work gold pair, confirmed
# faithful in this sprint's judge calibration (n=4). Real generate_from_chunks
# output is used here (not a hand-crafted paraphrase, see module docstring).
Q008_QUERY = "Quelle thèse Bergson explique-t-il à travers l'image du manteau accroché à un clou ?"
Q008_CHUNK_IDS = ("1896_MM_c3", "1919_ES_c16")

# Q009 (eval/gold_dataset.csv) — the real hybrid_search + rerank pipeline
# never surfaces the correct gold chunk (1907_EC_c130) for this query in its
# top candidates (confirmed empirically) — a genuine, persistent retrieval
# miss, not a hand-constructed one, so the real pipeline is exercised here
# rather than a stand-in chunk selection.
Q009_QUERY = "Quelle thèse Bergson explique-t-il en décrivant la grande chevauchée du vivant ?"

# Q002 (eval/gold_dataset.csv) — ground_truth_type "multi": any one of its
# several valid gold chunk_ids suffices as evidence (docs/ROADMAP.md,
# evaluation methodology), so a single one of the three is used here as the
# "strong case" — real generate_from_chunks output (see module docstring).
Q002_QUERY = (
    "Quelle thèse Bergson explique-t-il à travers l'image de la fonte d'un morceau de "
    "sucre dans un verre d'eau ?"
)
Q002_CHUNK_ID = "1907_EC_c9"

# Not a real corpus chunk_id — used only to exercise Layer 1's
# citation-resolution check.
UNKNOWN_CHUNK_ID = "9999_XX_c1"

# Real `generate_from_chunks` end_to_end output (eval/results/ragas_checkpoint.jsonl,
# item_id="Q004", mode="end_to_end", generated at commit 7c9d99f — see
# docs/anti_hallucination_guardrails.md's Sprint 10 calibration section) —
# not a hand-crafted fixture. Fabricates two work titles in prose ("Le
# comique de caractère" for the real 1900 work "Le rire"; the real title
# "L'évolution créatrice" misattributed to 1934 instead of 1907). RAGAS
# scored this answer faithfulness=0.0 (Layer 2 did catch it), but it never
# emits a `[chunk_id]` bracket citation at all, so Layer 1's
# citation-resolution half had nothing to flag before this branch.
Q004_E2E_FABRICATED_TITLE_ANSWER = (
    'Dans l\'œuvre de 1900 intitulée "Le comique de caractère", Bergson établit un '
    "rapport entre l'imagination poétique et la réalité en affirmant que la vision du "
    "poète poétique est une vision plus complète de la réalité. Selon lui, les "
    "personnages que crée le poète ne sont pas des compositions faites à partir de "
    "morceaux empruntés à droite et à gauche autour d'eux, mais des visions plus "
    "complètes de la réalité.\n\n"
    "Dans l'œuvre de 1934 intitulée \"L'évolution créatrice\", Bergson établit un "
    "rapport entre l'imagination et la réalité en affirmant que le possible est le "
    "mirage du présent dans le passé."
)

# Real `generate_from_chunks` end_to_end output (same checkpoint, item_id="Q002",
# mode="end_to_end") — fabricates "De l'évolution de la vie. Mécanisme et
# finalité" as the title of 1907_EC (the real title is "L'Évolution
# créatrice"). RAGAS scored this answer faithfulness=1.0 — Layer 2 missed
# this fabrication outright, the concrete case motivating this branch's
# Layer 1 extension (docs/anti_hallucination_guardrails.md, Sprint 10).
Q002_E2E_FABRICATED_TITLE_ANSWER = (
    "Dans l'œuvre de Henri Bergson intitulée \"De l'évolution de la vie. Mécanisme et "
    "finalité\" (1907_EC), Bergson utilise l'image de la fonte d'un morceau de sucre "
    "dans un verre d'eau pour expliquer sa thèse selon laquelle le temps est une durée "
    "créatrice et non pas un simple déroulement de moments successifs."
)

# Q009's 5 real chunks overflow the default JUDGE_NUM_CTX=8192 (confirmed
# empirically — see test_q009_persistent_retrieval_miss_gets_very_low_confidence_tier).
_Q009_NUM_CTX = 16384


def _collection_populated() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(COLLECTION_NAME):
            return False
        return client.count(collection_name=COLLECTION_NAME).count > 0
    except Exception:
        return False


def _model_reachable(model: str) -> bool:
    try:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=5,
        )
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)

RESOLVED_FALLBACK_MODEL = os.environ.get(FALLBACK_MODEL_ENV_VAR, DEFAULT_FALLBACK_MODEL)

_llm_skip = pytest.mark.skipif(
    not (_model_reachable(DEFAULT_MODEL) or _model_reachable(RESOLVED_FALLBACK_MODEL)),
    reason="no reachable generation LLM — start Ollama with the default model pulled, or set "
    "MISTRAL_API_KEY for the default fallback, or set "
    f"{FALLBACK_MODEL_ENV_VAR} to a different LiteLLM model string with its provider "
    "API key configured",
)

_judge_skip = pytest.mark.skipif(
    not _model_reachable(DEFAULT_JUDGE_MODEL),
    reason=f"no reachable judge model ({DEFAULT_JUDGE_MODEL}) — start Ollama with the "
    "default model pulled, or set MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL",
)


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()


@pytest.fixture(scope="module")
def dense_embedder() -> DenseEmbedder:
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder() -> SparseEmbedder:
    return SparseEmbedder()


def _load_chunk(client: QdrantClient, chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    point = client.retrieve(
        collection_name=COLLECTION_NAME, ids=[point_id_for(chunk_id)], with_payload=True
    )[0]
    payload = point.payload or {}
    return RetrievedChunk(score=score, **{field: payload[field] for field in PAYLOAD_FIELDS})


# --- Q001 / Q004: confirmed hallucination fixtures ----------------------


@_judge_skip
def test_q001_hallucination_flagged_and_blocks_auto_expand(client):
    """The correct gold chunk is the only evidence passed in (retrieval
    confidence is fine) — should_auto_expand must still be False, blocked by
    Layer 2 alone."""
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    confidence = retrieval_confidence_tier([chunk])
    evaluation = generate_evaluation(Q001_QUERY, [chunk], Q001_HALLUCINATED_ANSWER, confidence)

    assert evaluation.has_unsupported_claims
    assert any(
        "einstein" in claim.statement.lower() for claim in evaluation.unsupported_claims
    ), evaluation.unsupported_claims
    assert not should_auto_expand(evaluation)


@_judge_skip
def test_q004_hallucination_flagged_and_blocks_auto_expand(client):
    chunk = _load_chunk(client, Q004_CHUNK_ID)
    confidence = retrieval_confidence_tier([chunk])
    evaluation = generate_evaluation(Q004_QUERY, [chunk], Q004_HALLUCINATED_ANSWER, confidence)

    assert evaluation.has_unsupported_claims
    assert any(
        "kant" in claim.statement.lower() for claim in evaluation.unsupported_claims
    ), evaluation.unsupported_claims
    assert not should_auto_expand(evaluation)


# --- Q008: confirmed faithful, generation is unaffected by evaluation ---


@_llm_skip
@_judge_skip
def test_q008_answer_generated_and_returned_regardless_of_evaluation(client, reranker):
    chunks = [_load_chunk(client, chunk_id) for chunk_id in Q008_CHUNK_IDS]
    reranked = rerank(Q008_QUERY, chunks, reranker)

    result = generate_from_chunks(Q008_QUERY, reranked, client, temperature=0.0)
    answer_before_evaluation = result.answer
    assert answer_before_evaluation.strip()

    evaluation = generate_evaluation(
        Q008_QUERY, reranked, result.answer, retrieval_confidence_tier(reranked)
    )

    # generate_from_chunks' own output is untouched by generate_evaluation —
    # no hard refusal, no post-hoc modification of the answer.
    assert result.answer == answer_before_evaluation
    # should_auto_expand may legitimately be False here (known judge noise
    # floor, docs/ROADMAP.md) — only that it runs without crashing matters.
    assert should_auto_expand(evaluation) in (True, False)
    # Q008's confirmed-faithful answer is unaffected by the Sprint 10 Layer 1
    # title-fabrication check (docs/ROADMAP.md): it never names a work title
    # in prose, so this branch adds no new gate against it — explicit
    # regression check, not just an absence of failure.
    assert evaluation.structural.fabricated_titles == ()
    # Same regression check for fix/title-year-grounding's title+year
    # pairing check — Q008 is unaffected by it too.
    assert evaluation.structural.title_year_mismatches == ()


# --- Q009: persistent retrieval miss -------------------------------------


@_llm_skip
@_judge_skip
def test_q009_persistent_retrieval_miss_gets_very_low_confidence_tier(
    client, dense_embedder, sparse_embedder, reranker
):
    """The real hybrid_search + rerank pipeline for this query (not a
    hand-picked chunk selection) — confirmed empirically to never surface
    the correct gold chunk (1907_EC_c130) among its top candidates.

    These 5 real chunks are long enough, concatenated, to overflow the local
    judge's default context window (`JUDGE_NUM_CTX=8192`,
    src/generation/faithfulness.py) with a RagasOutputParserException,
    confirmed empirically here — a larger, but still consistent, `num_ctx`
    is passed to both `generate_from_chunks` and the judge (same discipline
    ragas_evaluation.md's Sprint 6 handoff note already documents: matching
    `num_ctx` between the two avoids Ollama reloading the model between every
    call).
    """
    candidates = hybrid_search(client, Q009_QUERY, dense_embedder, sparse_embedder, limit=10)
    reranked = rerank(Q009_QUERY, candidates, reranker)[:5]
    assert reranked, "expected at least one retrieved chunk"

    result = generate_from_chunks(Q009_QUERY, reranked, client, num_ctx=_Q009_NUM_CTX)
    assert result.answer.strip()

    confidence = retrieval_confidence_tier(reranked)
    assert confidence == "très faible"

    judge_llm = build_judge_llm()
    judge_llm.langchain_llm.model_kwargs["num_ctx"] = _Q009_NUM_CTX
    evaluation = generate_evaluation(
        Q009_QUERY, reranked, result.answer, confidence, judge_llm=judge_llm
    )
    assert evaluation.retrieval_confidence == "très faible"
    assert not should_auto_expand(evaluation)


# --- Q002: strong case ----------------------------------------------------


@_llm_skip
@_judge_skip
def test_q002_strong_case_auto_expands(client):
    chunk = _load_chunk(client, Q002_CHUNK_ID)
    result = generate_from_chunks(Q002_QUERY, [chunk], client, temperature=0.0)
    assert result.answer.strip()

    evaluation = generate_evaluation(
        Q002_QUERY, [chunk], result.answer, retrieval_confidence_tier([chunk])
    )
    assert should_auto_expand(evaluation)


# --- Layer 1: structural citation check -----------------------------------


@_judge_skip
def test_layer1_unknown_citation_is_flagged_and_blocks_auto_expand(client):
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    answer_with_unknown_citation = (
        "Bergson utilise l'image de la boule de neige, qu'il a empruntée à Albert "
        f"Einstein en 1950, pour illustrer la relativité du temps [{UNKNOWN_CHUNK_ID}]."
    )

    structural = check_structure(answer_with_unknown_citation, [chunk])
    assert structural.unknown_citations == (UNKNOWN_CHUNK_ID,)
    assert not structural.passed

    evaluation = generate_evaluation(
        Q001_QUERY, [chunk], answer_with_unknown_citation, retrieval_confidence_tier([chunk])
    )
    assert evaluation.structural.unknown_citations == (UNKNOWN_CHUNK_ID,)
    assert not should_auto_expand(evaluation)


def test_layer1_missing_citation_flagged_without_llm_call(client):
    """check_structure alone needs no LLM — confirms Layer 1 is independently
    testable and independently correct without exercising Layer 2 at all."""
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    structural = check_structure("Une réponse sans aucune citation.", [chunk])
    assert not structural.has_citation
    assert not structural.passed


# --- Layer 1 (Sprint 10 addition): prose-embedded title fabrication -------
#
# `docs/ROADMAP.md`'s Sprint 10 investigation confirmed check_structure's
# citation-resolution check was never designed to catch a fabricated work
# title embedded in prose (as opposed to a `[chunk_id]` bracket) — see
# `docs/anti_hallucination_guardrails.md`. These tests use real
# `generate_from_chunks` end_to_end output (the constants above), not
# hand-crafted answers, matching this module's own stated discipline for
# hallucination fixtures.


def test_check_title_fabrication_flags_real_fabricated_titles():
    """No LLM, no `chunks` argument needed — purely deterministic, exercised
    directly against the two real fabrications this check was built from."""
    assert check_title_fabrication(Q004_E2E_FABRICATED_TITLE_ANSWER) == ("Le comique de caractère",)
    assert check_title_fabrication(Q002_E2E_FABRICATED_TITLE_ANSWER) == (
        "De l'évolution de la vie. Mécanisme et finalité",
    )


def test_check_title_fabrication_does_not_flag_genuine_titles():
    """A genuine work-title reference — canonical title, alternate title, and
    an accent/case-insensitive spelling variant — must not be flagged: this
    branch must not introduce a new false-positive source while fixing the
    fabricated-title gap (docs/ROADMAP.md)."""
    answer = (
        "Dans l'œuvre intitulée \"L'Évolution créatrice\", Bergson développe sa thèse. "
        'Dans l\'ouvrage intitulé "Le rire", il analyse le mécanisme du comique, aussi '
        "connu sous son sous-titre, l'ouvrage intitulé \"essai sur la signification du "
        'comique". Enfin, dans l\'œuvre intitulée "matiere et memoire" (sans accents), '
        "il distingue perception et affection."
    )
    assert check_title_fabrication(answer) == ()


def test_q004_fabricated_title_caught_by_layer1_without_llm(client):
    """Q004's real fabricated-title case (docs/ROADMAP.md) is now caught by
    Layer 1 alone, deterministically — no LLM call needed to catch it,
    unlike before this branch where only Layer 2 (and, per the Q002 case
    below, not even reliably that) could catch it."""
    structural = check_structure(Q004_E2E_FABRICATED_TITLE_ANSWER, [])
    assert structural.fabricated_titles == ("Le comique de caractère",)
    assert not structural.passed

    # should_auto_expand must block on the fabricated title alone, even if
    # Layer 2 and retrieval confidence both look fine — constructing
    # FaithfulnessResult directly (rather than calling the judge) isolates
    # Layer 1's own contribution to the gate.
    evaluation = EvaluationResult(
        structural=structural,
        faithfulness=FaithfulnessResult(score=1.0, model="test", claims=()),
        retrieval_confidence="élevée",
    )
    assert not should_auto_expand(evaluation)


def test_q002_fabricated_title_layer2_missed_now_caught_by_layer1(client):
    """The real Q002 end_to_end answer scored faithfulness=1.0 by RAGAS
    (`eval/results/ragas_checkpoint.jsonl`) — Layer 2 missed this
    fabrication outright, the concrete finding motivating this branch
    (docs/anti_hallucination_guardrails.md, Sprint 10). Layer 1 now catches
    it independently of Layer 2's verdict."""
    structural = check_structure(Q002_E2E_FABRICATED_TITLE_ANSWER, [])
    assert structural.fabricated_titles == ("De l'évolution de la vie. Mécanisme et finalité",)

    # Reproduces the real historical judge output (faithfulness=1.0, no
    # claims flagged) to show should_auto_expand now blocks a case that,
    # before this branch, would have been allowed to auto-expand.
    evaluation = EvaluationResult(
        structural=structural,
        faithfulness=FaithfulnessResult(score=1.0, model="test", claims=()),
        retrieval_confidence="élevée",
    )
    assert not should_auto_expand(evaluation)


# --- Layer 1 (fix/title-year-grounding): title+year pairing ---------------
#
# Direct regression coverage for the scope gap
# docs/anti_hallucination_guardrails.md's Sprint 10 section named
# explicitly: a real, known title attached to the wrong year (e.g. Q004's
# real "1934 intitulée 'L'évolution créatrice'" fabrication above — the
# title is real, its year is not) was not flagged before this branch.


def test_check_title_year_mismatch_flags_real_title_wrong_year():
    """Hand-constructed answer reproducing Q004's actual historical
    misattribution: the real title "L'évolution créatrice" paired with 1934
    instead of its real publication year, 1907."""
    answer = "Dans l'œuvre de 1934 intitulée \"L'évolution créatrice\", Bergson développe sa thèse."
    mismatches = check_title_year_mismatch(answer)
    assert len(mismatches) == 1
    assert mismatches[0].work_id == "1907_EC"
    assert mismatches[0].correct_year == 1907
    assert mismatches[0].claimed_years == (1934,)

    structural = check_structure(answer, [])
    assert structural.title_year_mismatches == mismatches
    assert not structural.passed

    # Isolates Layer 1's own contribution to the gate, same discipline as
    # test_q004_fabricated_title_caught_by_layer1_without_llm above.
    evaluation = EvaluationResult(
        structural=structural,
        faithfulness=FaithfulnessResult(score=1.0, model="test", claims=()),
        retrieval_confidence="élevée",
    )
    assert not should_auto_expand(evaluation)


def test_check_title_year_mismatch_does_not_flag_correct_pairing():
    """No new false-positive source: the same real title paired with its
    actual, correct year must not be flagged."""
    answer = "Dans l'œuvre de 1907 intitulée \"L'Évolution créatrice\", Bergson développe sa thèse."
    assert check_title_year_mismatch(answer) == ()


def test_check_title_year_mismatch_ignores_titles_it_does_not_recognize():
    """A fabricated title (not a real work) is `check_title_fabrication`'s
    job, not this check's — check_title_year_mismatch must not also try to
    validate a year against a title it can't match to any known work."""
    answer = 'Dans l\'œuvre de 1900 intitulée "Le comique de caractère", Bergson écrit.'
    assert check_title_year_mismatch(answer) == ()


def test_q004_e2e_fabricated_answer_also_has_a_year_mismatch():
    """The real historical Q004 end_to_end answer (module constant above)
    contains both failure modes in the same text: a fabricated title
    ("Le comique de caractère", already covered by
    test_check_title_fabrication_flags_real_fabricated_titles) and, in the
    same answer, the real title "L'évolution créatrice" attached to the
    wrong year — the exact case this branch's check was built for."""
    mismatches = check_title_year_mismatch(Q004_E2E_FABRICATED_TITLE_ANSWER)
    assert len(mismatches) == 1
    assert mismatches[0].title == "L'évolution créatrice"
    assert mismatches[0].work_id == "1907_EC"
    assert mismatches[0].correct_year == 1907
    assert mismatches[0].claimed_years == (1934,)


# --- Sprint 11 (`feat/backend-reference-data`): text-level titles ---------
#
# Before this branch, a real, correctly-attributed text-level title (e.g.
# "L'effort intellectuel", a real 1902 article within 1919_ES) would have
# been flagged as fabricated by check_title_fabrication (only the 8
# work-level titles were known) — and check_title_year_mismatch had no way
# to validate its year against anything but 1919_ES's own 1919 publication
# date. Both are now resolved via src.works.TEXTS.


def test_check_title_fabrication_recognizes_text_level_titles():
    answer = 'Dans son article intitulé "L\'effort intellectuel", Bergson développe cette thèse.'
    assert check_title_fabrication(answer) == ()


def test_check_title_year_mismatch_validates_against_the_texts_own_year():
    """The text's own year (1902), not the enclosing anthology's own
    publication year (1919), is the correct year to check against."""
    correct = 'Dans son article de 1902 intitulé "L\'effort intellectuel", Bergson écrit.'
    assert check_title_year_mismatch(correct) == ()

    wrong = 'Dans son article de 1919 intitulé "L\'effort intellectuel", Bergson écrit.'
    mismatches = check_title_year_mismatch(wrong)
    assert len(mismatches) == 1
    assert mismatches[0].work_id == "1919_ES"
    assert mismatches[0].correct_year == 1902
    assert mismatches[0].claimed_years == (1919,)


@_llm_skip
def test_q004_title_year_grounding_empirical_regeneration(client):
    """Empirical check, not a guarantee (docs/anti_hallucination_guardrails.md):
    with the real title/year now shown directly in the prompt
    (fix/title-year-grounding, src/generation/prompt.py), regenerate Q004
    and report whether the original fabrication (an invented title and/or
    the real title "L'Évolution créatrice" attached to the wrong year)
    still occurs. LLMs can still err with correct context in front of them,
    just less often — this test documents the actual outcome via Layer 1
    rather than asserting the prompt fix eliminates the fabrication
    entirely; the guardrail machinery must simply keep running cleanly
    regardless of the outcome."""
    chunk = _load_chunk(client, Q004_CHUNK_ID)
    result = generate_from_chunks(Q004_QUERY, [chunk], client, temperature=0.0)
    assert result.answer.strip()
    # The real title/year the model actually saw for Q004_CHUNK_ID's real
    # work ("1900_R" / "Le rire") — not the fabricated "L'évolution
    # créatrice (1934)" the original hallucination invented, which belongs
    # to a different work (1907_EC) not even part of this chunk selection.
    assert "Le rire" in result.prompt
    assert "1900" in result.prompt

    structural = check_structure(result.answer, [chunk])
    print(
        f"\n[Q004 title/year grounding, empirical] "
        f"fabricated_titles={structural.fabricated_titles!r} "
        f"title_year_mismatches={structural.title_year_mismatches!r}\n"
        f"answer={result.answer!r}"
    )
    evaluation = EvaluationResult(
        structural=structural,
        faithfulness=FaithfulnessResult(score=1.0, model="test", claims=()),
        retrieval_confidence=retrieval_confidence_tier([chunk]),
    )
    assert should_auto_expand(evaluation) in (True, False)


# --- chunk_judgments: fixture shape and prompt content --------------------


@_llm_skip
def test_chunk_judgments_included_in_prompt(client):
    """A hand-constructed ChunkJudgment fixture — not from a real
    judge_chunks call, which doesn't exist yet on this branch — matching the
    committed interface contract (src/generation/chunk_judgment.py)."""
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    justification = "Passage central sur l'image de la boule de neige illustrant le changement."
    chunk_judgments: dict[str, ChunkJudgment] = {
        Q001_CHUNK_ID: {"label": "pertinent", "justification": justification}
    }

    result = generate_from_chunks(
        Q001_QUERY, [chunk], client, temperature=0.0, chunk_judgments=chunk_judgments
    )

    assert CHUNK_JUDGMENT_INSTRUCTION in result.prompt
    assert "pertinent" in result.prompt
    assert justification in result.prompt


# --- Manual regeneration: same evaluation path as an initial generation ---


@_llm_skip
@_judge_skip
def test_manual_regeneration_with_chunk_judgments_goes_through_same_evaluation(client):
    chunk = _load_chunk(client, Q001_CHUNK_ID)
    chunk_judgments: dict[str, ChunkJudgment] = {
        Q001_CHUNK_ID: {
            "label": "pertinent",
            "justification": "Confirmé pertinent lors d'une évaluation préalable.",
        }
    }

    # Exercises the manual-regeneration code path itself: generate_from_chunks
    # accepts chunk_judgments and still returns a usable GenerationResult.
    result = generate_from_chunks(
        Q001_QUERY, [chunk], client, temperature=0.0, chunk_judgments=chunk_judgments
    )
    assert result.answer.strip()
    confidence = retrieval_confidence_tier([chunk])
    assert should_auto_expand(
        generate_evaluation(Q001_QUERY, [chunk], result.answer, confidence)
    ) in (
        True,
        False,
    )

    # generate_evaluation applies identically regardless of how the answer
    # was produced — reuse Q001's confirmed-hallucination fixture logic
    # (same as test_q001_hallucination_flagged_and_blocks_auto_expand above)
    # against what a manual regeneration's output would look like, rather
    # than a separate assertion suite for this path.
    evaluation = generate_evaluation(Q001_QUERY, [chunk], Q001_HALLUCINATED_ANSWER, confidence)
    assert evaluation.has_unsupported_claims
    assert not should_auto_expand(evaluation)
