"""Generation-variant analysis over generation-mode result rows
(docs/prompts.md "Choosing a generation variant"). Pure functions: no LLM,
no I/O.

A result row is one generation of one gold question, judged by the frozen
judge: the judge-mode row (`{item_id, repeat, score (None = nan/failure),
error, claims, segments}`) plus `answer` (None if generation failed),
`chunk_ids` and `chunks_sha256` (the gold chunks actually given).

1. Gate (deterministic, no judge): no answer, in any repeat, names a work
   title the corpus doesn't have or pairs a real title with a wrong year
   (`src/generation/guardrail.py`, Layer 1: the checks the guardrail itself
   blocks on). Failing it rejects a candidate whatever its scores.
2. Among candidates passing the gate, two axes side by side, never a
   composite: (a) mean faithfulness by the frozen judge (higher = fewer
   unsupported claims); (b) stability over repeats: per-item score range and
   verdict flips (`judge_selection.stability`), with the number of items
   whose answer is identical in every repeat beside it. Dominance is
   `judge_selection.dominance`.
3. Substance is reported beside the axes, never folded into them: claims
   per answer, answer length, citations. An answer that says less has fewer
   claims to get wrong, so a faithfulness gain that comes with fewer claims
   is flagged.
4. The frozen judge doesn't reliably catch a negation that reverses a
   sentence (docs/prompts.md, "Frozen judge: baseline v3"): answer segments
   with a negation marker that the judge accepted are listed for reading by
   hand. A reading aid, over-inclusive on purpose, not a detector.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eval.scripts.judge_selection import (
    FAITHFUL,
    _statement_key,
    class_scores,
    flagged_faithful_statements,
    is_nan,
    rows_by_item,
    stability,
)

# Axis (a)'s name in `judge_selection.dominance` verdicts.
FAITHFULNESS_AXIS = "faithfulness mean (fewer unsupported claims)"

# "ne/n' ... pas" and its kin only count with a "ne"/"n'" in the segment:
# "plus", "point", "personne" alone are not negations.
_NE = re.compile(r"\bne\b|\bn'")
_WITH_NE = re.compile(r"\b(pas|plus|jamais|rien|aucune?|guère|point|nullement|personne)\b")
_ALONE = re.compile(r"\b(non|sans|ni|jamais|aucune?|nullement)\b")


def negation_markers(text: str) -> list[str]:
    """Negation words in `text` (French), sorted, de-duplicated. "ne ...
    que" (restriction) is not one."""
    folded = text.casefold().replace("’", "'")
    found = set(_ALONE.findall(folded))
    if _NE.search(folded):
        found |= set(_WITH_NE.findall(folded))
    return sorted(found)


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str


def structure(row: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Layer 1 of the guardrail on this run's answer, against the gold
    chunks it was given (None if generation failed)."""
    from src.generation.guardrail import check_structure

    if row.get("answer") is None:
        return None
    chunk_ids = row.get("chunk_ids") or item.get("chunk_ids", [])
    check = check_structure(row["answer"], [_Chunk(c) for c in chunk_ids])
    return {
        "citations": list(check.citations),
        "unknown_citations": list(check.unknown_citations),
        "fabricated_titles": list(check.fabricated_titles),
        "title_year_mismatches": [
            {"title": m.title, "correct_year": m.correct_year, "claimed": list(m.claimed_years)}
            for m in check.title_year_mismatches
        ],
    }


def gate(
    items: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]], repeat: int
) -> dict[str, Any]:
    """Every fabricated title and title/year mismatch, per item and repeat.
    A failed generation is not a fabrication: it is counted as nan, next to
    every mean, like any other failure."""
    grouped = rows_by_item(rows)
    failures: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        for run in grouped.get(item["id"], []):
            check = structure(run, item)
            if check and (check["fabricated_titles"] or check["title_year_mismatches"]):
                failures.setdefault(item["id"], []).append(
                    {
                        "repeat": run["repeat"],
                        "fabricated_titles": check["fabricated_titles"],
                        "title_year_mismatches": check["title_year_mismatches"],
                    }
                )
    generated = sum(r.get("answer") is not None for runs in grouped.values() for r in runs)
    return {
        "passed": generated > 0 and not failures,
        "failures": failures,
        "answers_checked": generated,
        "runs_expected": len(items) * repeat,
    }


def _per_run_mean(values: Mapping[int, list[float]]) -> dict[str, float]:
    return {str(r): (sum(v) / len(v) if v else float("nan")) for r, v in sorted(values.items())}


def substance(
    items: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]], repeat: int
) -> dict[str, Any]:
    """How much each answer says, and how it cites, per repeat (generated
    answers only; failed generations are nan elsewhere)."""
    grouped = rows_by_item(rows)
    claims: dict[int, list[float]] = {r: [] for r in range(1, repeat + 1)}
    length: dict[int, list[float]] = {r: [] for r in range(1, repeat + 1)}
    cites: dict[int, list[float]] = {r: [] for r in range(1, repeat + 1)}
    cited: dict[int, list[int]] = {r: [0, 0] for r in range(1, repeat + 1)}
    unknown: list[dict[str, Any]] = []
    for item in items:
        for run in grouped.get(item["id"], []):
            check = structure(run, item)
            if check is None or run["repeat"] not in claims:
                continue
            r = run["repeat"]
            if not run.get("error"):  # a judge failure extracted no claim: not "said nothing"
                claims[r].append(len(run.get("claims", [])))
            length[r].append(len(run["answer"]))
            cites[r].append(len(check["citations"]))
            cited[r][0] += bool(check["citations"])
            cited[r][1] += 1
            if check["unknown_citations"]:
                unknown.append(
                    {"item_id": item["id"], "repeat": r, "citations": check["unknown_citations"]}
                )
    all_claims = [c for values in claims.values() for c in values]
    return {
        "claims_per_answer": _per_run_mean(claims),
        "mean_claims_per_answer": sum(all_claims) / len(all_claims) if all_claims else float("nan"),
        "answer_chars": _per_run_mean(length),
        "citations_per_answer": _per_run_mean(cites),
        "answers_with_citation": {str(r): v for r, v in cited.items()},
        "unknown_citations": unknown,
    }


def identical_answers(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Items whose answer is byte-identical in every repeat (temperature 0
    is close to deterministic, not exactly)."""
    same, varied = [], []
    for item_id, runs in rows_by_item(rows).items():
        answers = [r.get("answer") for r in runs]
        if len(answers) < 2 or None in answers:
            continue
        (same if len(set(answers)) == 1 else varied).append(item_id)
    return {"identical": sorted(same), "varied": sorted(varied)}


def segment_text(row: Mapping[str, Any], segment: Mapping[str, Any]) -> str:
    return row["answer"][segment["start"] : segment["end"]]


def polarity_review(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Answer segments with a negation marker that the judge didn't flag
    (every claim drawn from it supported, or none drawn): the frozen judge
    can't be relied on to catch an inverted polarity there."""
    out = []
    for row in rows:
        if row.get("answer") is None:
            continue
        for segment in row.get("segments", []):
            text = segment_text(row, segment)
            markers = negation_markers(text)
            if not markers:
                continue
            claims = [c for c in row.get("claims", []) if c["segment_id"] == segment["id"]]
            if any(c["supported"] is False for c in claims):
                continue  # flagged: already among the unsupported claims
            out.append(
                {
                    "item_id": row["item_id"],
                    "repeat": row["repeat"],
                    "segment": text.strip(),
                    "markers": markers,
                    "claims": [c["statement"] for c in claims],
                }
            )
    return out


def distinct_segments(review: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """`review` entries, one per (item, segment text): the first repeat's."""
    seen: dict[tuple[str, str], Mapping[str, Any]] = {}
    for entry in review:
        seen.setdefault((entry["item_id"], _statement_key(entry["segment"])), entry)
    return list(seen.values())


def new_segments(
    review: Sequence[Mapping[str, Any]], baseline_rows: Iterable[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Entries of `review` whose segment appears in no baseline answer of
    the same item: what a variant newly asserts with a negation."""
    seen: dict[str, set[str]] = {}
    for row in baseline_rows:
        if row.get("answer") is None:
            continue
        for segment in row.get("segments", []):
            seen.setdefault(row["item_id"], set()).add(_statement_key(segment_text(row, segment)))
    return [e for e in review if _statement_key(e["segment"]) not in seen.get(e["item_id"], set())]


def summarize(
    items: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], repeat: int
) -> dict[str, Any]:
    """Everything a generation-mode result records about selection, JSON-ready."""
    scores = class_scores(items, rows, FAITHFUL, repeat)
    stable = stability(rows, repeat)
    return {
        "gate": gate(items, rows, repeat),
        "faithfulness": {
            "mean": scores.mean,
            "n_items": scores.n_items,
            "nan_per_run": {str(k): list(v) for k, v in scores.nan_per_run.items()},
            "unevaluated_per_run": {str(k): list(v) for k, v in scores.unevaluated_per_run.items()},
        },
        "stability": {
            "measured": stable.measured,
            "mean_range": stable.mean_range,
            "max_range": stable.max_range,
            "flips": stable.flips,
            "matched_statements": stable.matched_statements,
            "unmatched_statements": stable.unmatched_statements,
            "flipped": [list(f) for f in stable.flipped],
            **identical_answers(rows),
        },
        "substance": substance(items, rows, repeat),
        "unsupported_claims": flagged_faithful_statements(items, rows),
        "polarity_review": polarity_review(rows),
        "generation_failures": [
            {"item_id": r["item_id"], "repeat": r["repeat"], "error": r["error"]}
            for r in rows
            if r.get("answer") is None
        ],
    }


def fewer_claims_warning(
    base_mean: float, base_claims: float, mean: float, claims: float, name: str
) -> str | None:
    """A sentence when candidate `name` scores higher than the baseline
    while saying less (fewer claims per answer): its gain may come from
    fewer claims, not better ones."""
    if any(is_nan(v) for v in (base_mean, base_claims, mean, claims)):
        return None
    if mean > base_mean and claims < base_claims:
        return (
            f"{name} scores higher ({mean:.3f} vs {base_mean:.3f}) with fewer claims per answer "
            f"({claims:.1f} vs {base_claims:.1f}): the gain may come from saying less. Read the "
            "answers before crediting it."
        )
    return None
