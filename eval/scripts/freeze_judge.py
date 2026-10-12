#!/usr/bin/env python3
"""Freezes the faithfulness judge the owner designated as the winner of
judge selection (feat/prompt-comparison, docs/prompts.md "The frozen
judge"): writes `eval/frozen_judge.json` (committed) from that candidate's
judge-mode result file.

Running this IS the owner's designation: the tooling never picks a winner.
It refuses when the result

- is not a judge-mode result;
- failed the gate (or covers only part of the calibration set: the gate
  must rest on every hallucinated item), unless every missed item is named
  with --accept-miss (see below);
- was run with --repeat < 2 (stability unmeasured);
- has faithfulness prompt hashes other than the committed `prompts/`: a
  winning variant is promoted into `prompts/` first, in its own branch, so
  the frozen judge and the judge generation mode runs are the same thing.

--accept-miss ITEM_ID (repeatable, with --justification) is the owner's
explicit exception for a known miss: the gate itself is not loosened. Each
accepted item must be missed in the result, and missed only because the
judge gave the known claim a verdict ("judged supported" in every missed
repeat: never a nan, unevaluated claim or missing run). Any other miss
still refuses, and so does an accepted item the judge actually caught. The
exception, its per-repeat reasons and the justification are written into
the frozen record, whose `gate.passed` stays false.

Usage: python -m eval.scripts.freeze_judge eval/results/prompt_cmp_judge_<...>.json
       [--accept-miss Q008-p1-negation --justification "..."]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.scripts.calibration_set import (
    CALIBRATION_SET_PATH,
    calibration_set_hash,
    load_calibration_set,
)
from eval.scripts.judge_selection import summarize
from eval.scripts.prompt_results import (
    FROZEN_JUDGE_PATH,
    REPO_ROOT,
    committed_faithfulness_hashes,
    faithfulness_hashes,
    git_info,
    load_result,
)


class FreezeRefused(Exception):
    pass


# The only miss reason an exception can cover: a verdict the judge gave.
ACCEPTABLE_MISS_REASON = "judged supported"


def check_accepted_misses(gate: Mapping[str, Any], accepted: Sequence[str]) -> list[str]:
    """Reasons the gate still refuses once the `accepted` misses are set
    aside (empty if it passes, or fails only on accepted items)."""
    reasons = []
    missed = gate["missed"]
    unaccepted = [item_id for item_id in missed if item_id not in accepted]
    if not gate["detections"]:
        reasons.append("the gate failed (missed: no hallucinated item)")
    elif unaccepted:
        reasons.append(f"the gate failed (missed: {', '.join(unaccepted)})")
    for item_id in accepted:
        if item_id not in gate["detections"]:
            reasons.append(f"--accept-miss {item_id}: not a hallucinated item of this result")
        elif item_id not in missed:
            reasons.append(f"--accept-miss {item_id}: not missed (detected in every repeat)")
        else:
            per_repeat = gate["miss_reasons"][item_id]
            other = sorted({r for r in per_repeat if r not in (None, ACCEPTABLE_MISS_REASON)})
            if other:
                reasons.append(
                    f"--accept-miss {item_id}: missed for {', '.join(other)}, not only "
                    f"'{ACCEPTABLE_MISS_REASON}' (only a verdict can be accepted)"
                )
    return reasons


def check_freezable(
    result: Mapping[str, Any],
    calibration: Mapping[str, Any] | None = None,
    accepted_misses: Sequence[str] = (),
) -> dict[str, Any]:
    """The result's selection summary, recomputed from its rows; raises
    `FreezeRefused` naming every reason it can't be frozen."""
    header = result["header"]
    if header["mode"] != "judge":
        raise FreezeRefused(f"not a judge-mode result (mode: {header['mode']})")
    summary = summarize(result["items"], result["rows"], header["repeat"])
    reasons = check_accepted_misses(summary["gate"], accepted_misses)
    if header["repeat"] < 2:
        reasons.append(f"--repeat {header['repeat']} < 2: stability was not measured")
    if calibration is not None:
        if header["items"].get("calibration_set_sha256") != calibration_set_hash(calibration):
            reasons.append("run on another calibration set than the committed one")
        if header["items"]["ids"] != [item["id"] for item in calibration["items"]]:
            reasons.append("run on a subset of the calibration set (--items)")
    run_hashes = faithfulness_hashes(header["manifest"])
    committed = committed_faithfulness_hashes()
    if run_hashes != committed:
        changed = ", ".join(pid for pid in committed if run_hashes.get(pid) != committed[pid])
        reasons.append(
            f"faithfulness hashes differ from the committed prompts/ ({changed}): promote the "
            "winner into prompts/ first (its own branch), then rerun the defaults and freeze that"
        )
    if reasons:
        raise FreezeRefused("; ".join(reasons))
    return summary


def frozen_record(
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    source: Path,
    accepted_misses: Sequence[str] = (),
    justification: str | None = None,
) -> dict[str, Any]:
    header = result["header"]
    manifest = header["manifest"]
    gate = summary["gate"]
    return {
        "description": (
            "The frozen faithfulness judge (eval/scripts/freeze_judge.py, docs/prompts.md): the "
            "owner-designated winner of judge selection. Generation-mode comparisons only run "
            "against it; any change to a faithfulness prompt invalidates earlier ones."
        ),
        "faithfulness_prompts": {
            pid: {"version": manifest[pid]["version"], "hash": manifest[pid]["hash"]}
            for pid in committed_faithfulness_hashes()
        },
        "ragas_version": manifest["library:ragas"]["version"],
        "judge_model": header["models"]["judge"],
        "source_result": str(source.resolve().relative_to(REPO_ROOT))
        if source.resolve().is_relative_to(REPO_ROOT)
        else str(source),
        "gate": {
            "passed": gate["passed"],
            "per_origin": gate["per_origin"],
            "per_perturbation_type": gate["per_perturbation_type"],
            "repeat": header["repeat"],
            "accepted_misses": [
                {
                    "item": item_id,
                    "miss_reasons": gate["miss_reasons"][item_id],
                    "justification": justification,
                }
                for item_id in accepted_misses
            ],
        },
        "faithful_class_mean": summary["faithful_class"]["mean"],
        "result_commit": header["git"]["commit"],
        "commit": git_info()["commit"],
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("result", type=Path, help="The winning candidate's judge-mode result.")
    parser.add_argument("--output", type=Path, default=FROZEN_JUDGE_PATH)
    parser.add_argument("--calibration-set", type=Path, default=CALIBRATION_SET_PATH)
    parser.add_argument(
        "--accept-miss",
        action="append",
        default=[],
        metavar="ITEM_ID",
        help="Freeze despite this known gate miss (repeatable; needs --justification).",
    )
    parser.add_argument(
        "--justification",
        help="Why the accepted misses are tolerated, written into the frozen record.",
    )
    args = parser.parse_args(argv)
    if args.accept_miss and not (args.justification or "").strip():
        parser.error("--accept-miss needs a non-empty --justification")
    if args.justification and not args.accept_miss:
        parser.error("--justification only goes with --accept-miss")
    accepted = list(dict.fromkeys(args.accept_miss))

    result = load_result(args.result)
    try:
        summary = check_freezable(result, load_calibration_set(args.calibration_set), accepted)
    except FreezeRefused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    record = frozen_record(result, summary, args.result, accepted, args.justification)
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output}: commit it. Earlier generation-mode comparisons are now stale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
