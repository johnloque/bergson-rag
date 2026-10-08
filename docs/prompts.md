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
plain JSON values, never as a schema, so nothing about its fields reaches
the judge: they are documented with plain Python comments, not
`Field(description=...)`, so they don't pass for prompt text, and are not
hashed (an edit there changes nothing the model sees). Should a RAGAS
upgrade start sending the input schema, the golden snapshots would fail. The NLI prompt's output schema is
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
user-facing uses it yet; `feat/prompt-comparison` (below) is its first
user.

It replaces the **body** only: the examples and schema files stay the
default's. Comparing a variant that changes an examples file is handled by
the eval tooling, not the loader (see "Variants" below).

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

## Comparing prompt variants (`feat/prompt-comparison`)

Evaluation tooling only: production, the API, the UI and the committed
`prompts/` are untouched. `check_faithfulness`, `build_prompt` and
`generate_from_chunks` gained an optional keyword (`prompts=`,
`answer_prompt=`) defaulting to the committed prompts; only
`eval/scripts/run_prompt_comparison.py` passes it (a test checks that no
call in `src/api/` or the guardrail does).

**Every number this tooling produces is exploratory**: the gold set is
below the n=50 volume threshold (`docs/gold_dataset_protocol.md`), and
every report header says so. The tooling never picks a winner: the owner
does.

### What can be compared

- `generation.answer`;
- the **faithfulness family**: `faithfulness.segment_claims` and
  `faithfulness.nli_verifier`, their examples files included. The family
  is one variable: the two prompts are one judge.

`judge_chunk/*` is excluded: chunk judgments have no ground truth to score
a variant against, so a variant containing a `judge_chunk/` file is
refused. `generation.system` and the schema file aren't comparable either.

### Variants

`eval/prompt_variants/<name>/` is a partial overlay of `prompts/` (same
layout, only the files that differ) plus `variant.yaml` (`name`,
`hypothesis` = the observed failure targeted, `based_on` = the default
hash of each prompt in the family at creation, `status`
`draft|tested|rejected|promoted`, `results`). Layout, registry and rules:
[`eval/prompt_variants/README.md`](../eval/prompt_variants/README.md).
`eval/scripts/prompt_variants.py` resolves it:

- a body goes through `load_prompt(id, override_text=...)`;
- an examples file can't (the override is body-only), so the prompt is
  copied with the overlay's examples path and re-hashed with the loader's
  own `compute_hash`, same order (body, examples, schema); the examples are
  validated when the judge prompts are built
  (`build_faithfulness_prompts`, strict, like the defaults). A file copied
  unchanged hashes like the default;
- refused, with a readable reason: a missing or invalid `variant.yaml`,
  generation and faithfulness files together (**one variable at a time**),
  `judge_chunk/` files, schema files (their descriptions are compiled into
  Pydantic classes at import), unknown files;
- `based_on` different from the current default hash: a warning, and
  "STALE" in the header. Not blocked.

Harness flags: `--variant <name>`; `--prompt <id>=<path>` (repeatable, ad
hoc, the header says "ad hoc"); `--mode judge|generation` (only to run the
defaults: otherwise the mode follows from the files: `generation/` gives
generation mode, `faithfulness/` judge mode); `--items Q001,Q004`;
`--repeat N` (default 3). Each (item, repeat) is checkpointed and resumed
(`eval/scripts/checkpoint.py`, shared with `run_ragas_eval.py`) under a
fingerprint of the run's configuration.

**Lifecycle.** A variant starts from an observed failure, lives in its own
`exp/prompt-<name>` branch with its result files, ends `rejected` (kept, as
a lab notebook) or `promoted`. Promotion = copying its files into
`prompts/` in their own branch, with before/after numbers (the rules
above).

### Judge first, then generation

The judge is chosen before any generation prompt is compared, since a
generation comparison is only as good as the judge scoring it:

1. **Judge mode** runs each faithfulness candidate, the committed defaults
   included (`--mode judge`), on the same fixed answers.
2. The owner designates the winner (section "Choosing the judge"); it is
   promoted into `prompts/` if it isn't the defaults, then frozen
   (`eval/frozen_judge.json`).
3. **Generation mode** compares `generation.answer` variants, judged by the
   frozen judge.

### The two modes

- **Judge mode**: the answers are fixed, never regenerated: the calibration
  set below. No retrieval, no generation; each item's chunks are read from
  `data/processed/chunks/` and checked against the hashes stored at build
  time (re-chunking means rebuilding the set, never silently scoring
  against other text).
- **Generation mode**: the generation-only path (gold chunks from Qdrant,
  retrieval bypassed), same models, temperature 0, hosted fallback
  disabled (a silent switch to another model would break the comparison).
  The answers are judged with the committed faithfulness prompts, which
  must be the frozen judge: generation mode refuses to run unless
  `eval/frozen_judge.json` exists and matches the committed faithfulness
  hashes, the installed RAGAS and the judge model. `--allow-unfrozen-judge`
  runs anyway and stamps "JUDGE NOT FROZEN/MISMATCH" in the header.
  **Any later change to a faithfulness prompt invalidates earlier
  generation comparisons**: they were scored by another judge.

### Calibration set (`eval/calibration_set.json`)

Built by `python -m eval.scripts.calibration_set` (needs the chunks and, for
generated items, the local RAGAS checkpoint). Every item carries an
`origin` and a `label`:

| origin | label | what |
|---|---|---|
| `gold` | faithful | every `gold_dataset.csv` `expected_anwser`, against all the chunks of its `paragraph_ids` (multi: every listed chunk) |
| `generated` | hallucinated | a real answer from `eval/results/ragas_checkpoint.jsonl`, copied verbatim, with the substring of its known fabricated claim |
| `perturbed` | hallucinated | a mechanical, logged edit of a gold answer |

**Generated** items come only from `eval/calibration_labels.yaml`: the
owner supplies each label and substring; the tooling copies the answer,
checks the substring is in it, and never reconstructs or regenerates an
answer. A labeled answer missing from the checkpoint stops the build with
a "SUPPLY THIS" report naming it; checkpoint answers not labeled yet are
listed. The checkpoint doesn't store the chunks an end_to_end answer was
generated from, so generated items are judged against their item's gold
chunks. Seeded with the two fabrications documented in
`docs/anti_hallucination_guardrails.md` (Sprint 10): Q002 end_to_end
("De l'évolution de la vie. Mécanisme et finalité", which the judge scored
1.0) and Q004 end_to_end ("Le comique de caractère"). The Q001/Q004
"confirmed hallucinations" of `tests/test_guardrail.py` are hand-written
fixtures, not generated answers, so they're not in the set.

**Perturbed** items: seeded (`--seed`, default 1859), every edit stored as
data (source item, type, original span, replacement, fabricated substring
and its position). Types: (a) swap a proper noun (a philosopher, a work
title), (b) change a year, (c) insert one sentence from a fixed list, (d)
negate a claim (the edited window, a few words around the verb, is the
fabricated substring, so a frequent "n'est pas" doesn't discard every
negation). One per item by default, the type rotated deterministically,
moving to the next type when the answer offers no target;
`--perturbations-per-item N` (max 4) adds more, each costing a full
local-judge run per repeat. (a) and (b) only target a name or year that
appears in the item's chunks: the judge sees chunk text only, never a
work's title or date, so swapping one the chunks don't mention would
falsify nothing checkable. An edit whose replacement appears in the item's
chunks (substring check) is discarded and logged. A perturbed item shares
its source's chunks (paired design): the comparison matrix lists them
side by side.

**Perturbed items are reported apart from generated ones**, always: they
are cruder than real fabrications (an inserted sentence about Aristotle is
easier to catch than a plausible wrong title), so detecting them shows the
judge catches blatant errors, not subtle ones. The gate states how many
items of each origin it rests on, and detection per perturbation type.

### Choosing the judge

"Flags the known claim" = at least one claim drawn from an answer segment
overlapping the fabricated substring gets verdict 0. Claims are anchored to
whole sentences cut by code (see `src/generation/faithfulness.py`,
"Anchoring claims to answer segments"), not to quotes, so overlap is
decided at sentence level.

1. **Gate**: the candidate flags the known claim of every hallucinated
   item (generated and perturbed), in every repeat. A nan run counts as
   missed. Failing the gate rejects a candidate whatever its scores: a
   judge that flags nothing has a perfect faithful-class mean.
2. **Two axes, side by side, among gate-passing candidates**, never a
   composite score: (a) mean faithfulness on the **faithful** class (higher
   = fewer false flags); (b) stability over `--repeat` runs: per-item score
   range, and verdict flips (a statement with the same text in two runs and
   both verdicts; statements extracted in one run only are counted too).
   X is preferred over Y only if better-or-equal on both; otherwise the
   report states the trade-off and leaves it to the owner.
3. The **hallucinated** class is reported separately (lower is the correct
   direction). **No mean ever pools the two classes**: their scores move in
   opposite directions for a good judge, so a pooled mean rewards nothing
   and hides both.
4. Claims flagged in faithful items are listed with the judge's reasons, as
   investigation leads (a gold answer may well state something its chunks
   don't). Labels never change from this.

nan and parse failures are reported per run, next to every mean, never
dropped.

**Held-out check**: no calibration answer or chunk text may appear in the
judge's own few-shot examples (an 8-word overlap counts), checked at build
time against the committed examples and at every judge-mode run against
the candidate's examples, reported in the header. The committed examples
are RAGAS's English ones (a student named John, photosynthesis, Einstein)
and a French one about Descartes: no Bergson content, and no overlap.

### The frozen judge (`eval/frozen_judge.json`)

The frozen judge is the faithfulness prompt set, RAGAS version and judge
model of the candidate that wins judge selection, **as designated by the
owner**. `python -m eval.scripts.freeze_judge <result_file>` writes it
(committed): faithfulness prompt hashes, RAGAS version, judge model,
source result file, gate summary, commit, date. Running it is the
designation. It refuses if the result isn't judge mode, failed the gate,
covers only part of the calibration set, was run with `--repeat` < 2
(stability unmeasured), or has faithfulness hashes other than the
committed `prompts/`: a winning variant is promoted into `prompts/` first,
in its own branch, so that the frozen judge and the judge generation mode
runs are the same thing.

### Results and comparison

Each run writes `eval/results/prompt_cmp_<mode>_<label>_n<N>_<ts>.json`
and a `.md` report. The header holds the full manifest (every prompt, hash,
custom flag, RAGAS version), models, temperature, mode, retrieval config,
item count and count per origin, commit and dirty flag, variant name or
"ad hoc", staleness, and the frozen-judge status.

`python -m eval.scripts.compare_prompt_results BASE.json CAND.json [...]`
compares 2+ results, the first being the baseline. Refused unless the
manifests differ in exactly one prompt (the faithfulness family counts as
one, and must match the mode) and items, models, temperature and mode
match; `--force` compares anyway, stamped "NOT COMPARABLE".

**Noise floor**: `--rerun BASE_RERUN.json`, a second run of the baseline
with an identical configuration, gives each item's |run1 − run2|; a delta
at or below it is marked "within noise". Without a rerun file the report
says so and makes no noise claim. (The judge at temperature 0 is close to
deterministic, not exactly: `docs/anti_hallucination_guardrails.md`.)

The per-item matrix is the primary output (Markdown + CSV): id, category,
origin, label, each candidate's mean score, nan runs, claims and
unsupported claims per run, delta and noise marker; the nan rate per run
sits next to every mean. Generation-mode comparisons flag items whose gold
chunks appear in `docs/known_issues/`, when that directory exists.

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

- `tests/test_prompt_comparison.py` — variant overlays and their
  refusals, staleness, overrides kept off the API path, the calibration set
  (perturbation determinism, edits stored as data, discarded edits, the
  "supply this" stop, held-out overlap), the gate, the two axes and
  dominance, flip counting, nan handling, comparability, noise floor,
  freeze-judge refusals, and generation mode's frozen-judge refusal. No
  model call.

`tests/test_prompt_comparison_smoke.py` (slow) runs each mode once against
a real model with a throwaway fixture variant
(`tests/fixtures/prompt_variants/`): plumbing only.

The built-image check is a script, not part of CI (building the api image
takes minutes): `make test-container-prompts` builds the image and
compares the manifest inside the container with the host's.

## Packaging

The API image copies `prompts/` to `/app/prompts`, next to `src/`
(`Dockerfile`). The native `ml_service` runs no LLM and loads no prompt.
