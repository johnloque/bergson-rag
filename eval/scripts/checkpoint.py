"""JSONL checkpoint/resume shared by the eval scripts that make slow LLM
calls (`run_ragas_eval.py`, `run_prompt_comparison.py`): every result row
is appended and fsync'd as soon as it's computed, so a run killed mid-way
(observed repeatedly in this environment, unrelated to this project's code)
loses at most the row in flight, and re-running the same command resumes.

Kept free of heavy imports (no RAGAS, Qdrant or embedding models) so tests
and light scripts can use it."""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_checkpoint(path: Path) -> dict[str, dict]:
    """Rows keyed by their `key` field, or `mode:item_id` for rows written
    before keys existed (`run_ragas_eval.py`'s first runs). Later rows win,
    so a resumed run reads back what it last wrote."""
    if not path.exists():
        return {}
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("key") or f"{row['mode']}:{row['item_id']}"
            rows[key] = row
    return rows


def append_checkpoint(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
