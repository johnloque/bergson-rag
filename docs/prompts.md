# Prompts as versioned files (`refactor/prompts-to-files`)

Every prompt this project sends to an LLM lives under `prompts/`, in git —
no prompt wording remains in Python. Each prompt has a content hash, and
every generation, evaluation and chunk judgment records which prompt
versions produced it. The point: comparing prompt variants meaningfully
(Sprint 14, `docs/ROADMAP.md`) requires knowing exactly which prompt text
produced which result.

Files in git are the source of truth, per this project's local-first
design — no external prompt-management platform (Langfuse, LangSmith,
MLflow...).

## Layout

```
prompts/
├── generation/
│   ├── system.md                        generation.system
│   └── answer.md                        generation.answer
├── judge_chunk/
│   ├── system.md                        judge_chunk.system
│   ├── relevance.md                     judge_chunk.relevance
│   └── retry.md                         judge_chunk.retry
└── faithfulness/
    ├── segment_claims.md                faithfulness.segment_claims
    ├── segment_claims.examples.yaml
    ├── segment_claims.schema.yaml       output-schema field descriptions
    ├── nli_verifier.md                  faithfulness.nli_verifier
    └── nli_verifier.examples.yaml
```

A prompt's id is `<directory>.<file stem>`; the loader enforces that the
header's `id` matches the path. One file per message: a system message and
its user message are separate prompts (each with its own hash).

| Prompt | Used by | Sent |
|---|---|---|
| `generation.system`, `generation.answer` | `generate_from_chunks` (`src/generation/generate.py`) | every call |
| `judge_chunk.system`, `judge_chunk.relevance` | `judge_chunk` (`src/generation/chunk_judge.py`) | every call |
| `judge_chunk.retry` | same | only after an unparseable reply |
| `faithfulness.segment_claims` | `check_faithfulness` (`src/generation/faithfulness.py`) | once per evaluation |
| `faithfulness.nli_verifier` | same | once per extracted claim |

Each faithfulness prompt has its own examples file, not one shared
`examples_fr.yaml`: a shared file would put both prompts' examples in both
hashes, so editing one prompt's examples would make the other look changed
too. (They are not all French anyway: the NLI examples are RAGAS's English
ones with French reasons — see `src/generation/faithfulness.py`, "Judge
prompt languages".)

### Front-matter

```markdown
---
id: faithfulness.nli_verifier
version: v1
description: One line saying what the prompt does.
variables: []                          # the template's free variables
examples: [nli_verifier.examples.yaml] # optional, next to this file
library: ragas                         # optional, see "Library-owned text"
---
<body: the exact prompt text>
```

- `version` is a human label (`v1`, `v2`...) for reading results; the
  hash is what identifies the text.
- `variables` must list exactly the template's free variables: checked at
  load time, so the header can't drift from the template.

### Body: a Jinja2 template

Bodies are rendered with Jinja2: `StrictUndefined` (a missing variable
raises instead of rendering empty), `trim_blocks` + `lstrip_blocks` (a line
holding only a `{% ... %}` tag leaves no trace in the output), no
autoescaping, and the body's final newline is not part of the output.
`render()` also rejects variables the header doesn't declare.

The evidence-conditioned generation prompt keeps **all** its branching in
`answer.md` — mono/multi-work, convergent/divergent, low-confidence
caution, prior chunk judgments, evidence grouping per work —
not as fragments assembled in Python. `src/generation/prompt.py` only
shapes the input data (work labels, text-level titles, page displays).
One file, one hash, for the whole prompt.

Whitespace in `answer.md` is significant: the rendered prompt is
byte-identical to what the pre-refactor Python produced, and the golden
snapshots enforce it (see Tests).

### Examples files

A YAML list of `{input: ..., output: ...}` mappings, meant to be edited by
hand. At load time each entry is validated in strict mode against the
prompt's Pydantic models (`SegmentedAnswerInput`/`SegmentedClaimsOutput`,
RAGAS's `NLIStatementInput`/`NLIStatementOutput`) — no silent coercion of
`'1'` into `1`. An invalid entry fails the import with one readable line,
not a Pydantic traceback:

```
PromptError: nli_verifier.examples.yaml, example 2 (output, NLIStatementOutput):
field 'statements.0.verdict': Input should be a valid integer
```

## Hash

`sha256` over, in order, the body, each examples file listed in the
header, then the schema file if any, each with line endings normalized to
LF, joined with a NUL byte. For a single-file prompt that is simply `sha256` of the body.

- **LF normalization**: development happens on macOS, the app runs on Linux
  (CI, VPS); a CRLF checkout must not produce a "different" prompt.
- **Template, not rendered text**: the rendered prompt changes with every
  question and chunk set; the template is what a prompt variant *is*.
- **Header excluded**: rewording a description or bumping a version label
  doesn't create a new prompt. The examples files are hashed whole
  (comments included), since they are part of what the model sees.

## Library-owned text

The two faithfulness prompts are sent through RAGAS's `PydanticPrompt`,
which wraps them in its own text: the output JSON-schema sentence, the
`--------EXAMPLES-----------` separator, "Now perform the same with the
following input". That text belongs to the library and changes with its
version, so these prompts declare `library: ragas`, and their records
carry the installed version (`"library": "ragas==0.3.9"`).

RAGAS prompts used without any override are out of this project's
`prompts/` but listed in the manifest with the library version
(`LIBRARY_PROMPTS`, `src/prompts/loader.py`): that framing, `FixOutputFormat`
(RAGAS's retry on unparseable output), the `NLIStatementInput`/`Output`
schemas, and, in `eval/scripts/run_ragas_eval.py` only,
`ContextPrecisionPrompt` and `ContextRecallClassificationPrompt`.

### Output-schema field descriptions

RAGAS tells the judge what JSON to answer with by pasting the **output**
model's JSON schema into the prompt — field descriptions included. Those
descriptions are therefore prompt text, and live in a `schema` file next to
the prompt: `faithfulness/segment_claims.schema.yaml`, declared in the
header (`schema: ...`) and hashed with it.

```yaml
SegmentClaims:
  segment_id: The number of the segment these claims come from
  claims: Fully understandable, standalone statements ...
SegmentedClaimsOutput:
  segments: One entry per input segment, in order, each with its claims
```

`src/generation/faithfulness.py` defines the output models with
`Field(description=descriptions.get(model, field))`, then
`descriptions.check(...)` fails the import if a field has no entry, an
entry has no field, or a description was written in Python instead.

The **input** model (`SegmentedAnswerInput`, `AnswerSegment`) is sent as
plain JSON values, never as a schema, so its descriptions never reach the
judge: they stay in Python as documentation and are not hashed (an edit
there changes nothing the model sees). The NLI prompt's output schema is
RAGAS's own (`NLIStatementOutput`), covered by the library version.

## Loader API (`src/prompts/loader.py`)

- `load_prompt(id) -> Prompt` with `.id`, `.version`, `.text` (template
  source), `.hash`, `.custom`, `.render(**variables)`, `.record()`.
  Cached; the `prompts/` directory is resolved relative to the package,
  never the working directory.
- `load_examples(prompt, input_model, output_model)` — validated examples.
- `get_prompt_manifest()` — `{prompt_id: {version, hash}}` for every
  prompt, plus `library:ragas: {version, prompts}`. Logged once at API
  startup (`src/api/main.py`'s lifespan).

## `prompts_used` column

`generations`, `evaluations` and `chunk_judgments` each have a nullable
JSON column `prompts_used`:

```json
{"generation.system": {"version": "v1", "hash": "e6d6...", "custom": false},
 "generation.answer": {"version": "v1", "hash": "ea95...", "custom": false}}
```

It holds the prompt set in effect for that record's LLM calls: an
evaluation lists `faithfulness.segment_claims` and
`faithfulness.nli_verifier` (examples included in their hashes, plus the
`library` field); a chunk judgment lists `judge_chunk.retry` whether or
not a retry was actually needed.

Rows written before this branch stay `NULL` — not backfilled, which would
be a guess. Migration: the existing `_sync_additive_columns` step
(`src/api/db.py`) inspects each table at startup and runs
`ALTER TABLE ... ADD COLUMN` for a declared nullable column that's
missing — idempotent, never drops or recreates `data/app.db`. No Alembic.

## Overrides (future settings panel)

`load_prompt(id, override_text=...)` returns the same prompt with the
override as its body: `custom=True`, a hash computed over the override,
same header (version label, variables, examples). It never writes to
`prompts/` — a user's custom prompt is per-request data, recorded as such
in `prompts_used`, not a new version of the project's prompt. Nothing
user-facing uses it yet; it exists so the settings panel and
`feat/prompt-comparison` can build on it.

## Rules for changing a prompt

- **Wording changes go in their own branch**, never mixed with a move or a
  refactor, so the hash history separates "moved" from "edited".
- A PR changing anything under `prompts/` includes before/after evaluation
  numbers, same as retrieval changes (`CONTRIBUTING.md`).
- Bump `version` in the header so results are readable by humans; the hash
  changes on its own.
- Regenerate the golden snapshots (`uv run python -m
  tests.test_prompt_snapshots`) and review their diff: it shows exactly
  what the model will now receive.

## Tests

All fast (CI's `-m "not slow"` job):

- `tests/test_prompt_snapshots.py` — golden snapshots. Each prompt is
  captured at the LLM boundary (mocked `litellm.completion`, a recording
  RAGAS LLM) for Q001, Q002, Q007 and Q009, whose inputs together cover
  every branch of `answer.md`. The snapshots were committed from the
  pre-refactor implementation before any prompt moved; the refactor
  renders them byte-for-byte. Snapshot files are excluded from the
  whitespace pre-commit hooks and from git line-ending conversion
  (`.gitattributes`) — RAGAS ends every prompt with `"Output: "`.
- `tests/test_prompt_loader.py` — hashing (CRLF = LF, one-character body
  change, header-only change), StrictUndefined, header/template variable
  agreement, readable examples errors, overrides, manifest, cwd
  independence, and the Dockerfile shipping `prompts/`.
- `tests/test_prompts_used.py` — `/generate` → `/evaluate` →
  `/judge-chunk` populate `prompts_used` with the manifest's hashes;
  pre-existing rows read back as NULL; the add-column step is idempotent.

The built-image check is a script, not part of CI (building the api image
takes minutes): `make test-container-prompts` builds the image and
compares the manifest inside the container with the host's.

## Packaging

The API image copies `prompts/` to `/app/prompts`, next to `src/`
(`Dockerfile`). The native `ml_service` runs no LLM and loads no prompt.
