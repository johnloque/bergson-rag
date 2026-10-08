"""Judge-selection analysis over judge-mode result rows (feat/prompt-comparison,
docs/prompts.md "Choosing the judge"). Pure functions: no LLM, no I/O.

A result row is one `check_faithfulness` run on one calibration item:
`{item_id, repeat, score (None = nan/failure), error, claims: [{statement,
supported, reason, segment_id}], segments: [{id, start, end}]}`.

1. Gate: a candidate must flag the known fabricated claim of EVERY
   hallucinated item (generated and perturbed), in every repeat; otherwise
   it is rejected, whatever its scores. "Flags" = at least one claim drawn
   from a segment overlapping the fabricated substring gets verdict 0.
   Claims are anchored to whole answer segments (sentences, cut by code),
   not to generated quotes, so the overlap is decided at sentence level.
2. Among candidates passing the gate, two axes side by side, never a
   composite: (a) mean faithfulness on the FAITHFUL class (higher = fewer
   false flags); (b) stability over repeats: per-item score range and
   per-statement verdict flips (fewer = better). X is preferred over Y only
   if better-or-equal on both; otherwise the trade-off is reported.
3. Hallucinated-class scores are reported apart (lower is the correct
   direction). No mean ever pools the two classes.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

FAITHFUL = "faithful"
HALLUCINATED = "hallucinated"


def is_nan(score: float | None) -> bool:
    return score is None or (isinstance(score, float) and math.isnan(score))


def rows_by_item(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["item_id"], []).append(row)
    for runs in grouped.values():
        runs.sort(key=lambda r: r["repeat"])
    return grouped


def flags_known_claim(row: Mapping[str, Any], item: Mapping[str, Any]) -> bool:
    """Whether this run gave verdict 0 to a claim drawn from a segment that
    overlaps the item's fabricated substring."""
    start = item["fabricated_start"]
    end = start + len(item["fabricated_substring"])
    overlapping = {
        s["id"] for s in row.get("segments", []) if s["start"] < end and start < s["end"]
    }
    return any(
        claim["supported"] is False and claim["segment_id"] in overlapping
        for claim in row.get("claims", [])
    )


@dataclass
class GateResult:
    passed: bool
    repeat: int
    # item id -> per-repeat flagged booleans (a missing run counts as False)
    detections: dict[str, list[bool]]
    # origin -> (items detected in every repeat, items)
    per_origin: dict[str, tuple[int, int]]
    # perturbation type -> (detected, total)
    per_perturbation_type: dict[str, tuple[int, int]]
    missed: list[str]


def gate(
    items: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]], repeat: int
) -> GateResult:
    grouped = rows_by_item(rows)
    detections: dict[str, list[bool]] = {}
    per_origin: dict[str, list[int]] = {}
    per_type: dict[str, list[int]] = {}
    missed: list[str] = []
    for item in items:
        if item["label"] != HALLUCINATED:
            continue
        runs = {row["repeat"]: row for row in grouped.get(item["id"], [])}
        flagged = [r in runs and flags_known_claim(runs[r], item) for r in range(1, repeat + 1)]
        detections[item["id"]] = flagged
        detected = all(flagged)
        counts = per_origin.setdefault(item["origin"], [0, 0])
        counts[0] += detected
        counts[1] += 1
        if item["origin"] == "perturbed":
            type_counts = per_type.setdefault(item["perturbation"]["type"], [0, 0])
            type_counts[0] += detected
            type_counts[1] += 1
        if not detected:
            missed.append(item["id"])
    return GateResult(
        passed=bool(detections) and not missed,
        repeat=repeat,
        detections=detections,
        per_origin={k: (v[0], v[1]) for k, v in sorted(per_origin.items())},
        per_perturbation_type={k: (v[0], v[1]) for k, v in sorted(per_type.items())},
        missed=missed,
    )


def item_mean(runs: Sequence[Mapping[str, Any]]) -> float:
    """Mean score over an item's runs, nan runs excluded (nan if all are)."""
    scores = [r["score"] for r in runs if not is_nan(r["score"])]
    return sum(scores) / len(scores) if scores else float("nan")


@dataclass
class ClassScores:
    label: str
    mean: float  # mean over items of each item's mean over repeats
    n_items: int
    nan_per_run: dict[int, tuple[int, int]]  # repeat -> (nan runs, runs)


def class_scores(
    items: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]], label: str, repeat: int
) -> ClassScores:
    grouped = rows_by_item(rows)
    ids = [item["id"] for item in items if item["label"] == label]
    means = [item_mean(grouped.get(item_id, [])) for item_id in ids]
    finite = [m for m in means if not math.isnan(m)]
    nan_per_run: dict[int, tuple[int, int]] = {}
    for r in range(1, repeat + 1):
        runs = [row for item_id in ids for row in grouped.get(item_id, []) if row["repeat"] == r]
        missing = len(ids) - len(runs)
        nan_per_run[r] = (sum(is_nan(row["score"]) for row in runs) + missing, len(ids))
    return ClassScores(
        label=label,
        mean=sum(finite) / len(finite) if finite else float("nan"),
        n_items=len(ids),
        nan_per_run=nan_per_run,
    )


def _statement_key(statement: str) -> str:
    return re.sub(r"\s+", " ", statement).strip().casefold()


@dataclass
class Stability:
    measured: bool  # False when fewer than 2 repeats: nothing to compare
    mean_range: float  # mean over items of max-min score across repeats
    max_range: float
    flips: int  # statements (same text in 2+ runs) with both verdicts 0 and 1
    matched_statements: int  # statements found in 2+ runs of their item
    unmatched_statements: int  # statements found in a single run (extraction varied)
    ranges: dict[str, float] = field(default_factory=dict)
    flipped: list[tuple[str, str]] = field(default_factory=list)  # (item id, statement)


def stability(rows: Iterable[Mapping[str, Any]], repeat: int) -> Stability:
    grouped = rows_by_item(rows)
    if repeat < 2:
        return Stability(False, float("nan"), float("nan"), 0, 0, 0)
    ranges: dict[str, float] = {}
    flipped: list[tuple[str, str]] = []
    matched = unmatched = 0
    for item_id, runs in grouped.items():
        finite = [r["score"] for r in runs if not is_nan(r["score"])]
        if len(finite) >= 2:
            ranges[item_id] = max(finite) - min(finite)
        verdicts: dict[str, set[bool]] = {}
        seen_in: dict[str, set[int]] = {}
        texts: dict[str, str] = {}
        for run in runs:
            for claim in run.get("claims", []):
                key = _statement_key(claim["statement"])
                texts.setdefault(key, claim["statement"])
                seen_in.setdefault(key, set()).add(run["repeat"])
                if claim["supported"] is not None:
                    verdicts.setdefault(key, set()).add(claim["supported"])
        for key, repeats in seen_in.items():
            if len(repeats) < 2:
                unmatched += 1
                continue
            matched += 1
            if verdicts.get(key) == {True, False}:
                flipped.append((item_id, texts[key]))
    values = list(ranges.values())
    return Stability(
        measured=True,
        mean_range=sum(values) / len(values) if values else float("nan"),
        max_range=max(values) if values else float("nan"),
        flips=len(flipped),
        matched_statements=matched,
        unmatched_statements=unmatched,
        ranges=ranges,
        flipped=flipped,
    )


@dataclass(frozen=True)
class Axes:
    """The two selection axes for one gate-passing candidate."""

    name: str
    faithful_mean: float  # higher is better
    flips: int  # lower is better
    mean_range: float  # lower is better


def _no_worse(a: float, b: float, higher_is_better: bool) -> bool:
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return a >= b - 1e-12 if higher_is_better else a <= b + 1e-12


def dominance(x: Axes, y: Axes) -> str:
    """Verdict between two gate-passing candidates. X is preferred over Y
    only if better-or-equal on both axes ((a) faithful-class mean; (b)
    stability: flips and score range) and strictly better on one."""
    x_a = _no_worse(x.faithful_mean, y.faithful_mean, True)
    y_a = _no_worse(y.faithful_mean, x.faithful_mean, True)
    x_b = _no_worse(x.flips, y.flips, False) and _no_worse(x.mean_range, y.mean_range, False)
    y_b = _no_worse(y.flips, x.flips, False) and _no_worse(y.mean_range, x.mean_range, False)
    if x_a and x_b and y_a and y_b:
        return f"{x.name} and {y.name}: tie on both axes"
    if x_a and x_b:
        return f"{x.name} preferred over {y.name} (better-or-equal on both axes)"
    if y_a and y_b:
        return f"{y.name} preferred over {x.name} (better-or-equal on both axes)"
    better_a = x.name if x_a else y.name
    better_b = x.name if x_b else (y.name if y_b else None)
    stability_note = (
        f"{better_b} more stable" if better_b else "stability split (fewer flips vs. smaller range)"
    )
    return (
        f"trade-off between {x.name} and {y.name}: {better_a} has the higher faithful-class "
        f"mean (fewer false flags), {stability_note}; no preference without the owner's call"
    )


def flagged_faithful_statements(
    items: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Claims judged unsupported in FAITHFUL items: investigation leads,
    each with the judge's reason. Labels are never changed from this."""
    faithful = {item["id"] for item in items if item["label"] == FAITHFUL}
    return [
        {
            "item_id": row["item_id"],
            "repeat": row["repeat"],
            "statement": claim["statement"],
            "reason": claim["reason"],
        }
        for row in rows
        if row["item_id"] in faithful
        for claim in row.get("claims", [])
        if claim["supported"] is False
    ]


def summarize(
    items: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], repeat: int
) -> dict[str, Any]:
    """Everything a judge-mode result records about selection, JSON-ready."""
    gate_result = gate(items, rows, repeat)
    faithful = class_scores(items, rows, FAITHFUL, repeat)
    hallucinated = class_scores(items, rows, HALLUCINATED, repeat)
    stable = stability(rows, repeat)
    return {
        "gate": {
            "passed": gate_result.passed,
            "missed": gate_result.missed,
            "per_origin": {k: list(v) for k, v in gate_result.per_origin.items()},
            "per_perturbation_type": {
                k: list(v) for k, v in gate_result.per_perturbation_type.items()
            },
            "detections": gate_result.detections,
        },
        "faithful_class": {
            "mean": faithful.mean,
            "n_items": faithful.n_items,
            "nan_per_run": {str(k): list(v) for k, v in faithful.nan_per_run.items()},
        },
        "hallucinated_class": {
            "mean": hallucinated.mean,
            "n_items": hallucinated.n_items,
            "nan_per_run": {str(k): list(v) for k, v in hallucinated.nan_per_run.items()},
        },
        "stability": {
            "measured": stable.measured,
            "mean_range": stable.mean_range,
            "max_range": stable.max_range,
            "flips": stable.flips,
            "matched_statements": stable.matched_statements,
            "unmatched_statements": stable.unmatched_statements,
            "flipped": [list(f) for f in stable.flipped],
        },
        "flagged_faithful_statements": flagged_faithful_statements(items, rows),
    }
