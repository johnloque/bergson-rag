#!/usr/bin/env python3
"""Runs one prompt candidate (a variant, an ad hoc override, or the committed
defaults) for later side-by-side comparison (feat/prompt-comparison,
docs/prompts.md "Comparing prompt variants"). Evaluation tooling only: the
API and the default code path never see an override.

Two modes, derived from the overridden files (`eval/scripts/prompt_variants.py`):

- **judge** (faithfulness/ files): the answers are fixed, never regenerated:
  `eval/calibration_set.json`, and each candidate judge scores them. The
  committed defaults are run through the same procedure (`--mode judge`).
- **generation** (generation/answer.md): generation-only path (gold chunks,
  retrieval bypassed), same models, temperature 0, hosted fallback disabled;
  answers are judged with the committed faithfulness prompts, which must be
  the frozen judge (`eval/frozen_judge.json`) unless
  `--allow-unfrozen-judge`, which stamps the header.

Every (item, repeat) is checkpointed (`eval/scripts/checkpoint.py`) under a
fingerprint of the run's configuration, so an interrupted run resumes and
two candidates never share entries.

Usage:
  python -m eval.scripts.run_prompt_comparison --variant <name> [--repeat 3]
  python -m eval.scripts.run_prompt_comparison --mode judge          # defaults
  python -m eval.scripts.run_prompt_comparison --prompt generation.answer=path.md
  [--items Q001,Q004]  (judge mode: ids or source items, e.g. Q004 = Q004 + its
  perturbed/generated copies)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.scripts.calibration_set import (
    CALIBRATION_SET_PATH,
    calibration_set_hash,
    calibration_texts,
    held_out_overlaps,
    load_calibration_set,
    load_chunk_texts,
    resolve_chunk_texts,
)
from eval.scripts.checkpoint import append_checkpoint, load_checkpoint
from eval.scripts.judge_selection import is_nan, item_mean, rows_by_item, summarize
from eval.scripts.prompt_results import (
    DEFAULT_CHECKPOINT_PATH,
    NOT_FROZEN,
    RESULTS_DIR,
    exploratory_banner,
    frozen_judge_status,
    git_info,
    result_paths,
    write_result,
)
from eval.scripts.prompt_variants import (
    MODES,
    VARIANTS_DIR,
    PromptOverrides,
    VariantError,
    resolve,
)
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR

DEFAULT_REPEAT = 3
DEFAULT_MODEL = "ollama_chat/mistral"  # src.generation.generate.DEFAULT_MODEL, without its import
TEMPERATURE = 0.0
GENERATION_RETRIEVAL = (
    "bypassed: gold chunks (paragraph_ids resolved via src.paragraph_chunk_map, read from Qdrant)"
)
JUDGE_RETRIEVAL = "none: fixed answers judged against their calibration-set chunks"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--variant", help="eval/prompt_variants/<name>")
    parser.add_argument(
        "--prompt",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Ad hoc body override, repeatable; the header says 'ad hoc'.",
    )
    parser.add_argument("--mode", choices=MODES, help="Required only to run the defaults.")
    parser.add_argument("--items", help="Comma-separated item ids (default: all).")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    parser.add_argument("--judge-model", default=DEFAULT_MODEL)
    parser.add_argument("--generation-model", default=DEFAULT_MODEL)
    parser.add_argument("--allow-unfrozen-judge", action="store_true")
    parser.add_argument("--calibration-set", type=Path, default=CALIBRATION_SET_PATH)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--variants-dir", type=Path, default=VARIANTS_DIR)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT_PATH)
    parser.add_argument("--fresh", action="store_true", help="Ignore checkpointed rows.")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    return args


def fingerprint(config: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def select_items(items: Sequence[dict], wanted: str | None) -> list[dict]:
    """`wanted` ids match an item's own id or its source item."""
    if not wanted:
        return list(items)
    ids = {part.strip() for part in wanted.split(",") if part.strip()}
    selected = [i for i in items if i["id"] in ids or i.get("source_item") in ids]
    unknown = ids - {i["id"] for i in selected} - {i.get("source_item") for i in selected}
    if unknown:
        raise VariantError(f"--items: unknown item id(s) {sorted(unknown)}")
    return selected


def faithfulness_row(result: Any) -> dict[str, Any]:
    """The serializable part of a `FaithfulnessResult`."""
    score = None if math.isnan(result.score) else result.score
    return {
        "score": score,
        "error": None,
        "claims": [
            {
                "statement": c.statement,
                "supported": c.supported,
                "reason": c.reason,
                "segment_id": c.segment_id,
            }
            for c in result.claims
        ],
        "segments": [{"id": s.id, "start": s.start, "end": s.end} for s in result.segments],
        "unevaluated_claims": sum(c.supported is None for c in result.claims),
    }


def failed_row(error: BaseException) -> dict[str, Any]:
    message = f"{type(error).__name__}: {str(error)[:300]}"
    return {"score": None, "error": message, "claims": [], "segments": [], "unevaluated_claims": 0}


def run_items(
    items: Sequence[Mapping[str, Any]],
    repeat: int,
    run_fingerprint: str,
    compute: Callable[[Mapping[str, Any], int], dict[str, Any]],
    checkpoint: dict[str, dict],
    checkpoint_path: Path | None,
) -> list[dict[str, Any]]:
    """`compute(item, repeat)` for every (item, repeat) not already in
    `checkpoint`; each new row is checkpointed as soon as it exists."""
    rows = []
    for item in items:
        for r in range(1, repeat + 1):
            key = f"{run_fingerprint}:{item['id']}:r{r}"
            if key in checkpoint:
                rows.append(checkpoint[key])
                continue
            print(f"  {item['id']} run {r}/{repeat}", flush=True)
            row = {"key": key, "item_id": item["id"], "repeat": r, **compute(item, r)}
            if row["error"]:
                print(f"WARNING: {item['id']} run {r}: {row['error']} (recorded as nan)")
            if checkpoint_path is not None:
                append_checkpoint(checkpoint_path, row)
            checkpoint[key] = row
            rows.append(row)
    return rows


def base_header(
    overrides: PromptOverrides, args: argparse.Namespace, items: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    per_origin: dict[str, int] = {}
    for item in items:
        origin = item.get("origin", "gold")
        per_origin[origin] = per_origin.get(origin, 0) + 1
    variant = overrides.variant
    return {
        "banner": exploratory_banner(len(items)),
        "mode": overrides.mode,
        "source": {
            "kind": overrides.kind,
            "label": "ad hoc" if overrides.kind == "ad hoc" else overrides.label,
            "variant": None
            if variant is None
            else {
                "name": variant.name,
                "status": variant.status,
                "hypothesis": variant.hypothesis,
                "based_on": variant.based_on,
            },
            "ad_hoc_paths": overrides.ad_hoc_paths,
        },
        "overridden_prompts": list(overrides.overridden),
        "manifest": overrides.manifest(),
        "stale": list(overrides.stale),
        "models": {
            "judge": args.judge_model,
            "generation": args.generation_model if overrides.mode == "generation" else None,
        },
        "temperature": {
            "judge": TEMPERATURE,
            "generation": TEMPERATURE if overrides.mode == "generation" else None,
        },
        "retrieval": GENERATION_RETRIEVAL if overrides.mode == "generation" else JUDGE_RETRIEVAL,
        "items": {
            "count": len(items),
            "ids": [item["id"] for item in items],
            "per_origin": per_origin,
        },
        "repeat": args.repeat,
        "git": git_info(),
    }


def run_judge_mode(
    overrides: PromptOverrides, args: argparse.Namespace
) -> tuple[dict[str, Any], list[dict], dict]:
    from src.generation.faithfulness import (
        build_faithfulness_prompts,
        build_judge_llm,
        check_faithfulness,
    )
    from src.retrieval.hybrid import RetrievedChunk

    calibration = load_calibration_set(args.calibration_set)
    items = select_items(calibration["items"], args.items)
    all_chunk_texts = load_chunk_texts(args.chunks_dir)
    texts = {item["id"]: resolve_chunk_texts(item, all_chunk_texts) for item in items}
    try:
        prompts = build_faithfulness_prompts(
            overrides.prompts["faithfulness.segment_claims"],
            overrides.prompts["faithfulness.nli_verifier"],
        )
    except Exception as error:  # an invalid examples file in the variant
        raise VariantError(str(error)) from None
    examples = [p for prompt in prompts.sources for p in prompt.examples_paths]
    overlaps = held_out_overlaps(calibration_texts(calibration, all_chunk_texts), examples)

    header = base_header(overrides, args, items)
    header["items"]["calibration_set_sha256"] = calibration_set_hash(calibration)
    header["items"]["calibration_set"] = str(args.calibration_set)
    header["frozen_judge"] = {
        "matches": None,
        "status": "n/a (judge mode: this run is a candidate)",
    }
    header["held_out_check"] = {
        "examples_files": [str(p) for p in examples],
        "overlaps": overlaps,
    }
    if overlaps:
        print(f"WARNING: held-out check: calibration text found in judge examples: {overlaps}")

    judge_llm = build_judge_llm(args.judge_model)

    def compute(item: Mapping[str, Any], _: int) -> dict[str, Any]:
        chunks = [
            RetrievedChunk(
                score=1.0,
                work_id=ref["chunk_id"].rsplit("_c", 1)[0],
                chunk_id=ref["chunk_id"],
                section_id="",
                section_path="",
                paragraph_ids=[],
                page_start={},
                page_end={},
                text=text,
            )
            for ref, text in zip(item["chunks"], texts[item["id"]], strict=True)
        ]
        try:
            result = check_faithfulness(
                item["query"],
                item["answer"],
                chunks,
                judge_llm=judge_llm,
                model=args.judge_model,
                prompts=prompts,
            )
        except Exception as error:  # parse failure after RAGAS's own retry, etc.
            return failed_row(error)
        return faithfulness_row(result)

    return header, items, {"compute": compute}


def run_generation_mode(
    overrides: PromptOverrides, args: argparse.Namespace
) -> tuple[dict[str, Any], list[dict], dict]:
    from qdrant_client import QdrantClient

    from eval.scripts.run_eval import GOLD_DATASET_PATH, load_gold_dataset
    from eval.scripts.run_ragas_eval import generation_extra_params, load_gold_chunks
    from src.generation.faithfulness import build_judge_llm, check_faithfulness
    from src.generation.generate import generate_from_chunks

    gold = load_gold_dataset(GOLD_DATASET_PATH, args.chunks_dir)
    by_id = {
        g.id: {
            "id": g.id,
            "origin": "gold",
            "label": "faithful",
            "category": g.category,
            "query": g.query,
            "chunk_ids": list(g.chunk_ids),
        }
        for g in gold
    }
    items = select_items(list(by_id.values()), args.items)
    header = base_header(overrides, args, items)
    header["fallback_model"] = "disabled (a silent switch to a hosted model would change models)"

    client = QdrantClient(url=args.qdrant_url)
    judge_llm = build_judge_llm(args.judge_model)
    answer_prompt = overrides.prompts["generation.answer"]
    extra = generation_extra_params(args.generation_model)

    def compute(item: Mapping[str, Any], _: int) -> dict[str, Any]:
        chunks = load_gold_chunks(client, tuple(item["chunk_ids"]))
        try:
            generated = generate_from_chunks(
                item["query"],
                chunks,
                client,
                model=args.generation_model,
                fallback_model="",
                temperature=TEMPERATURE,
                answer_prompt=answer_prompt,
                **extra,
            )
        except Exception as error:
            return {**failed_row(error), "answer": None, "num_chunks": len(chunks)}
        try:
            judged = faithfulness_row(
                check_faithfulness(
                    item["query"],
                    generated.answer,
                    chunks,
                    judge_llm=judge_llm,
                    model=args.judge_model,
                )
            )
        except Exception as error:
            judged = failed_row(error)
        return {
            **judged,
            "answer": generated.answer,
            "num_chunks": len(chunks),
            "prompts_used": generated.prompts_used,
        }

    return header, items, {"compute": compute}


def _fmt(value: float | None) -> str:
    return "nan" if is_nan(value) else f"{value:.3f}"


def render_report(result: Mapping[str, Any]) -> str:
    header, rows, summary = result["header"], result["rows"], result.get("summary")
    items = result["items"]
    grouped = rows_by_item(rows)
    source = header["source"]
    lines = [
        f"# Prompt comparison run: {header['mode']} mode, {source['label']}",
        "",
        f"> **{header['banner']}**",
        "",
    ]
    if header["stale"]:
        lines += [f"> **STALE VARIANT**: {'; '.join(header['stale'])}", ""]
    if header["frozen_judge"]["matches"] is False:
        lines += [f"> **{NOT_FROZEN}**: {header['frozen_judge']['status']}", ""]
    lines += [
        f"- **Created**: {header['created']}",
        f"- **Command**: `{header['command']}`",
        f"- **Source**: {source['kind']} `{source['label']}`"
        + (f" — hypothesis: {source['variant']['hypothesis']}" if source["variant"] else ""),
        f"- **Overridden prompts**: {', '.join(header['overridden_prompts']) or 'none (defaults)'}",
        f"- **Models**: judge `{header['models']['judge']}`"
        + (
            f", generation `{header['models']['generation']}`"
            if header["models"]["generation"]
            else ""
        )
        + f"; temperature {header['temperature']}",
        f"- **Retrieval**: {header['retrieval']}",
        f"- **Items**: {header['items']['count']} {header['items']['per_origin']}; "
        f"repeat {header['repeat']}",
        f"- **Git**: `{header['git']['commit']}` ({header['git']['branch']}), "
        f"dirty: {header['git']['dirty']}",
        f"- **Frozen judge**: {header['frozen_judge']['status']}",
    ]
    if "held_out_check" in header:
        overlaps = header["held_out_check"]["overlaps"]
        lines.append(
            f"- **Held-out check** (calibration text vs. judge examples): "
            f"{'OVERLAP ' + json.dumps(overlaps, ensure_ascii=False) if overlaps else 'no overlap'}"
        )
    lines += [
        "",
        "## Prompt manifest",
        "",
        "| prompt | version | hash | custom |",
        "|---|---|---|---|",
    ]
    for pid, entry in header["manifest"].items():
        if pid.startswith("library:"):
            lines.append(f"| {pid} | {entry['version']} | — | — |")
        else:
            lines.append(
                f"| {pid} | {entry['version']} | `{entry['hash'][:12]}` | {entry['custom']} |"
            )

    if summary:
        gate = summary["gate"]
        lines += [
            "",
            "## Gate (every hallucinated item flagged in every run)",
            "",
            f"**{'PASSED' if gate['passed'] else 'FAILED'}**"
            + (f" — missed: {', '.join(gate['missed'])}" if gate["missed"] else ""),
            "",
            "Rests on: "
            + ", ".join(f"{origin} {d}/{n}" for origin, (d, n) in gate["per_origin"].items())
            + ". Per perturbation type: "
            + (
                ", ".join(f"{t} {d}/{n}" for t, (d, n) in gate["per_perturbation_type"].items())
                or "none"
            )
            + ". Perturbed items are crude edits: catching them shows the judge catches "
            "blatant errors, not subtle ones.",
        ]
        for key, title, direction in (
            ("faithful_class", "Faithful class", "higher = fewer false flags"),
            ("hallucinated_class", "Hallucinated class", "lower is the correct direction"),
        ):
            block = summary[key]
            nan = ", ".join(f"run {r}: {n}/{t}" for r, (n, t) in block["nan_per_run"].items())
            lines += [
                "",
                f"## {title} ({direction}, never pooled)",
                "",
                f"Mean {_fmt(block['mean'])} over {block['n_items']} items; nan per run: {nan}",
            ]
        stab = summary["stability"]
        lines += ["", "## Stability over repeats", ""]
        if stab["measured"]:
            lines.append(
                f"Mean per-item score range {_fmt(stab['mean_range'])} (max "
                f"{_fmt(stab['max_range'])}); verdict flips {stab['flips']} of "
                f"{stab['matched_statements']} statements seen in 2+ runs; "
                f"{stab['unmatched_statements']} statements extracted in one run only."
            )
        else:
            lines.append("Not measured (--repeat 1).")
        flagged = summary["flagged_faithful_statements"]
        lines += ["", "## Statements flagged in faithful items (investigation leads)", ""]
        lines += [
            f"- {f['item_id']} run {f['repeat']}: {f['statement']} — {f['reason']}" for f in flagged
        ] or ["None."]

    lines += [
        "",
        "## Per item",
        "",
        "| id | origin | label | category | scores per run | mean | nan runs | claims | "
        "unsupported |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in items:
        runs = grouped.get(item["id"], [])
        lines.append(
            f"| {item['id']} | {item.get('origin', 'gold')} | {item.get('label', '')} | "
            f"{item.get('category', '')} | {' / '.join(_fmt(r['score']) for r in runs)} | "
            f"{_fmt(item_mean(runs))} | {sum(is_nan(r['score']) for r in runs)}/{len(runs)} | "
            f"{sum(len(r['claims']) for r in runs)} | "
            f"{sum(c['supported'] is False for r in runs for c in r['claims'])} |"
        )
    errors = [f"{r['item_id']} run {r['repeat']}: {r['error']}" for r in rows if r["error"]]
    lines += ["", "## Failures (recorded as nan, never dropped)", ""]
    lines += [f"- {e}" for e in errors] or ["None."]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        overrides = resolve(args.variant, args.prompt, args.mode, args.variants_dir)
    except VariantError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    for message in overrides.stale:
        print(f"WARNING: stale variant: {message}", file=sys.stderr)

    frozen: dict[str, Any] = {}
    if overrides.mode == "generation":
        matches, status = frozen_judge_status(args.judge_model)
        if not matches and not args.allow_unfrozen_judge:
            print(
                f"ERROR: generation mode needs a frozen judge matching the committed faithfulness "
                f"prompts: {status}. Freeze one (python -m eval.scripts.freeze_judge), or pass "
                "--allow-unfrozen-judge to run anyway with the header stamped "
                f"'{NOT_FROZEN}'.",
                file=sys.stderr,
            )
            return 2
        frozen = {"matches": matches, "status": status if matches else f"{NOT_FROZEN}: {status}"}

    try:
        runner = run_judge_mode if overrides.mode == "judge" else run_generation_mode
        header, items, run = runner(overrides, args)
    except (VariantError, FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if frozen:
        header["frozen_judge"] = frozen

    now = datetime.now(UTC)
    header["created"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    header["command"] = "python -m eval.scripts.run_prompt_comparison " + " ".join(
        sys.argv[1:] if argv is None else argv
    )
    run_fingerprint = fingerprint(
        {
            "mode": header["mode"],
            "manifest": header["manifest"],
            "models": header["models"],
            "temperature": header["temperature"],
            "items": header["items"]["ids"],
            "calibration": header["items"].get("calibration_set_sha256"),
        }
    )
    header["fingerprint"] = run_fingerprint
    checkpoint = {} if args.fresh else load_checkpoint(args.checkpoint)
    print(f"{header['banner']}\nRunning {header['mode']} mode, {header['source']['label']}:")
    rows = run_items(
        items, args.repeat, run_fingerprint, run["compute"], checkpoint, args.checkpoint
    )

    result: dict[str, Any] = {"header": header, "items": items, "rows": rows}
    if header["mode"] == "judge":
        result["summary"] = summarize(items, rows, args.repeat)
    json_path, md_path = result_paths(
        header["mode"],
        header["source"]["label"],
        len(items),
        now.strftime("%Y%m%dT%H%M%SZ"),
        args.output_dir,
    )
    write_result(json_path, result)
    md_path.write_text(render_report(json.loads(json_path.read_text())), encoding="utf-8")
    print(f"Wrote {json_path}\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
