"""RAGAS-based faithfulness checking (docs/ROADMAP.md, Sprint 5 — "preliminary
end-to-end evaluation (RAGAS)"), designed for two consumers from the start:

1. `eval/scripts/run_ragas_eval.py` (this sprint) — calls `check_faithfulness`
   once per gold item, in a loop, to score generation quality in batch.
2. Sprint 6's anti-hallucination guardrail (not built yet) — will call
   `check_faithfulness` once per generated answer, at production latency,
   right after `generate_from_chunks` returns. Not wired up here (that's
   Sprint 6's own commit), but this module is the function it imports.

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
decision, no per-claim structural citation check. This module returns the
raw RAGAS score only — Sprint 6 decides what to do with it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import litellm
from langchain_litellm import ChatLiteLLM
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
# RAGAS's own internal fix-the-format retry. Confirmed fixed empirically at
# num_ctx=8192 against this project's real chunk sizes (up to 5 concatenated
# chunks, eval/scripts/run_ragas_eval.py's end_to_end mode). Only applied
# for an Ollama-served model — passing an Ollama-specific param to a hosted
# provider (e.g. the Mistral API fallback) would error.
JUDGE_NUM_CTX = 8192
_OLLAMA_PROVIDERS = ("ollama", "ollama_chat")


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


@dataclass(frozen=True)
class FaithfulnessResult:
    # Fraction of extracted claims entailed by `chunks`; NaN if the answer
    # yielded no claims.
    score: float
    model: str  # judge model used (LiteLLM model string)


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
    from a batch eval loop and from a future single-answer guardrail check.

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
    score = Faithfulness(llm=llm).single_turn_score(sample)
    return FaithfulnessResult(score=score, model=model)
