"""Slow smoke tests for the prompt-comparison harness, one per mode, with
throwaway fixture variants (tests/fixtures/prompt_variants/): plumbing only
(a real model call goes in, a result file with the right header comes out),
no claim about any score. The fast tests are tests/test_prompt_comparison.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.scripts import run_prompt_comparison
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR
from tests.test_faithfulness import _collection_populated, _model_reachable

FIXTURE_VARIANTS = Path(__file__).resolve().parent / "fixtures" / "prompt_variants"
MODEL = run_prompt_comparison.DEFAULT_MODEL

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not _model_reachable(MODEL), reason=f"no reachable model ({MODEL})"),
    pytest.mark.skipif(
        not DEFAULT_CHUNKS_DIR.is_dir(), reason="data/processed/chunks missing (run ingestion)"
    ),
]


def _single_result(directory: Path, mode: str) -> dict:
    (path,) = directory.glob(f"prompt_cmp_{mode}_*.json")
    assert path.with_suffix(".md").is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def test_judge_mode_smoke(tmp_path):
    code = run_prompt_comparison.main(
        [
            "--variant",
            "smoke_judge",
            "--variants-dir",
            str(FIXTURE_VARIANTS),
            "--items",
            "Q006",
            "--repeat",
            "1",
            "--output-dir",
            str(tmp_path),
            "--checkpoint",
            str(tmp_path / "ckpt.jsonl"),
        ]  # fmt: skip
    )
    assert code == 0
    result = _single_result(tmp_path, "judge")
    header = result["header"]
    assert header["mode"] == "judge" and header["source"]["label"] == "smoke_judge"
    assert header["manifest"]["faithfulness.nli_verifier"]["custom"] is True
    assert header["manifest"]["faithfulness.segment_claims"]["custom"] is False
    assert header["items"]["per_origin"] == {"gold": 1, "perturbed": 1}
    assert {row["item_id"] for row in result["rows"]} == {i["id"] for i in result["items"]}
    assert "gate" in result["summary"]


@pytest.mark.skipif(not _collection_populated(), reason="Qdrant not reachable or index empty")
def test_generation_mode_smoke(tmp_path):
    code = run_prompt_comparison.main(
        [
            "--variant",
            "smoke_generation",
            "--variants-dir",
            str(FIXTURE_VARIANTS),
            "--items",
            "Q001",
            "--repeat",
            "1",
            "--allow-unfrozen-judge",
            "--output-dir",
            str(tmp_path),
            "--checkpoint",
            str(tmp_path / "ckpt.jsonl"),
        ]  # fmt: skip
    )
    assert code == 0
    result = _single_result(tmp_path, "generation")
    header = result["header"]
    assert header["manifest"]["generation.answer"]["custom"] is True
    (row,) = result["rows"]
    assert row["answer"] and row["prompts_used"]["generation.answer"]["custom"] is True
    assert header["temperature"]["generation"] == 0.0
