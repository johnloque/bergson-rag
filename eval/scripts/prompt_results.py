"""Result files of the prompt-comparison harness, and the frozen judge
(feat/prompt-comparison, docs/prompts.md).

A result file (`eval/results/prompt_cmp_<mode>_<label>_n<N>_<ts>.json`, with
a `.md` report beside it) is `{header, rows, summary}`. The header records
everything a comparison must check: the full prompt manifest (every prompt,
hash, custom flag, RAGAS version), models, temperature, mode, retrieval
config, items and their origins, commit and dirty flag, the variant (or
"ad hoc"/"default"), staleness, and the frozen-judge match status.

`eval/frozen_judge.json` records the faithfulness judge chosen by the owner
(`eval/scripts/freeze_judge.py`); generation mode only runs against it.
"""

from __future__ import annotations

import importlib.metadata
import json
import math
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eval.scripts.prompt_variants import FAITHFULNESS_IDS
from src.prompts.loader import load_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = REPO_ROOT / "eval" / "results"
FROZEN_JUDGE_PATH = REPO_ROOT / "eval" / "frozen_judge.json"
DEFAULT_CHECKPOINT_PATH = RESULTS_DIR / "prompt_comparison_checkpoint.jsonl"

# docs/gold_dataset_protocol.md: below this, every number is exploratory.
PROTOCOL_TARGET_N = 50
NOT_FROZEN = "JUDGE NOT FROZEN/MISMATCH"
NOT_COMPARABLE = "NOT COMPARABLE"


def exploratory_banner(n: int) -> str:
    return (
        f"EXPLORATORY: n={n} items, below the n={PROTOCOL_TARGET_N} volume threshold "
        "(docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling "
        "never picks a winner: the owner does."
    )


def git_info() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            return "unknown"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(run("status", "--porcelain")),
    }


def ragas_version() -> str:
    return importlib.metadata.version("ragas")


def faithfulness_hashes(manifest: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    return {pid: manifest[pid]["hash"] for pid in FAITHFULNESS_IDS}


def committed_faithfulness_hashes() -> dict[str, str]:
    return {pid: load_prompt(pid).hash for pid in FAITHFULNESS_IDS}


def frozen_judge_status(judge_model: str, path: Path = FROZEN_JUDGE_PATH) -> tuple[bool, str]:
    """(matches, explanation): whether `path` exists and records the
    committed faithfulness prompts, the installed RAGAS and `judge_model`."""
    if not path.is_file():
        return False, f"{path.name} not found: no judge has been frozen yet"
    frozen = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    committed = committed_faithfulness_hashes()
    for pid, digest in committed.items():
        recorded = frozen.get("faithfulness_prompts", {}).get(pid, {}).get("hash")
        if recorded != digest:
            problems.append(
                f"{pid}: frozen {str(recorded)[:12]}, committed {digest[:12]} (a faithfulness "
                "prompt changed since the judge was frozen)"
            )
    if frozen.get("ragas_version") != ragas_version():
        problems.append(f"ragas: frozen {frozen.get('ragas_version')}, installed {ragas_version()}")
    if frozen.get("judge_model") != judge_model:
        problems.append(f"judge model: frozen {frozen.get('judge_model')}, this run {judge_model}")
    if problems:
        return False, "; ".join(problems)
    return (
        True,
        f"matches {path.name} (frozen {frozen.get('date')} from {frozen.get('source_result')})",
    )


def _jsonable(value: Any) -> Any:
    """NaN -> None, recursively: result files are strict JSON."""
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def result_paths(
    mode: str, label: str, n: int, timestamp: str, output_dir: Path
) -> tuple[Path, Path]:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
    stem = output_dir / f"prompt_cmp_{mode}_{safe}_n{n}_{timestamp}"
    return stem.with_suffix(".json"), stem.with_suffix(".md")


def write_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(_jsonable(result), ensure_ascii=False, indent=2, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def load_result(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not {"header", "rows"} <= data.keys():
        raise ValueError(f"{path}: not a prompt-comparison result file (no header/rows)")
    return data


def score_of(row: Mapping[str, Any]) -> float:
    return float("nan") if row["score"] is None else float(row["score"])
