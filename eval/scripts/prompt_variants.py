"""Prompt variants for the prompt-comparison harness (feat/prompt-comparison,
docs/prompts.md "Comparing prompt variants").

A variant is `eval/prompt_variants/<name>/`: a partial overlay of `prompts/`
(same layout, only the files that differ) plus a `variant.yaml`. This module
resolves a variant, an ad hoc `--prompt <id>=<path>` set, or the committed
defaults into one `PromptOverrides`: the effective `Prompt` of every
comparable prompt id, the run mode the overridden files imply, and whether
the variant was written against defaults that have since changed.

Rules enforced here, not left to the reader:

- Only `generation.answer` and the faithfulness family
  (`faithfulness.segment_claims` + `faithfulness.nli_verifier`, their
  examples files included) are comparable. `judge_chunk/` files are refused:
  chunk judgments have no ground truth to score a variant against.
- One variable at a time: generation and faithfulness files in the same
  variant are refused. The faithfulness family counts as one variable.
- Bodies go through `load_prompt(id, override_text=...)`. That API replaces
  the body only, so an overlaid examples file is swapped in here: same
  prompt, the overlay's examples path, re-hashed with the loader's own
  `compute_hash` (same order: body, examples, schema). Examples are
  validated when the judge prompts are built
  (`src.generation.faithfulness.build_faithfulness_prompts`). Schema files
  are refused: their descriptions are compiled into Pydantic classes at
  import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from src.prompts.loader import (
    PROMPTS_DIR,
    Prompt,
    PromptError,
    all_prompt_ids,
    compute_hash,
    get_prompt_manifest,
    load_prompt,
    normalize_newlines,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VARIANTS_DIR = REPO_ROOT / "eval" / "prompt_variants"
VARIANT_FILE = "variant.yaml"
STATUSES = ("draft", "tested", "rejected", "promoted")
_VARIANT_KEYS = {"name", "hypothesis", "based_on", "status", "results"}

Mode = Literal["judge", "generation"]
MODES: tuple[Mode, ...] = ("judge", "generation")

# A family is one variable: comparing two results is allowed only if they
# differ in exactly one family (eval/scripts/compare_prompt_results.py).
FAMILIES: dict[str, tuple[str, ...]] = {
    "generation.answer": ("generation.answer",),
    "faithfulness": ("faithfulness.segment_claims", "faithfulness.nli_verifier"),
}
FAMILY_MODE: dict[str, Mode] = {"generation.answer": "generation", "faithfulness": "judge"}
COMPARABLE_IDS = tuple(pid for ids in FAMILIES.values() for pid in ids)
FAITHFULNESS_IDS = FAMILIES["faithfulness"]


def family_of(prompt_id: str) -> str | None:
    for family, ids in FAMILIES.items():
        if prompt_id in ids:
            return family
    return None


class VariantError(ValueError):
    """A variant or ad hoc override can't be used; the message says why."""


@dataclass(frozen=True)
class VariantMeta:
    name: str
    hypothesis: str
    based_on: dict[str, str]  # prompt id -> default hash when the variant was created
    status: str
    results: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class PromptOverrides:
    """The prompts one harness run uses. `prompts` holds every comparable
    prompt id, overridden or not; anything else is the committed default."""

    kind: Literal["default", "variant", "ad hoc"]
    mode: Mode
    prompts: dict[str, Prompt]
    overridden: tuple[str, ...] = ()
    variant: VariantMeta | None = None
    ad_hoc_paths: dict[str, str] = field(default_factory=dict)
    stale: tuple[str, ...] = ()  # why `based_on` no longer matches the defaults

    @property
    def label(self) -> str:
        if self.kind == "variant":
            assert self.variant is not None
            return self.variant.name
        return "adhoc" if self.kind == "ad hoc" else "default"

    def manifest(self) -> dict[str, dict[str, Any]]:
        """`get_prompt_manifest()` with every prompt's full record (custom
        flag, library version) and this run's overrides in place."""
        manifest = get_prompt_manifest()
        for prompt_id in all_prompt_ids():
            manifest[prompt_id] = (self.prompts.get(prompt_id) or load_prompt(prompt_id)).record()
        return manifest


def _overlay_map() -> dict[str, tuple[str, str]]:
    """Overlay path (relative to `prompts/`) -> (prompt id, "body" | "examples")
    for every file a variant may contain."""
    allowed: dict[str, tuple[str, str]] = {}
    for prompt_id in COMPARABLE_IDS:
        group, _, name = prompt_id.partition(".")
        allowed[f"{group}/{name}.md"] = (prompt_id, "body")
        for path in load_prompt(prompt_id).examples_paths:
            allowed[f"{group}/{path.name}"] = (prompt_id, "examples")
    return allowed


def _refusal(relative: str) -> str:
    if relative.startswith("judge_chunk/"):
        return (
            f"{relative}: judge_chunk prompts are out of scope for comparison "
            "(no ground truth to score a variant against)"
        )
    if relative.endswith(".schema.yaml"):
        return (
            f"{relative}: schema files can't be overridden (their field descriptions are "
            "compiled into Pydantic classes at import, src/generation/faithfulness.py)"
        )
    if (PROMPTS_DIR / relative).is_file():
        return f"{relative}: not a comparable prompt (only {', '.join(COMPARABLE_IDS)})"
    return f"{relative}: no such file under prompts/ (an overlay mirrors prompts/' layout)"


def _overlay_body(path: Path, default: Prompt) -> str:
    """The body of an overlay prompt file. A copied file keeps its
    front-matter header; it must name the same prompt and declare the same
    variables (an override reuses the default's header). A bare body is
    accepted too."""
    raw = normalize_newlines(path.read_text(encoding="utf-8"))
    if not raw.startswith("---\n"):
        return raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        raise VariantError(f"{path}: unterminated front-matter header (no closing '---')")
    try:
        header = yaml.safe_load(raw[4 : end + 1]) or {}
    except yaml.YAMLError as error:
        raise VariantError(f"{path}: invalid front-matter YAML: {error}") from None
    if not isinstance(header, dict):
        raise VariantError(f"{path}: front-matter header must be a YAML mapping")
    if header.get("id", default.id) != default.id:
        raise VariantError(f"{path}: header id {header['id']!r} doesn't match {default.id!r}")
    variables = header.get("variables", list(default.variables))
    variables = [variables] if isinstance(variables, str) else list(variables or [])
    if set(variables) != set(default.variables):
        raise VariantError(
            f"{path}: declares variables {sorted(variables)}, the default "
            f"{default.id} has {sorted(default.variables)} (an override can't change them)"
        )
    return raw[end + len("\n---\n") :]


def _with_examples(prompt: Prompt, overlay: dict[str, Path]) -> Prompt:
    """`prompt` with its examples files replaced by the overlay's (matched by
    file name), re-hashed exactly as the loader hashes a prompt."""
    examples = tuple(overlay.get(path.name, path) for path in prompt.examples_paths)
    extra = (*examples, *((prompt.schema_path,) if prompt.schema_path else ()))
    texts = [prompt.text, *(path.read_text(encoding="utf-8") for path in extra)]
    return replace(prompt, examples_paths=examples, hash=compute_hash(texts), custom=True)


def _check_family(overridden: set[str], where: str) -> Mode:
    families = {family_of(pid) for pid in overridden}
    if len(families) > 1:
        raise VariantError(
            f"{where} overrides both generation and faithfulness prompts: one variable at a "
            "time (split it into two variants)"
        )
    return FAMILY_MODE[families.pop()]  # type: ignore[index]


def _read_meta(directory: Path) -> VariantMeta:
    path = directory / VARIANT_FILE
    if not path.is_file():
        raise VariantError(
            f"variant {directory.name!r}: missing {VARIANT_FILE} (required keys: "
            f"{', '.join(sorted(_VARIANT_KEYS))}; see eval/prompt_variants/README.md)"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise VariantError(f"{path}: invalid YAML: {error}") from None
    if not isinstance(data, dict):
        raise VariantError(f"{path}: expected a YAML mapping")
    missing = _VARIANT_KEYS - data.keys()
    unknown = data.keys() - _VARIANT_KEYS
    if missing or unknown:
        problems = [
            f"missing {sorted(missing)}" if missing else "",
            f"unknown {sorted(unknown)}" if unknown else "",
        ]
        raise VariantError(f"{path}: {'; '.join(p for p in problems if p)} keys")
    if data["name"] != directory.name:
        raise VariantError(f"{path}: name {data['name']!r} doesn't match its directory")
    if not isinstance(data["hypothesis"], str) or not data["hypothesis"].strip():
        raise VariantError(f"{path}: 'hypothesis' must name the observed failure it targets")
    if data["status"] not in STATUSES:
        raise VariantError(f"{path}: status {data['status']!r} not one of {', '.join(STATUSES)}")
    based_on = data["based_on"]
    if not isinstance(based_on, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in based_on.items()
    ):
        raise VariantError(f"{path}: 'based_on' must map each prompt id to its default hash")
    results = data["results"] or []
    if not isinstance(results, list) or not all(isinstance(r, str) for r in results):
        raise VariantError(f"{path}: 'results' must be a list of result file paths")
    return VariantMeta(
        name=data["name"],
        hypothesis=data["hypothesis"].strip(),
        based_on=dict(based_on),
        status=data["status"],
        results=tuple(results),
        path=directory,
    )


def load_variant(name: str, variants_dir: Path = VARIANTS_DIR) -> PromptOverrides:
    directory = variants_dir / name
    if not directory.is_dir():
        available = (
            sorted(p.name for p in variants_dir.iterdir() if p.is_dir())
            if variants_dir.is_dir()
            else []
        )
        raise VariantError(
            f"no variant {name!r} in {variants_dir} (available: {available or 'none'})"
        )
    meta = _read_meta(directory)

    allowed = _overlay_map()
    refusals: list[str] = []
    bodies: dict[str, Path] = {}
    examples: dict[str, dict[str, Path]] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if not path.is_file() or path.name.startswith(".") or relative == VARIANT_FILE:
            continue
        if relative not in allowed:
            refusals.append(_refusal(relative))
            continue
        prompt_id, kind = allowed[relative]
        if kind == "body":
            bodies[prompt_id] = path
        else:
            examples.setdefault(prompt_id, {})[path.name] = path
    if refusals:
        raise VariantError(f"variant {name!r} refused:\n  - " + "\n  - ".join(refusals))
    overridden = set(bodies) | set(examples)
    if not overridden:
        raise VariantError(f"variant {name!r} has no prompt files (nothing to compare)")
    mode = _check_family(overridden, f"variant {name!r}")

    prompts = {pid: load_prompt(pid) for pid in COMPARABLE_IDS}
    for prompt_id in sorted(overridden):
        try:
            prompt = load_prompt(prompt_id)
            if prompt_id in bodies:
                body = _overlay_body(bodies[prompt_id], prompt)
                prompt = load_prompt(prompt_id, override_text=body)
            if prompt_id in examples:
                prompt = _with_examples(prompt, examples[prompt_id])
        except PromptError as error:
            raise VariantError(f"variant {name!r}: {error}") from None
        prompts[prompt_id] = prompt

    family = FAMILIES[next(f for f in FAMILIES if overridden & set(FAMILIES[f]))]
    if set(meta.based_on) != set(family):
        raise VariantError(
            f"{directory / VARIANT_FILE}: 'based_on' must list the default hash of each prompt "
            f"in the family it changes: {', '.join(family)} (got {sorted(meta.based_on)})"
        )
    stale = tuple(
        f"{pid}: variant based on {meta.based_on[pid][:12]}, current default is "
        f"{load_prompt(pid).hash[:12]}"
        for pid in family
        if meta.based_on[pid] != load_prompt(pid).hash
    )
    return PromptOverrides(
        kind="variant",
        mode=mode,
        prompts=prompts,
        overridden=tuple(sorted(overridden)),
        variant=meta,
        stale=stale,
    )


def load_ad_hoc(specs: list[str]) -> PromptOverrides:
    """`--prompt <id>=<path>` overrides (bodies only, repeatable)."""
    bodies: dict[str, Path] = {}
    for spec in specs:
        prompt_id, sep, raw_path = spec.partition("=")
        if not sep or not raw_path:
            raise VariantError(f"--prompt {spec!r}: expected <prompt id>=<path>")
        if prompt_id.startswith("judge_chunk."):
            raise VariantError(
                f"--prompt {prompt_id}: judge_chunk prompts are out of scope for comparison "
                "(no ground truth to score a variant against)"
            )
        if prompt_id not in COMPARABLE_IDS:
            raise VariantError(
                f"--prompt {prompt_id}: not a comparable prompt (only {', '.join(COMPARABLE_IDS)})"
            )
        if prompt_id in bodies:
            raise VariantError(f"--prompt {prompt_id} given twice")
        path = Path(raw_path)
        if not path.is_file():
            raise VariantError(f"--prompt {prompt_id}: no such file {path}")
        bodies[prompt_id] = path
    if not bodies:
        raise VariantError("no --prompt given")
    mode = _check_family(set(bodies), "--prompt")
    prompts = {pid: load_prompt(pid) for pid in COMPARABLE_IDS}
    for prompt_id, path in bodies.items():
        try:
            body = _overlay_body(path, prompts[prompt_id])
            prompts[prompt_id] = load_prompt(prompt_id, override_text=body)
        except PromptError as error:
            raise VariantError(f"--prompt {prompt_id}: {error}") from None
    return PromptOverrides(
        kind="ad hoc",
        mode=mode,
        prompts=prompts,
        overridden=tuple(sorted(bodies)),
        ad_hoc_paths={pid: str(path) for pid, path in sorted(bodies.items())},
    )


def defaults(mode: Mode) -> PromptOverrides:
    """The committed prompts, run like any variant (`--mode` with no
    override)."""
    return PromptOverrides(
        kind="default", mode=mode, prompts={pid: load_prompt(pid) for pid in COMPARABLE_IDS}
    )


def resolve(
    variant: str | None,
    prompt_specs: list[str] | None,
    mode: Mode | None,
    variants_dir: Path = VARIANTS_DIR,
) -> PromptOverrides:
    """What the harness's `--variant`/`--prompt`/`--mode` flags select. The
    mode follows from the overridden files; `--mode` is required only for a
    defaults run, and must agree otherwise."""
    if variant and prompt_specs:
        raise VariantError("--variant and --prompt are exclusive (one variable at a time)")
    if variant:
        overrides = load_variant(variant, variants_dir)
    elif prompt_specs:
        overrides = load_ad_hoc(prompt_specs)
    elif mode is None:
        raise VariantError(
            "no --variant or --prompt: pass --mode judge|generation to run the defaults"
        )
    else:
        return defaults(mode)
    if mode is not None and mode != overrides.mode:
        raise VariantError(
            f"--mode {mode} contradicts the overridden files ({', '.join(overrides.overridden)} "
            f"imply {overrides.mode} mode)"
        )
    return overrides
