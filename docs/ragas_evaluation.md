# RAGAS evaluation — methodology and Sprint 6 handoff

Full detail behind the Sprint 5 "RAGAS evaluation — implemented" line in
[`ROADMAP.md`](ROADMAP.md). Covers `eval/scripts/run_ragas_eval.py`'s design,
the shared faithfulness implementation, and what Sprint 6 needs to know
before wiring the anti-hallucination guardrail.

## `eval/scripts/run_ragas_eval.py`

Two modes, reported separately and never merged (same discipline as the
Test A/B generation split) — `generation_only` (`generate_from_chunks`
called directly on each gold item's own `chunk_ids`, retrieval bypassed) and
`end_to_end` (real hybrid retrieval + rerank + generate). Metrics:
faithfulness, context precision, context recall (`ragas` package, pinned
`ragas==0.3.9` + `langchain-community==0.3.30` — `ragas>=0.4`
unconditionally imports a `langchain_community` path that's since been
dropped upstream, breaking `import ragas` regardless of provider; see
`pyproject.toml` for the tracking issue links).

Judge LLM: local Mistral via Ollama by default, any LiteLLM model string via
`--judge-model`; both generation and judging pinned to `temperature=0` for
this script, with an explicit two-run determinism check (generated answers
and RAGAS scores compared exactly) reported in the output rather than
assumed. Latest result: [`eval/results/`](../eval/results/) (exploratory at
the current gold dataset size, well below the n=50 protocol target —
reported honestly, not withheld).

## Shared faithfulness implementation

`src/generation/faithfulness.py`'s `check_faithfulness(query, answer,
chunks, judge_llm=None, model=...)` is the one faithfulness implementation
for both this sprint's eval harness (called once per gold item, in a loop)
and **Sprint 6's future anti-hallucination guardrail** (which will call the
same function once per generated answer, at production latency, right after
`generate_from_chunks` returns) — no separate hand-rolled "for the
guardrail" version exists or should be built.

It wraps RAGAS's `Faithfulness` metric via
`Faithfulness.single_turn_score(SingleTurnSample(...))`, RAGAS's supported
non-batch entry point (no `Dataset`/`evaluate()` call needed), through
`LangchainLLMWrapper(langchain_litellm.ChatLiteLLM(...))` — not
`ragas.llms.llm_factory`, whose `provider="litellm"` path returns an
`InstructorLLM` that these legacy prompt-based metrics cannot use (confirmed
empirically: raises `AttributeError` on `.agenerate_prompt`).

Measured latency against the local Mistral judge: ~8-9s per single
faithfulness check (two internal LLM calls — claim extraction, then
per-claim entailment) — acceptable for a per-answer guardrail check, not
sub-second.

## Sprint 6 handoff

`build_judge_llm` sets `num_ctx=8192` for an Ollama-served judge model
(`JUDGE_NUM_CTX`) — a default Ollama context window (2048-4096) was found to
truncate RAGAS's judging prompt on this project's real multi-chunk contexts,
producing free-text instead of JSON (`RagasOutputParserException` even after
RAGAS's own retry; observed on `eval/scripts/run_ragas_eval.py`'s
`end_to_end` mode, 5 chunks).

The guardrail's natural call pattern — `generate_from_chunks` immediately
followed by `check_faithfulness` on that answer — means generation and
judging alternate on the same local Ollama server; if they request
different `num_ctx` values, Ollama reloads the ~5.5GB model between every
call (tens of seconds each, confirmed empirically). `generate_from_chunks`
now accepts `**extra_params` forwarded to `litellm.completion` for exactly
this: Sprint 6 should call it with the same `num_ctx`
(`src.generation.faithfulness.JUDGE_NUM_CTX`) it passes the judge, the way
`eval/scripts/run_ragas_eval.py`'s `generation_extra_params()` already
does — not rediscover this from scratch.

Sprint 6 should import `check_faithfulness` directly rather than
reimplementing it; `judge_chunks` and the guardrail's own decision layer
(structural citation check, confidence-based refusal) remain out of scope
here, as before.
