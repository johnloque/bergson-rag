"""Post-generation anti-hallucination guardrail (docs/ROADMAP.md, Sprint 6).

Presentation-only, unified gating. There is no hard refusal anywhere in this
system: `generate_from_chunks` (`src/generation/generate.py`) always runs and
always returns an answer, regardless of retrieval confidence or the
evaluation this module computes on that answer afterward. `generate_evaluation`
runs identically after any `generate_from_chunks` call — an initial
generation or a manual regeneration (`chunk_judgments` populated or not) —
no special-cased path for either. What this module decides is only whether
the caller's UI may auto-expand the answer it already has; the actual
collapsed-by-default rendering and persistence of the evaluation result are
both deferred to Sprint 7 (docs/ROADMAP.md).

No second LLM call for the guardrail decision: `generate_evaluation` makes
exactly one call into `check_faithfulness` (`src/generation/faithfulness.py`,
the local 7B judge by default) per generated answer. Judge calibration
(n=4: Q001/Q004 confirmed hallucinations, Q006/Q008 confirmed faithful,
`docs/ROADMAP.md`) found the hosted Mistral judge rates confirmed
hallucinations as faithful (0.857-0.929) — a second opinion from it could
overturn a correct local-judge signal in exactly the wrong direction, so it
is never consulted here.

Three inputs feed `EvaluationResult`:

- Layer 1, `check_structure` — deterministic, no LLM call: every citation in
  the answer must name a chunk_id present in `chunks`, and at least one
  citation must be present at all. Parses citations with
  `src.generation.prompt.CITATION_PATTERN`, imported rather than a second
  hardcoded copy of the same regex — that module is what actually tells the
  model the `[chunk_id]` format to use (`CITATION_INSTRUCTION`), so it's the
  one place that format is allowed to change. As of the
  `fix/faithfulness-citation-detection` branch (docs/ROADMAP.md, Sprint 10),
  Layer 1 also flags prose-embedded fabricated work titles — see
  "Prose-embedded title fabrication" below.
- Layer 2, `check_faithfulness` — the one LLM call, reused as-is from
  Sprint 5/6's shared faithfulness module; per-claim verdicts, not just the
  aggregate score, are read off `FaithfulnessResult.claims`.
- Retrieval confidence tier, `src.generation.signals.retrieval_confidence_tier`
  — deterministic, no LLM call, the exact same best-cross-encoder-score
  signal Sprint 5's prompt conditioning already computes for
  `EvidenceSignals.is_confident`, one shared definition rather than two
  independently-tuned ones (see that module's docstring for why an earlier
  CV-based version of this signal was dropped in favor of a max-score one).
  Since the retrieval-confidence-split correction (docs/ROADMAP.md), this
  module no longer calls that function itself: `generate_evaluation` takes
  the tier as a parameter, computed once by `/generate` (persisted on the
  generation record) and shown to the user pre-generation via
  `/confidence-preview` — both API-level call sites of the shared function,
  never this one.

`should_auto_expand` folds `retrieval_confidence` and Layer 2 into one
boolean: confidence at "moyenne" or above (`CONFIDENT_TIERS`,
`src/generation/signals.py` — the same set Sprint 5's `is_confident` also
checks against), and no claim flagged unsupported (Layer 2). Layer 1's
citation-resolution half (`StructuralCheck.unknown_citations`/
`has_citation`) is carried on `EvaluationResult` for the caller (and
Sprint 7's UI badge) but deliberately does not gate `should_auto_expand` on
its own: the local generation model was found, empirically, to often omit
`[chunk_id]` citations even from otherwise well-grounded answers
(`CITATION_INSTRUCTION` in `src/generation/prompt.py` is a request, not an
enforced constraint) — gating on citation *presence* would make auto-expand
practically unreachable regardless of actual faithfulness. A citation to a
chunk_id absent from `chunks`, in practice, is accompanied by a claim
Layer 2 also flags unsupported (the fabricated "evidence" isn't in
`retrieved_contexts` either), so Layer 2 still catches that failure mode in
practice even though this half of Layer 1 isn't wired into the gate
directly. `StructuralCheck.fabricated_titles` (below) *is* wired into the
gate — a different failure mode with no equivalent omission problem.

## Prose-embedded title fabrication (Sprint 10 addition)

Layer 1's citation-resolution check only ever verified *structured*
`[chunk_id]` citations against `chunks` — it had no way to catch a claim
like `l'œuvre de 1900 intitulée "Le comique de caractère"` (a title that
does not exist in the corpus; the real 1900 work is "Le rire", alt. title
"Essai sur la signification du comique") embedded in ordinary prose rather
than a bracket citation. This is a real, confirmed gap, not a hypothetical
one: a real `end_to_end` `generate_from_chunks` call for Q004
(`eval/results/ragas_checkpoint.jsonl`) produced exactly this fabrication,
and a second one two sentences later ("l'œuvre de 1934 intitulée
'L'évolution créatrice'" — that title is the real 1907 work, not the 1934
one) — and RAGAS's own faithfulness score for that answer was 0.0, so
Layer 2 *did* catch it. But a real Q002 `end_to_end` answer fabricated
"De l'évolution de la vie. Mécanisme et finalité" as the title of 1907_EC
(the real title is "L'Évolution créatrice") and RAGAS scored that answer
faithfulness=1.0 — Layer 2 missed it outright. See
`docs/anti_hallucination_guardrails.md`'s Sprint 10 section for the full
calibration this finding is drawn from.

`check_structure` now also runs `check_title_fabrication`: it extracts any
quoted title following the cue word "intitulé(e)" (the pattern both real
fabrications above actually used) and flags it if it doesn't match, after
accent/case/whitespace normalization, any of the corpus's 8 known work
titles or alternate titles (`KNOWN_WORK_TITLES` below). No LLM call, no
dependency on `chunks` — the corpus is a fixed, closed set of 8 works
(docs/ROADMAP.md scope decision), so this list is hardcoded here rather
than read from `data/processed/works/*.json` at import time (a gitignored
build artifact that may not exist yet in a fresh checkout or CI). Anchoring
on the "intitulé(e)" cue specifically (rather than any quoted span) is a
deliberate precision choice: at the time this check was built, the model
was never given real work titles in the prompt (`src/generation/prompt.py`
only ever showed it `work_id`, e.g. `1907_EC`), so any title it named was
drawn from its own background knowledge, not from the retrieved evidence —
but a quoted span *without* that cue is often a genuine verbatim quotation
from a chunk, which must not be flagged. `fix/title-year-grounding`
(below) has since added the real title/year to the prompt too, but the cue
anchor is kept as-is on that branch rather than revisited (see that
section for why).

Scope boundary, stated plainly: this only verifies that the *title itself*
exists in the corpus, not that the surrounding attribution (year, author)
is also correct — a real title attached to the wrong year (e.g. the Q004
answer above also said "l'œuvre de 1934 intitulée 'L'évolution créatrice'";
that title is real, its year is not) is not flagged by this check in
isolation. This is a deliberate scope limit, not an oversight: verifying
year/author attribution would need matching a title to a specific claimed
date, a fuzzier and more error-prone check than closed-set title lookup,
and is left to Layer 2 (which does not reliably catch it either — see the
calibration note above). Every case this check *is* designed for, it must
answer as false or true — it does not need to catch every fabrication in a
given answer, since a single flagged title already blocks auto-expand for
the whole answer.

Unlike the citation-resolution half of Layer 1, `fabricated_titles` *does*
gate `should_auto_expand` (see below): the citation-omission problem that
justified leaving citation-resolution out of the gate doesn't apply here —
a title fabrication is a positive, specific claim the model chose to make,
not an omission, and the cue-anchored extraction above was designed
specifically to avoid flagging genuine quotations, so it carries a low
false-positive risk consistent with the rest of Layer 1's deterministic
design.

## Title+year pairing (`fix/title-year-grounding`)

The scope boundary named above — a real title attached to the wrong year
isn't flagged — is exactly the gap `check_title_year_mismatch` closes, now
that `src.works.WORKS` (a work_id -> {title, year} table, also this
project's Sprint 11 date-range-filtering table, docs/ROADMAP.md) exists to
validate against. `KNOWN_WORK_TITLES` below is now derived from that same
table instead of an independently hardcoded copy, so the two checks can't
drift apart on what a "real" title is.

This is the safety-net half of a two-part fix; the primary mitigation is
prompt-level: `src/generation/prompt.py` now shows the real title and year
for every chunk's source work directly in the prompt (alongside `work_id`,
not replacing it), removing the model's need to recall either from its own
background knowledge in the first place — the actual root cause of both
fabrication shapes seen in calibration (an invented title entirely, and a
real title attached to the wrong year). `check_title_year_mismatch` is what
still runs after generation regardless, the same defense-in-depth
discipline every other guardrail layer here follows (Layer 1 + Layer 2 +
confidence tier, none trusted alone).

`check_title_year_mismatch` reuses the existing "intitulé(e)" cue-anchored
extraction as-is (`_extract_cited_titles` below) rather than a broader
title-detection rewrite: the prompt grounding above is expected to make the
cue-word fragility concern lower priority (a model given the correct title
directly is far less likely to introduce it via an unanticipated phrasing),
and this branch has no new evidence yet that a broader rewrite is still
needed — revisit only if it turns out to be. For each cue-matched title
that *does* match a known work (an unmatched one is `check_title_fabrication`'s
job, not this check's), a fixed character window around the cue match is
searched for a 4-digit year; if a year is found there and it isn't that
work's real year, the pairing is flagged. The window is a documented
placeholder (`_YEAR_CONTEXT_WINDOW` below), sized from the two real
fabrication cases this project has on record (both put the wrong year
within about 15 characters of the cue), not fit against a larger sample —
same discipline as this project's other unfit thresholds
(`CONVERGENCE_THRESHOLD`, `_TIER_THRESHOLDS` in `src/generation/signals.py`).

Like `fabricated_titles`, `title_year_mismatches` gates `should_auto_expand`
directly: it is a positive, specific attribution claim, not an omission.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from ragas.llms.base import LangchainLLMWrapper

from src.generation.faithfulness import (
    DEFAULT_JUDGE_MODEL,
    ClaimVerdict,
    FaithfulnessResult,
    check_faithfulness,
)
from src.generation.prompt import CITATION_PATTERN
from src.generation.signals import CONFIDENT_TIERS, GenerationChunk, RetrievalConfidenceTier
from src.works import WORKS

# The corpus's fixed, closed set of 8 works (docs/ROADMAP.md scope
# decision) — canonical title plus any alternate/subtitle actually present
# in the source XML. Derived from `src.works.WORKS` (`fix/title-year-grounding`)
# rather than an independently hardcoded copy, so this and
# `check_title_year_mismatch` below can't drift apart on what a "real" title
# is; `WORKS` itself is still hardcoded, not read from
# `data/processed/works/*.json` (a gitignored build artifact) — this module
# must work before any ingestion has run (a fresh checkout, CI).
KNOWN_WORK_TITLES: dict[str, tuple[str, ...]] = {
    work_id: (metadata.title, *metadata.alt_titles) for work_id, metadata in WORKS.items()
}


def _normalize_title(title: str) -> str:
    """Accent/case/punctuation-insensitive comparison key — a judge-free
    string match still has to tolerate "L'Évolution créatrice" vs. "l
    evolution creatrice", not just byte-identical strings."""
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = stripped.replace("’", "'").lower()
    stripped = re.sub(r"[^a-z0-9']+", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


_KNOWN_TITLES_NORMALIZED = frozenset(
    _normalize_title(title) for titles in KNOWN_WORK_TITLES.values() for title in titles
)

# Anchored on the "intitulé(e)" cue specifically, not any quoted span — see
# this module's docstring ("Prose-embedded title fabrication") for why: a
# quoted span without this cue is often a genuine verbatim quotation from a
# chunk, which must not be flagged. Both real fabrications this check was
# built from actually used this exact cue word.
_TITLE_CUE_PATTERN = re.compile(r"intitulée?\s*[«\"“]([^»\"”]{2,150})[»\"”]", re.IGNORECASE)


def _extract_cited_titles(answer: str) -> tuple[str, ...]:
    """Quoted work titles `answer` introduces with "intitulé(e)" —
    order-preserved, de-duplicated."""
    found = [match.group(1).strip() for match in _TITLE_CUE_PATTERN.finditer(answer)]
    return tuple(dict.fromkeys(t for t in found if t))


def check_title_fabrication(answer: str) -> tuple[str, ...]:
    """Titles `answer` names (via the "intitulé(e)" cue) that don't match,
    after normalization, any of the corpus's known 8 work titles/alternate
    titles — purely deterministic, no LLM call, no dependency on `chunks`
    (the check is against the whole corpus, not just the chunks passed to
    this particular generation)."""
    return tuple(
        title
        for title in _extract_cited_titles(answer)
        if _normalize_title(title) not in _KNOWN_TITLES_NORMALIZED
    )


_WORK_ID_BY_NORMALIZED_TITLE: dict[str, str] = {
    _normalize_title(title): work_id
    for work_id, metadata in WORKS.items()
    for title in (metadata.title, *metadata.alt_titles)
}

# A 4-digit year, anchored so it doesn't match inside a work_id/chunk_id
# token like "1907_EC" or "1907_EC_c5" (the trailing "_" is a word
# character, same class as the preceding digit, so \b doesn't fall between
# them — deliberate, not an oversight: a chunk_id mentioned near a title is
# not the model's own year claim about that title).
_YEAR_PATTERN = re.compile(r"(?<!\d)(1[89]\d{2})(?!\d)(?!_)")

# Characters searched before/after each "intitulé(e)" cue match for a year
# claim — see the module docstring ("Title+year pairing") for why this is a
# documented placeholder, not a fit threshold.
_YEAR_CONTEXT_WINDOW = 60


@dataclass(frozen=True)
class TitleYearMismatch:
    """A known, real title (`title`, matching `work_id`) that `answer`
    pairs with a year other than that work's real `correct_year` —
    `claimed_years` holds whichever wrong year(s) appeared near the title's
    "intitulé(e)" mention."""

    title: str
    work_id: str
    correct_year: int
    claimed_years: tuple[int, ...]


def check_title_year_mismatch(answer: str) -> tuple[TitleYearMismatch, ...]:
    """For each "intitulé(e)"-cued title in `answer` that matches a real
    known work (an unmatched one is `check_title_fabrication`'s job, not
    this check's), flags it if a year mentioned within
    `_YEAR_CONTEXT_WINDOW` characters of the cue doesn't match that work's
    real publication year. Purely deterministic, no LLM call, no dependency
    on `chunks` — same discipline as `check_title_fabrication`."""
    mismatches = []
    for match in _TITLE_CUE_PATTERN.finditer(answer):
        title = match.group(1).strip()
        work_id = _WORK_ID_BY_NORMALIZED_TITLE.get(_normalize_title(title))
        if work_id is None:
            continue
        start = max(0, match.start() - _YEAR_CONTEXT_WINDOW)
        end = min(len(answer), match.end() + _YEAR_CONTEXT_WINDOW)
        context = answer[start:end]
        correct_year = WORKS[work_id].year
        claimed_years = tuple(
            sorted({int(year) for year in _YEAR_PATTERN.findall(context)} - {correct_year})
        )
        if claimed_years:
            mismatches.append(
                TitleYearMismatch(
                    title=title,
                    work_id=work_id,
                    correct_year=correct_year,
                    claimed_years=claimed_years,
                )
            )
    return tuple(mismatches)


def _extract_citations(answer: str) -> tuple[str, ...]:
    """chunk_ids cited in `answer`, in the `[chunk_id]` bracket form
    `CITATION_INSTRUCTION` (src/generation/prompt.py) asks the model to
    produce — order-preserved, de-duplicated. A single bracket may list more
    than one chunk_id (comma/semicolon-separated); each is extracted
    individually."""
    found: list[str] = []
    for bracket in CITATION_PATTERN.findall(answer):
        for token in re.split(r"[,;]\s*", bracket):
            token = token.strip()
            if token:
                found.append(token)
    return tuple(dict.fromkeys(found))


@dataclass(frozen=True)
class StructuralCheck:
    """Layer 1: deterministic, no LLM call. `has_citation`/`passed` are
    derived from `citations`/`unknown_citations`/`fabricated_titles`, not
    stored redundantly — same convention as `EvidenceSignals.is_multi_work`
    (`src/generation/signals.py`)."""

    citations: tuple[str, ...]
    unknown_citations: tuple[str, ...]  # cited chunk_ids absent from `chunks`
    # Quoted work titles the answer names that don't match any of the
    # corpus's 8 real works (`check_title_fabrication`, Sprint 10).
    fabricated_titles: tuple[str, ...] = ()
    # Real, known titles the answer pairs with the wrong publication year
    # (`check_title_year_mismatch`, `fix/title-year-grounding`).
    title_year_mismatches: tuple[TitleYearMismatch, ...] = ()

    @property
    def has_citation(self) -> bool:
        return bool(self.citations)

    @property
    def passed(self) -> bool:
        return (
            self.has_citation
            and not self.unknown_citations
            and not self.fabricated_titles
            and not self.title_year_mismatches
        )


def check_structure(answer: str, chunks: Sequence[GenerationChunk]) -> StructuralCheck:
    """Every citation `answer` makes must name a chunk_id present in
    `chunks`, and at least one citation must be present — purely structural,
    no LLM call, independent of `check_faithfulness` (Layer 2). Also runs
    `check_title_fabrication` (Sprint 10) to catch prose-embedded fabricated
    work titles, and `check_title_year_mismatch` (`fix/title-year-grounding`)
    to catch a real title paired with the wrong year — two failure modes the
    citation-resolution check above was never designed to catch (see module
    docstring)."""
    known_ids = {chunk.chunk_id for chunk in chunks}
    citations = _extract_citations(answer)
    unknown = tuple(citation for citation in citations if citation not in known_ids)
    fabricated_titles = check_title_fabrication(answer)
    title_year_mismatches = check_title_year_mismatch(answer)
    return StructuralCheck(
        citations=citations,
        unknown_citations=unknown,
        fabricated_titles=fabricated_titles,
        title_year_mismatches=title_year_mismatches,
    )


@dataclass(frozen=True)
class EvaluationResult:
    structural: StructuralCheck
    faithfulness: FaithfulnessResult
    retrieval_confidence: RetrievalConfidenceTier

    @property
    def unsupported_claims(self) -> tuple[ClaimVerdict, ...]:
        return tuple(claim for claim in self.faithfulness.claims if not claim.supported)

    @property
    def has_unsupported_claims(self) -> bool:
        return bool(self.unsupported_claims)


def generate_evaluation(
    query: str,
    chunks: Sequence[GenerationChunk],
    answer: str,
    retrieval_confidence: RetrievalConfidenceTier,
    judge_llm: LangchainLLMWrapper | None = None,
    model: str = DEFAULT_JUDGE_MODEL,
) -> EvaluationResult:
    """Runs after any `generate_from_chunks` call (initial or manual
    regeneration) on its output — never inside `generate_from_chunks` itself,
    which stays generation-only and fast (docs/ROADMAP.md, Sprint 5 vs. 6).

    Applies identically regardless of caller: an initial generation and a
    manual regeneration (`chunk_judgments` populated or not) both get
    evaluated the same way here, no special-cased path for either — this
    function only sees `(query, chunks, answer)`, not how `answer` was
    produced.

    `retrieval_confidence` is supplied by the caller rather than computed
    here (docs/ROADMAP.md, the retrieval-confidence-split correction):
    `src.generation.signals.retrieval_confidence_tier` is the single shared
    computation, called once at generation time (`/generate`) and again,
    identically, wherever the pre-generation preview needs it
    (`/confidence-preview`) — this function just receives whichever value
    the caller already has (typically the persisted one from the
    `generations` row) rather than recomputing it a third time from
    `chunks`.

    `judge_llm`/`model` are forwarded to `check_faithfulness` unchanged (pass
    a pre-built `judge_llm` to reuse across many evaluations, same as that
    function's own contract) — the only LLM call this function makes.
    """
    structural = check_structure(answer, chunks)
    faithfulness = check_faithfulness(query, answer, chunks, judge_llm=judge_llm, model=model)
    return EvaluationResult(
        structural=structural, faithfulness=faithfulness, retrieval_confidence=retrieval_confidence
    )


def should_auto_expand(evaluation: EvaluationResult) -> bool:
    """True only if retrieval confidence is at least "moyenne", no claim was
    flagged unsupported by Layer 2, AND Layer 1 found no fabricated work
    title or title/year mismatch — see the module docstring for why Layer
    1's citation-resolution half (`unknown_citations`/`has_citation`) isn't
    part of this gate while `fabricated_titles`/`title_year_mismatches` are.
    The first generated answer is always rendered collapsed by default
    regardless of this result (Sprint 7, docs/ROADMAP.md) — this only
    decides whether it may then auto-expand; the user can always expand it
    manually either way."""
    confidence_ok = evaluation.retrieval_confidence in CONFIDENT_TIERS
    no_fabricated_titles = not evaluation.structural.fabricated_titles
    no_year_mismatches = not evaluation.structural.title_year_mismatches
    return (
        confidence_ok
        and not evaluation.has_unsupported_claims
        and no_fabricated_titles
        and no_year_mismatches
    )
