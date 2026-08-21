"""RAGAS-based faithfulness checking (docs/ROADMAP.md, Sprint 5 — "preliminary
end-to-end evaluation (RAGAS)"), designed for two consumers from the start:

1. `eval/scripts/run_ragas_eval.py` (Sprint 5) — calls `check_faithfulness`
   once per gold item, in a loop, to score generation quality in batch.
2. `generate_evaluation` (Sprint 6, `src/generation/guardrail.py`) — calls
   `check_faithfulness` once per generated answer, right after
   `generate_from_chunks` returns.

One implementation, not two: there is no separate hand-rolled "for the
guardrail" faithfulness check. Both consumers call the same function.

## Why this wraps `ragas.metrics.Faithfulness` via `LangchainLLMWrapper`,
not `ragas.llms.llm_factory`

`Faithfulness.single_turn_score(SingleTurnSample(...))` is a fully supported,
non-batch entry point — RAGAS does not force a `Dataset`/`evaluate()` call
for a single (query, answer, contexts) triple, so no custom claims-extraction
reimplementation was needed here. But RAGAS 0.3.x ships two parallel LLM
abstractions: the newer `llm_factory(..., provider="litellm")` returns an
`InstructorLLM`, which legacy prompt-based metrics (`Faithfulness`,
`LLMContextPrecisionWithReference`, `LLMContextRecall`) cannot use — they
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

A single `check_faithfulness` call costs ~2 LLM round trips internally
(claim extraction, then per-claim entailment against the cited contexts) —
observed ~8-9s end to end on this project's dev machine (single-chunk
evidence; see `JUDGE_NUM_CTX` below for the multi-chunk case). Fine for a
per-answer guardrail check (a few extra seconds after generation), not
sub-second. Confirmed deterministic across repeated calls at
`temperature=0` on the same input (docs/ROADMAP.md eval determinism
requirement) — see `eval/scripts/run_ragas_eval.py`'s own determinism check
for the full-pipeline verification.

Deliberately out of scope here (separate, already-deferred work,
docs/ROADMAP.md Sprint 6): no threshold/`is_faithful` boolean, no refusal
decision, no structural citation check (that's `check_structure` in
`src/generation/guardrail.py`, Sprint 6's own module — deliberately kept out
of this shared eval/guardrail module since it needs no LLM call at all).
`check_faithfulness` does return the per-claim RAGAS verdicts (`claims`
below) alongside the aggregate score, as of Sprint 6 — needed to flag which
claim is unsupported, not just that some are, for the anti-hallucination
guardrail (`generate_evaluation`, `src/generation/guardrail.py`).

## Getting per-claim verdicts without a second LLM call

`ragas.metrics.Faithfulness.single_turn_score(...)` only returns the
aggregate float — it discards the per-claim verdicts computed along the way.
Sprint 6 needs those verdicts, so `check_faithfulness` below calls the
metric's own two internal async steps directly (`_create_statements`, then
`_create_verdicts`) instead of going through `single_turn_score`. This is
the exact same two LLM calls `single_turn_score` would make internally
(claim extraction, then per-claim entailment) — not a second faithfulness
pass — just with the intermediate verdicts kept instead of thrown away.
Uses `ragas.async_utils.run`, the same sync-wrapper helper
`single_turn_score` itself uses internally, to run these two async calls in
this module's otherwise-sync API.

## Grounding claims back to a verbatim quote, for UI highlighting

The frontend (`AnswerCard.tsx`, via `annotateAnswer.tsx`) wants to highlight
the exact unsupported span inside the *original* answer text. RAGAS's own
`StatementGeneratorPrompt` (`ragas.metrics._faithfulness`) is unsuitable as
the source for that span: its instruction explicitly tells the judge to
rewrite each sentence into a pronoun-free, self-contained statement — by
design not a verbatim substring of the answer (confirmed against real
output: the extracted statement essentially never `indexOf`-matches the
answer it was drawn from). Using it for highlighting silently produced no
highlights at all.

Fix: replace RAGAS's own statement-generation step with
`_GROUNDED_STATEMENT_PROMPT` below, a `PydanticPrompt` that asks for the
same atomic, pronoun-free statements *plus* a `quote` field the instruction
requires to be copied character-for-character from the answer. The NLI
entailment step (`metric._create_verdicts`) is untouched — it still judges
the paraphrased `statement` text against the cited chunks, so the
faithfulness score's meaning doesn't change. `quote` is then validated
against the real answer text (`_ground_quote_in_answer`) — a local judge
does not reliably honor "copy verbatim" — and dropped (not fabricated) when
it doesn't actually occur in the answer, same best-effort philosophy the
old frontend-only matching already documented.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any

import litellm
from langchain_litellm import ChatLiteLLM
from pydantic import BaseModel, Field
from ragas.dataset_schema import SingleTurnSample

# Imported from ragas.llms.base, not the public ragas.llms re-export: the
# re-export wraps this class in a DeprecationHelper instance (steering
# callers toward llm_factory), which is not usable as a static type and
# fires a DeprecationWarning on every construction. The steering doesn't
# apply here regardless — llm_factory's provider="litellm" path returns an
# InstructorLLM, which Faithfulness/LLMContextPrecisionWithReference/
# LLMContextRecall cannot use (see module docstring); LangchainLLMWrapper
# is the only working option for these metrics in ragas 0.3.9.
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import Faithfulness

# `StatementGeneratorInput` (question, answer) is reused as-is as the input
# to our own grounded-statement prompt below — only the *output* shape needs
# to change (see "Grounding claims back to a verbatim quote" above).
# Imported from the private module since `ragas.metrics` doesn't re-export
# it; it's a stable-shaped Pydantic model, not internal machinery.
from ragas.metrics._faithfulness import StatementGeneratorInput
from ragas.prompt import PydanticPrompt

from src.generation.generate import DEFAULT_MODEL
from src.generation.signals import GenerationChunk

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


class GroundedStatement(BaseModel):
    statement: str = Field(
        description="A fully understandable, standalone statement extracted "
        "from the answer, with no pronouns"
    )
    quote: str = Field(
        description="The exact, character-for-character substring of the "
        "answer that this statement was derived from — copied verbatim, "
        "never paraphrased or summarized"
    )


class GroundedStatementGeneratorOutput(BaseModel):
    statements: list[GroundedStatement] = Field(
        description="The generated statements, each paired with its verbatim source quote"
    )


class GroundedStatementGeneratorPrompt(
    PydanticPrompt[StatementGeneratorInput, GroundedStatementGeneratorOutput]
):
    """Same decomposition RAGAS's own `StatementGeneratorPrompt` does
    (`ragas.metrics._faithfulness`), plus a `quote` field per statement so
    the UI can highlight the actual span in the answer — see this module's
    docstring, "Grounding claims back to a verbatim quote"."""

    instruction = (
        "Given a question and an answer, analyze the complexity of each sentence in the "
        "answer. Break down each sentence into one or more fully understandable statements. "
        "Ensure that no pronouns are used in any statement. For each statement, also give a "
        "'quote': the exact substring of the answer, copied character-for-character, that the "
        "statement was derived from. The quote must appear verbatim in the answer — do not "
        "paraphrase, summarize, or alter it in any way. Format the outputs in JSON."
    )
    input_model = StatementGeneratorInput
    output_model = GroundedStatementGeneratorOutput
    examples = [
        (
            StatementGeneratorInput(
                question="Who was Albert Einstein and what is he best known for?",
                answer="He was a German-born theoretical physicist, widely acknowledged to be "
                "one of the greatest and most influential physicists of all time. He was best "
                "known for developing the theory of relativity, he also made important "
                "contributions to the development of the theory of quantum mechanics.",
            ),
            GroundedStatementGeneratorOutput(
                statements=[
                    GroundedStatement(
                        statement="Albert Einstein was a German-born theoretical physicist.",
                        quote="He was a German-born theoretical physicist",
                    ),
                    GroundedStatement(
                        statement="Albert Einstein is recognized as one of the greatest and "
                        "most influential physicists of all time.",
                        quote="widely acknowledged to be one of the greatest and most "
                        "influential physicists of all time",
                    ),
                    GroundedStatement(
                        statement="Albert Einstein was best known for developing the theory "
                        "of relativity.",
                        quote="He was best known for developing the theory of relativity",
                    ),
                    GroundedStatement(
                        statement="Albert Einstein also made important contributions to the "
                        "development of the theory of quantum mechanics.",
                        quote="he also made important contributions to the development of "
                        "the theory of quantum mechanics",
                    ),
                ]
            ),
        )
    ]


_GROUNDED_STATEMENT_PROMPT = GroundedStatementGeneratorPrompt()


def _ground_quote_in_answer(answer: str, quote: str) -> str | None:
    """Validates that `quote` (as returned by `_GROUNDED_STATEMENT_PROMPT`)
    actually occurs in `answer` — the judge is only asked to copy verbatim,
    not guaranteed to. Tolerates a case mismatch (returning the answer's own
    casing, so highlighting always matches what's on screen); anything else
    (paraphrased or fabricated quote) is treated as ungrounded and dropped
    rather than guessed at, same best-effort philosophy as the rest of this
    module's claim handling."""
    quote = quote.strip()
    if not quote:
        return None
    if quote in answer:
        return quote
    idx = answer.lower().find(quote.lower())
    if idx == -1:
        return None
    return answer[idx : idx + len(quote)]


@dataclass(frozen=True)
class ClaimVerdict:
    """One RAGAS-extracted claim from the scored answer, with its entailment
    verdict against `chunks`. `reason` is RAGAS's own judge-generated
    explanation for the verdict, not post-hoc computed. `quote` is the
    verbatim span of `answer` this claim was grounded to (for UI
    highlighting) — `None` when the judge's quote couldn't be validated
    against the answer text (`_ground_quote_in_answer`)."""

    statement: str
    supported: bool
    reason: str
    quote: str | None = None


@dataclass(frozen=True)
class FaithfulnessResult:
    # Fraction of extracted claims entailed by `chunks`; NaN if the answer
    # yielded no claims.
    score: float
    model: str  # judge model used (LiteLLM model string)
    # Per-claim breakdown behind `score`; empty iff the answer yielded no
    # claims (score is NaN in that case too).
    claims: tuple[ClaimVerdict, ...] = ()


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
    llm = judge_llm if judge_llm is not None else build_judge_llm(model)
    sample = SingleTurnSample(
        user_input=query,
        response=answer,
        retrieved_contexts=[chunk.text for chunk in chunks],
    )
    metric = Faithfulness(llm=llm)
    row = sample.to_dict()

    async def _score() -> Any:
        grounded = await _GROUNDED_STATEMENT_PROMPT.generate(
            llm=llm, data=StatementGeneratorInput(question=query, answer=answer)
        )
        if not grounded.statements:
            return None
        statement_texts = [s.statement for s in grounded.statements]
        verdicts = await metric._create_verdicts(row, statement_texts, None)
        return grounded, verdicts

    result = _run_on_background_loop(_score())
    if result is None:
        return FaithfulnessResult(score=float("nan"), model=model, claims=())
    grounded, verdicts = result

    score = metric._compute_score(verdicts)
    # NLI verdicts echo back the exact statement text they were given
    # (`StatementFaithfulnessAnswer.statement`, "the original statement,
    # word-by-word") — matched by that text back to the quote extracted
    # alongside it, rather than assumed positional, since a local judge
    # isn't guaranteed to preserve order/count between the two LLM calls.
    quote_by_statement = {s.statement: s.quote for s in grounded.statements}
    claims = tuple(
        ClaimVerdict(
            statement=v.statement,
            supported=bool(v.verdict),
            reason=v.reason,
            quote=_ground_quote_in_answer(answer, quote_by_statement[v.statement])
            if v.statement in quote_by_statement
            else None,
        )
        for v in verdicts.statements
    )
    return FaithfulnessResult(score=score, model=model, claims=claims)
