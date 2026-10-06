"""Unit tests for src/prompts/loader.py (refactor/prompts-to-files,
docs/prompts.md): hashing, template strictness, examples validation,
overrides, manifest. Pure logic over temporary prompt files — fast.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path

import jinja2
import pytest
from pydantic import BaseModel

from src.generation.faithfulness import SegmentedAnswerInput, SegmentedClaimsOutput
from src.prompts import loader
from src.prompts.loader import (
    PromptError,
    get_prompt_manifest,
    load_examples,
    load_prompt,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

HEADER = "---\nid: demo.greet\nversion: v1\ndescription: A test prompt.\nvariables: [name]\n---\n"
BODY = "Bonjour {{ name }} !\nComment vas-tu ?\n"


@pytest.fixture()
def prompts_dir(tmp_path, monkeypatch):
    """An isolated prompts/ tree; the loader's cache is cleared around it so
    neither side sees the other's files."""
    monkeypatch.setattr(loader, "PROMPTS_DIR", tmp_path)
    loader._load_default.cache_clear()
    (tmp_path / "demo").mkdir()
    yield tmp_path
    loader._load_default.cache_clear()


def _write(prompts_dir: Path, name: str, content: str, newline: str = "\n") -> None:
    with (prompts_dir / "demo" / name).open("w", encoding="utf-8", newline=newline) as f:
        f.write(content)


def _hash_of(prompts_dir: Path, content: str, newline: str = "\n") -> str:
    _write(prompts_dir, "greet.md", content, newline=newline)
    loader._load_default.cache_clear()
    return load_prompt("demo.greet").hash


# --- hashing ----------------------------------------------------------------


def test_crlf_and_lf_line_endings_hash_identically(prompts_dir):
    assert _hash_of(prompts_dir, HEADER + BODY) == _hash_of(
        prompts_dir, HEADER + BODY, newline="\r\n"
    )


def test_crlf_file_renders_with_lf(prompts_dir):
    _write(prompts_dir, "greet.md", HEADER + BODY, newline="\r\n")
    assert "\r" not in load_prompt("demo.greet").render(name="Henri")


def test_one_character_body_change_changes_hash(prompts_dir):
    assert _hash_of(prompts_dir, HEADER + BODY) != _hash_of(
        prompts_dir, HEADER + BODY.replace("!", ".")
    )


def test_header_only_change_keeps_hash(prompts_dir):
    edited_header = HEADER.replace("v1", "v2").replace("A test prompt.", "Reworded.")
    assert _hash_of(prompts_dir, HEADER + BODY) == _hash_of(prompts_dir, edited_header + BODY)


def test_single_file_hash_is_plain_sha256_of_body(prompts_dir):
    import hashlib

    assert _hash_of(prompts_dir, HEADER + BODY) == hashlib.sha256(BODY.encode()).hexdigest()


def test_examples_file_is_part_of_the_hash(prompts_dir):
    header = HEADER.replace("variables: [name]", "variables: [name]\nexamples: [greet.yaml]")
    _write(prompts_dir, "greet.yaml", "- {input: {}, output: {}}\n")
    first = _hash_of(prompts_dir, header + BODY)
    _write(prompts_dir, "greet.yaml", "- {input: {}, output: {}}\n# edited\n")
    assert _hash_of(prompts_dir, header + BODY) != first


# --- template strictness ----------------------------------------------------


def test_missing_template_variable_raises(prompts_dir):
    _write(prompts_dir, "greet.md", HEADER + BODY)
    with pytest.raises(jinja2.UndefinedError):
        load_prompt("demo.greet").render()


def test_unexpected_template_variable_raises(prompts_dir):
    _write(prompts_dir, "greet.md", HEADER + BODY)
    with pytest.raises(PromptError, match="unexpected template variables"):
        load_prompt("demo.greet").render(name="Henri", nom="Henri")


def test_header_variables_must_match_template(prompts_dir):
    _write(prompts_dir, "greet.md", HEADER + BODY + "{{ extra }}\n")
    expected = r"declares variables \['name'\].*uses \['extra', 'name'\]"
    with pytest.raises(PromptError, match=expected):
        load_prompt("demo.greet")


def test_header_id_must_match_path(prompts_dir):
    _write(prompts_dir, "greet.md", HEADER.replace("demo.greet", "demo.other") + BODY)
    with pytest.raises(PromptError, match="doesn't match its path"):
        load_prompt("demo.greet")


def test_missing_header_raises(prompts_dir):
    _write(prompts_dir, "greet.md", BODY)
    with pytest.raises(PromptError, match="missing YAML front-matter"):
        load_prompt("demo.greet")


# --- examples ---------------------------------------------------------------


class _In(BaseModel):
    question: str


class _Out(BaseModel):
    verdict: int


def _examples_prompt(prompts_dir: Path, examples_yaml: str):
    header = "---\nid: demo.judge\nversion: v1\ndescription: d\nvariables: []\n"
    _write(prompts_dir, "judge.md", header + "examples: [judge.yaml]\n---\nJuge.\n")
    _write(prompts_dir, "judge.yaml", examples_yaml)
    return load_prompt("demo.judge")


def test_valid_examples_load_as_models(prompts_dir):
    prompt = _examples_prompt(prompts_dir, "- input: {question: q}\n  output: {verdict: 1}\n")
    assert load_examples(prompt, _In, _Out) == [(_In(question="q"), _Out(verdict=1))]


def test_invalid_example_error_names_example_and_field(prompts_dir):
    prompt = _examples_prompt(
        prompts_dir,
        "- input: {question: q}\n  output: {verdict: 1}\n"
        "- input: {question: q}\n  output: {verdict: oui}\n",
    )
    with pytest.raises(PromptError) as raised:
        load_examples(prompt, _In, _Out)
    message = str(raised.value)
    assert "judge.yaml, example 2 (output, _Out)" in message
    assert "field 'verdict'" in message
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_example_with_a_string_number_is_rejected_not_coerced(prompts_dir):
    prompt = _examples_prompt(prompts_dir, "- input: {question: q}\n  output: {verdict: '1'}\n")
    with pytest.raises(PromptError, match="example 1 .*field 'verdict'"):
        load_examples(prompt, _In, _Out)


def test_example_missing_output_key_is_reported(prompts_dir):
    prompt = _examples_prompt(prompts_dir, "- input: {question: q}\n")
    with pytest.raises(PromptError, match="example 1: expected exactly the keys"):
        load_examples(prompt, _In, _Out)


def test_real_segment_claims_examples_report_nested_field(prompts_dir, monkeypatch):
    """The real models, with a nested error: the path down to the field."""
    prompt = _examples_prompt(
        prompts_dir,
        "- input:\n    question: q\n    segments:\n      - {segment_id: 0, text: t}\n"
        "  output:\n    segments:\n      - {segment_id: zéro, claims: []}\n",
    )
    with pytest.raises(PromptError, match=r"field 'segments\.0\.segment_id'"):
        load_examples(prompt, SegmentedAnswerInput, SegmentedClaimsOutput)


# --- overrides --------------------------------------------------------------


def test_override_is_custom_with_its_own_hash_and_writes_nothing():
    default = load_prompt("judge_chunk.retry")
    path = REPO_ROOT / "prompts" / "judge_chunk" / "retry.md"
    before = path.read_bytes()

    custom = load_prompt("judge_chunk.retry", override_text="Réponds en JSON, s'il te plaît.")

    assert custom.custom is True and default.custom is False
    assert custom.hash != default.hash
    assert custom.render() == "Réponds en JSON, s'il te plaît."
    assert custom.record() == {"version": default.version, "hash": custom.hash, "custom": True}
    assert path.read_bytes() == before
    assert load_prompt("judge_chunk.retry") == default


def test_override_must_keep_the_template_variables():
    with pytest.raises(PromptError, match="declares variables"):
        load_prompt("judge_chunk.relevance", override_text="{{ query }} {{ unknown }}")


# --- manifest, records, packaging -------------------------------------------


def test_manifest_lists_every_prompt_and_the_ragas_version():
    manifest = get_prompt_manifest()
    assert set(manifest) == {
        "faithfulness.nli_verifier",
        "faithfulness.segment_claims",
        "generation.answer",
        "generation.system",
        "judge_chunk.relevance",
        "judge_chunk.retry",
        "judge_chunk.system",
        "library:ragas",
    }
    assert manifest["library:ragas"]["version"] == importlib.metadata.version("ragas")
    assert manifest["library:ragas"]["prompts"]
    for prompt_id, entry in manifest.items():
        if not prompt_id.startswith("library:"):
            assert entry["version"] == "v1"
            assert re.fullmatch(r"[0-9a-f]{64}", entry["hash"])


def test_ragas_wrapped_prompts_record_the_library_version():
    record = load_prompt("faithfulness.nli_verifier").record()
    assert record["library"] == f"ragas=={importlib.metadata.version('ragas')}"
    assert "library" not in load_prompt("generation.answer").record()


def test_prompts_dir_resolves_independently_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loader._load_default.cache_clear()
    try:
        assert loader.PROMPTS_DIR == REPO_ROOT / "prompts"
        assert load_prompt("generation.system").text
    finally:
        loader._load_default.cache_clear()


def test_api_image_ships_prompts_dir():
    """Static half of the container check (the built-image half is
    scripts/test_container_prompts.sh): the Dockerfile copies prompts/ next
    to src/, and .dockerignore doesn't exclude it."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    assert re.search(r"^COPY prompts/ prompts/$", dockerfile, re.MULTILINE)
    ignored = (REPO_ROOT / ".dockerignore").read_text().splitlines()
    assert not any(line.strip().rstrip("/") in {"prompts", "prompts/*", "*.md"} for line in ignored)
    assert os.path.isdir(REPO_ROOT / "prompts")
