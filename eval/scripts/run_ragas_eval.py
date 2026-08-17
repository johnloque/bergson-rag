#!/usr/bin/env python3
"""RAGAS generation evaluation against eval/gold_dataset.csv (docs/ROADMAP.md,
Sprint 5 — "preliminary end-to-end evaluation (RAGAS)"). Metrics: faithfulness
(src/generation/faithfulness.py — the same function Sprint 6's guardrail will
later call on a single generated answer), context precision, context recall
(`ragas.metrics.LLMContextPrecisionWithReference` / `LLMContextRecall`,
scored directly here — batch-only, no dual-purpose reuse requirement).

Two modes, reported separately, never merged into one number (same
discipline as this project's Test A/B generation split,
docs/generation_strategy.md):

- **generation_only**: `generate_from_chunks` called directly on each gold
  item's own `chunk_ids`, retrieval bypassed entirely. Isolates
  generation/faithfulness quality from retrieval quality.
- **end_to_end**: real `hybrid_search` + `rerank` + `generate_from_chunks`,
  reflecting actual production behavior including retrieval imperfection.

Judge LLM: local Mistral via Ollama by default (`ollama_chat/mistral`,
cost-free, docs/ROADMAP.md), any LiteLLM model string via `--judge-model`.
Generation LLM: same default and override mechanism, `--generation-model`.
Both are pinned to `temperature=0` for this script specifically — LLM
sampling is a new nondeterminism source this project hasn't had to handle
before (unlike the RRF tie-break fix, this one is sampling-based, not a
missing secondary sort key) — verified, not assumed, by `check_determinism`
below. Unlike this project's retrieval determinism checks (RRF fusion,
reranking — deterministic by construction, cheap to run twice in full), a
RAGAS-scored item costs several LLM round trips (generation + faithfulness'
own 2 internal calls + context precision + context recall), so a full
double-run over every item in both modes is not the same cost class —
confirmed impractically slow in practice (>1.5h for under 1.5 of 2 planned
passes before being interrupted). `check_determinism` therefore runs the
*full* gold set once (that pass's results are the ones reported below) and
re-runs only `--determinism-sample` items (default 2, both modes) a second
time, comparing the overlap exactly. A mismatch is reported as a finding,
not treated as a bug to fail the script over — LLM sampling determinism at
temperature=0 is a property of the model/runtime, not of this project's own
code.

`RAGAS_DO_NOT_TRACK` is forced on: RAGAS's usage-analytics POST has no route
to the internet in this project's normal (offline-capable, local-first) dev
setup, and failing/retrying that call on every single metric invocation was
adding real, measured latency — turned off outright rather than left as an
opt-in the next run forgets.

Every (mode, item) result is checkpointed to `--checkpoint` (JSONL,
fsync'd) as soon as it's computed: this script's own background process
was observed being killed mid-run by the host environment (unrelated to
this project's code), and a killed run should lose at most the one pair in
flight, not the whole pass — re-running the same command resumes instead of
restarting. `--fresh` ignores an existing checkpoint.

Usage: python3 -m eval.scripts.run_ragas_eval [--evidence-limit 5]
    [--judge-model ollama_chat/mistral] [--generation-model ollama_chat/mistral]
Requires Qdrant running with the built index (scripts/build_index.py) and a
reachable LLM for both generation and judging (Ollama running locally with
the default model pulled, or MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL —
see docs/generation_strategy.md).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import litellm
from qdrant_client import QdrantClient
from ragas.dataset_schema import SingleTurnSample
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall

from eval.scripts.metrics import BREAKDOWN_ATTRS, GoldItem
from eval.scripts.run_eval import GOLD_DATASET_PATH, QDRANT_URL, print_gold_dataset_status
from src.generation.faithfulness import (
    DEFAULT_JUDGE_MODEL,
    JUDGE_NUM_CTX,
    build_judge_llm,
    check_faithfulness,
)
from src.generation.generate import DEFAULT_MODEL, generate_from_chunks
from src.generation.signals import GenerationChunk
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME, PAYLOAD_FIELDS, point_id_for
from src.retrieval.hybrid import RetrievedChunk, hybrid_search
from src.retrieval.reranking import DEFAULT_RERANK_CANDIDATES, CrossEncoderReranker, rerank

# Read dynamically by ragas on every tracked call (not cached at import), so
# setting it here — before any metric actually runs — is sufficient even
# though it comes after the ragas import above. See module docstring.
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "True")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "eval" / "results"
DEFAULT_CHECKPOINT_PATH = RESULTS_DIR / "ragas_checkpoint.jsonl"

# Mirrors scripts/query_pipeline.py's DEFAULT_LIMIT — the number of reranked
# chunks actually handed to the LLM as evidence in a real query, so
# end_to_end mode reflects the same evidence size a user would get.
DEFAULT_EVIDENCE_LIMIT = 5

# Eval runs need reproducible generation to score reproducibly — greedy
# decoding regardless of what a caller not doing determinism-sensitive
# scoring might otherwise want (see generate_from_chunks' own docstring).
GENERATION_TEMPERATURE = 0.0

_OLLAMA_PROVIDERS = ("ollama", "ollama_chat")


def generation_extra_params(generation_model: str) -> dict:
    """Extra `generate_from_chunks` kwargs for `generation_model` — matches
    the judge's `num_ctx` (`src/generation/faithfulness.py`) when generation
    is also Ollama-served, so a single item's generate-then-judge calls
    never disagree on context-window size (see generate_from_chunks'
    docstring for why a mismatch is expensive, not just imprecise)."""
    _, provider, _, _ = litellm.get_llm_provider(generation_model)
    return {"num_ctx": JUDGE_NUM_CTX} if provider in _OLLAMA_PROVIDERS else {}


# Items (both modes) re-run a second time to check determinism, out of the
# full gold set — see module docstring for why this is a bounded sample
# rather than a full second pass.
DEFAULT_DETERMINISM_SAMPLE = 2

MODES = ("generation_only", "end_to_end")
MODE_LABELS = {
    "generation_only": "generation-only (gold chunk_ids, retrieval bypassed)",
    "end_to_end": "end-to-end (hybrid retrieval + rerank + generate)",
}

ANSWER_PREVIEW_LEN = 80
QUERY_PREVIEW_LEN = 60


def git_info() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            return "unknown"

    dirty = bool(run("status", "--porcelain"))
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": "yes (uncommitted changes present)" if dirty else "no",
    }


def load_gold_chunks(client: QdrantClient, chunk_ids: tuple[str, ...]) -> list[RetrievedChunk]:
    """Gold `chunk_ids` read straight from Qdrant, in the given order,
    bypassing retrieval entirely (generation_only mode). `score` is a
    placeholder (1.0) — nothing here comes from a real ranking."""
    if not chunk_ids:
        return []
    points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id_for(chunk_id) for chunk_id in chunk_ids],
        with_payload=True,
    )
    by_chunk_id = {(p.payload or {})["chunk_id"]: p.payload or {} for p in points}
    missing = [c for c in chunk_ids if c not in by_chunk_id]
    if missing:
        print(f"WARNING: gold chunk_id(s) not found in index: {missing}", file=sys.stderr)
    return [
        RetrievedChunk(score=1.0, **{field: by_chunk_id[c][field] for field in PAYLOAD_FIELDS})
        for c in chunk_ids
        if c in by_chunk_id
    ]


def retrieve_end_to_end(
    client: QdrantClient,
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    reranker: CrossEncoderReranker,
    query: str,
    evidence_limit: int,
    rerank_candidates: int,
) -> Sequence[GenerationChunk]:
    candidates = hybrid_search(
        client, query, dense_embedder, sparse_embedder, limit=max(evidence_limit, rerank_candidates)
    )
    return rerank(query, candidates, reranker)[:evidence_limit]


@dataclass(frozen=True)
class GenerationOutcome:
    item: GoldItem
    mode: str
    num_chunks: int
    answer: str
    faithfulness: float
    context_precision: float
    context_recall: float


def _checkpoint_key(mode: str, item_id: str) -> str:
    return f"{mode}:{item_id}"


def load_checkpoint(path: Path) -> dict[str, dict]:
    """Rows keyed by `mode:item_id` (or an explicit `key` field — used to
    namespace the determinism rerun's own checkpoint entries, see
    `check_determinism`, distinct from the full run's entries for the same
    `mode`/`item_id`), so a killed/resumed run (`run_both_modes` below) can
    skip whatever was already computed and persisted rather than
    recomputing it — real environment behavior observed running this
    script (background process killed mid-run repeatedly, unrelated to
    this project's own code), not a hypothetical concern."""
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("key") or _checkpoint_key(row["mode"], row["item_id"])
            rows[key] = row
    return rows


def append_checkpoint(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _outcome_to_row(outcome: GenerationOutcome, key: str) -> dict:
    return {
        "key": key,
        "mode": outcome.mode,
        "item_id": outcome.item.id,
        "num_chunks": outcome.num_chunks,
        "answer": outcome.answer,
        "faithfulness": outcome.faithfulness,
        "context_precision": outcome.context_precision,
        "context_recall": outcome.context_recall,
    }


def _row_to_outcome(row: dict, items_by_id: dict[str, GoldItem]) -> GenerationOutcome:
    return GenerationOutcome(
        item=items_by_id[row["item_id"]],
        mode=row["mode"],
        num_chunks=row["num_chunks"],
        answer=row["answer"],
        faithfulness=row["faithfulness"],
        context_precision=row["context_precision"],
        context_recall=row["context_recall"],
    )


def _safe_score(label: str, mode: str, item_id: str, failures: list[str], fn) -> float:
    """RAGAS's own structured-output retry (fix_output_format_prompt) does
    not always recover: a small local judge model (7B, this project's
    cost-free default) occasionally answers a judging prompt with free-text
    prose instead of the requested JSON, especially on end_to_end mode's
    longer, multi-chunk contexts — observed empirically, not hypothetical
    (RagasOutputParserException after RAGAS's internal retries are
    exhausted). One item's parse failure must not crash the whole batch:
    recorded as NaN and logged, same discipline as RAGAS's own NaN-on-no-
    statements case, and surfaced in the report rather than hidden."""
    try:
        return fn()
    except Exception as exc:
        note = f"{mode}/{item_id}/{label}: {type(exc).__name__}"
        print(f"WARNING: {note} — judge output failed to parse, recording NaN.", file=sys.stderr)
        failures.append(note)
        return float("nan")


def score_outcome(
    client: QdrantClient,
    item: GoldItem,
    mode: str,
    chunks: Sequence[GenerationChunk],
    generation_model: str,
    judge_llm: LangchainLLMWrapper,
    judge_model: str,
    failures: list[str],
) -> GenerationOutcome | None:
    if not chunks:
        print(f"WARNING: {mode}/{item.id}: no evidence chunks — skipping.", file=sys.stderr)
        return None

    result = generate_from_chunks(
        item.query,
        chunks,
        client,
        model=generation_model,
        temperature=GENERATION_TEMPERATURE,
        **generation_extra_params(generation_model),
    )
    faithfulness = _safe_score(
        "faithfulness",
        mode,
        item.id,
        failures,
        lambda: check_faithfulness(
            item.query, result.answer, chunks, judge_llm=judge_llm, model=judge_model
        ).score,
    )
    sample = SingleTurnSample(
        user_input=item.query,
        response=result.answer,
        retrieved_contexts=[chunk.text for chunk in chunks],
        reference=item.expected_anwser,
    )
    precision = _safe_score(
        "context_precision",
        mode,
        item.id,
        failures,
        lambda: LLMContextPrecisionWithReference(llm=judge_llm).single_turn_score(sample),
    )
    recall = _safe_score(
        "context_recall",
        mode,
        item.id,
        failures,
        lambda: LLMContextRecall(llm=judge_llm).single_turn_score(sample),
    )
    return GenerationOutcome(
        item=item,
        mode=mode,
        num_chunks=len(chunks),
        answer=result.answer,
        faithfulness=faithfulness,
        context_precision=precision,
        context_recall=recall,
    )


def run_both_modes(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    reranker: CrossEncoderReranker,
    judge_llm: LangchainLLMWrapper,
    generation_model: str,
    judge_model: str,
    evidence_limit: int,
    rerank_candidates: int,
    failures: list[str],
    checkpoint: dict[str, dict] | None = None,
    checkpoint_path: Path | None = None,
    checkpoint_key_prefix: str = "",
) -> dict[str, list[GenerationOutcome]]:
    """`checkpoint`/`checkpoint_path`: when given, each (mode, item) pair
    already present in `checkpoint` is reused as-is (no LLM calls at all —
    not even retrieval for end_to_end, since the point is to skip the
    expensive work) instead of recomputed, and every freshly computed pair
    is appended to `checkpoint_path` immediately (fsync'd) so a kill mid-run
    loses at most the one (mode, item) pair in flight, not the whole run.
    `checkpoint_key_prefix` namespaces the checkpoint keys used for lookup
    and storage (not the `mode` value on the outcome itself) — used by
    `check_determinism` so its rerun pass gets its own checkpoint entries,
    distinct from the full run's entries for the same (mode, item)."""
    items_by_id = {item.id: item for item in items}
    results: dict[str, list[GenerationOutcome]] = {mode: [] for mode in MODES}
    for item in items:
        for mode in MODES:
            key = _checkpoint_key(checkpoint_key_prefix + mode, item.id)
            if checkpoint is not None and key in checkpoint:
                results[mode].append(_row_to_outcome(checkpoint[key], items_by_id))
                continue

            chunks = (
                load_gold_chunks(client, item.chunk_ids)
                if mode == "generation_only"
                else retrieve_end_to_end(
                    client,
                    dense_embedder,
                    sparse_embedder,
                    reranker,
                    item.query,
                    evidence_limit,
                    rerank_candidates,
                )
            )
            outcome = score_outcome(
                client, item, mode, chunks, generation_model, judge_llm, judge_model, failures
            )
            if outcome is None:
                continue
            results[mode].append(outcome)
            if checkpoint_path is not None:
                row = _outcome_to_row(outcome, key)
                append_checkpoint(checkpoint_path, row)
                if checkpoint is not None:
                    checkpoint[key] = row
    return results


def _floats_match(a: float, b: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) < 1e-9


def outcomes_match(a: GenerationOutcome, b: GenerationOutcome) -> bool:
    return (
        a.answer == b.answer
        and _floats_match(a.faithfulness, b.faithfulness)
        and _floats_match(a.context_precision, b.context_precision)
        and _floats_match(a.context_recall, b.context_recall)
    )


def check_determinism(
    client: QdrantClient,
    items: list[GoldItem],
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    reranker: CrossEncoderReranker,
    judge_llm: LangchainLLMWrapper,
    generation_model: str,
    judge_model: str,
    evidence_limit: int,
    rerank_candidates: int,
    determinism_sample: int,
    checkpoint: dict[str, dict] | None = None,
    checkpoint_path: Path | None = None,
) -> tuple[dict[str, list[GenerationOutcome]], list[str], list[str], int]:
    """Runs both modes once over the *full* gold set (checkpointed — see
    `run_both_modes` — so items already computed in a prior, interrupted
    invocation are reused, not redone) — that pass's results are the ones
    reported below — then re-runs only the first `determinism_sample` items
    (both modes) a second time and compares the overlap exactly (generated
    answer text and every RAGAS score). The rerun is checkpointed too, under
    a `"rerun:"`-prefixed key so it never collides with or gets satisfied by
    the full run's own entries for the same (mode, item) — it must be an
    independent computation to mean anything as a determinism check, but a
    kill mid-rerun (observed happening in this environment even for this
    small a sample) should still not force starting the rerun itself over
    from nothing. See module docstring for why this is a bounded sample
    rather than a second full pass. Returns (results, mismatches, judge-
    parse-failure notes from the full run, number of (mode, item) pairs
    actually checked). A mismatch does NOT abort the script: LLM sampling
    determinism at temperature=0 is a property of the model/runtime, not of
    this project's own code, so it's reported as a finding either way."""
    print(f"=== Full run over n={len(items)} (both modes) ===")
    failures: list[str] = []
    full = run_both_modes(
        client,
        items,
        dense_embedder,
        sparse_embedder,
        reranker,
        judge_llm,
        generation_model,
        judge_model,
        evidence_limit,
        rerank_candidates,
        failures,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
    )

    sample_items = items[:determinism_sample]
    print(
        f"=== Determinism check: re-running {len(sample_items)} item(s) "
        f"({[i.id for i in sample_items]}), both modes, compared against the full run ==="
    )
    rerun_failures: list[str] = []
    rerun = run_both_modes(
        client,
        sample_items,
        dense_embedder,
        sparse_embedder,
        reranker,
        judge_llm,
        generation_model,
        judge_model,
        evidence_limit,
        rerank_candidates,
        rerun_failures,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        checkpoint_key_prefix="rerun:",
    )

    mismatches = []
    checked = 0
    for mode in MODES:
        full_by_id = {o.item.id: o for o in full[mode]}
        rerun_by_id = {o.item.id: o for o in rerun[mode]}
        for item_id, outcome in rerun_by_id.items():
            checked += 1
            other = full_by_id.get(item_id)
            if other is None or not outcomes_match(outcome, other):
                mismatches.append(f"{mode}/{item_id}")

    if mismatches:
        print(f"MISMATCHES (rerun vs. full run): {mismatches}")
    else:
        print(f"OK — {checked} (mode, item) pair(s) checked, identical answers and scores.\n")
    if failures or rerun_failures:
        print(f"Judge parse failures — full run: {failures}  determinism rerun: {rerun_failures}")
    return full, mismatches, failures, checked


def mean_ignore_nan(values: list[float]) -> float:
    finite = [v for v in values if not math.isnan(v)]
    return sum(finite) / len(finite) if finite else float("nan")


def aggregate_ragas(outcomes: list[GenerationOutcome]) -> dict:
    return {
        "faithfulness": mean_ignore_nan([o.faithfulness for o in outcomes]),
        "context_precision": mean_ignore_nan([o.context_precision for o in outcomes]),
        "context_recall": mean_ignore_nan([o.context_recall for o in outcomes]),
        "n": len(outcomes),
    }


def breakdown_ragas_by(outcomes: list[GenerationOutcome], attr: str) -> dict[str, dict]:
    groups: dict[str, list[GenerationOutcome]] = {}
    for outcome in outcomes:
        groups.setdefault(getattr(outcome.item, attr), []).append(outcome)
    return {value: aggregate_ragas(group) for value, group in sorted(groups.items())}


def _fmt(value: float) -> str:
    return "nan" if math.isnan(value) else f"{value:.3f}"


def render_aggregate_table(results: dict[str, list[GenerationOutcome]]) -> str:
    headers = ["mode", "faithfulness", "context_precision", "context_recall", "n"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for mode in MODES:
        metrics = aggregate_ragas(results[mode])
        cells = [
            MODE_LABELS[mode],
            _fmt(metrics["faithfulness"]),
            _fmt(metrics["context_precision"]),
            _fmt(metrics["context_recall"]),
            str(metrics["n"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_breakdown_table(attr: str, results: dict[str, list[GenerationOutcome]]) -> str:
    per_mode = {mode: breakdown_ragas_by(results[mode], attr) for mode in MODES}
    values = sorted({value for bd in per_mode.values() for value in bd})

    headers = [attr, "mode", "faithfulness", "context_precision", "context_recall", "n"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for value in values:
        for mode in MODES:
            metrics = per_mode[mode].get(value)
            if metrics is None:
                continue
            cells = [
                value,
                MODE_LABELS[mode],
                _fmt(metrics["faithfulness"]),
                _fmt(metrics["context_precision"]),
                _fmt(metrics["context_recall"]),
                str(metrics["n"]),
            ]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_per_item_table(outcomes: list[GenerationOutcome]) -> str:
    headers = [
        "id",
        "query",
        "n_chunks",
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for outcome in outcomes:
        query_preview = outcome.item.query
        if len(query_preview) > QUERY_PREVIEW_LEN:
            query_preview = query_preview[:QUERY_PREVIEW_LEN].rstrip() + "…"
        answer_preview = outcome.answer.replace("\n", " ")
        if len(answer_preview) > ANSWER_PREVIEW_LEN:
            answer_preview = answer_preview[:ANSWER_PREVIEW_LEN].rstrip() + "…"
        cells = [
            outcome.item.id,
            query_preview.replace("|", "\\|"),
            str(outcome.num_chunks),
            _fmt(outcome.faithfulness),
            _fmt(outcome.context_precision),
            _fmt(outcome.context_recall),
            answer_preview.replace("|", "\\|"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(
    items: list[GoldItem],
    results: dict[str, list[GenerationOutcome]],
    mismatches: list[str],
    determinism_checked: int,
    judge_failures: list[str],
    generation_model: str,
    judge_model: str,
    evidence_limit: int,
    rerank_candidates: int,
    timestamp: str,
    git: dict[str, str],
) -> str:
    n = len(items)
    exploratory_banner = (
        f"> **EXPLORATORY — NOT STATISTICALLY MEANINGFUL AT n={n}.** "
        f"docs/gold_dataset_protocol.md targets n=50 (this project's own "
        "established threshold for treating a result as decision-grade, "
        "same discipline as every other small-n eval report here); this is "
        "a small-sample pass only, reported honestly rather than withheld."
    )

    determinism_scope_note = (
        f"Checked on a bounded sample ({determinism_checked} of {len(MODES) * n} (mode, item) "
        f"pairs, not a full second pass — see `eval/scripts/run_ragas_eval.py`'s module "
        "docstring: a full double-run over every item in both modes was measured "
        "impractically slow (>1.5h for under 1.5 of 2 planned passes before being "
        "interrupted)."
    )
    if mismatches:
        determinism_section = (
            f"**MISMATCH** — {len(mismatches)} of {determinism_checked} checked (mode, item) "
            f"pairs differed from the full run (generated answer text and/or a RAGAS score): "
            f"{', '.join(mismatches)}. Both `generate_from_chunks` and the RAGAS judge calls "
            f"were pinned to `temperature=0`; this means greedy decoding at temperature=0 is "
            "not bit-reproducible for this model/runtime combination on this machine, not a "
            f"bug in this project's own code — reported as a finding, not silently assumed "
            f"away. {determinism_scope_note}"
        )
    else:
        determinism_section = (
            f"OK — {determinism_checked} checked (mode, item) pair(s), identical generated "
            "answers and identical RAGAS scores (faithfulness, context precision, context "
            f"recall) between the rerun and the full run, at `temperature=0`. "
            f"{determinism_scope_note}"
        )

    if judge_failures:
        judge_failures_section = (
            f"\n**{len(judge_failures)} judge call(s) failed to parse and were recorded as "
            f"NaN** (excluded from the means above, not silently dropped): "
            f"{', '.join(judge_failures)}. Observed cause: the local 7B judge model "
            "occasionally answers a RAGAS judging prompt with free-text prose instead of "
            "the requested structured JSON, even after RAGAS's own internal "
            "fix-the-format retry — more likely on end_to_end mode's longer, "
            "multi-chunk contexts. A known characteristic of this project's "
            "cost-free default judge, not a bug in this evaluation.\n"
        )
    else:
        judge_failures_section = ""

    breakdown_sections = "\n\n".join(
        f"### By {attr}\n\n{render_breakdown_table(attr, results)}" for attr in BREAKDOWN_ATTRS
    )
    mode_sections = "\n\n".join(
        f"### {MODE_LABELS[mode]}\n\n{render_per_item_table(results[mode])}" for mode in MODES
    )

    return f"""# RAGAS generation evaluation — faithfulness, context precision, context recall

- **Generated**: {timestamp}
- **Git commit**: `{git['commit']}` (branch `{git['branch']}`)
- **Working tree had uncommitted changes at run time**: {git['dirty']}
- **Gold dataset**: `eval/gold_dataset.csv`, n={n}
- **Generation model**: `{generation_model}` (temperature=0 for this run)
- **Judge model**: `{judge_model}` (temperature=0)
- **End-to-end evidence limit**: top-{evidence_limit} reranked chunks \
(rerank candidate pool={rerank_candidates})
- **Command**: `python -m eval.scripts.run_ragas_eval \
--generation-model {generation_model} --judge-model {judge_model} \
--evidence-limit {evidence_limit} --rerank-candidates {rerank_candidates}`

This file's name and the metadata above identify this as a small-n pass —
compare the `n=` value here against any later re-run before treating results
as comparable.

{exploratory_banner}

## Determinism check

{determinism_section}
{judge_failures_section}
## Aggregate — generation-only vs. end-to-end (exploratory at n={n})

Reported separately per mode, never merged: generation-only isolates
generation/faithfulness quality from retrieval quality (a bad score here
means the prompt or model is at fault, not retrieval); end-to-end reflects
realistic production behavior, retrieval imperfection included.

{render_aggregate_table(results)}

{breakdown_sections}

## Per-item detail

{mode_sections}

## Metrics

- **faithfulness**: fraction of claims extracted from the generated answer
  that are entailed by the cited chunks (`src/generation/faithfulness.py`,
  RAGAS `Faithfulness`) — the same function Sprint 6's anti-hallucination
  guardrail will call on a single generated answer at production latency;
  no separate implementation exists for eval vs. guardrail use.
- **context_precision** (`ragas.metrics.LLMContextPrecisionWithReference`):
  of the retrieved/gold chunks actually used as evidence, the fraction
  judged relevant to `expected_anwser`.
- **context_recall** (`ragas.metrics.LLMContextRecall`): of the claims in
  `expected_anwser`, the fraction attributable to the retrieved/gold chunks
  used as evidence.

## Modes

- `generation_only`: `generate_from_chunks` called directly on each gold
  item's own `chunk_ids` (read straight from Qdrant, `load_gold_chunks`),
  retrieval bypassed entirely.
- `end_to_end`: `src/retrieval/hybrid.py` hybrid search (candidate pool =
  max(evidence_limit, rerank_candidates)) -> `src/retrieval/reranking.py`
  cross-encoder rerank -> top-{evidence_limit} -> `generate_from_chunks`,
  mirroring `scripts/query_pipeline.py`'s real pipeline.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-limit",
        type=int,
        default=DEFAULT_EVIDENCE_LIMIT,
        help=(
            "Reranked chunks passed to generation in end_to_end mode "
            f"(default: {DEFAULT_EVIDENCE_LIMIT})."
        ),
    )
    parser.add_argument(
        "--rerank-candidates",
        type=int,
        default=DEFAULT_RERANK_CANDIDATES,
        help=f"Candidate pool size passed to the reranker (default: {DEFAULT_RERANK_CANDIDATES}).",
    )
    parser.add_argument(
        "--determinism-sample",
        type=int,
        default=DEFAULT_DETERMINISM_SAMPLE,
        help=(
            "Number of gold items (both modes) re-run a second time to check "
            f"determinism (default: {DEFAULT_DETERMINISM_SAMPLE}) — see module docstring "
            "for why this is bounded rather than a full second pass."
        ),
    )
    parser.add_argument(
        "--generation-model",
        default=DEFAULT_MODEL,
        help=f"LiteLLM model string used for generation (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help=f"LiteLLM model string used as the RAGAS judge (default: {DEFAULT_JUDGE_MODEL}).",
    )
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .md path (default: eval/results/eval_ragas_n<N>_<timestamp>.md).",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_CHECKPOINT_PATH,
        help=(
            "Per-item results file (JSONL) — re-running this script re-uses any "
            "(mode, item) pair already present instead of recomputing it, so an "
            f"interrupted run can resume (default: {DEFAULT_CHECKPOINT_PATH})."
        ),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any existing --checkpoint file and recompute every item from scratch.",
    )
    args = parser.parse_args()

    items = print_gold_dataset_status(GOLD_DATASET_PATH)

    client = QdrantClient(url=args.qdrant_url)
    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()
    reranker = CrossEncoderReranker()
    judge_llm = build_judge_llm(args.judge_model)

    checkpoint = {} if args.fresh else load_checkpoint(args.checkpoint)
    if checkpoint:
        print(f"Resuming from checkpoint: {len(checkpoint)} (mode, item) pair(s) already done.")

    results, mismatches, judge_failures, determinism_checked = check_determinism(
        client,
        items,
        dense_embedder,
        sparse_embedder,
        reranker,
        judge_llm,
        args.generation_model,
        args.judge_model,
        args.evidence_limit,
        args.rerank_candidates,
        args.determinism_sample,
        checkpoint=checkpoint,
        checkpoint_path=args.checkpoint,
    )

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    git = git_info()

    report = render_report(
        items,
        results,
        mismatches,
        determinism_checked,
        judge_failures,
        args.generation_model,
        args.judge_model,
        args.evidence_limit,
        args.rerank_candidates,
        timestamp,
        git,
    )

    output_path = args.output
    if output_path is None:
        file_timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"eval_ragas_n{len(items)}_{file_timestamp}.md"

    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
