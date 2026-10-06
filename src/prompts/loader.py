"""Loads the LLM prompts versioned under `prompts/` (refactor/prompts-to-files,
docs/prompts.md) — the single source of truth for every prompt text this
project sends to an LLM. No prompt wording lives in Python any more.

## File format

`prompts/<group>/<name>.md`, with id `<group>.<name>` (enforced: the id in
the header must match the path). A YAML front-matter header, then the body:

    ---
    id: generation.answer
    version: v1
    description: One line.
    variables: [query, chunks]
    examples: [answer.examples.yaml]   # optional, files next to this one
    schema: answer.schema.yaml          # optional, see "Output schema"
    library: ragas                      # optional, see "Library dependency"
    ---
    <body: the exact prompt text, a Jinja2 template>

The body is rendered with Jinja2 (`StrictUndefined`, `trim_blocks`,
`lstrip_blocks`, no autoescape; the body's single trailing newline is not
part of the output). `variables` must list exactly the template's free
variables — checked at load time, so a header and its template can't drift
apart.

## Output schema

A RAGAS `PydanticPrompt` sends its output model's JSON schema to the LLM,
field descriptions included — prompt text, so it lives here too. The
`schema` file maps each output model to its fields' descriptions
(`load_field_descriptions`); the Python models read their descriptions
from it, and are checked against it (no field undescribed, no entry
without a field).

## Hash

`sha256` over the body, then each examples file in header order, then the
schema file, all with line endings normalized to LF, joined with a NUL byte
(so a one-file prompt's hash is just `sha256` of its body). The header is
excluded: editing a description or version label doesn't make a "new"
prompt. The template is hashed, not the rendered text, which varies with
every input.

## Library dependency

A prompt declaring `library: ragas` is sent wrapped in that library's own
text (RAGAS's `PydanticPrompt` framing: output-schema sentence, example
separators, "Now perform the same..."), which this project doesn't own. The
record of such a prompt therefore carries the installed library version
too, since that text changes with it.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Any

import jinja2
import jinja2.meta
import yaml
from pydantic import BaseModel, ValidationError

# Resolved from this file, never from the working directory: identical
# locally, under pytest, and in the API image (Dockerfile copies prompts/
# next to src/).
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

_HEADER_KEYS = {"id", "version", "description", "variables", "examples", "schema", "library"}
_REQUIRED_HEADER_KEYS = {"id", "version", "description", "variables"}

_ENV = jinja2.Environment(
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
)

# Prompts used through RAGAS without being overridden by this project — they
# live in the library and change with its version. Listed in the manifest
# with that version (docs/prompts.md).
LIBRARY_PROMPTS: dict[str, tuple[str, ...]] = {
    "ragas": (
        "PydanticPrompt.to_string framing around faithfulness.* prompts",
        "FixOutputFormat (retry on unparseable judge output)",
        "NLIStatementInput/NLIStatementOutput JSON schemas",
        "ContextPrecisionPrompt (eval/scripts/run_ragas_eval.py only)",
        "ContextRecallClassificationPrompt (eval/scripts/run_ragas_eval.py only)",
    ),
}


class PromptError(ValueError):
    """A prompt file or examples file is malformed."""


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compute_hash(parts: Sequence[str]) -> str:
    joined = "\0".join(normalize_newlines(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _library_version(library: str) -> str:
    return f"{library}=={importlib.metadata.version(library)}"


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    description: str
    variables: tuple[str, ...]
    text: str  # the body (template source), LF line endings
    hash: str
    custom: bool
    examples_paths: tuple[Path, ...] = ()
    schema_path: Path | None = None
    library: str | None = None  # e.g. "ragas==0.3.9"
    _template: jinja2.Template = field(repr=False, compare=False, default=None)  # type: ignore[assignment]

    def render(self, **variables: Any) -> str:
        unexpected = set(variables) - set(self.variables)
        if unexpected:
            raise PromptError(f"{self.id}: unexpected template variables {sorted(unexpected)}")
        return self._template.render(**variables)

    def record(self) -> dict[str, Any]:
        """This prompt's entry in a `prompts_used` column (src/api/models.py)."""
        entry: dict[str, Any] = {"version": self.version, "hash": self.hash, "custom": self.custom}
        if self.library is not None:
            entry["library"] = self.library
        return entry

    @property
    def extra_paths(self) -> tuple[Path, ...]:
        """Files hashed after the body, in hash order."""
        return (*self.examples_paths, *((self.schema_path,) if self.schema_path else ()))


def prompts_used(*prompts: Prompt) -> dict[str, dict[str, Any]]:
    return {prompt.id: prompt.record() for prompt in prompts}


def _path_for(prompt_id: str) -> Path:
    group, _, name = prompt_id.partition(".")
    if not group or not name or "/" in prompt_id or ".." in prompt_id:
        raise PromptError(f"invalid prompt id {prompt_id!r} (expected '<group>.<name>')")
    return PROMPTS_DIR / group / f"{name}.md"


def _split_front_matter(path: Path, raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        raise PromptError(f"{path}: missing YAML front-matter header (must start with '---')")
    end = raw.find("\n---\n", 4)
    if end == -1:
        raise PromptError(f"{path}: unterminated front-matter header (no closing '---')")
    header = yaml.safe_load(raw[4 : end + 1]) or {}
    if not isinstance(header, dict):
        raise PromptError(f"{path}: front-matter header must be a YAML mapping")
    return header, raw[end + len("\n---\n") :]


def _compile(prompt_id: str, body: str, variables: Sequence[str]) -> jinja2.Template:
    try:
        parsed = _ENV.parse(body)
    except jinja2.TemplateSyntaxError as error:
        message = f"{prompt_id}: template syntax error line {error.lineno}: {error}"
        raise PromptError(message) from None
    free = jinja2.meta.find_undeclared_variables(parsed)
    if free != set(variables):
        raise PromptError(
            f"{prompt_id}: header declares variables {sorted(variables)} but the template "
            f"uses {sorted(free)}"
        )
    return _ENV.from_string(body)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


@cache
def _load_default(prompt_id: str) -> Prompt:
    path = _path_for(prompt_id)
    if not path.is_file():
        raise PromptError(f"no prompt {prompt_id!r} (expected file {path})")
    header, body = _split_front_matter(path, normalize_newlines(path.read_text(encoding="utf-8")))

    missing = _REQUIRED_HEADER_KEYS - header.keys()
    if missing:
        raise PromptError(f"{path}: front-matter is missing {sorted(missing)}")
    unknown = header.keys() - _HEADER_KEYS
    if unknown:
        raise PromptError(f"{path}: unknown front-matter keys {sorted(unknown)}")
    if header["id"] != prompt_id:
        raise PromptError(f"{path}: header id {header['id']!r} doesn't match its path")

    variables = tuple(_as_list(header["variables"]))
    examples_paths = tuple(path.parent / name for name in _as_list(header.get("examples")))
    schema_path = path.parent / header["schema"] if header.get("schema") else None
    for extra_path in (*examples_paths, *((schema_path,) if schema_path else ())):
        if not extra_path.is_file():
            raise PromptError(f"{path}: file {extra_path} not found")
    library = header.get("library")
    prompt = Prompt(
        id=prompt_id,
        version=str(header["version"]),
        description=str(header["description"]),
        variables=variables,
        text=body,
        hash="",
        custom=False,
        examples_paths=examples_paths,
        schema_path=schema_path,
        library=_library_version(library) if library else None,
        _template=_compile(prompt_id, body, variables),
    )
    return replace(prompt, hash=_hash(body, prompt.extra_paths))


def _hash(body: str, extra_paths: Sequence[Path]) -> str:
    return compute_hash([body, *(p.read_text(encoding="utf-8") for p in extra_paths)])


def load_prompt(prompt_id: str, override_text: str | None = None) -> Prompt:
    """The prompt `prompt_id` (`prompts/<group>/<name>.md`).

    `override_text` replaces the body (e.g. a user-edited prompt from a
    future settings panel): the result is marked `custom=True`, hashed over
    the override, and nothing is ever written to `prompts/`. The header
    (version, variables, examples, schema) stays the default file's — an
    override must use the same template variables."""
    default = _load_default(prompt_id)
    if override_text is None:
        return default
    body = normalize_newlines(override_text)
    return replace(
        default,
        text=body,
        hash=_hash(body, default.extra_paths),
        custom=True,
        _template=_compile(prompt_id, body, default.variables),
    )


def all_prompt_ids() -> list[str]:
    return sorted(f"{path.parent.name}.{path.stem}" for path in PROMPTS_DIR.glob("*/*.md"))


def get_prompt_manifest() -> dict[str, dict[str, Any]]:
    """`{prompt_id: {version, hash}}` for every prompt under `prompts/`, plus
    one `library:<name>` entry per library whose own prompts are used
    unmodified (`LIBRARY_PROMPTS`), with its installed version."""
    manifest: dict[str, dict[str, Any]] = {}
    for prompt_id in all_prompt_ids():
        prompt = load_prompt(prompt_id)
        manifest[prompt_id] = {"version": prompt.version, "hash": prompt.hash}
    for library, prompts in LIBRARY_PROMPTS.items():
        manifest[f"library:{library}"] = {
            "version": importlib.metadata.version(library),
            "prompts": list(prompts),
        }
    return manifest


def _format_validation_error(error: ValidationError) -> str:
    return "; ".join(
        f"field '{'.'.join(str(part) for part in item['loc']) or '<root>'}': {item['msg']}"
        for item in error.errors()
    )


def load_examples[InputT: BaseModel, OutputT: BaseModel](
    prompt: Prompt, input_model: type[InputT], output_model: type[OutputT]
) -> list[tuple[InputT, OutputT]]:
    """`prompt`'s few-shot examples, validated against the prompt's own
    input/output models. Each examples file is a YAML list of
    `{input: ..., output: ...}` mappings. Any problem raises `PromptError`
    naming the file, the example (1-based) and the field — these files are
    edited by hand."""
    examples: list[tuple[InputT, OutputT]] = []
    for path in prompt.examples_paths:
        try:
            entries = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise PromptError(f"{path}: invalid YAML: {error}") from None
        if not isinstance(entries, list):
            raise PromptError(f"{path}: expected a YAML list of examples")
        for number, entry in enumerate(entries, start=1):
            where = f"{path.name}, example {number}"
            if not isinstance(entry, dict) or set(entry) != {"input", "output"}:
                raise PromptError(f"{where}: expected exactly the keys 'input' and 'output'")
            parsed: list[BaseModel] = []
            for part, model in (("input", input_model), ("output", output_model)):
                try:
                    parsed.append(model.model_validate(entry[part], strict=True))
                except ValidationError as error:
                    raise PromptError(
                        f"{where} ({part}, {model.__name__}): {_format_validation_error(error)}"
                    ) from None
            examples.append((parsed[0], parsed[1]))  # type: ignore[arg-type]
    return examples


@dataclass(frozen=True)
class FieldDescriptions:
    """A prompt's output-schema field descriptions (its `schema` file):
    `{model name: {field name: description}}`. Read field by field while the
    models are being defined (`get`), then checked against the finished
    models (`check`)."""

    path: Path
    descriptions: dict[str, dict[str, str]]

    def get(self, model: str, field_name: str) -> str:
        try:
            return self.descriptions[model][field_name]
        except KeyError:
            message = f"{self.path.name}: no description for {model}.{field_name}"
            raise PromptError(message) from None

    def check(self, *models: type[BaseModel]) -> None:
        """Each of `models` has exactly the fields its entry describes, and
        the file describes no other model — so no description is missing,
        stale, or hand-written in Python instead of read from this file."""
        names = {model.__name__ for model in models}
        unknown_models = self.descriptions.keys() - names
        if unknown_models:
            raise PromptError(f"{self.path.name}: no such output model {sorted(unknown_models)}")
        for model in models:
            described = self.descriptions.get(model.__name__, {})
            fields = model.model_fields
            for problem, names_ in (
                ("fields without a description", fields.keys() - described.keys()),
                ("descriptions for no field", described.keys() - fields.keys()),
            ):
                if names_:
                    raise PromptError(
                        f"{self.path.name}: {model.__name__} has {problem}: {sorted(names_)}"
                    )
            for name, info in fields.items():
                if info.description != described[name]:
                    raise PromptError(
                        f"{self.path.name}: {model.__name__}.{name}'s description is not the "
                        "one from this file"
                    )


def load_field_descriptions(prompt: Prompt) -> FieldDescriptions:
    """`prompt`'s `schema` file, shape-checked (hand-edited, like examples)."""
    path = prompt.schema_path
    if path is None:
        raise PromptError(f"{prompt.id}: header declares no schema file")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise PromptError(f"{path}: invalid YAML: {error}") from None
    if not isinstance(data, dict):
        raise PromptError(f"{path.name}: expected a mapping of model name to fields")
    for model, fields in data.items():
        if not isinstance(fields, dict):
            raise PromptError(f"{path.name}: {model}: expected a mapping of field to description")
        for field_name, description in fields.items():
            if not isinstance(description, str) or not description.strip():
                message = f"{path.name}: {model}.{field_name}: empty or non-text description"
                raise PromptError(message)
    return FieldDescriptions(path=path, descriptions=data)
