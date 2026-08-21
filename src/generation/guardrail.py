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
  one place that format is allowed to change.
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

`should_auto_expand` folds two of the three into one boolean: retrieval
confidence at "moyenne" or above (`CONFIDENT_TIERS`,
`src/generation/signals.py` — the same set Sprint 5's `is_confident` also
checks against), and no claim flagged unsupported (Layer 2) — matching the
decision rule as specified. Layer 1 (`StructuralCheck`) is carried on
`EvaluationResult` for the caller (and Sprint 7's UI badge) but deliberately
does not gate `should_auto_expand` on its own: the local generation model
was found, empirically, to often omit `[chunk_id]` citations even from
otherwise well-grounded answers (`CITATION_INSTRUCTION` in
`src/generation/prompt.py` is a request, not an enforced constraint) —
gating on citation *presence* would make auto-expand practically
unreachable regardless of actual faithfulness. A citation to a chunk_id
absent from `chunks`, in practice, is accompanied by a claim Layer 2 also
flags unsupported (the fabricated "evidence" isn't in `retrieved_contexts`
either), so Layer 2 still catches that failure mode in practice even though
Layer 1 isn't wired into the gate directly.
"""

from __future__ import annotations

import re
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
    derived from `citations`/`unknown_citations`, not stored redundantly —
    same convention as `EvidenceSignals.is_multi_work`
    (`src/generation/signals.py`)."""

    citations: tuple[str, ...]
    unknown_citations: tuple[str, ...]  # cited chunk_ids absent from `chunks`

    @property
    def has_citation(self) -> bool:
        return bool(self.citations)

    @property
    def passed(self) -> bool:
        return self.has_citation and not self.unknown_citations


def check_structure(answer: str, chunks: Sequence[GenerationChunk]) -> StructuralCheck:
    """Every citation `answer` makes must name a chunk_id present in
    `chunks`, and at least one citation must be present — purely structural,
    no LLM call, independent of `check_faithfulness` (Layer 2)."""
    known_ids = {chunk.chunk_id for chunk in chunks}
    citations = _extract_citations(answer)
    unknown = tuple(citation for citation in citations if citation not in known_ids)
    return StructuralCheck(citations=citations, unknown_citations=unknown)


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
    """True only if retrieval confidence is at least "moyenne" AND no claim
    was flagged unsupported by Layer 2 — see the module docstring for why
    Layer 1 (`evaluation.structural`) isn't part of this gate. The first
    generated answer is always rendered collapsed by default regardless of
    this result (Sprint 7, docs/ROADMAP.md) — this only decides whether it
    may then auto-expand; the user can always expand it manually either
    way."""
    confidence_ok = evaluation.retrieval_confidence in CONFIDENT_TIERS
    return confidence_ok and not evaluation.has_unsupported_claims
