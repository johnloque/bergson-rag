"""Prompt-comparison tooling (feat/prompt-comparison, docs/prompts.md
"Comparing prompt variants"). Fast: no LLM, no Qdrant — judge results are
built by hand, `check_faithfulness`/`litellm` are never really called.
The real-model smoke tests are in tests/test_prompt_comparison_smoke.py."""

from __future__ import annotations

import ast
import json
import random
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from eval.scripts import (
    calibration_set,
    compare_prompt_results,
    freeze_judge,
    judge_selection,
    prompt_results,
    prompt_variants,
    run_prompt_comparison,
)
from eval.scripts.calibration_set import GoldRow, MissingText
from eval.scripts.judge_selection import Axes
from eval.scripts.prompt_variants import VariantError
from src.prompts.loader import load_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS = REPO_ROOT / "prompts"


# --- helpers ----------------------------------------------------------------


def _hashes(*ids: str) -> dict[str, str]:
    return {pid: load_prompt(pid).hash for pid in ids}


def make_variant(
    root: Path,
    name: str,
    files: dict[str, str],
    based_on: dict[str, str] | None = None,
    meta: dict[str, Any] | None = None,
    with_yaml: bool = True,
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    for relative, text in files.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if with_yaml:
        if based_on is None:
            touched = {
                prompt_variants.family_of(f"{r.split('/')[0]}.{r.split('/')[1].split('.')[0]}")
                for r in files
            }
            based_on = {
                pid: load_prompt(pid).hash
                for family in touched
                if family
                for pid in prompt_variants.FAMILIES[family]
            }
        data = {
            "name": name,
            "hypothesis": "Observed failure: test.",
            "based_on": based_on,
            "status": "draft",
            "results": [],
            **(meta or {}),
        }
        (directory / "variant.yaml").write_text(json.dumps(data), encoding="utf-8")
    return directory


def default_file(prompt_id: str, transform=lambda body: body + " Changed.") -> str:
    """The default prompt file (header included), body transformed."""
    group, _, name = prompt_id.partition(".")
    raw = (PROMPTS / group / f"{name}.md").read_text(encoding="utf-8")
    end = raw.index("\n---\n", 4) + len("\n---\n")
    return raw[:end] + transform(raw[end:].rstrip("\n")) + "\n"


def item(
    item_id: str,
    label: str = "faithful",
    origin: str = "gold",
    answer: str = "Une phrase. Une autre phrase.",
    substring: str | None = None,
    ptype: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "origin": origin,
        "label": label,
        "source_item": item_id.split("-")[0],
        "category": "cat",
        "answer": answer,
        "chunks": [{"chunk_id": "W_c1", "sha256": "x"}],
        "paragraph_ids": ["W_p1"],
        "fabricated_substring": substring,
        "fabricated_start": answer.index(substring) if substring else None,
        "perturbation": {"type": ptype} if ptype else None,
    }


def row(
    item_id: str,
    repeat: int,
    score: float | None,
    claims: list[tuple[str, bool | None, int]] = (),  # type: ignore[assignment]
    segments: list[tuple[int, int, int]] = ((0, 0, 11), (1, 12, 29)),  # type: ignore[assignment]
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "key": f"fp:{item_id}:r{repeat}",
        "item_id": item_id,
        "repeat": repeat,
        "score": score,
        "error": error,
        "claims": [
            {"statement": s, "supported": v, "reason": "raison", "segment_id": seg}
            for s, v, seg in claims
        ],
        "segments": [{"id": i, "start": a, "end": b} for i, a, b in segments],
        "unevaluated_claims": 0,
    }


HALLU_ANSWER = "Une phrase. Kant a dit cela."  # segment 1 = "Kant a dit cela."
HALLU_SEGMENTS = [(0, 0, 11), (1, 12, 28)]


def judge_items() -> list[dict[str, Any]]:
    return [
        item("Q001"),
        item("Q002"),
        item("Q001-gen", "hallucinated", "generated", HALLU_ANSWER, "Kant"),
        item(
            "Q002-p1-proper_noun", "hallucinated", "perturbed", HALLU_ANSWER, "Kant", "proper_noun"
        ),
    ]


def judge_rows(repeat: int = 2, flag: bool = True, faithful_score: float = 1.0) -> list[dict]:
    rows = []
    for r in range(1, repeat + 1):
        rows += [
            row("Q001", r, faithful_score, [("Une phrase.", True, 0)]),
            row("Q002", r, faithful_score, [("Une autre phrase.", True, 1)]),
        ]
        for hid in ("Q001-gen", "Q002-p1-proper_noun"):
            rows.append(
                row(
                    hid,
                    r,
                    0.5,
                    [("Une phrase.", True, 0), ("Kant a dit cela.", not flag, 1)],
                    HALLU_SEGMENTS,
                )
            )
    return rows


def manifest(**changes: str) -> dict[str, Any]:
    base = prompt_variants.defaults("judge").manifest()
    for pid, digest in changes.items():
        base[pid.replace("__", ".")] = {
            **base[pid.replace("__", ".")],
            "hash": digest,
            "custom": True,
        }
    return base


def result(
    mode: str = "judge",
    label: str = "default",
    manifest_: dict | None = None,
    rows: list[dict] | None = None,
    items: list[dict] | None = None,
    repeat: int = 2,
    models: dict | None = None,
) -> dict[str, Any]:
    items = items if items is not None else judge_items()
    return {
        "header": {
            "banner": "EXPLORATORY",
            "mode": mode,
            "source": {
                "kind": "variant" if label != "default" else "default",
                "label": label,
                "variant": None,
            },
            "overridden_prompts": [],
            "manifest": manifest_ if manifest_ is not None else manifest(),
            "stale": [],
            "models": models or {"judge": "ollama_chat/mistral", "generation": None},
            "temperature": {"judge": 0.0, "generation": None},
            "retrieval": "none",
            "items": {
                "count": len(items),
                "ids": [i["id"] for i in items],
                "per_origin": {},
                "calibration_set_sha256": "c" * 64,
            },
            "repeat": repeat,
            "git": {"commit": "abc", "branch": "b", "dirty": False},
            "frozen_judge": {"matches": None, "status": "n/a"},
        },
        "items": items,
        "rows": rows if rows is not None else judge_rows(repeat),
    }


# --- overlay resolution -----------------------------------------------------


def test_variant_overlay_resolves_only_the_overridden_body(tmp_path):
    body_file = default_file("faithfulness.nli_verifier")
    make_variant(tmp_path, "v1", {"faithfulness/nli_verifier.md": body_file})
    overrides = prompt_variants.load_variant("v1", tmp_path)

    assert overrides.mode == "judge"
    assert overrides.overridden == ("faithfulness.nli_verifier",)
    nli = overrides.prompts["faithfulness.nli_verifier"]
    expected = load_prompt("faithfulness.nli_verifier", override_text=nli.text)
    assert nli.custom and nli.hash == expected.hash
    assert nli.text.rstrip("\n").endswith("Changed.")
    assert nli.examples_paths == load_prompt("faithfulness.nli_verifier").examples_paths
    assert overrides.prompts["faithfulness.segment_claims"] is load_prompt(
        "faithfulness.segment_claims"
    )
    assert not overrides.stale

    entries = overrides.manifest()
    assert entries["faithfulness.nli_verifier"]["custom"] is True
    assert entries["faithfulness.nli_verifier"]["hash"] == nli.hash
    assert entries["faithfulness.segment_claims"]["custom"] is False
    assert entries["judge_chunk.system"]["custom"] is False
    assert entries["library:ragas"]["version"]


def test_unchanged_copy_hashes_like_the_default(tmp_path):
    """Same file format as prompts/: an overlay copied unchanged has the
    default's hash, so the comparison check sees no difference."""
    make_variant(
        tmp_path,
        "same",
        {"faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier", lambda b: b)},
    )
    prompt = prompt_variants.load_variant("same", tmp_path).prompts["faithfulness.nli_verifier"]
    assert prompt.hash == load_prompt("faithfulness.nli_verifier").hash


def test_variant_bare_body_and_generation_mode(tmp_path):
    default = load_prompt("generation.answer")
    make_variant(tmp_path, "g", {"generation/answer.md": default.text + "\nEn bref."})
    overrides = prompt_variants.load_variant("g", tmp_path)
    assert overrides.mode == "generation"
    assert overrides.prompts["generation.answer"].custom


def test_variant_examples_overlay_is_swapped_in_and_rehashed(tmp_path):
    default = load_prompt("faithfulness.nli_verifier")
    examples = default.examples_paths[0].read_text(encoding="utf-8") + "\n# edited\n"
    make_variant(tmp_path, "ex", {f"faithfulness/{default.examples_paths[0].name}": examples})
    prompt = prompt_variants.load_variant("ex", tmp_path).prompts["faithfulness.nli_verifier"]
    assert prompt.custom
    assert prompt.examples_paths == (
        tmp_path / "ex" / "faithfulness" / default.examples_paths[0].name,
    )
    assert prompt.hash != default.hash
    from src.prompts.loader import compute_hash

    assert prompt.hash == compute_hash([default.text, examples])


def test_variant_invalid_examples_fail_when_judge_prompts_are_built(tmp_path):
    from src.generation.faithfulness import build_faithfulness_prompts
    from src.prompts.loader import PromptError

    name = load_prompt("faithfulness.nli_verifier").examples_paths[0].name
    make_variant(tmp_path, "bad", {f"faithfulness/{name}": "- input: {}\n  output: nope\n"})
    overrides = prompt_variants.load_variant("bad", tmp_path)
    with pytest.raises(PromptError):
        build_faithfulness_prompts(
            overrides.prompts["faithfulness.segment_claims"],
            overrides.prompts["faithfulness.nli_verifier"],
        )


@pytest.mark.parametrize(
    ("files", "message"),
    [
        (
            {
                "generation/answer.md": default_file("generation.answer"),
                "faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier"),
            },
            "one variable at a time",
        ),
        ({"judge_chunk/system.md": "x"}, "judge_chunk prompts are out of scope"),
        ({"faithfulness/segment_claims.schema.yaml": "x: {}"}, "schema files can't be overridden"),
        ({"generation/system.md": "x"}, "not a comparable prompt"),
        ({"generation/nope.md": "x"}, "no such file under prompts/"),
        ({}, "has no prompt files"),
    ],
)
def test_variant_refusals(tmp_path, files, message):
    make_variant(tmp_path, "v", files, based_on={})
    with pytest.raises(VariantError, match=message):
        prompt_variants.load_variant("v", tmp_path)


def test_variant_with_judge_chunk_among_valid_files_is_refused(tmp_path):
    make_variant(
        tmp_path,
        "v",
        {
            "faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier"),
            "judge_chunk/retry.md": "x",
        },
    )
    with pytest.raises(VariantError, match="judge_chunk"):
        prompt_variants.load_variant("v", tmp_path)


def test_variant_without_yaml_is_refused_readably(tmp_path):
    make_variant(tmp_path, "v", {"faithfulness/nli_verifier.md": "x"}, with_yaml=False)
    with pytest.raises(VariantError, match="missing variant.yaml"):
        prompt_variants.load_variant("v", tmp_path)


@pytest.mark.parametrize(
    ("meta", "message"),
    [
        ({"status": "winning"}, "status 'winning' not one of"),
        ({"hypothesis": " "}, "observed failure"),
        ({"name": "other"}, "doesn't match its directory"),
        ({"results": "x.json"}, "list of result file paths"),
        ({"extra": 1}, "unknown"),
    ],
)
def test_invalid_variant_yaml_is_refused_readably(tmp_path, meta, message):
    make_variant(
        tmp_path,
        "v",
        {"faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier")},
        meta=meta,
    )
    with pytest.raises(VariantError, match=message):
        prompt_variants.load_variant("v", tmp_path)


def test_variant_yaml_that_isnt_yaml_is_refused(tmp_path):
    directory = make_variant(tmp_path, "v", {"faithfulness/nli_verifier.md": "x"}, with_yaml=False)
    (directory / "variant.yaml").write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(VariantError, match="invalid YAML"):
        prompt_variants.load_variant("v", tmp_path)


def test_overlay_header_must_keep_id_and_variables(tmp_path):
    text = default_file("faithfulness.nli_verifier").replace("variables: []", "variables: [x]")
    make_variant(tmp_path, "v", {"faithfulness/nli_verifier.md": text})
    with pytest.raises(VariantError, match="can't change them"):
        prompt_variants.load_variant("v", tmp_path)


def test_stale_based_on_warns_and_is_flagged_but_does_not_block(tmp_path):
    based_on = _hashes(*prompt_variants.FAITHFULNESS_IDS)
    based_on["faithfulness.nli_verifier"] = "0" * 64
    make_variant(
        tmp_path,
        "old",
        {"faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier")},
        based_on,
    )
    overrides = prompt_variants.load_variant("old", tmp_path)
    assert len(overrides.stale) == 1 and "faithfulness.nli_verifier" in overrides.stale[0]

    args = run_prompt_comparison.parse_args(["--variant", "old", "--repeat", "1"])
    header = run_prompt_comparison.base_header(overrides, args, [item("Q001")])
    assert header["stale"] == list(overrides.stale)
    report = run_prompt_comparison.render_report(
        {
            "header": {
                **header,
                "created": "now",
                "command": "cmd",
                "frozen_judge": {"matches": None, "status": "n/a"},
            },
            "items": [item("Q001")],
            "rows": [],
        }
    )
    assert "STALE VARIANT" in report


def test_based_on_must_cover_the_family(tmp_path):
    make_variant(
        tmp_path,
        "v",
        {"faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier")},
        based_on=_hashes("faithfulness.nli_verifier"),
    )
    with pytest.raises(VariantError, match="based_on"):
        prompt_variants.load_variant("v", tmp_path)


def test_ad_hoc_and_flag_resolution(tmp_path):
    body = tmp_path / "nli.md"
    body.write_text("New instruction.", encoding="utf-8")
    overrides = prompt_variants.resolve(None, [f"faithfulness.nli_verifier={body}"], None)
    assert overrides.kind == "ad hoc" and overrides.mode == "judge"
    assert overrides.ad_hoc_paths == {"faithfulness.nli_verifier": str(body)}
    args = run_prompt_comparison.parse_args(["--prompt", f"faithfulness.nli_verifier={body}"])
    assert run_prompt_comparison.base_header(overrides, args, [])["source"]["label"] == "ad hoc"

    with pytest.raises(VariantError, match="out of scope"):
        prompt_variants.resolve(None, [f"judge_chunk.system={body}"], None)
    with pytest.raises(VariantError, match="one variable"):
        prompt_variants.resolve(
            None, [f"faithfulness.nli_verifier={body}", f"generation.answer={body}"], None
        )
    with pytest.raises(VariantError, match="exclusive"):
        prompt_variants.resolve("v", [f"faithfulness.nli_verifier={body}"], None)
    with pytest.raises(VariantError, match="contradicts"):
        prompt_variants.resolve(None, [f"faithfulness.nli_verifier={body}"], "generation")
    with pytest.raises(VariantError, match="--mode"):
        prompt_variants.resolve(None, None, None)
    assert prompt_variants.resolve(None, None, "judge").kind == "default"


def test_harness_reports_refused_variant_without_running(tmp_path, capsys):
    make_variant(tmp_path, "v", {"judge_chunk/system.md": "x"}, based_on={})
    with mock.patch.object(run_prompt_comparison, "run_judge_mode") as runner:
        code = run_prompt_comparison.main(["--variant", "v", "--variants-dir", str(tmp_path)])
    assert code == 2 and not runner.called
    assert "judge_chunk prompts are out of scope" in capsys.readouterr().err


# --- overrides stay on the eval path ----------------------------------------


def test_defaults_untouched_by_overrides(tmp_path):
    from src.generation import faithfulness
    from src.generation.prompt import ANSWER_PROMPT

    before = (faithfulness._NLI_PROMPT.instruction, ANSWER_PROMPT.hash)
    make_variant(
        tmp_path, "v", {"faithfulness/nli_verifier.md": default_file("faithfulness.nli_verifier")}
    )
    overrides = prompt_variants.load_variant("v", tmp_path)
    custom = faithfulness.build_faithfulness_prompts(
        overrides.prompts["faithfulness.segment_claims"],
        overrides.prompts["faithfulness.nli_verifier"],
    )
    assert custom.nli.instruction.endswith("Changed.")
    assert (faithfulness._NLI_PROMPT.instruction, ANSWER_PROMPT.hash) == before
    assert not load_prompt("faithfulness.nli_verifier").custom
    assert faithfulness.faithfulness_prompts_used() == faithfulness.faithfulness_prompts_used(
        faithfulness.DEFAULT_FAITHFULNESS_PROMPTS
    )
    assert all(not entry["custom"] for entry in faithfulness.faithfulness_prompts_used().values())


def test_generate_from_chunks_uses_answer_prompt_only_when_given():
    import litellm

    from src.generation.generate import generate_from_chunks
    from src.generation.prompt import generation_prompts_used
    from src.retrieval.hybrid import RetrievedChunk

    chunk = RetrievedChunk(
        score=1.0,
        work_id="1907_EC",
        chunk_id="1907_EC_c13",
        section_id="s",
        section_path="p",
        paragraph_ids=["1907_EC_p13"],
        page_start={"display": "1"},
        page_end={"display": "1"},
        text="Texte.",
    )
    custom = load_prompt(
        "generation.answer",
        override_text="Q: {{ query }} {{ chunks }} {{ works }} {{ is_multi_work }} "
        "{{ is_convergent }} {{ is_confident }}",
    )
    reply = litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "R."}}])
    with (
        mock.patch("src.generation.generate.fetch_dense_vectors", return_value={}),
        mock.patch("litellm.completion", return_value=reply) as completion,
    ):
        default_result = generate_from_chunks("Question ?", [chunk], mock.Mock(), fallback_model="")
        custom_result = generate_from_chunks(
            "Question ?", [chunk], mock.Mock(), fallback_model="", answer_prompt=custom
        )
    default_user = completion.call_args_list[0].kwargs["messages"][1]["content"]
    custom_user = completion.call_args_list[1].kwargs["messages"][1]["content"]
    assert not default_user.startswith("Q: Question ?")
    assert custom_user.startswith("Q: Question ?")
    assert default_result.prompts_used == generation_prompts_used()
    assert default_result.prompts_used["generation.answer"]["custom"] is False
    assert custom_result.prompts_used["generation.answer"] == custom.record()


def test_api_and_guardrail_never_pass_prompt_overrides():
    """Overrides are threaded through the eval path only: no call in the API
    or the guardrail passes `prompts=`/`answer_prompt=`."""
    paths = [
        *(REPO_ROOT / "src" / "api").glob("*.py"),
        REPO_ROOT / "src" / "generation" / "guardrail.py",
    ]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                keywords = {k.arg for k in node.keywords}
                assert not keywords & {"prompts", "answer_prompt"}, f"{path.name}:{node.lineno}"


# --- calibration set --------------------------------------------------------

CHUNK = "La durée est continue. Kant n'y est pas. Il écrit en 1907 sur la vie."
Q001_ANSWER = "Dans ce livre, Bergson dit que la durée est continue. Kant le nie en 1907."
GOLD = [
    GoldRow("Q001", "cat", "Question 1 ?", ("W_p1",), Q001_ANSWER),
    GoldRow(
        "Q002",
        "cat",
        "Question 2 ?",
        ("W_p1",),
        "Bergson pense que la vie est un élan. Il le montre.",
    ),
]


def build(labels=(), checkpoint=None, per_item=1, seed=7, chunk=CHUNK):
    return calibration_set.build_calibration_set(
        GOLD,
        {"Q001": ["W_c1"], "Q002": ["W_c1"]},
        {"W_c1": chunk},
        list(labels),
        checkpoint or {},
        seed=seed,
        per_item=per_item,
    )


def test_calibration_items_carry_origin_label_and_chunks():
    data = build()
    gold = [i for i in data["items"] if i["origin"] == "gold"]
    assert [i["id"] for i in gold] == ["Q001", "Q002"]
    assert all(
        i["label"] == "faithful" and i["answer"] == g.expected_answer
        for i, g in zip(gold, GOLD, strict=True)
    )
    assert gold[0]["chunks"] == [{"chunk_id": "W_c1", "sha256": calibration_set.text_hash(CHUNK)}]
    perturbed = [i for i in data["items"] if i["origin"] == "perturbed"]
    assert perturbed and all(i["label"] == "hallucinated" for i in perturbed)
    assert all(i["chunks"] == gold[0]["chunks"] for i in perturbed)  # paired design


def test_gold_chunks_resolve_every_paragraph(tmp_path):
    chunks = [
        {"chunk_id": "1907_EC_c1", "paragraph_ids": ["1907_EC_p1"], "text": "a"},
        {"chunk_id": "1907_EC_c2", "paragraph_ids": ["1907_EC_p2", "1907_EC_p3"], "text": "b"},
    ]
    (tmp_path / "1907_EC.json").write_text(json.dumps(chunks), encoding="utf-8")
    row = GoldRow("Q9", "c", "q", ("1907_EC_p1", "1907_EC_p2", "1907_EC_p3"), "a")
    assert calibration_set.gold_chunk_ids(row, tmp_path) == ["1907_EC_c1", "1907_EC_c2"]


def test_perturbation_is_deterministic_and_stored_as_data():
    first, second = build(per_item=2), build(per_item=2)
    assert first == second
    for entry in (i for i in first["items"] if i["origin"] == "perturbed"):
        edit = entry["perturbation"]
        assert set(edit) == {"source_item", "type", "original_span", "replacement", "start"}
        assert edit["type"] in calibration_set.PERTURBATION_TYPES
        start = entry["fabricated_start"]
        assert (
            entry["answer"][start : start + len(entry["fabricated_substring"])]
            == entry["fabricated_substring"]
        )
        assert not calibration_set.appears_in(edit["replacement"], [CHUNK])


def test_perturbation_types_rotate_deterministically():
    data = build(per_item=1)
    types = [i["perturbation"]["type"] for i in data["items"] if i["origin"] == "perturbed"]
    # Q001 starts at type 0 (proper noun), Q002 at type 1 (year: none in its answer -> next).
    assert types == ["proper_noun", "unsupported_sentence"]
    assert {"item": "Q002", "type": "year", "status": "not applicable"} in data["perturbation_log"]


def test_swaps_only_target_names_and_years_present_in_the_chunks():
    rng = random.Random(0)
    answer = "Dans Le Rire (1900), Bergson cite Kant."
    assert calibration_set.perturb(answer, "proper_noun", rng, ["sans nom propre"]) is None
    assert calibration_set.perturb(answer, "year", rng, ["sans date"]) is None
    edit = calibration_set.perturb(answer, "proper_noun", rng, ["Kant", "Le Rire"])
    assert edit is not None and edit.original_span in ("Kant", "Le Rire")


def test_edit_whose_replacement_appears_in_chunks_is_discarded_and_logged():
    rng_state = random.Random("7:Q001:0:proper_noun")
    planned = calibration_set.perturb(GOLD[0].expected_answer, "proper_noun", rng_state, [CHUNK])
    assert planned is not None
    data = build(chunk=CHUNK + " " + planned.replacement)
    log = data["perturbation_log"]
    assert any(
        e["status"] == "discarded" and e["item"] == "Q001" and e["type"] == "proper_noun"
        for e in log
    )
    assert all(
        i["perturbation"]["replacement"] != planned.replacement
        for i in data["items"]
        if i["origin"] == "perturbed" and i["source_item"] == "Q001"
    )


def test_negation_edits_a_window_not_a_bare_verb():
    edit = calibration_set.perturb(
        "Pour lui, la durée est continue et vécue.", "negation", random.Random(0), []
    )
    assert edit is not None
    assert "n'est pas" in edit.replacement and len(edit.replacement.split()) > 3
    edit = calibration_set.perturb("Pour lui, c'est la durée.", "negation", random.Random(0), [])
    assert edit is not None and "ce n'est pas" in edit.answer.lower()


LABEL = {
    "checkpoint_key": "end_to_end:Q002",
    "label": "hallucinated",
    "fabricated_substring": "un élan cosmique",
    "note": "owner",
}


def test_generated_items_are_copied_verbatim_from_the_checkpoint():
    answer = " Bergson voit la vie comme un élan cosmique. [W_c1]"
    checkpoint = {
        "end_to_end:Q002": {
            "mode": "end_to_end",
            "item_id": "Q002",
            "answer": answer,
            "faithfulness": 1.0,
        },
        "generation_only:Q001": {"mode": "generation_only", "item_id": "Q001", "answer": "x"},
        "rerun:end_to_end:Q002": {"mode": "end_to_end", "item_id": "Q002", "answer": answer},
    }
    data = build([LABEL], checkpoint)
    generated = [i for i in data["items"] if i["origin"] == "generated"]
    assert len(generated) == 1 and generated[0]["answer"] == answer
    assert generated[0]["fabricated_start"] == answer.index("un élan cosmique")
    assert generated[0]["chunks"][0]["chunk_id"] == "W_c1"  # gold chunks
    assert data["unlabeled_checkpoint_items"] == ["generation_only:Q001"]


def test_missing_generated_text_stops_with_a_supply_this_report(tmp_path, capsys):
    with pytest.raises(MissingText, match="end_to_end:Q002"):
        build([LABEL], {})

    labels = tmp_path / "labels.yaml"
    labels.write_text(json.dumps({"generated": [LABEL]}), encoding="utf-8")
    output = tmp_path / "set.json"
    with (
        mock.patch.object(calibration_set, "read_gold_rows", return_value=GOLD),
        mock.patch.object(calibration_set, "load_chunk_texts", return_value={"W_c1": CHUNK}),
        mock.patch.object(calibration_set, "gold_chunk_ids", return_value=["W_c1"]),
    ):
        code = calibration_set.main(
            [
                "--labels",
                str(labels),
                "--checkpoint",
                str(tmp_path / "none.jsonl"),
                "--output",
                str(output),
            ]
        )
    assert code == 1 and not output.exists()
    err = capsys.readouterr().err
    assert "SUPPLY THIS" in err and "end_to_end:Q002" in err and "never reconstructed" in err


def test_label_substring_must_be_verbatim():
    checkpoint = {
        "end_to_end:Q002": {"mode": "end_to_end", "item_id": "Q002", "answer": "autre chose"}
    }
    with pytest.raises(ValueError, match="verbatim"):
        build([LABEL], checkpoint)


def test_chunk_texts_are_checked_against_build_hashes():
    data = build()
    gold = data["items"][0]
    assert calibration_set.resolve_chunk_texts(gold, {"W_c1": CHUNK}) == [CHUNK]
    with pytest.raises(ValueError, match="rebuild"):
        calibration_set.resolve_chunk_texts(gold, {"W_c1": CHUNK + " (re-chunked)"})


def test_held_out_overlap_detected(tmp_path):
    examples = tmp_path / "x.examples.yaml"
    examples.write_text(
        "- input:\n    context: Il dit que la durée est continue et que le temps vécu diffère.\n",
        encoding="utf-8",
    )
    texts = {
        "chunk W_c1": "Ici, il dit que la durée est continue et que le temps vécu diffère beaucoup."
    }
    overlaps = calibration_set.held_out_overlaps(texts, [examples])
    assert overlaps and overlaps[0]["calibration_text"] == "chunk W_c1"
    assert not calibration_set.held_out_overlaps(
        {"a": "Rien de commun ici du tout, vraiment rien."}, [examples]
    )


def test_committed_calibration_set_is_consistent_and_held_out():
    data = calibration_set.load_calibration_set()
    labels = calibration_set.read_labels()
    by_origin: dict[str, list] = {}
    for entry in data["items"]:
        by_origin.setdefault(entry["origin"], []).append(entry)
        if entry["label"] == "hallucinated":
            start = entry["fabricated_start"]
            assert (
                entry["answer"][start : start + len(entry["fabricated_substring"])]
                == entry["fabricated_substring"]
            )
    assert len(by_origin["gold"]) == len(calibration_set.read_gold_rows())
    assert {g["generated"]["checkpoint_key"] for g in by_origin["generated"]} == {
        label["checkpoint_key"] for label in labels
    }
    examples = [
        p for pid in prompt_variants.FAITHFULNESS_IDS for p in load_prompt(pid).examples_paths
    ]
    answers = {f"answer {i['id']}": i["answer"] for i in data["items"]}
    assert calibration_set.held_out_overlaps(answers, examples) == []


# --- gate, axes, stability --------------------------------------------------


def test_flags_known_claim_needs_a_zero_verdict_in_an_overlapping_segment():
    hallu = judge_items()[2]
    assert judge_selection.flags_known_claim(
        row("x", 1, 0.5, [("Kant a dit cela.", False, 1)], HALLU_SEGMENTS), hallu
    )
    assert not judge_selection.flags_known_claim(
        row("x", 1, 0.5, [("Une phrase.", False, 0)], HALLU_SEGMENTS), hallu
    )
    assert not judge_selection.flags_known_claim(
        row("x", 1, 0.5, [("Kant a dit cela.", None, 1)], HALLU_SEGMENTS), hallu
    )


def test_gate_fails_a_variant_flagging_nothing_whatever_its_faithful_mean():
    summary = judge_selection.summarize(
        judge_items(), judge_rows(flag=False, faithful_score=1.0), 2
    )
    assert summary["faithful_class"]["mean"] == 1.0
    assert not summary["gate"]["passed"]
    assert summary["gate"]["missed"] == ["Q001-gen", "Q002-p1-proper_noun"]


def test_gate_fails_when_one_perturbed_item_is_missing():
    rows = [r for r in judge_rows() if r["item_id"] != "Q002-p1-proper_noun"]
    gate = judge_selection.gate(judge_items(), rows, 2)
    assert not gate.passed and gate.missed == ["Q002-p1-proper_noun"]
    assert gate.per_origin == {"generated": (1, 1), "perturbed": (0, 1)}
    assert gate.per_perturbation_type == {"proper_noun": (0, 1)}


def test_gate_requires_every_repeat():
    rows = judge_rows()
    rows[-1]["claims"][1]["supported"] = True  # perturbed item, run 2: missed
    gate = judge_selection.gate(judge_items(), rows, 2)
    assert not gate.passed and gate.detections["Q002-p1-proper_noun"] == [True, False]


def test_gate_passes_and_reports_counts_per_origin():
    gate = judge_selection.gate(judge_items(), judge_rows(), 2)
    assert gate.passed and gate.per_origin == {"generated": (1, 1), "perturbed": (1, 1)}


def test_classes_are_never_pooled():
    summary = judge_selection.summarize(judge_items(), judge_rows(), 2)
    assert summary["faithful_class"]["mean"] == 1.0
    assert summary["hallucinated_class"]["mean"] == 0.5
    assert not {"mean", "overall", "pooled"} & summary.keys()
    lines = compare_prompt_results.class_means([result()])
    assert len(lines) == 4  # header, separator, faithful, hallucinated: no pooled row


def test_dominance_requires_better_or_equal_on_both_axes():
    a = Axes("A", 0.9, 1, 0.05)
    assert "A preferred over B" in judge_selection.dominance(a, Axes("B", 0.8, 2, 0.05))
    assert "B preferred over A" in judge_selection.dominance(a, Axes("B", 0.95, 0, 0.0))
    trade = judge_selection.dominance(a, Axes("B", 0.95, 3, 0.05))
    assert trade.startswith("trade-off") and "owner" in trade
    assert "tie" in judge_selection.dominance(a, Axes("B", 0.9, 1, 0.05))
    split = judge_selection.dominance(a, Axes("B", 0.9, 0, 0.1))
    assert split.startswith("trade-off") and "stability split" in split


def test_repeat_flip_counting():
    rows = [
        row("Q001", 1, 1.0, [("La durée est continue.", True, 0), ("Elle dure.", True, 1)]),
        row("Q001", 2, 0.5, [("La  durée est continue.", False, 0), ("Autre.", True, 1)]),
        row("Q001", 3, 1.0, [("La durée est continue.", True, 0), ("Elle dure.", True, 1)]),
    ]
    stab = judge_selection.stability(rows, 3)
    assert stab.flips == 1 and stab.flipped == [("Q001", "La durée est continue.")]
    assert stab.matched_statements == 2  # "la durée..." and "elle dure."
    assert stab.unmatched_statements == 1  # "autre." seen once
    assert stab.ranges == {"Q001": 0.5}
    assert not judge_selection.stability(rows[:1], 1).measured


def test_nan_runs_are_counted_per_run_never_dropped():
    rows = judge_rows()
    rows[0] = row("Q001", 1, None, error="RagasOutputParserException: x")
    scores = judge_selection.class_scores(judge_items(), rows, "faithful", 2)
    assert scores.nan_per_run == {1: (1, 2), 2: (0, 2)}
    assert scores.mean == 1.0  # Q001's other run still counts
    missing = [r for r in rows if not (r["item_id"] == "Q002" and r["repeat"] == 2)]
    assert judge_selection.class_scores(judge_items(), missing, "faithful", 2).nan_per_run[2] == (
        1,
        2,
    )

    report = run_prompt_comparison.render_report(
        {**result(rows=rows), "summary": judge_selection.summarize(judge_items(), rows, 2)}
        | {"header": {**result()["header"], "created": "t", "command": "c"}}
    )
    assert "Q001 run 1: RagasOutputParserException" in report
    assert "nan per run: run 1: 1/2, run 2: 0/2" in report


def test_faithfulness_row_maps_nan_and_counts_unevaluated_claims():
    from src.generation.faithfulness import ClaimVerdict, FaithfulnessResult
    from src.generation.segmentation import Segment

    out = run_prompt_comparison.faithfulness_row(
        FaithfulnessResult(
            score=float("nan"),
            model="m",
            claims=(ClaimVerdict("c", None, None, 0),),
            segments=(Segment(0, "Une phrase.", 0, 11),),
        )
    )
    assert out["score"] is None and out["unevaluated_claims"] == 1
    assert out["segments"] == [{"id": 0, "start": 0, "end": 11}]
    failed = run_prompt_comparison.failed_row(RuntimeError("boom"))
    assert failed["score"] is None and failed["error"] == "RuntimeError: boom"


def test_run_items_reuses_checkpointed_rows(tmp_path):
    path = tmp_path / "ckpt.jsonl"
    calls = []

    def compute(entry, r):
        calls.append((entry["id"], r))
        return {"score": 1.0, "error": None, "claims": [], "segments": []}

    items = [item("Q001"), item("Q002")]
    run_prompt_comparison.run_items(items, 2, "fp", compute, {}, path)
    assert len(calls) == 4
    from eval.scripts.checkpoint import load_checkpoint

    rows = run_prompt_comparison.run_items(items, 2, "fp", compute, load_checkpoint(path), path)
    assert len(calls) == 4 and len(rows) == 4
    run_prompt_comparison.run_items(items, 2, "other-config", compute, load_checkpoint(path), path)
    assert len(calls) == 8


# --- comparison -------------------------------------------------------------


def test_comparability_one_family_counts_as_one_prompt():
    base = result()
    both = result(
        label="v",
        manifest_=manifest(
            faithfulness__nli_verifier="1" * 64, faithfulness__segment_claims="2" * 64
        ),
    )
    assert compare_prompt_results.comparability_problems([base, both]) == []


@pytest.mark.parametrize(
    ("other", "message"),
    [
        (result(label="v"), "identical"),
        (
            result(
                label="v",
                manifest_=manifest(
                    faithfulness__nli_verifier="1" * 64, generation__answer="2" * 64
                ),
            ),
            "differ in 2 prompts",
        ),
        (
            result(label="v", manifest_=manifest(judge_chunk__system="1" * 64)),
            "not a comparable one",
        ),
        (result(label="v", manifest_=manifest(generation__answer="1" * 64)), "judge-mode results"),
        (
            result(
                label="v",
                manifest_=manifest(faithfulness__nli_verifier="1" * 64),
                items=judge_items()[:3],
                rows=[],
            ),
            "items differ",
        ),
        (
            result(
                label="v",
                manifest_=manifest(faithfulness__nli_verifier="1" * 64),
                models={"judge": "other", "generation": None},
            ),
            "models differs",
        ),
    ],
)
def test_comparability_refusals(other, message):
    problems = compare_prompt_results.comparability_problems([result(), other])
    assert any(message in p for p in problems), problems


def _write(path: Path, data: dict) -> Path:
    prompt_results.write_result(path, data)
    return path


def test_compare_refuses_then_force_stamps_not_comparable(tmp_path, capsys):
    a = _write(tmp_path / "a.json", result())
    b = _write(tmp_path / "b.json", result(label="v"))
    out = tmp_path / "out"
    assert compare_prompt_results.main([str(a), str(b), "--output-dir", str(out)]) == 2
    assert "not comparable" in capsys.readouterr().err
    assert compare_prompt_results.main([str(a), str(b), "--output-dir", str(out), "--force"]) == 0
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    csv_text = next(out.glob("*.csv")).read_text(encoding="utf-8")
    assert "NOT COMPARABLE" in md and csv_text.startswith('"NOT COMPARABLE')


def test_noise_floor_marks_deltas_within_noise():
    base = result()
    rerun = result(
        rows=[{**r, "score": 0.9 if r["item_id"] == "Q001" else r["score"]} for r in judge_rows()]
    )
    floor = compare_prompt_results.noise_floor(base, rerun)
    assert floor["Q001"] == pytest.approx(0.1) and floor["Q002"] == 0.0
    assert compare_prompt_results.noise_marker(0.05, floor["Q001"]) == "within noise"
    assert compare_prompt_results.noise_marker(-0.2, floor["Q001"]) == "outside noise"
    assert compare_prompt_results.noise_marker(0.01, floor["Q002"]) == "outside noise"
    assert compare_prompt_results.noise_marker(0.2, None) == "no noise floor"
    assert compare_prompt_results.noise_marker(float("nan"), 0.1) == "nan"
    with pytest.raises(ValueError, match="not a rerun"):
        compare_prompt_results.noise_floor(
            base, result(manifest_=manifest(faithfulness__nli_verifier="1" * 64))
        )


def test_compare_matrix_and_report(tmp_path):
    variant_rows = judge_rows(faithful_score=0.5)
    variant_rows[0] = row("Q001", 1, None, error="parse")
    a = _write(tmp_path / "a.json", result())
    b = _write(
        tmp_path / "b.json",
        result(
            label="v", manifest_=manifest(faithfulness__nli_verifier="1" * 64), rows=variant_rows
        ),
    )
    rerun = _write(tmp_path / "r.json", result())
    out = tmp_path / "out"
    assert (
        compare_prompt_results.main(
            [str(a), str(b), "--rerun", str(rerun), "--output-dir", str(out)]
        )
        == 0
    )
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "EXPLORATORY" in md and "Differs in**: faithfulness" in md
    assert "nan per run" in md and "run 1: 1/2" in md
    assert "Gate" in md and "PASSED" in md
    assert "trade-off" in md or "preferred" in md
    lines = next(out.glob("*.csv")).read_text(encoding="utf-8").splitlines()
    columns = lines[1].split(",")
    assert columns[:4] == ["id", "category", "origin", "label"]
    q001 = dict(zip(columns, lines[2].split(","), strict=True))
    assert q001["nan runs[v]"] == "1/2" and q001["delta[v]"] == "-0.500"
    assert q001["noise[v]"] == "outside noise" and q001["noise floor"] == "0.000"


def test_compare_without_rerun_makes_no_noise_claim(tmp_path):
    a = _write(tmp_path / "a.json", result())
    b = _write(
        tmp_path / "b.json",
        result(label="v", manifest_=manifest(faithfulness__nli_verifier="1" * 64)),
    )
    out = tmp_path / "out"
    compare_prompt_results.main([str(a), str(b), "--output-dir", str(out)])
    md = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "no noise claim is made" in md and "within noise" not in md


def test_known_issue_items_flagged_from_docs(tmp_path):
    (tmp_path / "issue.md").write_text("Chunk 1907_EC_c13 is truncated.", encoding="utf-8")
    items = [
        {"id": "Q001", "chunk_ids": ["1907_EC_c13"]},
        {"id": "Q002", "chunk_ids": ["1907_EC_c25"]},
    ]
    assert compare_prompt_results.known_issue_items(items, tmp_path) == {"Q001": ["issue.md"]}
    assert compare_prompt_results.known_issue_items(items, tmp_path / "absent") == {}


# --- frozen judge -----------------------------------------------------------


def _committed_result(**kwargs) -> dict:
    return result(manifest_=prompt_variants.defaults("judge").manifest(), **kwargs)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (result(mode="generation"), "not a judge-mode result"),
        (_committed_result(rows=judge_rows(flag=False)), "the gate failed"),
        (_committed_result(repeat=1, rows=judge_rows(repeat=1)), "stability was not measured"),
        (result(manifest_=manifest(faithfulness__nli_verifier="1" * 64)), "promote the winner"),
    ],
)
def test_freeze_judge_refusals(data, message):
    with pytest.raises(freeze_judge.FreezeRefused, match=message):
        freeze_judge.check_freezable(data)


def test_freeze_judge_refuses_a_subset_of_the_calibration_set():
    calibration = {"items": judge_items() + [item("Q003")]}
    data = _committed_result()
    data["header"]["items"]["calibration_set_sha256"] = calibration_set.calibration_set_hash(
        calibration
    )
    with pytest.raises(freeze_judge.FreezeRefused, match="subset"):
        freeze_judge.check_freezable(data, calibration)


def test_freeze_judge_writes_record_and_generation_mode_accepts_it(tmp_path, capsys):
    calibration = {"items": judge_items()}
    data = _committed_result()
    data["header"]["items"]["calibration_set_sha256"] = calibration_set.calibration_set_hash(
        calibration
    )
    source = _write(tmp_path / "winner.json", data)
    cal_path = tmp_path / "cal.json"
    cal_path.write_text(json.dumps(calibration), encoding="utf-8")
    frozen = tmp_path / "frozen_judge.json"
    assert (
        freeze_judge.main(
            [str(source), "--output", str(frozen), "--calibration-set", str(cal_path)]
        )
        == 0
    )
    record = json.loads(frozen.read_text(encoding="utf-8"))
    assert set(record["faithfulness_prompts"]) == set(prompt_variants.FAITHFULNESS_IDS)
    assert record["judge_model"] == "ollama_chat/mistral" and record["gate"]["passed"]
    for key in ("ragas_version", "source_result", "commit", "date"):
        assert record[key]
    assert prompt_results.frozen_judge_status("ollama_chat/mistral", frozen)[0]
    matches, why = prompt_results.frozen_judge_status("other/model", frozen)
    assert not matches and "judge model" in why

    record["faithfulness_prompts"]["faithfulness.nli_verifier"]["hash"] = "0" * 64
    frozen.write_text(json.dumps(record), encoding="utf-8")
    matches, why = prompt_results.frozen_judge_status("ollama_chat/mistral", frozen)
    assert not matches and "faithfulness.nli_verifier" in why


def test_generation_mode_refused_without_a_matching_frozen_judge(tmp_path, capsys):
    missing = tmp_path / "frozen_judge.json"
    with (
        mock.patch.object(prompt_results, "FROZEN_JUDGE_PATH", missing),
        mock.patch.object(
            run_prompt_comparison,
            "frozen_judge_status",
            lambda m: prompt_results.frozen_judge_status(m, missing),
        ),
        mock.patch.object(run_prompt_comparison, "run_generation_mode") as runner,
    ):
        code = run_prompt_comparison.main(["--mode", "generation", "--output-dir", str(tmp_path)])
    assert code == 2 and not runner.called
    err = capsys.readouterr().err
    assert "frozen judge" in err and "--allow-unfrozen-judge" in err


def test_allow_unfrozen_judge_stamps_the_header(tmp_path):
    missing = tmp_path / "frozen_judge.json"
    items = [{"id": "Q001", "origin": "gold", "label": "faithful", "category": "c"}]

    def fake_runner(overrides, args):
        header = run_prompt_comparison.base_header(overrides, args, items)
        return (
            header,
            items,
            {"compute": lambda i, r: {"score": 1.0, "error": None, "claims": [], "segments": []}},
        )

    with (
        mock.patch.object(
            run_prompt_comparison,
            "frozen_judge_status",
            lambda m: prompt_results.frozen_judge_status(m, missing),
        ),
        mock.patch.object(run_prompt_comparison, "run_generation_mode", fake_runner),
    ):
        code = run_prompt_comparison.main(
            [
                "--mode",
                "generation",
                "--allow-unfrozen-judge",
                "--repeat",
                "1",
                "--output-dir",
                str(tmp_path),
                "--checkpoint",
                str(tmp_path / "c.jsonl"),
            ]  # fmt: skip
        )
    assert code == 0
    data = json.loads(
        next(tmp_path.glob("prompt_cmp_generation_default_*.json")).read_text(encoding="utf-8")
    )
    assert data["header"]["frozen_judge"]["matches"] is False
    assert data["header"]["frozen_judge"]["status"].startswith(prompt_results.NOT_FROZEN)
    md = next(tmp_path.glob("prompt_cmp_generation_default_*.md")).read_text(encoding="utf-8")
    assert prompt_results.NOT_FROZEN in md and "EXPLORATORY" in md
    header = data["header"]
    for key in (
        "manifest",
        "models",
        "temperature",
        "mode",
        "retrieval",
        "items",
        "git",
        "source",
        "stale",
    ):
        assert key in header
    assert header["git"]["dirty"] in (True, False)
