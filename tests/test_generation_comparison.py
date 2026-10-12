"""Generation-variant comparison (docs/prompts.md, "Choosing a generation
variant"): the gate, the axes, substance, the polarity review list, the
generation-mode harness's records, and both reports. No model call, no
data/processed."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from eval.scripts import (
    compare_prompt_results,
    generation_selection,
    generation_variant_report,
    prompt_results,
    prompt_variants,
    run_prompt_comparison,
)
from src.generation.faithfulness import JUDGE_INPUT_VERSION

ANSWER = "Bergson parle de durée [W_c1]. La durée n'est pas mesurable."
# segment 0 = first sentence, segment 1 = the negated one
SEGMENTS = [(0, 0, 30), (1, 31, len(ANSWER))]


def gen_item(item_id: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "origin": "gold",
        "label": "faithful",
        "category": "cat",
        "query": f"Question {item_id} ?",
        "chunk_ids": ["W_c1"],
    }


def gen_row(
    item_id: str,
    repeat: int,
    score: float | None = 1.0,
    answer: str | None = ANSWER,
    negated_supported: bool | None = True,
    error: str | None = None,
    chunks_sha256: str = "h" * 64,
) -> dict[str, Any]:
    claims = []
    if answer is not None and not error:
        claims = [
            {
                "statement": "Bergson parle de durée.",
                "supported": True,
                "reason": "r",
                "segment_id": 0,
            },
            {
                "statement": "La durée n'est pas mesurable.",
                "supported": negated_supported,
                "reason": "r",
                "segment_id": 1,
            },
        ]
    return {
        "key": f"fp:{item_id}:r{repeat}",
        "item_id": item_id,
        "repeat": repeat,
        "score": score,
        "error": error,
        "claims": claims,
        "segments": [{"id": i, "start": a, "end": b} for i, a, b in SEGMENTS]
        if answer is not None
        else [],
        "unevaluated_claims": 0,
        "answer": answer,
        "num_chunks": 1,
        "chunk_ids": ["W_c1"],
        "chunks_sha256": chunks_sha256,
    }


def gen_manifest(**changes: str) -> dict[str, Any]:
    base = prompt_variants.defaults("generation").manifest()
    for pid, digest in changes.items():
        pid = pid.replace("__", ".")
        base[pid] = {**base[pid], "hash": digest, "custom": True}
    return base


def gen_result(
    label: str = "default",
    rows: list[dict] | None = None,
    repeat: int = 2,
    manifest_: dict | None = None,
    gold_sha: str = "g" * 64,
) -> dict[str, Any]:
    items = [gen_item("Q001"), gen_item("Q002")]
    if rows is None:
        rows = [gen_row(i["id"], r) for i in items for r in range(1, repeat + 1)]
    return {
        "header": {
            "banner": "EXPLORATORY",
            "mode": "generation",
            "source": {"kind": "default" if label == "default" else "variant", "label": label},
            "overridden_prompts": [],
            "manifest": manifest_ if manifest_ is not None else gen_manifest(),
            "stale": [],
            "models": {"judge": "ollama_chat/mistral", "generation": "ollama_chat/mistral"},
            "temperature": {"judge": 0.0, "generation": 0.0},
            "retrieval": "bypassed",
            "judge_input_version": JUDGE_INPUT_VERSION,
            "items": {
                "count": len(items),
                "ids": [i["id"] for i in items],
                "per_origin": {"gold": len(items)},
                "gold_set_sha256": gold_sha,
            },
            "repeat": repeat,
            "git": {"commit": "abc", "branch": "b", "dirty": False},
            "frozen_judge": {"matches": True, "status": "matches frozen_judge.json", "record": {}},
        },
        "items": items,
        "rows": rows,
    }


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


VARIANT_MANIFEST = gen_manifest(generation__answer="1" * 64)


# --- analysis ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "markers"),
    [
        ("La durée n'est pas mesurable.", ["pas"]),
        ("Elle ne se mesure jamais.", ["jamais"]),
        ("Il n’y a rien de tel.", ["rien"]),
        ("Ce n'est qu'une image.", []),  # ne ... que: a restriction
        ("Elle ne retient que l'utile.", []),
        ("Un point de vue plus large.", []),  # no ne: not negations
        ("Un temps sans durée, ni mesure.", ["ni", "sans"]),
    ],
)
def test_negation_markers(text, markers):
    assert generation_selection.negation_markers(text) == markers


def test_gate_fails_on_a_fabricated_title_in_any_repeat():
    fabricated = "Bergson l'écrit dans un ouvrage intitulé « Le Rire des dieux » [W_c1]."
    rows = [gen_row("Q001", 1), gen_row("Q001", 2, answer=fabricated), gen_row("Q002", 1)]
    gate = generation_selection.gate([gen_item("Q001"), gen_item("Q002")], rows, 2)
    assert not gate["passed"]
    assert gate["failures"] == {
        "Q001": [
            {"repeat": 2, "fabricated_titles": ["Le Rire des dieux"], "title_year_mismatches": []}
        ]
    }


def test_gate_flags_a_real_title_with_a_wrong_year():
    answer = "Dans l'ouvrage intitulé « L'Évolution créatrice » (1922), Bergson écrit ceci."
    gate = generation_selection.gate([gen_item("Q001")], [gen_row("Q001", 1, answer=answer)], 1)
    (failure,) = gate["failures"]["Q001"]
    assert failure["title_year_mismatches"][0]["claimed"] == [1922]


def test_gate_passes_and_a_failed_generation_is_not_a_fabrication():
    rows = [gen_row("Q001", 1), gen_row("Q002", 1, score=None, answer=None, error="Timeout")]
    gate = generation_selection.gate([gen_item("Q001"), gen_item("Q002")], rows, 1)
    assert gate["passed"] and gate["answers_checked"] == 1 and gate["runs_expected"] == 2
    summary = generation_selection.summarize([gen_item("Q001"), gen_item("Q002")], rows, 1)
    assert summary["generation_failures"] == [{"item_id": "Q002", "repeat": 1, "error": "Timeout"}]
    assert summary["faithfulness"]["nan_per_run"] == {"1": [1, 2]}


def test_substance_counts_claims_only_where_the_judge_answered():
    judge_failed = gen_row("Q002", 1, score=None, error="parse failure")
    rows = [gen_row("Q001", 1), judge_failed]
    sub = generation_selection.substance([gen_item("Q001"), gen_item("Q002")], rows, 1)
    assert sub["claims_per_answer"] == {"1": 2.0}  # not (2 + 0) / 2
    assert sub["answers_with_citation"] == {"1": [2, 2]}
    assert sub["answer_chars"]["1"] == len(ANSWER)


def test_substance_lists_citations_to_chunks_not_given():
    answer = "La durée est continue [W_c1] [X_c9]."
    sub = generation_selection.substance([gen_item("Q001")], [gen_row("Q001", 1, answer=answer)], 1)
    assert sub["unknown_citations"] == [{"item_id": "Q001", "repeat": 1, "citations": ["X_c9"]}]


def test_identical_answers_across_repeats():
    rows = [
        gen_row("Q001", 1),
        gen_row("Q001", 2),
        gen_row("Q002", 1),
        gen_row("Q002", 2, answer=ANSWER + " Autre."),
    ]
    assert generation_selection.identical_answers(rows) == {
        "identical": ["Q001"],
        "varied": ["Q002"],
    }


def test_polarity_review_lists_negated_segments_the_judge_accepted():
    accepted = generation_selection.polarity_review([gen_row("Q001", 1)])
    assert accepted == [
        {
            "item_id": "Q001",
            "repeat": 1,
            "segment": "La durée n'est pas mesurable.",
            "markers": ["pas"],
            "claims": ["La durée n'est pas mesurable."],
        }
    ]
    # Flagged by the judge: already among the unsupported claims.
    assert generation_selection.polarity_review([gen_row("Q001", 1, negated_supported=False)]) == []
    # A segment no claim was drawn from is listed too: nothing judged it.
    no_claim = {**gen_row("Q001", 1), "claims": []}
    assert len(generation_selection.polarity_review([no_claim])) == 1


def test_new_segments_drop_what_the_baseline_already_wrote_for_that_item():
    review = generation_selection.polarity_review([gen_row("Q001", 1), gen_row("Q002", 1)])
    baseline = [gen_row("Q001", 1)]
    new = generation_selection.new_segments(review, baseline)
    assert [e["item_id"] for e in new] == ["Q002"]


def test_fewer_claims_warning_only_when_higher_and_saying_less():
    warn = generation_selection.fewer_claims_warning
    assert "saying less" in warn(0.6, 5.0, 0.8, 3.0, "v")
    assert warn(0.6, 5.0, 0.8, 6.0, "v") is None
    assert warn(0.6, 5.0, 0.5, 3.0, "v") is None
    assert warn(float("nan"), 5.0, 0.8, 3.0, "v") is None


def test_dominance_names_the_generation_axis():
    from eval.scripts.judge_selection import Axes, dominance

    verdict = dominance(
        Axes("a", 0.9, 3, 0.1), Axes("b", 0.8, 1, 0.05), generation_selection.FAITHFULNESS_AXIS
    )
    assert "trade-off" in verdict and "faithfulness mean (fewer unsupported claims)" in verdict


# --- comparability ----------------------------------------------------------


def test_generation_results_with_another_gold_set_or_chunk_text_are_not_comparable():
    variant = gen_result("v", manifest_=VARIANT_MANIFEST, gold_sha="x" * 64)
    problems = compare_prompt_results.comparability_problems([gen_result(), variant])
    assert any("gold set differs" in p for p in problems), problems

    rows = [gen_row("Q001", 1, chunks_sha256="z" * 64), gen_row("Q002", 1)]
    variant = gen_result("v", rows=rows, repeat=1, manifest_=VARIANT_MANIFEST)
    problems = compare_prompt_results.comparability_problems([gen_result(repeat=1), variant])
    assert problems == ["gold chunk text differs between runs on Q001 (re-indexed?)"]


def test_compare_generation_report_has_axes_warning_and_new_polarity(tmp_path):
    base = _write(tmp_path / "b.json", gen_result())
    shorter = "La durée n'est jamais mesurée."
    rows = [
        {
            **gen_row(i, r, answer=shorter),
            "claims": [{"statement": shorter, "supported": True, "reason": "r", "segment_id": 0}],
            "segments": [{"id": 0, "start": 0, "end": len(shorter)}],
        }
        for i in ("Q001", "Q002")
        for r in (1, 2)
    ]
    base_data = json.loads(base.read_text(encoding="utf-8"))
    for row in base_data["rows"]:
        row["score"] = 0.5
    _write(base, base_data)
    var = _write(tmp_path / "v.json", gen_result("v", rows=rows, manifest_=VARIANT_MANIFEST))
    out = tmp_path / "out"
    assert compare_prompt_results.main([str(base), str(var), "--output-dir", str(out)]) == 0
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "Gate: no fabricated work title" in md
    assert "v preferred over default" in md
    assert "**Warning**: v scores higher (1.000 vs 0.500) with fewer claims" in md
    assert "**v**: 2" in md and "La durée n'est jamais mesurée." in md


# --- generation variant report ----------------------------------------------


def test_generation_variant_report_baseline_alone(tmp_path):
    rerun_rows = [gen_row(i, r) for i in ("Q001", "Q002") for r in (1, 2)]
    rerun_rows[0]["score"] = 0.5  # Q001 repeat 1
    b1 = _write(tmp_path / "b1.json", gen_result())
    b2 = _write(tmp_path / "b2.json", gen_result(rows=rerun_rows))
    out = tmp_path / "out"
    assert (
        generation_variant_report.main(["--baseline", str(b1), str(b2), "--output-dir", str(out)])
        == 0
    )
    report = json.loads(next(out.glob("prompt_cmp_genbase_*.json")).read_text(encoding="utf-8"))
    base = report["baseline"]
    assert base["noise_floor"]["nonzero"] == {"Q001": pytest.approx(0.25)}
    assert base["pooled_stability"]["repeats"] == 4
    assert base["pooled_stability"]["identical"] == ["Q001", "Q002"]
    assert len(base["distinct_polarity_review"]) == 2  # one segment per item, deduplicated
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert md.startswith("# Generation baseline") and "EXPLORATORY" in md
    assert "Polarity review: negated segments the judge accepted" in md


def test_generation_variant_report_vs_variant(tmp_path):
    b1 = _write(tmp_path / "b1.json", gen_result())
    b2 = _write(tmp_path / "b2.json", gen_result())
    new_answer = ANSWER + " Elle n'est jamais spatiale."
    rows = []
    for i in ("Q001", "Q002"):
        for r in (1, 2):
            row = gen_row(i, r, score=0.5, answer=new_answer)
            row["segments"].append({"id": 2, "start": len(ANSWER) + 1, "end": len(new_answer)})
            row["claims"].append(
                {
                    "statement": "Elle est spatiale.",
                    "supported": False,
                    "reason": "non",
                    "segment_id": 0,
                }
            )
            rows.append(row)
    var = _write(tmp_path / "v.json", gen_result("v", rows=rows, manifest_=VARIANT_MANIFEST))
    out = tmp_path / "out"
    argv = ["--baseline", str(b1), str(b2), "--variant", str(var), "--output-dir", str(out)]
    assert generation_variant_report.main(argv) == 0
    report = json.loads(next(out.glob("prompt_cmp_genvs_v_*.json")).read_text(encoding="utf-8"))
    assert [c["statement"] for c in report["newly_unsupported"]] == ["Elle est spatiale."] * 2
    assert [e["segment"] for e in report["new_polarity_review"]] == [
        "Elle n'est jamais spatiale."
    ] * 2
    q001 = report["items"][0]
    assert q001["delta"] == pytest.approx(-0.5) and q001["noise"] == "outside noise"
    assert report["fewer_claims_warning"] is None  # lower score, more claims
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "default preferred over v" in md
    assert "newly asserted by the variant" in md


def test_generation_variant_report_refusals(tmp_path, capsys):
    b1 = _write(tmp_path / "b1.json", gen_result())
    b2 = _write(tmp_path / "b2.json", gen_result())
    out = tmp_path / "out"
    argv = ["--baseline", str(b1), str(b2), "--output-dir", str(out)]
    assert generation_variant_report.main([*argv, "--variant", str(b1)]) == 2
    assert "not comparable" in capsys.readouterr().err
    judge = gen_result()
    judge["header"]["mode"] = "judge"
    j = _write(tmp_path / "j.json", judge)
    assert generation_variant_report.main([*argv, "--variant", str(j)]) == 2
    assert "generation-mode result files only" in capsys.readouterr().err
    reindexed = gen_result(
        rows=[gen_row(i, r, chunks_sha256="z" * 64) for i in ("Q001", "Q002") for r in (1, 2)]
    )
    b3 = _write(tmp_path / "b3.json", reindexed)
    assert (
        generation_variant_report.main(["--baseline", str(b1), str(b3), "--output-dir", str(out)])
        == 2
    )
    assert "different gold chunk text" in capsys.readouterr().err


# --- harness: generation mode -----------------------------------------------


def _chunk(chunk_id: str, text: str = "Texte du chunk.") -> SimpleNamespace:
    return SimpleNamespace(chunk_id=chunk_id, text=text)


def test_generation_mode_records_chunks_refuses_missing_ones_and_summarizes(tmp_path):
    gold = [
        SimpleNamespace(id="Q001", category="c", query="Q1 ?", chunk_ids=("W_c1",)),
        SimpleNamespace(id="Q002", category="c", query="Q2 ?", chunk_ids=("W_c1", "W_c2")),
    ]
    judged = SimpleNamespace(score=1.0, claims=[], segments=[])
    generated = SimpleNamespace(answer="Réponse [W_c1].", prompts_used={})
    frozen = tmp_path / "frozen_judge.json"
    record = json.loads(prompt_results.FROZEN_JUDGE_PATH.read_text(encoding="utf-8"))
    frozen.write_text(json.dumps(record), encoding="utf-8")
    with (
        mock.patch("eval.scripts.run_eval.load_gold_dataset", return_value=gold),
        mock.patch(
            "eval.scripts.run_ragas_eval.load_gold_chunks",
            side_effect=lambda client, ids: [_chunk("W_c1")],  # W_c2 not in the index
        ),
        mock.patch("eval.scripts.run_ragas_eval.generation_extra_params", return_value={}),
        mock.patch("qdrant_client.QdrantClient"),
        mock.patch("src.generation.faithfulness.build_judge_llm"),
        mock.patch("src.generation.faithfulness.check_faithfulness", return_value=judged),
        mock.patch(
            "src.generation.generate.generate_from_chunks", return_value=generated
        ) as generate,
        mock.patch.object(prompt_results, "FROZEN_JUDGE_PATH", frozen),
        mock.patch.object(
            run_prompt_comparison,
            "frozen_judge_status",
            lambda m: prompt_results.frozen_judge_status(m, frozen),
        ),
        mock.patch.object(
            run_prompt_comparison,
            "frozen_judge_record",
            lambda: prompt_results.frozen_judge_record(frozen),
        ),
    ):
        code = run_prompt_comparison.main(
            [
                "--mode",
                "generation",
                "--repeat",
                "1",
                "--output-dir",
                str(tmp_path),
                "--checkpoint",
                str(tmp_path / "c.jsonl"),
            ]  # fmt: skip
        )
    assert code == 0
    assert generate.call_count == 1  # Q002 never generated from fewer chunks
    data = json.loads(
        next(tmp_path.glob("prompt_cmp_generation_*.json")).read_text(encoding="utf-8")
    )
    q001, q002 = data["rows"]
    assert q001["chunk_ids"] == ["W_c1"] and len(q001["chunks_sha256"]) == 64
    assert q002["answer"] is None and "W_c2" in q002["error"]
    header = data["header"]
    assert len(header["items"]["gold_set_sha256"]) == 64
    assert header["frozen_judge"]["record"]["accepted_misses"][0]["item"] == "Q008-p1-negation"
    assert header["frozen_judge"]["record"]["judge_input_version"] == JUDGE_INPUT_VERSION
    assert data["summary"]["gate"]["passed"]
    assert data["summary"]["generation_failures"][0]["item_id"] == "Q002"
    md = next(tmp_path.glob("prompt_cmp_generation_*.md")).read_text(encoding="utf-8")
    assert "Polarity review" in md and "Q008-p1-negation" in md


def test_gold_set_and_chunk_hashes_move_with_their_inputs():
    item = gen_item("Q001")
    assert run_prompt_comparison.gold_set_hash([item]) != run_prompt_comparison.gold_set_hash(
        [{**item, "chunk_ids": ["W_c2"]}]
    )
    assert run_prompt_comparison.chunks_hash([_chunk("W_c1")]) != run_prompt_comparison.chunks_hash(
        [_chunk("W_c1", "Autre texte.")]
    )
