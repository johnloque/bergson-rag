#!/usr/bin/env python3
"""Generation baseline report, alone or against a `generation.answer`
variant (docs/prompts.md, "Choosing a generation variant"): the generation
counterpart of `judge_variant_report.py`, over generation-mode results
judged by the frozen judge.

Without `--variant`, it writes the baseline's own report: fabrication gate,
faithfulness and nan per run, substance (claims, length, citations),
stability per run and pooled, identical answers, noise floor between the
baseline and its rerun, unsupported claims and the polarity review list.

With `--variant` (1 or 2 runs) it adds:
- the gate side by side;
- the two selection axes and the dominance verdict, when both pass the
  gate in every run (no composite score, no winner picked);
- the fewer-claims warning: a faithfulness gain that comes with fewer
  claims per answer may come from saying less;
- the claims the variant newly gets flagged on, and the negated segments
  it newly asserts and the judge accepted (the frozen judge's known blind
  spot: read them by hand);
- per-item deltas (variant run 1 - baseline run 1), marked against the
  baseline's noise floor.

Usage: python -m eval.scripts.generation_variant_report \\
           --baseline BASE_RUN1.json BASE_RUN2.json \\
           [--variant VAR_RUN1.json [VAR_RUN2.json]] [--force] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.scripts import generation_selection
from eval.scripts.compare_prompt_results import (
    chunk_text_changes,
    comparability_problems,
    differing_units,
    noise_floor,
)
from eval.scripts.judge_selection import (
    Axes,
    _statement_key,
    dominance,
    is_nan,
    item_mean,
    rows_by_item,
    stability,
)
from eval.scripts.judge_variant_report import floor_stats, item_deltas, pooled
from eval.scripts.prompt_results import (
    NOT_COMPARABLE,
    NOT_FROZEN,
    RESULTS_DIR,
    exploratory_banner,
    load_result,
    write_result,
)


def candidate(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-run summaries, pooled stability and review lists, and (with 2
    runs) the noise floor."""
    items = results[0]["items"]
    changed = chunk_text_changes(results)
    if changed:
        raise ValueError(f"runs of one candidate saw different gold chunk text on {changed}")
    rows, total = pooled(results)
    pooled_stab = stability(rows, total)
    runs = [
        generation_selection.summarize(items, r["rows"], r["header"]["repeat"]) for r in results
    ]
    unsupported = {}
    for run in runs:
        for c in run["unsupported_claims"]:
            unsupported.setdefault((c["item_id"], _statement_key(c["statement"])), c)
    means = [run["faithfulness"]["mean"] for run in runs]
    finite = [m for m in means if not is_nan(m)]
    claims = [run["substance"]["mean_claims_per_answer"] for run in runs]
    finite_claims = [c for c in claims if not is_nan(c)]
    return {
        "label": results[0]["header"]["source"]["label"],
        "frozen_judge": [r["header"]["frozen_judge"] for r in results],
        "runs": runs,
        "rows": rows,
        # over every run: the means the selection axes and the warning use
        "faithfulness_mean": sum(finite) / len(finite) if finite else float("nan"),
        "mean_claims_per_answer": sum(finite_claims) / len(finite_claims)
        if finite_claims
        else float("nan"),
        "gate_passed": all(run["gate"]["passed"] for run in runs),
        "pooled_stability": {
            "runs": len(results),
            "repeats": total,
            "mean_range": pooled_stab.mean_range,
            "max_range": pooled_stab.max_range,
            "flips": pooled_stab.flips,
            "matched_statements": pooled_stab.matched_statements,
            "unmatched_statements": pooled_stab.unmatched_statements,
            "flipped": [list(f) for f in pooled_stab.flipped],
            **generation_selection.identical_answers(rows),
        },
        "distinct_unsupported": list(unsupported.values()),
        "distinct_polarity_review": generation_selection.distinct_segments(
            generation_selection.polarity_review(rows)
        ),
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
        "noise_floor": floor_stats(noise_floor(results[0], results[1]))
        if len(results) > 1
        else None,
    }


def newly_unsupported(base: Mapping[str, Any], var: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Claims the variant gets flagged on that no baseline run made and got
    flagged on, for the same item."""
    seen = {(c["item_id"], _statement_key(c["statement"])) for c in base["distinct_unsupported"]}
    return [
        c
        for c in var["distinct_unsupported"]
        if (c["item_id"], _statement_key(c["statement"])) not in seen
    ]


def _fmt(value: float | None) -> str:
    return "nan" if is_nan(value) else f"{value:.3f}"


def _per_repeat(counts: Mapping[str, Sequence[int]]) -> str:
    return ", ".join(f"r{r} {n}/{t}" for r, (n, t) in counts.items())


def _axes(cand: Mapping[str, Any]) -> Axes:
    stab = cand["pooled_stability"]
    return Axes(cand["label"], cand["faithfulness_mean"], stab["flips"], stab["mean_range"])


def render(report: Mapping[str, Any]) -> str:
    base, var = report["baseline"], report["variant"]
    cands = [base, var] if var else [base]
    title = f"# Generation variant `{var['label']}` vs baseline" if var else "# Generation baseline"
    lines = [title, ""]
    if report["problems"]:
        lines += [f"> **{NOT_COMPARABLE}** (--force): {'; '.join(report['problems'])}", ""]
    if any(f["matches"] is False for cand in cands for f in cand["frozen_judge"]):
        lines += [f"> **{NOT_FROZEN}**: at least one run was not scored by the frozen judge", ""]
    lines += [f"> **{report['banner']}**", ""]
    lines += ["- **baseline**: " + ", ".join(f"`{p}`" for p in report["baseline_files"])]
    if var:
        lines += [
            "- **variant**: " + ", ".join(f"`{p}`" for p in report["variant_files"]),
            f"- **Differs in**: {', '.join(report['differs_in']) or 'nothing'}",
        ]
    lines.append(f"- **Frozen judge**: {base['frozen_judge'][0]['status']}")
    lines += [
        "",
        "## Gate (no fabricated work title, no title/year mismatch, in any run)",
        "",
        "| candidate | run | gate | answers checked | failures |",
        "|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            gate = run["gate"]
            failures = ", ".join(
                f"{i} r{f['repeat']}" for i, fs in gate["failures"].items() for f in fs
            )
            lines.append(
                f"| {cand['label']} | {k} | {'PASSED' if gate['passed'] else 'FAILED'} | "
                f"{gate['answers_checked']}/{gate['runs_expected']} | {failures or '—'} |"
            )
    lines += [
        "",
        "## Faithfulness by the frozen judge, and failures (per run)",
        "",
        "| candidate | run | mean (higher = fewer unsupported claims) | nan per repeat | "
        "unevaluated per repeat | unsupported claims | generation failures |",
        "|---|---|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            f = run["faithfulness"]
            lines.append(
                f"| {cand['label']} | {k} | {_fmt(f['mean'])} | {_per_repeat(f['nan_per_run'])} | "
                f"{_per_repeat(f['unevaluated_per_run'])} | {len(run['unsupported_claims'])} | "
                f"{len(run['generation_failures'])} |"
            )
    lines += [
        "",
        "## Substance (beside the axes: an answer that says less has less to get wrong)",
        "",
        "| candidate | run | claims/answer | chars/answer | citations/answer | "
        "answers with a citation | citations to a chunk not given |",
        "|---|---|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            s = run["substance"]
            cited = sum(v[0] for v in s["answers_with_citation"].values())
            answers = sum(v[1] for v in s["answers_with_citation"].values())
            lines.append(
                f"| {cand['label']} | {k} | {_fmt(s['mean_claims_per_answer'])} | "
                f"{_fmt(_mean(s['answer_chars']))} | {_fmt(_mean(s['citations_per_answer']))} | "
                f"{cited}/{answers} | {len(s['unknown_citations'])} |"
            )
    if var and report["fewer_claims_warning"]:
        lines += ["", f"**Warning**: {report['fewer_claims_warning']}"]
    lines += [
        "",
        "## Stability",
        "",
        "| candidate | scope | mean range | max range | flips | matched | single-run | "
        "identical answers |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cand in cands:
        for k, run in enumerate(cand["runs"], 1):
            s = run["stability"]
            lines.append(
                f"| {cand['label']} | run {k} | {_fmt(s['mean_range'])} | {_fmt(s['max_range'])} | "
                f"{s['flips']} | {s['matched_statements']} | {s['unmatched_statements']} | "
                f"{len(s['identical'])} |"
            )
        p = cand["pooled_stability"]
        lines.append(
            f"| {cand['label']} | pooled ({p['runs']} runs, {p['repeats']} repeats) | "
            f"{_fmt(p['mean_range'])} | {_fmt(p['max_range'])} | {p['flips']} | "
            f"{p['matched_statements']} | {p['unmatched_statements']} | {len(p['identical'])} |"
        )
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
        lines += ["", "## Selection axes (only if both pass the gate in every run)", ""]
        if base["gate_passed"] and var["gate_passed"]:
            verdict = dominance(_axes(base), _axes(var), generation_selection.FAITHFULNESS_AXIS)
            lines.append(f"- {verdict}")
        else:
            lines.append("- Not applicable: at least one candidate fails the gate in some run.")
    claims_title = "Claims newly flagged unsupported" if var else "Unsupported claims"
    claims = report["newly_unsupported"] if var else base["distinct_unsupported"]
    lines += ["", f"## {claims_title} (distinct, all runs, with the judge's reason)", ""]
    lines += [f"- {c['item_id']}: {c['statement']} — {c['reason']}" for c in claims] or ["None."]
    review = report["new_polarity_review"] if var else base["distinct_polarity_review"]
    lines += [
        "",
        "## Polarity review: negated segments "
        + ("newly asserted by the variant" if var else "the judge accepted")
        + " (read by hand)",
        "",
        "The frozen judge does not reliably detect a negation that reverses a sentence's "
        'meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness delta says '
        "nothing about these. Check each against its chunks.",
        "",
    ]
    lines += [f"- {e['item_id']} ({', '.join(e['markers'])}): {e['segment']}" for e in review] or [
        "None."
    ]
    lines += _per_item_means(cands)
    if var:
        lines += [
            "",
            "## Deltas (run 1 of each, marked against the baseline floor)",
            "",
            "| id | baseline | variant | delta | floor | noise |",
            "|---|---|---|---|---|---|",
        ]
        for d in report["items"]:
            lines.append(
                f"| {d['id']} | {_fmt(d['baseline'])} | {_fmt(d['variant'])} | "
                f"{_fmt(d['delta'])} | {_fmt(d['noise_floor'])} | {d['noise']} |"
            )
    return "\n".join(lines) + "\n"


def _mean(per_run: Mapping[str, float]) -> float:
    finite = [v for v in per_run.values() if not is_nan(v)]
    return sum(finite) / len(finite) if finite else float("nan")


def _per_item_means(cands: Sequence[Mapping[str, Any]]) -> list[str]:
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
    report: dict[str, Any] = {
        "banner": exploratory_banner(baseline[0]["header"]["items"]["count"]),
        "problems": list(problems),
        "differs_in": differing_units([baseline[0], variant[0]]) if variant else [],
        "baseline_files": [str(p) for p in baseline_paths],
        "variant_files": [str(p) for p in variant_paths],
        "baseline": base,
        "variant": var,
        "fewer_claims_warning": None,
        "newly_unsupported": [],
        "new_polarity_review": [],
        "items": [],
    }
    if var:
        report["fewer_claims_warning"] = generation_selection.fewer_claims_warning(
            base["faithfulness_mean"],
            base["mean_claims_per_answer"],
            var["faithfulness_mean"],
            var["mean_claims_per_answer"],
            var["label"],
        )
        report["newly_unsupported"] = newly_unsupported(base, var)
        report["new_polarity_review"] = generation_selection.new_segments(
            var["distinct_polarity_review"], base["rows"]
        )
        report["items"] = item_deltas(baseline[0], variant[0], base["noise_floor"]["per_item"])
    for cand in (base, var):
        if cand:
            del cand["rows"]  # pooled copies of the result files' rows: not worth rewriting
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--baseline",
        nargs=2,
        type=Path,
        required=True,
        metavar=("RUN1", "RUN2"),
        help="The baseline (committed defaults, --mode generation) and its rerun.",
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
    if any(r["header"]["mode"] != "generation" for r in [*baseline, *variant]):
        print("ERROR: generation-mode result files only", file=sys.stderr)
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
        f"genvs_{report['variant']['label']}"
        if variant
        else f"genbase_{report['baseline']['label']}"
    )
    stem = args.output_dir / f"prompt_cmp_{name}_{stamp}"
    write_result(stem.with_suffix(".json"), report)
    stem.with_suffix(".md").write_text(render(report), encoding="utf-8")
    print(f"Wrote {stem.with_suffix('.md')}\nWrote {stem.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
