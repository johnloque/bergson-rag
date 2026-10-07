"""RAGAS-based faithfulness checking (docs/ROADMAP.md, Sprint 5 — "preliminary
end-to-end evaluation (RAGAS)"), designed for two consumers from the start:

1. `eval/scripts/run_ragas_eval.py` (Sprint 5) — calls `check_faithfulness`
   once per gold item, in a loop, to score generation quality in batch.
2. `generate_evaluation` (Sprint 6, `src/generation/guardrail.py`) — calls
   `check_faithfulness` once per generated answer, right after
   `generate_from_chunks` returns.

One implementation, not two: there is no separate hand-rolled "for the
guardrail" faithfulness check. Both consumers call the same function.

## Why the judge LLM is a `LangchainLLMWrapper`, not `ragas.llms.llm_factory`

Both judging steps below run RAGAS `PydanticPrompt`s (the claim-extraction
prompt is this module's own, the NLI prompt a variant of RAGAS's), and
RAGAS 0.3.x ships two parallel LLM abstractions: the newer
`llm_factory(..., provider="litellm")` returns an
`InstructorLLM`, which `PydanticPrompt.generate` — and the legacy
prompt-based metrics built on it (`Faithfulness`,
`LLMContextPrecisionWithReference`, `LLMContextRecall`) — cannot use: they
call `.agenerate_prompt(...)`, a method only `LangchainLLMWrapper` exposes
(confirmed empirically: `InstructorLLM` raises `AttributeError` on it).
`LangchainLLMWrapper` wrapping `langchain_litellm.ChatLiteLLM` (the actively
maintained standalone package — not `langchain_community`'s own `ChatLiteLLM`,
which langchain-community's own deprecation notice points away from) is what
actually works, and keeps model access on LiteLLM (this project's
standing multi-provider abstraction, `docs/generation_strategy.md`) rather
than a second, parallel provider-switching path — `model` is still a plain
LiteLLM model string (e.g. `"ollama_chat/mistral"`), same convention as
`generate_from_chunks`.

## Packaging note

`ragas` and `langchain-community` are both pinned in `pyproject.toml` below
their latest releases: `ragas>=0.4` unconditionally imports
`langchain_community.chat_models.vertexai` at module load time, a path
`langchain-community` has since dropped — breaks `import ragas` for every
non-VertexAI user (upstream issue, unresolved as of this pin; see
`pyproject.toml` for tracking links). Verified fixed at `ragas==0.3.9` +
`langchain-community==0.3.30`.

## Latency (measured against this project's default judge, local Mistral
7B via Ollama)

A single `check_faithfulness` call costs 1 + N LLM round trips (claim
extraction, then one entailment call per claim — see "One NLI call per
claim" below). Measured on this project's dev machine with 5 real reranked
chunks (13-20k characters of context) and 6-11 claims: ~30-45s for
extraction, ~60-120s for the NLI calls (feat/segment-claims benchmark). The
older "~8-9s" figure was for single-chunk evidence and a short answer. Fine
for an on-demand check, far from sub-second. Confirmed deterministic across repeated calls at
`temperature=0` on the same input (docs/ROADMAP.md eval determinism
requirement) — see `eval/scripts/run_ragas_eval.py`'s own determinism check
for the full-pipeline verification.

Deliberately out of scope here (separate, already-deferred work,
docs/ROADMAP.md Sprint 6): no threshold/`is_faithful` boolean, no refusal
decision, no structural citation check (that's `check_structure` in
`src/generation/guardrail.py`, Sprint 6's own module — deliberately kept out
of this shared eval/guardrail module since it needs no LLM call at all).
`check_faithfulness` does return the per-claim verdicts (`claims` below)
alongside the aggregate score, as of Sprint 6 — needed to flag which
claim is unsupported, not just that some are, for the anti-hallucination
guardrail (`generate_evaluation`, `src/generation/guardrail.py`).

## One NLI call per claim

RAGAS's own `Faithfulness` metric judges all claims in one NLI call and
returns a list of verdicts, each echoing its statement's text. Neither the
list position nor the echoed text is a guaranteed link back to the claim:
a local judge can drop, merge or reorder items, or alter the echo. This
module calls the NLI prompt once per claim instead, so each response is by
construction the verdict for that claim — no matching step at all.

Measured against single-call judging on 4 gold items (30 claims, 5 real
reranked chunks each): the two disagreed on 9 verdicts, and checked against
the chunks' text, per-claim judging was right on 6 of them. Single-call
judging accepted 4 claims absent from the context (vs 2), with the same
boilerplate reason repeated across neighboring claims — judging claims
together lets one claim's verdict bleed into the next, the same
contamination `src/generation/chunk_judge.py` avoids by judging one chunk
per call. Cost: the long shared prefix (instructions, examples, context)
comes first in the prompt, so Ollama reuses its cache across the N calls;
estimated latency overhead 0-20%.

A claim whose NLI output can't be parsed (`RagasOutputParserException`,
observed once in 30 calls) is kept with `supported=None` ("not evaluated")
rather than failing the whole check; it is excluded from `score`.

The NLI step does not use `ragas.metrics.Faithfulness` itself: the prompt is
run directly, and `score` is computed here (supported / evaluated claims).

## Anchoring claims to answer segments, for UI coloring

The frontend colors every sentence of the answer by the verdicts of the
claims drawn from it, so each claim must be tied back to the span of the
answer it comes from. RAGAS's own `StatementGeneratorPrompt`
(`ragas.metrics._faithfulness`) returns bare, pronoun-free reformulations
with no link to their source sentence (it leaves sentence detection to the
LLM and keeps no index).

A previous version asked the judge to also copy a verbatim `quote` of the
source span. It proved unreliable: a quote is *generated* text, so a local
judge altered punctuation and apostrophes, paraphrased, or stitched
non-contiguous fragments together (a resolved pronoun's antecedent comes
from another sentence), and the quote then matched nothing in the answer.

Current approach: the answer is cut into sentence segments by code
(`src/generation/segmentation.py`, no LLM), and `_SEGMENT_CLAIMS_PROMPT`
below asks the judge to decompose each numbered segment into claims,
grouped under that segment's id. The anchor is *selected*, not generated, so
it always designates a real span of the answer; the output shape guarantees
one segment per claim. The attribution itself is trusted as-is (only ids
that don't exist are dropped). The NLI step (`_NLI_PROMPT`) then judges
each reformulated claim's text against the cited chunks.

## Judge prompt languages

The local 7B judge answers in the language of the prompt, not of the
answer — even when told not to translate — and the UI shows both the claims
and the verdict `reason`s verbatim to a French-speaking reader. So:

- `_SEGMENT_CLAIMS_PROMPT` is entirely in French (instruction and example):
  with an English prompt, every claim of a French answer came back
  translated into English.
- `_NLI_PROMPT` keeps RAGAS's own English `NLIStatementPrompt` (instruction
  and examples) and only asks for, and shows, the `reason`s in French. A
  fully French translation was tried first and degraded the verdicts
  themselves: the judge marked a fabricated claim ("Bergson borrowed this
  image from Einstein in 1950") as supported while its own French reason
  said the context contained nothing about it — a verdict/reason mismatch
  the English prompt didn't produce on the same input.
"""

from __future__ import annotations

import asyncio
import atexit
import re
import threading
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any

import litellm
from langchain_litellm import ChatLiteLLM
from pydantic import BaseModel, Field
from ragas.exceptions import RagasOutputParserException

# Imported from ragas.llms.base, not the public ragas.llms re-export: the
# re-export wraps this class in a DeprecationHelper instance (steering
# callers toward llm_factory), which is not usable as a static type and
# fires a DeprecationWarning on every construction. The steering doesn't
# apply here regardless — llm_factory's provider="litellm" path returns an
# InstructorLLM, which Faithfulness/LLMContextPrecisionWithReference/
# LLMContextRecall cannot use (see module docstring); LangchainLLMWrapper
# is the only working option for these metrics in ragas 0.3.9.
from ragas.llms.base import LangchainLLMWrapper

# The NLI step's input/output models, reused as-is by `_NLI_PROMPT` below
# (only the prompt's language changes). Imported from the private module
# since `ragas.metrics` doesn't re-export them; they're stable-shaped
# Pydantic models, not internal machinery.
from ragas.metrics._faithfulness import NLIStatementInput, NLIStatementOutput
from ragas.prompt import PydanticPrompt

from src.generation.generate import DEFAULT_MODEL
from src.generation.prompt import CITATION_PATTERN
from src.generation.segmentation import Segment, segment_answer
from src.generation.signals import GenerationChunk
from src.prompts.loader import (
    load_examples,
    load_field_descriptions,
    load_prompt,
    prompts_used,
)

# Same default model as generate_from_chunks (src/generation/generate.py) —
# local Mistral via Ollama, cost-free by default (docs/ROADMAP.md).
DEFAULT_JUDGE_MODEL = DEFAULT_MODEL

# A judge model should be as reproducible as the thing it's grading — fixed
# at 0 regardless of caller (eval batch run or a future guardrail call),
# not just for eval runs specifically.
JUDGE_TEMPERATURE = 0.0

# Ollama's own request-level default context window (2048-4096 depending on
# server config) is too small for RAGAS's judging prompts: they bundle
# lengthy few-shot examples on top of the actual (query, answer, contexts)
# triple, and truncation mid-generation was observed to produce free-text
# instead of the requested JSON — RagasOutputParserException even after
# RAGAS's own internal fix-the-format retry. num_ctx=8192 turned out not to
# be a safe general default: tests/test_guardrail.py's Q009 case overflowed
# it with as few as 5 real (long) chunks, and it reliably overflows on the
# API's old default retrieval top_k of 10 (confirmed against a real
# conversation, /evaluate raising the same RagasOutputParserException as an
# unhandled 500). 16384 is the value that test already had to pass
# explicitly to work around the overflow — promoted here to the default so
# every caller gets it, not just that one test. Only applied for an
# Ollama-served model — passing an Ollama-specific param to a hosted
# provider (e.g. the Mistral API fallback) would error.
JUDGE_NUM_CTX = 16384
_OLLAMA_PROVIDERS = ("ollama", "ollama_chat")

# `ragas.async_utils.run` (RAGAS's own sync-wrapper, used here until the fix
# below) drives each await with a fresh `asyncio.run(...)`, which opens and
# then immediately closes a brand-new event loop per call. litellm's async
# HTTP client cache keys clients by event-loop id specifically to avoid
# reusing one across loops (`LLMClientCache.update_cache_key_with_event_loop`
# in `litellm/caching/llm_caching_handler.py`), so every such call builds a
# fresh `AsyncHTTPHandler` — and its underlying TCP connection to the judge
# provider (typically local Ollama) is never closed, because the loop that
# would run its cleanup is already gone by the time it'd be evicted. Two
# calls per `check_faithfulness` invocation (statements, then verdicts) times
# every `/evaluate` request leaks two connections each; against Ollama's
# single-slot local server (`-np 1`) this was observed to eventually wedge it
# entirely (near-idle CPU, no progress on any request) after enough
# `/evaluate` calls piled up established-but-abandoned connections.
#
# Fix: run every judge-LLM coroutine on one persistent background event loop
# instead of a new one per call, so litellm's cache key stays stable and it
# reuses (rather than re-leaks) the same client and connection.
_background_loop: asyncio.AbstractEventLoop | None = None
_background_loop_thread: threading.Thread | None = None
_background_loop_init_lock = threading.Lock()


def _get_background_loop() -> asyncio.AbstractEventLoop:
    global _background_loop, _background_loop_thread
    with _background_loop_init_lock:
        if _background_loop is None:
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever, name="faithfulness-judge-loop", daemon=True
            )
            thread.start()
            _background_loop = loop
            _background_loop_thread = thread
            atexit.register(_stop_background_loop)
        return _background_loop


def _stop_background_loop() -> None:
    global _background_loop, _background_loop_thread
    loop, thread = _background_loop, _background_loop_thread
    if loop is not None:
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None:
        thread.join(timeout=5)
    _background_loop = None
    _background_loop_thread = None


def _run_on_background_loop[T](coro: Coroutine[Any, Any, T]) -> T:
    """Schedules `coro` on the shared judge-LLM event loop and blocks the
    calling (sync) thread for its result — this module's replacement for
    `ragas.async_utils.run` (see the note above for why)."""
    future = asyncio.run_coroutine_threadsafe(coro, _get_background_loop())
    return future.result()


def build_judge_llm(
    model: str = DEFAULT_JUDGE_MODEL, temperature: float = JUDGE_TEMPERATURE
) -> LangchainLLMWrapper:
    """A RAGAS-compatible LLM wrapper for `model` (any LiteLLM model string),
    reusable across many `check_faithfulness` calls — build once, pass via
    `judge_llm` to avoid reconstructing it per item in a batch loop."""
    _, provider, _, _ = litellm.get_llm_provider(model)
    model_kwargs = {"num_ctx": JUDGE_NUM_CTX} if provider in _OLLAMA_PROVIDERS else {}
    return LangchainLLMWrapper(
        ChatLiteLLM(model=model, temperature=temperature, model_kwargs=model_kwargs)
    )


_SEGMENT_CLAIMS_SOURCE = load_prompt("faithfulness.segment_claims")
_NLI_SOURCE = load_prompt("faithfulness.nli_verifier")


# Input model: RAGAS sends only its values (as JSON), never its schema, so
# nothing here reaches the judge — plain comments rather than
# Field(description=...), which would look like prompt text. Prompt-facing
# descriptions are the output models' below.
class AnswerSegment(BaseModel):
    segment_id: int  # the segment's number
    text: str  # the segment's text, one sentence of the answer


class SegmentedAnswerInput(BaseModel):
    question: str  # the question to answer
    segments: list[AnswerSegment]  # the answer, split into numbered segments, in order


# Output models: RAGAS sends their JSON schema to the judge, descriptions
# included — prompt text, read from prompts/faithfulness/segment_claims.schema.yaml
# and part of the prompt's hash (docs/prompts.md).
_OUTPUT_DESCRIPTIONS = load_field_descriptions(_SEGMENT_CLAIMS_SOURCE)


class SegmentClaims(BaseModel):
    segment_id: int = Field(description=_OUTPUT_DESCRIPTIONS.get("SegmentClaims", "segment_id"))
    claims: list[str] = Field(description=_OUTPUT_DESCRIPTIONS.get("SegmentClaims", "claims"))


class SegmentedClaimsOutput(BaseModel):
    segments: list[SegmentClaims] = Field(
        description=_OUTPUT_DESCRIPTIONS.get("SegmentedClaimsOutput", "segments")
    )


_OUTPUT_DESCRIPTIONS.check(SegmentClaims, SegmentedClaimsOutput)


class SegmentClaimsPrompt(PydanticPrompt[SegmentedAnswerInput, SegmentedClaimsOutput]):
    """Same decomposition RAGAS's own `StatementGeneratorPrompt` does
    (`ragas.metrics._faithfulness`), but over pre-cut, numbered segments,
    with each claim grouped under the segment it comes from — see this
    module's docstring, "Anchoring claims to answer segments"."""

    # Instruction and examples are in French: the local 7B judge was observed
    # to answer in the language of the prompt rather than of the answer, even
    # when told not to translate — and the UI shows claims verbatim. Wording
    # lives in prompts/faithfulness/segment_claims{.md,.examples.yaml}.
    instruction = _SEGMENT_CLAIMS_SOURCE.render()
    input_model = SegmentedAnswerInput
    output_model = SegmentedClaimsOutput
    examples = load_examples(_SEGMENT_CLAIMS_SOURCE, SegmentedAnswerInput, SegmentedClaimsOutput)


_SEGMENT_CLAIMS_PROMPT = SegmentClaimsPrompt()


class FrenchReasonNLIStatementPrompt(PydanticPrompt[NLIStatementInput, NLIStatementOutput]):
    """RAGAS's own `NLIStatementPrompt` (`ragas.metrics._faithfulness`) —
    same instruction, same examples, same models — except that the verdict
    `reason`s are asked for, and shown in the examples, in French (see this
    module's docstring, "Judge prompt languages")."""

    # Wording in prompts/faithfulness/nli_verifier{.md,.examples.yaml}, kept
    # exactly as benchmarked (feat/segment-claims), including "Copy each
    # statement word-by-word" — the echo itself is no longer relied on, since
    # each call judges a single claim (see "One NLI call per claim").
    instruction = _NLI_SOURCE.render()
    input_model = NLIStatementInput
    output_model = NLIStatementOutput
    examples = load_examples(_NLI_SOURCE, NLIStatementInput, NLIStatementOutput)


_NLI_PROMPT = FrenchReasonNLIStatementPrompt()


def faithfulness_prompts_used() -> dict[str, dict[str, Any]]:
    """`prompts_used` record for one `check_faithfulness` call."""
    return prompts_used(_SEGMENT_CLAIMS_SOURCE, _NLI_SOURCE)


def _text_for_judge(segment: Segment) -> str:
    """The segment's text without its `[chunk_id]` citations. They assert
    nothing, and the judge was observed to mistake one for a segment id —
    `"segment_id": 1907_EC_c5`, invalid JSON that RAGAS's own fix-the-format
    retry then failed to recover, failing the whole check."""
    text = CITATION_PATTERN.sub("", segment.text)
    return re.sub(r"\s+([.,])", r"\1", re.sub(r"\s+", " ", text)).strip()


def _anchor_claims(
    segments: Sequence[Segment], output: SegmentedClaimsOutput
) -> list[tuple[int, str]]:
    """(segment_id, claim) pairs from the judge's grouped output, in order.
    The judge's attribution is trusted; only ids that designate no real
    segment, and blank claims, are dropped."""
    valid_ids = {segment.id for segment in segments}
    return [
        (group.segment_id, claim.strip())
        for group in output.segments
        if group.segment_id in valid_ids
        for claim in group.claims
        if claim.strip()
    ]


@dataclass(frozen=True)
class ClaimVerdict:
    """One claim extracted from the scored answer, with its entailment
    verdict against `chunks`. `reason` is the judge's own explanation for
    the verdict (`_NLI_PROMPT`), not post-hoc computed. `supported` and
    `reason` are `None` when the claim couldn't be evaluated (unparseable
    NLI output). `segment_id` is the answer segment
    (`FaithfulnessResult.segments`) the claim was drawn from."""

    statement: str
    supported: bool | None
    reason: str | None
    segment_id: int


def _claim_verdict(segment_id: int, claim: str, output: NLIStatementOutput | None) -> ClaimVerdict:
    """`output` is the NLI response for this one claim alone. Anything but
    exactly one verdict (or no response at all) leaves it not evaluated."""
    if output is None or len(output.statements) != 1:
        return ClaimVerdict(statement=claim, supported=None, reason=None, segment_id=segment_id)
    answer = output.statements[0]
    return ClaimVerdict(
        statement=claim,
        supported=bool(answer.verdict),
        reason=answer.reason,
        segment_id=segment_id,
    )


def _score(claims: Sequence[ClaimVerdict]) -> float:
    """Fraction of evaluated claims that are supported; NaN if none was."""
    evaluated = [claim.supported for claim in claims if claim.supported is not None]
    return sum(evaluated) / len(evaluated) if evaluated else float("nan")


@dataclass(frozen=True)
class FaithfulnessResult:
    # Fraction of evaluated claims entailed by `chunks`; NaN if the answer
    # yielded no claims, or none could be evaluated.
    score: float
    model: str  # judge model used (LiteLLM model string)
    # Per-claim breakdown behind `score`; empty iff the answer yielded no
    # claims (score is NaN in that case too).
    claims: tuple[ClaimVerdict, ...] = ()
    # The answer's sentence segments (src/generation/segmentation.py) that
    # `claims` are anchored to. Returned even when no claim was extracted,
    # so every segment can still be shown (as neutral).
    segments: tuple[Segment, ...] = ()


def check_faithfulness(
    query: str,
    answer: str,
    chunks: Sequence[GenerationChunk],
    judge_llm: LangchainLLMWrapper | None = None,
    model: str = DEFAULT_JUDGE_MODEL,
) -> FaithfulnessResult:
    """RAGAS faithfulness of `answer` (as produced by `generate_from_chunks`,
    or any other source) against `chunks` as cited evidence for `query`.

    Works standalone on a single triple — no retrieval, no gold dataset, no
    RAGAS `Dataset`/`evaluate()` call involved, so this is equally usable
    from a batch eval loop and from the anti-hallucination guardrail
    (`generate_evaluation`, `src/generation/guardrail.py`, Sprint 6).

    `judge_llm`: pass a pre-built wrapper (`build_judge_llm`) to reuse across
    many calls in a batch loop, instead of rebuilding one per item. When
    omitted, one is built from `model` for this call only. `model` always
    labels the returned result — it is not read back off a caller-supplied
    `judge_llm`, so pass the matching string when you supply one.
    """
    segments = segment_answer(answer)
    if not segments:
        return FaithfulnessResult(score=float("nan"), model=model)

    llm = judge_llm if judge_llm is not None else build_judge_llm(model)
    context = "\n".join(chunk.text for chunk in chunks)

    async def _judge(claim: str) -> NLIStatementOutput | None:
        try:
            return await _NLI_PROMPT.generate(
                llm=llm, data=NLIStatementInput(context=context, statements=[claim])
            )
        except RagasOutputParserException:
            return None

    async def _run() -> tuple[ClaimVerdict, ...]:
        output = await _SEGMENT_CLAIMS_PROMPT.generate(
            llm=llm,
            data=SegmentedAnswerInput(
                question=query,
                segments=[
                    AnswerSegment(segment_id=s.id, text=_text_for_judge(s)) for s in segments
                ],
            ),
        )
        # Sequential on purpose: the judge (local Ollama) serves one request
        # at a time anyway, and in-order calls keep the shared prompt prefix
        # in its cache.
        return tuple(
            [
                _claim_verdict(segment_id, claim, await _judge(claim))
                for segment_id, claim in _anchor_claims(segments, output)
            ]
        )

    claims = _run_on_background_loop(_run())
    return FaithfulnessResult(score=_score(claims), model=model, claims=claims, segments=segments)
