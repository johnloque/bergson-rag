#!/usr/bin/env python3
"""Judge baseline report, alone or against a variant, the way the baseline
itself was analysed (docs/prompts.md, "Judge baseline"): calls `summarize`,
`stability` and `noise_floor` directly instead of going through
`compare_prompt_results`.

Without `--variant`, it writes the baseline's own report: every number of
the "Judge baseline" section (gate with per-repeat detections of missed
items, class means and nan per class and repeat, flagged faithful
statements, stability per run and pooled, noise floor, per-item means per
run). Error messages, quoted reasons and the grouping of flagged
statements stay a manual reading of the result files.

With `--variant` it adds, over `compare_prompt_results`:
- the baseline's noise floor between its two runs (the CLI refuses two
  identical manifests), with its max/mean/zero counts;
- stability pooled over every run of a candidate (repeats renumbered, so 2
  runs x 3 repeats = 6), as reported for the baseline;
- the gate side by side: items newly caught, newly missed, still missed;
- the variant's own noise floor when it was run twice too.

Deltas are variant run 1 - baseline run 1 per item, marked against the
baseline floor (as the CLI does). This tooling never picks a winner.

Usage: python -m eval.scripts.judge_variant_report \\
           [--baseline BASE_RUN1.json BASE_RUN2.json] \\
           [--variant VAR_RUN1.json [VAR_RUN2.json]] [--force] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.scripts.compare_prompt_results import (
    comparability_problems,
    differing_units,
    noise_floor,
    noise_marker,
)
from eval.scripts.judge_selection import (
    FAITHFUL,
    HALLUCINATED,
    Axes,
    _statement_key,
    dominance,
    is_nan,
    item_mean,
    rows_by_item,
    stability,
    summarize,
)
from eval.scripts.prompt_results import (
    NOT_COMPARABLE,
    RESULTS_DIR,
    exploratory_banner,
    load_result,
    write_result,
)

BASELINE_RUNS = (
    RESULTS_DIR / "prompt_cmp_judge_default_n26_20261008T124431Z.json",
    RESULTS_DIR / "prompt_cmp_judge_default_n26_20261008T141004Z.json",
)


def pooled(results: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Rows of every run, repeats renumbered run after run, and the total
    repeat count: run k's repeat r becomes (k - 1) * R + r."""
    repeat = results[0]["header"]["repeat"]
    if any(r["header"]["repeat"] != repeat for r in results):
        raise ValueError("runs of one candidate must share --repeat to be pooled")
    rows = [
        {**row, "repeat": k * repeat + row["repeat"]}
        for k, result in enumerate(results)
        for row in result["rows"]
    ]
    return rows, repeat * len(results)


def floor_stats(floor: Mapping[str, float]) -> dict[str, Any]:
    finite = {k: v for k, v in floor.items() if not math.isnan(v)}
    return {
        "zero": sum(v == 0 for v in finite.values()),
        "nonzero": {k: v for k, v in finite.items() if v != 0},
        "nan": sorted(k for k, v in floor.items() if math.isnan(v)),
        "max": max(finite.values()) if finite else float("nan"),
        "mean": sum(finite.values()) / len(finite) if finite else float("nan"),
        "n_finite": len(finite),
        "per_item": dict(floor),
    }


def candidate(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-run summaries, pooled stability and (with 2 runs) the noise floor."""
    items = results[0]["items"]
    rows, total = pooled(results)
    pooled_stab = stability(rows, total)
    runs = [summarize(items, r["rows"], r["header"]["repeat"]) for r in results]
    missed = sorted({i for run in runs for i in run["gate"]["missed"]})
    flagged = {
        (f["item_id"], _statement_key(f["statement"]))
        for run in runs
        for f in run["flagged_faithful_statements"]
    }
    return {
        "label": results[0]["header"]["source"]["label"],
        "runs": runs,
        # missed item -> per run, per repeat: flagged or not
        "missed_detections": {i: [run["gate"]["detections"][i] for run in runs] for i in missed},
        "distinct_flagged_faithful": {
            "statements": len(flagged),
            "items": sorted({item_id for item_id, _ in flagged}),
        },
        "item_means": {
            item["id"]: [item_mean(rows_by_item(r["rows"]).get(item["id"], [])) for r in results]
            for item in items
        },
        "item_nan_runs": {
            item["id"]: [
                [sum(is_nan(row["score"]) for row in group), len(group)]
                for r in results
                for group in [rows_by_item(r["rows"]).get(item["id"], [])]
            ]
            for item in items
        },
        "nan_rows": [
            [sum(is_nan(row["score"]) for row in r["rows"]), len(r["rows"])] for r in results
        ],
        "pooled_stability": {
            "runs": len(results),
            "repeats": total,
            "mean_range": pooled_stab.mean_range,
            "max_range": pooled_stab.max_range,
            "flips": pooled_stab.flips,
            "matched_statements": pooled_stab.matched_statements,
            "unmatched_statements": pooled_stab.unmatched_statements,
            "flipped": [list(f) for f in pooled_stab.flipped],
        },
        "noise_floor": floor_stats(noise_floor(results[0], results[1]))
        if len(results) > 1
        else None,
    }


def gate_diff(base: Mapping[str, Any], var: Mapping[str, Any]) -> dict[str, list[str]]:
    """Over every run of each candidate: an item counts as missed if any run
    missed it."""
    base_missed = set(base["missed_detections"])
    var_missed = set(var["missed_detections"])
    return {
        "newly_caught": sorted(base_missed - var_missed),
        "newly_missed": sorted(var_missed - base_missed),
        "still_missed": sorted(base_missed & var_missed),
    }


def item_deltas(
    base: Mapping[str, Any], var: Mapping[str, Any], floor: Mapping[str, float]
) -> list[dict[str, Any]]:
    base_rows, var_rows = rows_by_item(base["rows"]), rows_by_item(var["rows"])
    out = []
    for item in base["items"]:
        b = item_mean(base_rows.get(item["id"], []))
        v = item_mean(var_rows.get(item["id"], []))
        delta = v - b
        out.append(
            {
                "id": item["id"],
                "label": item["label"],
                "origin": item.get("origin", "gold"),
                "baseline": b,
                "variant": v,
                "delta": delta,
                "noise_floor": floor.get(item["id"], float("nan")),
                "noise": noise_marker(delta, floor.get(item["id"], float("nan"))),
            }
        )
    return out


def _fmt(value: float | None) -> str:
    return "nan" if is_nan(value) else f"{value:.3f}"


def _tf(flags: Sequence[bool]) -> str:
    return "[" + ",".join("T" if f else "F" for f in flags) + "]"


def _axes(name: str, cand: Mapping[str, Any]) -> Axes:
    stab = cand["pooled_stability"]
    means = [run["faithful_class"]["mean"] for run in cand["runs"]]
    finite = [m for m in means if not is_nan(m)]
    mean = sum(finite) / len(finite) if finite else float("nan")
    return Axes(name, mean, stab["flips"], stab["mean_range"])


def render(report: Mapping[str, Any]) -> str:
    base, var = report["baseline"], report["variant"]
    cands = [base, var] if var else [base]
    title = f"# Judge variant `{var['label']}` vs baseline" if var else "# Judge baseline"
    lines = [title, ""]
    if report["problems"]:
        lines += [f"> **{NOT_COMPARABLE}** (--force): {'; '.join(report['problems'])}", ""]
    lines += [f"> **{report['banner']}**", ""]
    lines += ["- **baseline**: " + ", ".join(f"`{p}`" for p in report["baseline_files"])]
    if var:
        lines += [
            "- **variant**: " + ", ".join(f"`{p}`" for p in report["variant_files"]),
            f"- **Differs in**: {', '.join(report['differs_in']) or 'nothing'}",
        ]
    lines += [
        "",
        "## Gate (every hallucinated item flagged, in every repeat)",
        "",
        "| candidate | run | gate | detected/items per origin | per perturbation type | missed |",
        "|---|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            gate = run["gate"]
            origins = ", ".join(f"{o} {d}/{n}" for o, (d, n) in gate["per_origin"].items())
            types = ", ".join(f"{t} {d}/{n}" for t, (d, n) in gate["per_perturbation_type"].items())
            lines.append(
                f"| {cand['label']} | {k} | {'PASSED' if gate['passed'] else 'FAILED'} | "
                f"{origins} | {types or 'none'} | {', '.join(gate['missed']) or '—'} |"
            )
    for cand in cands:
        lines += ["", f"Missed by {cand['label']}, detections per repeat (run 1 / run 2 …):"]
        lines += [
            f"- {item_id}: " + " / ".join(_tf(flags) for flags in per_run)
            for item_id, per_run in cand["missed_detections"].items()
        ] or ["- none"]
    if var:
        diff = report["gate_diff"]
        lines += [
            "",
            f"- Newly caught: {', '.join(diff['newly_caught']) or '—'}",
            f"- Newly missed: {', '.join(diff['newly_missed']) or '—'}",
            f"- Still missed: {', '.join(diff['still_missed']) or '—'}",
        ]
    lines += [
        "",
        "## Class means and nan (per run)",
        "",
        "| candidate | run | faithful (higher = fewer false flags) | hallucinated (lower = "
        "correct) | nan rows | nan per repeat, faithful | nan per repeat, hallucinated | "
        "flagged faithful statements |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cand in cands:
        runs = zip(cand["runs"], cand["nan_rows"], strict=True)
        for k, (run, (nan, total)) in enumerate(runs, 1):
            per_class = [
                ", ".join(
                    f"r{r} {n}/{t}" for r, (n, t) in run[f"{cls}_class"]["nan_per_run"].items()
                )
                for cls in (FAITHFUL, HALLUCINATED)
            ]
            lines.append(
                f"| {cand['label']} | {k} | {_fmt(run['faithful_class']['mean'])} | "
                f"{_fmt(run['hallucinated_class']['mean'])} | {nan}/{total} | "
                f"{per_class[0]} | {per_class[1]} | {len(run['flagged_faithful_statements'])} |"
            )
    for cand in cands:
        distinct = cand["distinct_flagged_faithful"]
        lines.append(
            f"\nDistinct flagged faithful statements, {cand['label']} (all runs): "
            f"{distinct['statements']} across {len(distinct['items'])} items "
            f"({', '.join(distinct['items']) or '—'})"
        )
    lines += [
        "",
        "## Stability",
        "",
        "| candidate | scope | mean range | max range | flips | matched | single-run |",
        "|---|---|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            s = run["stability"]
            lines.append(
                f"| {cand['label']} | run {k} | {_fmt(s['mean_range'])} | {_fmt(s['max_range'])} | "
                f"{s['flips']} | {s['matched_statements']} | {s['unmatched_statements']} |"
            )
        p = cand["pooled_stability"]
        lines.append(
            f"| {cand['label']} | pooled ({p['runs']} runs, {p['repeats']} repeats) | "
            f"{_fmt(p['mean_range'])} | {_fmt(p['max_range'])} | {p['flips']} | "
            f"{p['matched_statements']} | {p['unmatched_statements']} |"
        )
    for cand in cands:
        flipped = cand["pooled_stability"]["flipped"]
        lines += ["", f"Flipped statements, {cand['label']} (pooled): {len(flipped)}"]
        lines += [f"- {item_id}: {statement}" for item_id, statement in flipped]
    lines += ["", "## Noise floor (per-item |run 1 - run 2|)", ""]
    for cand in cands:
        nf = cand["noise_floor"]
        if nf is None:
            lines.append(f"- **{cand['label']}**: single run, no floor")
            continue
        nonzero = ", ".join(f"{k} {_fmt(v)}" for k, v in nf["nonzero"].items()) or "—"
        lines.append(
            f"- **{cand['label']}**: 0 on {nf['zero']} items; nonzero: {nonzero}; "
            f"nan on {len(nf['nan'])} ({', '.join(nf['nan']) or '—'}); "
            f"max {_fmt(nf['max'])}, mean {_fmt(nf['mean'])} over {nf['n_finite']} finite items"
        )
    if var:
        lines += ["", "## Selection axes (only if both pass the gate)", ""]
        if all(run["gate"]["passed"] for cand in cands for run in cand["runs"]):
            lines.append(f"- {dominance(_axes(base['label'], base), _axes(var['label'], var))}")
        else:
            lines.append("- Not applicable: at least one candidate fails the gate in some run.")
    lines += _per_item_means(cands)
    if var:
        lines += [
            "",
            "## Deltas (run 1 of each, marked against the baseline floor)",
            "",
            "| id | label | origin | baseline | variant | delta | floor | noise |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for d in report["items"]:
            lines.append(
                f"| {d['id']} | {d['label']} | {d['origin']} | {_fmt(d['baseline'])} | "
                f"{_fmt(d['variant'])} | {_fmt(d['delta'])} | {_fmt(d['noise_floor'])} | "
                f"{d['noise']} |"
            )
    return "\n".join(lines) + "\n"


def _per_item_means(cands: Sequence[Mapping[str, Any]]) -> list[str]:
    """Mean over repeats per item and run, nan runs beside it."""
    columns = [
        f"{cand['label']} run {k}" for cand in cands for k in range(1, len(cand["runs"]) + 1)
    ]
    lines = [
        "",
        "## Per-item means (mean of repeats; nan runs/runs)",
        "",
        "| id | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for item_id in cands[0]["item_means"]:
        cells = [
            f"{_fmt(mean)} ({nan}/{total})"
            for cand in cands
            for mean, (nan, total) in zip(
                cand["item_means"][item_id], cand["item_nan_runs"][item_id], strict=True
            )
        ]
        lines.append(f"| {item_id} | " + " | ".join(cells) + " |")
    return lines


def build_report(
    baseline: Sequence[Mapping[str, Any]],
    variant: Sequence[Mapping[str, Any]],
    baseline_paths: Sequence[Path],
    variant_paths: Sequence[Path],
    problems: Sequence[str],
) -> dict[str, Any]:
    base = candidate(baseline)
    var = candidate(variant) if variant else None
    return {
        "banner": exploratory_banner(baseline[0]["header"]["items"]["count"]),
        "problems": list(problems),
        "differs_in": differing_units([baseline[0], variant[0]]) if variant else [],
        "baseline_files": [str(p) for p in baseline_paths],
        "variant_files": [str(p) for p in variant_paths],
        "baseline": base,
        "variant": var,
        "gate_diff": gate_diff(base, var) if var else None,
        "items": item_deltas(baseline[0], variant[0], base["noise_floor"]["per_item"])
        if variant
        else [],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--baseline",
        nargs=2,
        type=Path,
        default=list(BASELINE_RUNS),
        metavar=("RUN1", "RUN2"),
        help="The baseline and its rerun (default: the committed judge baseline).",
    )
    parser.add_argument(
        "--variant",
        nargs="+",
        type=Path,
        default=[],
        help="1 or 2 runs of the variant (none: the baseline's own report).",
    )
    parser.add_argument(
        "--force", action="store_true", help=f"Report anyway, stamped {NOT_COMPARABLE}."
    )
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)
    if len(args.variant) > 2:
        parser.error("--variant takes 1 or 2 result files")

    baseline = [load_result(p) for p in args.baseline]
    variant = [load_result(p) for p in args.variant]
    if any(r["header"]["mode"] != "judge" for r in [*baseline, *variant]):
        print("ERROR: judge-mode result files only", file=sys.stderr)
        return 2
    problems = comparability_problems([baseline[0], variant[0]]) if variant else []
    if problems and not args.force:
        print("ERROR: not comparable:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 2
    try:
        report = build_report(baseline, variant, args.baseline, args.variant, problems)
    except ValueError as error:  # a "rerun" that isn't one, or mismatched --repeat
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = (
        f"judgevs_{report['variant']['label']}"
        if variant
        else f"judgebase_{report['baseline']['label']}"
    )
    stem = args.output_dir / f"prompt_cmp_{name}_{stamp}"
    write_result(stem.with_suffix(".json"), report)
    stem.with_suffix(".md").write_text(render(report), encoding="utf-8")
    print(f"Wrote {stem.with_suffix('.md')}\nWrote {stem.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
