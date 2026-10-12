#!/usr/bin/env python3
"""Compares 2+ prompt-comparison result files side by side (feat/prompt-comparison,
docs/prompts.md "Comparing results"). The first file is the baseline.

Refused unless the files are comparable: their prompt manifests differ in
exactly one prompt (the faithfulness family counts as one) and their items,
models, temperature and mode match. `--force` runs anyway and stamps
"NOT COMPARABLE" on the output.

Noise floor: `--rerun <file>`, a second run of the baseline (identical
configuration), gives each item's |run1 - run2|; a delta at or below it is
marked "within noise". Without a rerun file the report says so and makes no
noise claim.

The per-item matrix is the primary output (Markdown + CSV): id, category,
origin, scores, delta, nan flags, statement counts, outside-noise marker;
the nan rate per run is given next to every mean. Judge-mode results also
get the gate, the two selection axes and pairwise dominance
(`eval/scripts/judge_selection.py`); the two classes are never pooled.
Generation-mode results get theirs from `eval/scripts/generation_selection.py`
(fabrication gate, faithfulness and stability axes, substance beside them,
and the negated segments each candidate newly asserts, for reading by hand).

Usage: python -m eval.scripts.compare_prompt_results BASE.json CAND.json [...]
           [--rerun BASE_RERUN.json] [--force]
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.scripts import generation_selection
from eval.scripts.judge_selection import (
    FAITHFUL,
    HALLUCINATED,
    Axes,
    class_scores,
    dominance,
    format_miss,
    is_nan,
    item_mean,
    rows_by_item,
    summarize,
)
from eval.scripts.prompt_results import (
    NOT_COMPARABLE,
    NOT_FROZEN,
    RESULTS_DIR,
    exploratory_banner,
    load_result,
)
from eval.scripts.prompt_variants import FAMILIES, FAMILY_MODE, family_of

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWN_ISSUES_DIR = REPO_ROOT / "docs" / "known_issues"


def _unit(prompt_id: str) -> str:
    """Comparison unit: the faithfulness family is one, every other prompt
    (and each library entry) its own."""
    return family_of(prompt_id) or prompt_id


def _unit_signature(manifest: Mapping[str, Mapping[str, Any]], unit: str) -> tuple:
    return tuple(
        sorted(
            (pid, entry.get("hash"), entry.get("version"))
            for pid, entry in manifest.items()
            if _unit(pid) == unit
        )
    )


def differing_units(results: Sequence[Mapping[str, Any]]) -> list[str]:
    manifests = [r["header"]["manifest"] for r in results]
    units = sorted({_unit(pid) for m in manifests for pid in m})
    return [u for u in units if len({_unit_signature(m, u) for m in manifests}) > 1]


def comparability_problems(results: Sequence[Mapping[str, Any]]) -> list[str]:
    """Why these results can't be compared ([] if they can)."""
    problems = []
    headers = [r["header"] for r in results]
    for field in ("mode", "models", "temperature"):
        values = {repr(h[field]) for h in headers}
        if len(values) > 1:
            problems.append(f"{field} differs: {' vs '.join(sorted(values))}")
    if len({tuple(h["items"]["ids"]) for h in headers}) > 1:
        problems.append("items differ (ids or order)")
    if len({h["items"].get("calibration_set_sha256") for h in headers}) > 1:
        problems.append("calibration set differs (different texts or chunks)")
    if len({h["items"].get("gold_set_sha256") for h in headers}) > 1:
        problems.append("gold set differs (questions or chunk ids)")
    changed = chunk_text_changes(results)
    if changed:
        problems.append(
            f"gold chunk text differs between runs on {', '.join(changed)} (re-indexed?)"
        )
    versions = {h.get("judge_input_version", 1) for h in headers}
    if len(versions) > 1:
        problems.append(
            f"judge input version differs ({' vs '.join(map(str, sorted(versions)))}): the code "
            "changed what the judge is given or how its replies are read"
        )
    units = differing_units(results)
    if not units:
        problems.append(
            "manifests are identical: that's a rerun (use it as --rerun), not a variant"
        )
    elif len(units) > 1:
        problems.append(f"manifests differ in {len(units)} prompts, not one: {', '.join(units)}")
    elif units[0] not in FAMILIES:
        problems.append(f"the differing prompt ({units[0]}) is not a comparable one")
    elif FAMILY_MODE[units[0]] != headers[0]["mode"]:
        problems.append(f"{units[0]} differs, but these are {headers[0]['mode']}-mode results")
    return problems


def chunk_text_changes(results: Sequence[Mapping[str, Any]]) -> list[str]:
    """Generation-mode items whose gold chunks weren't the same text in
    every run of every result."""
    seen: dict[str, set[str]] = {}
    for result in results:
        for row in result["rows"]:
            if row.get("chunks_sha256"):
                seen.setdefault(row["item_id"], set()).add(row["chunks_sha256"])
    return sorted(item_id for item_id, digests in seen.items() if len(digests) > 1)


def noise_floor(base: Mapping[str, Any], rerun: Mapping[str, Any]) -> dict[str, float]:
    """Per-item |baseline mean - rerun mean| (nan where either is nan)."""
    for field in ("mode", "manifest", "models", "temperature"):
        if base["header"][field] != rerun["header"][field]:
            raise ValueError(f"--rerun is not a rerun of the baseline: {field} differs")
    if base["header"]["items"]["ids"] != rerun["header"]["items"]["ids"]:
        raise ValueError("--rerun is not a rerun of the baseline: items differ")
    base_rows, rerun_rows = rows_by_item(base["rows"]), rows_by_item(rerun["rows"])
    floor = {}
    for item_id in base["header"]["items"]["ids"]:
        a, b = item_mean(base_rows.get(item_id, [])), item_mean(rerun_rows.get(item_id, []))
        floor[item_id] = abs(a - b) if not (math.isnan(a) or math.isnan(b)) else float("nan")
    return floor


def noise_marker(delta: float, floor: float | None) -> str:
    if floor is None:
        return "no noise floor"
    if math.isnan(delta) or math.isnan(floor):
        return "nan"
    return "within noise" if abs(delta) <= floor + 1e-12 else "outside noise"


def known_issue_items(items: Sequence[Mapping[str, Any]], directory: Path) -> dict[str, list[str]]:
    """Items whose gold chunk or paragraph ids appear in docs/known_issues/
    (item id -> matching files). Empty if the directory doesn't exist."""
    if not directory.is_dir():
        return {}
    texts = {
        p.name: p.read_text(encoding="utf-8", errors="ignore")
        for p in directory.rglob("*")
        if p.is_file()
    }
    flagged: dict[str, list[str]] = {}
    for item in items:
        ids = [
            *item.get("chunk_ids", []),
            *(c["chunk_id"] for c in item.get("chunks", [])),
            *item.get("paragraph_ids", []),
        ]
        hits = sorted(name for name, text in texts.items() if any(i in text for i in ids))
        if hits:
            flagged[item["id"]] = hits
    return flagged


def _fmt(value: float | None) -> str:
    return "nan" if is_nan(value) else f"{value:.3f}"


def _labels(results: Sequence[Mapping[str, Any]]) -> list[str]:
    labels = [r["header"]["source"]["label"] for r in results]
    return [f"{i}:{label}" if labels.count(label) > 1 else label for i, label in enumerate(labels)]


def build_matrix(
    results: Sequence[Mapping[str, Any]],
    floor: Mapping[str, float] | None,
    known_issues: Mapping[str, list[str]],
) -> tuple[list[str], list[list[str]]]:
    labels = _labels(results)
    base_items = results[0]["items"]
    grouped = [rows_by_item(r["rows"]) for r in results]
    columns = ["id", "category", "origin", "label"]
    for label in labels:
        columns += [
            f"score[{label}]",
            f"nan runs[{label}]",
            f"claims/run[{label}]",
            f"unsupported/run[{label}]",
            f"unevaluated/run[{label}]",
        ]
    for label in labels[1:]:
        columns += [f"delta[{label}]", f"noise[{label}]"]
    columns += ["noise floor"]
    if known_issues:
        columns += ["known issue"]
    matrix = []
    for item in base_items:
        row = [
            item["id"],
            item.get("category", ""),
            item.get("origin", "gold"),
            item.get("label", ""),
        ]
        means = []
        for runs_by_item in grouped:
            runs = runs_by_item.get(item["id"], [])
            mean = item_mean(runs)
            means.append(mean)
            n = len(runs) or 1
            row += [
                _fmt(mean),
                f"{sum(is_nan(r['score']) for r in runs)}/{len(runs)}",
                f"{sum(len(r['claims']) for r in runs) / n:.1f}",
                f"{sum(c['supported'] is False for r in runs for c in r['claims']) / n:.1f}",
                f"{sum(c['supported'] is None for r in runs for c in r['claims']) / n:.1f}",
            ]
        item_floor = None if floor is None else floor.get(item["id"], float("nan"))
        for mean in means[1:]:
            delta = mean - means[0]
            row += [
                _fmt(delta) if not math.isnan(delta) else "nan",
                noise_marker(delta, item_floor),
            ]
        row.append("none (no --rerun)" if item_floor is None else _fmt(item_floor))
        if known_issues:
            row.append(", ".join(known_issues.get(item["id"], [])))
        matrix.append(row)
    return columns, matrix


def _nan_rate(nan_per_run: Mapping[int, tuple[int, int]]) -> str:
    return ", ".join(f"run {r}: {n}/{t}" for r, (n, t) in nan_per_run.items())


def _missed(gate: Mapping[str, Any]) -> str:
    return ", ".join(format_miss(i, gate["miss_reasons"][i]) for i in gate["missed"])


def class_means(results: Sequence[Mapping[str, Any]]) -> list[str]:
    """Mean per file and class, nan rate per run beside it. Judge mode keeps
    the faithful and hallucinated classes apart; generation items are all
    gold questions (one class)."""
    lines = [
        "| candidate | class | mean | items | nan per run | runs with unevaluated claims |",
        "|---|---|---|---|---|---|",
    ]
    for label, result in zip(_labels(results), results, strict=True):
        repeat = result["header"]["repeat"]
        classes = (FAITHFUL, HALLUCINATED) if result["header"]["mode"] == "judge" else (FAITHFUL,)
        for cls in classes:
            scores = class_scores(result["items"], result["rows"], cls, repeat)
            direction = {
                "faithful": "higher = fewer false flags",
                "hallucinated": "lower = correct",
            }
            lines.append(
                f"| {label} | {cls} ({direction[cls]}) | {_fmt(scores.mean)} | {scores.n_items} | "
                f"{_nan_rate(scores.nan_per_run)} | {_nan_rate(scores.unevaluated_per_run)} |"
            )
    return lines


def judge_sections(results: Sequence[Mapping[str, Any]]) -> list[str]:
    labels = _labels(results)
    summaries = [summarize(r["items"], r["rows"], r["header"]["repeat"]) for r in results]
    lines = [
        "## Gate: every hallucinated item flagged, in every run",
        "",
        "| candidate | gate | detected/items per origin | per perturbation type | missed |",
        "|---|---|---|---|---|",
    ]
    for label, summary in zip(labels, summaries, strict=True):
        gate = summary["gate"]
        origins = ", ".join(f"{o} {d}/{n}" for o, (d, n) in gate["per_origin"].items())
        types = ", ".join(f"{t} {d}/{n}" for t, (d, n) in gate["per_perturbation_type"].items())
        lines.append(
            f"| {label} | {'PASSED' if gate['passed'] else 'FAILED (rejected)'} | {origins} | "
            f"{types or 'none'} | {_missed(gate) or '—'} |"
        )
    lines += [
        "",
        "Missed: a miss is a miss for the gate, whatever its reason (nan = the check "
        "failed; unevaluated = the known claim got no verdict; judged supported).",
        "",
        "Perturbed items are mechanical edits, cruder than real fabrications: catching them "
        "shows the judge catches blatant errors, not subtle ones.",
        "",
        "## Selection axes (gate-passing candidates only, no composite score)",
        "",
        "| candidate | (a) faithful-class mean | (b) verdict flips | (b) mean score range |",
        "|---|---|---|---|",
    ]
    passing: list[Axes] = []
    for label, summary in zip(labels, summaries, strict=True):
        if not summary["gate"]["passed"]:
            continue
        stab = summary["stability"]
        if not stab["measured"]:
            lines.append(
                f"| {label} | {_fmt(summary['faithful_class']['mean'])} | "
                "unmeasured (--repeat 1) | — |"
            )
            continue
        axes = Axes(label, summary["faithful_class"]["mean"], stab["flips"], stab["mean_range"])
        passing.append(axes)
        lines.append(
            f"| {label} | {_fmt(axes.faithful_mean)} | {axes.flips} | {_fmt(axes.mean_range)} |"
        )
    lines += [
        "",
        "Pairwise verdicts (the owner designates the winner; this tooling never does):",
        "",
    ]
    pairs = [dominance(x, y) for i, x in enumerate(passing) for y in passing[i + 1 :]]
    lines += [f"- {p}" for p in pairs] or [
        "- Fewer than two gate-passing candidates with measured stability."
    ]
    lines += [
        "",
        "## Statements flagged in faithful items (investigation leads, labels unchanged)",
        "",
    ]
    for label, summary in zip(labels, summaries, strict=True):
        flagged = summary["flagged_faithful_statements"]
        lines.append(f"**{label}**: {len(flagged)}")
        lines += [
            f"- {f['item_id']} run {f['repeat']}: {f['statement']} — {f['reason']}" for f in flagged
        ]
        lines.append("")
    return lines


def generation_sections(results: Sequence[Mapping[str, Any]]) -> list[str]:
    labels = _labels(results)
    summaries = [
        generation_selection.summarize(r["items"], r["rows"], r["header"]["repeat"])
        for r in results
    ]
    lines = [
        "## Gate: no fabricated work title, no title/year mismatch, in any run",
        "",
        "| candidate | gate | answers checked | failures |",
        "|---|---|---|---|",
    ]
    for label, summary in zip(labels, summaries, strict=True):
        gate = summary["gate"]
        failures = ", ".join(
            f"{item_id} run {f['repeat']}" for item_id, fs in gate["failures"].items() for f in fs
        )
        lines.append(
            f"| {label} | {'PASSED' if gate['passed'] else 'FAILED (rejected)'} | "
            f"{gate['answers_checked']}/{gate['runs_expected']} | {failures or '—'} |"
        )
    lines += [
        "",
        "## Selection axes, substance beside them (no composite score)",
        "",
        "| candidate | (a) faithfulness mean | (b) verdict flips | (b) mean score range | "
        "identical answers | claims/answer | generation failures |",
        "|---|---|---|---|---|---|---|",
    ]
    passing: list[Axes] = []
    for label, summary in zip(labels, summaries, strict=True):
        stab = summary["stability"]
        mean = summary["faithfulness"]["mean"]
        measured = stab["measured"]
        lines.append(
            f"| {label} | {_fmt(mean)} | {stab['flips'] if measured else 'unmeasured'} | "
            f"{_fmt(stab['mean_range']) if measured else '—'} | {len(stab['identical'])} | "
            f"{_fmt(summary['substance']['mean_claims_per_answer'])} | "
            f"{len(summary['generation_failures'])} |"
        )
        if summary["gate"]["passed"] and measured:
            passing.append(Axes(label, mean, stab["flips"], stab["mean_range"]))
    lines += [
        "",
        "Pairwise verdicts, gate-passing candidates with measured stability (the owner "
        "designates the winner; this tooling never does):",
        "",
    ]
    pairs = [
        dominance(x, y, generation_selection.FAITHFULNESS_AXIS)
        for i, x in enumerate(passing)
        for y in passing[i + 1 :]
    ]
    lines += [f"- {p}" for p in pairs] or [
        "- Fewer than two gate-passing candidates with measured stability."
    ]
    base = summaries[0]
    warnings = [
        generation_selection.fewer_claims_warning(
            base["faithfulness"]["mean"],
            base["substance"]["mean_claims_per_answer"],
            summary["faithfulness"]["mean"],
            summary["substance"]["mean_claims_per_answer"],
            label,
        )
        for label, summary in zip(labels[1:], summaries[1:], strict=True)
    ]
    lines += [f"- **Warning**: {w}" for w in warnings if w]
    lines += [
        "",
        "## Negated segments newly asserted (polarity review, read by hand)",
        "",
        "The frozen judge does not reliably detect a negation that reverses a sentence's "
        "meaning: these segments carry a negation marker, the judge accepted them, and the "
        "baseline never wrote them for that item.",
        "",
    ]
    for label, summary in zip(labels[1:], summaries[1:], strict=True):
        new = generation_selection.distinct_segments(
            generation_selection.new_segments(summary["polarity_review"], results[0]["rows"])
        )
        lines.append(f"**{label}**: {len(new)}")
        lines += [f"- {e['item_id']} (first in run {e['repeat']}): {e['segment']}" for e in new]
        lines.append("")
    return lines


def render(
    results: Sequence[Mapping[str, Any]],
    paths: Sequence[Path],
    problems: Sequence[str],
    floor: Mapping[str, float] | None,
    rerun_path: Path | None,
    known_issues: Mapping[str, list[str]],
    known_issues_dir: Path,
    columns: list[str],
    matrix: list[list[str]],
) -> str:
    header = results[0]["header"]
    labels = _labels(results)
    lines = [f"# Prompt comparison: {header['mode']} mode", ""]
    if problems:
        lines += [f"> **{NOT_COMPARABLE}** (--force): {'; '.join(problems)}", ""]
    lines += [f"> **{exploratory_banner(header['items']['count'])}**", ""]
    for label, result, path in zip(labels, results, paths, strict=True):
        h = result["header"]
        flags = []
        if h["source"]["kind"] == "ad hoc":
            flags.append("ad hoc")
        if h["stale"]:
            flags.append("STALE: " + "; ".join(h["stale"]))
        if h["frozen_judge"]["matches"] is False:
            flags.append(NOT_FROZEN)
        if h["git"]["dirty"]:
            flags.append("dirty tree")
        lines.append(
            f"- **{label}**: `{path}` (commit `{h['git']['commit'][:10]}`; "
            f"{', '.join(flags) or 'clean'})"
        )
    units = differing_units(results)
    lines += [
        "",
        f"- **Differs in**: {', '.join(units) or 'nothing'}; models {header['models']}, "
        f"temperature {header['temperature']}, items {header['items']['count']} "
        f"{header['items']['per_origin']}",
        "- **Noise floor**: "
        + (
            f"from `{rerun_path}` (per-item |run1 - run2| of the baseline)"
            if floor is not None
            else "no baseline rerun file given: no noise claim is made"
        ),
    ]
    if header["mode"] == "generation":
        lines.append(
            f"- **Known issues** (`{known_issues_dir}`): "
            + (
                f"{len(known_issues)} item(s) flagged"
                if known_issues
                else (
                    "directory absent, nothing flagged" if not known_issues_dir.is_dir() else "none"
                )
            )
        )
    lines += ["", "## Means (nan rate per run beside each)", "", *class_means(results), ""]
    if header["mode"] == "judge":
        lines += judge_sections(results)
    else:
        lines += generation_sections(results)
    lines += [
        "## Per-item matrix",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
        *("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |" for row in matrix),
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "results", nargs="+", type=Path, help="Result files; the first is the baseline."
    )
    parser.add_argument("--rerun", type=Path, help="A rerun of the baseline, for the noise floor.")
    parser.add_argument(
        "--force", action="store_true", help=f"Compare anyway, stamped {NOT_COMPARABLE}."
    )
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--known-issues-dir", type=Path, default=KNOWN_ISSUES_DIR)
    args = parser.parse_args(argv)
    if len(args.results) < 2:
        parser.error("need at least two result files")

    results = [load_result(path) for path in args.results]
    problems = comparability_problems(results)
    if problems and not args.force:
        print(
            "ERROR: not comparable:\n  - "
            + "\n  - ".join(problems)
            + "\n(--force to compare anyway, stamped NOT COMPARABLE)",
            file=sys.stderr,
        )
        return 2
    floor = None
    if args.rerun:
        try:
            floor = noise_floor(results[0], load_result(args.rerun))
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
    known = (
        known_issue_items(results[0]["items"], args.known_issues_dir)
        if results[0]["header"]["mode"] == "generation"
        else {}
    )
    columns, matrix = build_matrix(results, floor, known)
    report = render(
        results,
        args.results,
        problems,
        floor,
        args.rerun,
        known,
        args.known_issues_dir,
        columns,
        matrix,
    )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = args.output_dir / f"prompt_cmp_compare_{results[0]['header']['mode']}_{stamp}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".md").write_text(report, encoding="utf-8")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if problems:
        writer.writerow([f"{NOT_COMPARABLE}: {'; '.join(problems)}"])
    writer.writerow([exploratory_banner(results[0]["header"]["items"]["count"])])
    writer.writerow(columns)
    writer.writerows(matrix)
    stem.with_suffix(".csv").write_text(buffer.getvalue(), encoding="utf-8")
    print(f"Wrote {stem.with_suffix('.md')}\nWrote {stem.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
