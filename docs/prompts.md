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
local-judge run per repeat. `--extra-negations N` (default 2) then adds
N more (d) edits, one per gold item, drawn with the seed among the items
that don't already have a negation and offer a usable one (Q002-p2 and
Q010-p2 at seed 1859); it only adds items, the rotated ones are unchanged,
and asking for more than are eligible stops the build. (a) and (b) only target a name or year that
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

**Accepted misses.** `--accept-miss ITEM_ID --justification "..."`
(repeatable) is the owner's explicit exception for a known gate miss; the
gate itself is unchanged. Each accepted item must be missed in the result,
and missed only because the judge gave the known claim a verdict
(`judged supported` in every missed repeat; a nan, an unevaluated claim or
a missing run can't be accepted). Any other miss still refuses, and so does
an accepted item that was actually detected. The record keeps
`gate.passed: false` and lists each exception under
`gate.accepted_misses` (item, per-repeat reasons, justification); the
frozen-judge status stamped in every generation-mode header names them.

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

### Judge baseline (`exp/judge-baseline`)

Measurement only: the **committed default** faithfulness prompts, judge
mode, on `eval/calibration_set.json` as committed (sha256 `482bed45…`).
Two identical runs, each `--repeat 3`: commit `d7aed49`, clean tree,
temperature 0, local judge `ollama_chat/mistral` (Ollama digest
`6577803aa9a0`), RAGAS 0.3.9, same fingerprint (`e8022718318f09a1`), one
checkpoint file per run so the second run re-judged every item instead of
replaying the first.

- Run 1: [`prompt_cmp_judge_default_n26_20261008T124431Z`](../eval/results/prompt_cmp_judge_default_n26_20261008T124431Z.md)
- Run 2 (baseline rerun, for the noise floor): [`prompt_cmp_judge_default_n26_20261008T141004Z`](../eval/results/prompt_cmp_judge_default_n26_20261008T141004Z.md)

EXPLORATORY: n=26, below the n=50 threshold; no number here is
decision-grade.

**Set.** 26 items: 12 faithful (`gold`), 14 hallucinated, which split into
2 `generated` (Q002 and Q004 end_to_end, Sprint 10) and 12 `perturbed`
(9 `unsupported_sentence`, 2 `negation`, 1 `proper_noun`; no `year`
perturbation found a target). Held-out check against
`segment_claims.examples.yaml` and `nli_verifier.examples.yaml` (the
per-prompt files that replaced `examples_fr.yaml`): no 8-word overlap, at
build time and in both run headers.

#### 1. Gate: failed, identically in both runs

The gate rests on **14 items: 2 generated, 12 perturbed**. Detected in
every repeat:

| | run 1 | run 2 |
|---|---|---|
| generated | 1/2 | 1/2 |
| perturbed | 9/12 | 9/12 |
| — `unsupported_sentence` | 7/9 | 7/9 |
| — `negation` | 1/2 | 1/2 |
| — `proper_noun` | 1/1 | 1/1 |

Missed, with per-repeat detections (run 1 / run 2):

- **`Q002-gen-end_to_end`** (generated): `[F,F,F]` / `[F,F,F]`. **nan in
  all 6 runs**: never judged. The NLI reply fails to parse
  (`OutputParserException: Failed to parse StringIO`): the judge
  re-escapes the double quotes around the fabricated title
  (`"De l'évolution de la vie. Mécanisme et finalité"`) inside its JSON
  statement and breaks it. Source: chunks `1907_EC_c25`, `1907_EC_c398`,
  `1934_PM_c16`. None of them states a title (the judge never sees one).
  No statements and no reasons were recorded.
- **`Q001-p1-unsupported_sentence`**: `[F,F,F]` / `[F,F,F]`. **nan in all
  6 runs**: `segment_claims` fails to parse even after RAGAS's
  `FixOutputFormat` retries. Inserted sentence: « Bergson déclare avoir
  emprunté cette idée à Aristote, dont il cite longuement la
  Métaphysique. » Source chunk `1907_EC_c13` mentions neither Aristote nor
  la Métaphysique. No statements and no reasons were recorded.
- **`Q010-p1-unsupported_sentence`**: `[F,F,F]` / `[F,F,F]`. **nan in all
  6 runs**, with the same `segment_claims` parse failure. Inserted sentence: « Il
  illustre ensuite ce point par l'exemple d'une horloge arrêtée dans une
  maison vide. » Source chunk `1932_2S_c170` has no horloge. No statements
  and no reasons were recorded.
- **`Q008-p1-negation`**: `[T,F,F]` / `[T,T,F]`. **The only miss on a
  judged verdict**, and an unstable one: detected in 3 of 6 runs. Edit:
  « et le mental sont solidaires » → « et le mental **ne** sont **pas**
  solidaires ». Statement (identical in every run): « De manière
  analogue, le cérébral et le mental ne sont pas solidaires, sans pour
  autant qu'on puisse établir d'équivalence entre eux. » Source
  (`1919_ES_c32`): « Un vêtement est solidaire du clou auquel il est
  accroché ; il tombe si l'on arrache le clou […] il ne s'ensuit pas que
  chaque détail du clou corresponde à un détail du vêtement, ni que le
  clou soit l'équivalent du vêtement ». NLI reasons:
  - verdict 0 (caught): « …il n'y a pas de mention d'une absence de
    solidarité entre le cerveau et le mental, ni d'une absence
    d'équivalence entre eux. »
  - verdict 1 (missed): « …l'auteur suggère implicitement que le cerveau
    et le mental sont solidaires, ce qui est en accord avec
    l'affirmation. » The reason states the opposite of the statement and
    still concludes "supported".

So 3 of the 4 misses are parse failures, counted as missed under the
gate's rule. They are deterministic, and they say nothing about what the
judge would have answered. Only Q008-p1 shows the judge reading a
statement and accepting it. On the 11 items that parsed, the known claim was
flagged in every repeat for 10 of them.

#### 2. Faithful class

Mean faithfulness **0.611** (run 1) and **0.617** (run 2) over 12 items, with no
nan. Per item (mean of 3 repeats, run 1 / run 2):

| Item | Q001 | Q002 | Q003 | Q004 | Q005 | Q006 | Q007 | Q008 | Q009 | Q010 | Q011 | Q012 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| run 1 | 0.500 | 0.273 | 1.000 | 0.500 | 1.000 | 0.667 | 0.622 | 0.778 | 0.000 | 0.500 | 0.889 | 0.600 |
| run 2 | 0.500 | 0.273 | 1.000 | 0.500 | 1.000 | 0.667 | 0.644 | 0.778 | 0.000 | 0.556 | 0.889 | 0.600 |

27 distinct statements are flagged across 10 of the 12 gold answers (78
flags in run 1, 77 in run 2). Only Q003 and Q005 are never flagged. All of
them are listed with their reasons in the result files
(`summary.flagged_faithful_statements`). These are investigation leads,
and the labels are unchanged. They fall into three groups:

- **Work title or date** (Q001, Q006, Q007, Q009, Q010: each answer's
  opening sentence, e.g. « Dans l'Évolution Créatrice (1907)… », « Dans
  Les Deux Sources (1932)… »). The judge sees chunk text only, never a
  work's title or date, so these statements can't be supported by
  construction; reasons say « ne mentionne pas explicitement l'œuvre… ».
- **Paraphrase or inference beyond the chunk wording** (most of Q002, Q004,
  Q009, Q012, Q007 « utile à la vie pratique et à la plupart des
  sciences », Q011 r3 only): reasons of the form « ne mentionne pas
  explicitement… ». Whether the gold answer overreaches or the judge reads
  too literally is the owner's call.
- **Reasons that may misread the chunk**: Q002 « Les états d'un tel système
  sont juxtaposés dans l'espace » is rejected because « l'univers déroule
  ses états successifs ». In Q009 « L'humanité s'appuie sur l'animal »,
  the reason inverts the image (« l'animal est sous l'homme, pas
  l'inverse »). In Q010 « Bergson récuse la transformation graduelle
  interne », the reason infers that Bergson doesn't reject the transformation
  from the chunk describing it (chunk not re-read here).
  Q008's clou/vêtement statement flips (below).

Hallucinated class, for reference (lower is the correct direction): 0.485 /
0.479 over the 11 parsed items. Never pooled with the faithful class.

#### 3. Stability

- **Within each run** (3 repeats): mean per-item score range 0.063
  (run 1) and 0.071 (run 2), max 0.333. 2 verdict flips per run, the same
  two statements both times:
  - Q008 (faithful): « En effet, si on arrache le clou, le vêtement tombe,
    mais on ne peut pas en conclure que la forme du clou dessine celle du
    vêtement… »
  - Q008-p1-negation: the negated statement above.

  Matched statements: 112 (run 1) and 113 (run 2). Statements extracted in
  a single repeat only: 7 and 8.
- **Across both runs** (`stability()` over the 6 runs pooled): mean range
  0.071, max 0.333, **the same 2 flips and no other**, 119 matched
  statements, 2 extracted only once.
- **Noise floor**: `noise_floor(run1, run2)` from
  `eval/scripts/compare_prompt_results.py`, called directly. The CLI refuses
  two results with identical manifests by design. Per-item |run 1 mean −
  run 2 mean|:
  - 0 on 19 items;
  - nonzero on 4: Q007 0.022, Q010 0.056, Q007-p1 0.048, Q008-p1 0.111;
  - nan on 3 (the three always-nan items).

  Max 0.111, mean 0.010 over the 23 finite items. Future comparisons
  should pass run 2 as `--rerun`.

Score movement concentrates in Q007, Q008, Q010, Q011 and their perturbed
copies. Everything else is identical to three decimals across all 6 runs.

#### 4. nan and parse failures

**9/78 rows (11.5%) in each run**, the same 9 both times: Q002-gen ×3,
Q001-p1 ×3 and Q010-p1 ×3. All of them are in the hallucinated class, and the
faithful class has no nan. Per class and repeat: faithful 0/12, hallucinated
3/14, in every repeat of both runs. There were no unevaluated claims.

#### 5. Verdict

**The committed defaults do not pass the gate**: 10 of 14 hallucinated
items flagged in every repeat (generated 1/2, perturbed 9/12), with the
same result in both runs. Three of the four misses are deterministic parse
failures (nan), counted as missed by the gate's rule. The fourth,
Q008-p1-negation, is a genuine and unstable miss: the negation is accepted
in 3 of 6 runs. The faithful-class mean is **0.611 / 0.617**. Stability is
high: 2 flipping statements, both in the Q008 pair, and a noise floor of 0
on 19 of 26 items, max 0.111. This is a baseline, not a selection result:
no other candidate has been run, the frozen judge is not designated, and
nothing here recommends a prompt change.

### Judge baseline v2 (`exp/judge-baseline-v2`)

The baseline above was produced at **judge input version 1**. Two code
changes since then alter what the judge is given and how its replies are
read (`JUDGE_INPUT_VERSION = 2`, `src/generation/faithfulness.py`), and
neither touches a prompt: replies are repaired before parsing (#57), and
each chunk of the NLI context sits under its title/year header (#58). This
baseline replaces the first for every comparison. `compare_prompt_results`
refuses to compare results across versions anyway.

Same protocol: the committed default prompts (unchanged hashes), judge mode,
`eval/calibration_set.json` (sha256 `482bed45…`). Two identical runs, each
`--repeat 3`: commit `28b41a3` (main after #58), clean tree, temperature 0,
`ollama_chat/mistral`, RAGAS 0.3.9. Same fingerprint (`665a4089d953`), one
checkpoint file per run.

- Run 1: [`prompt_cmp_judge_default_n26_20261009T100635Z`](../eval/results/prompt_cmp_judge_default_n26_20261009T100635Z.md)
- Run 2 (rerun, for the noise floor): [`prompt_cmp_judge_default_n26_20261009T112759Z`](../eval/results/prompt_cmp_judge_default_n26_20261009T112759Z.md)
- Report (`judge_variant_report --baseline`): [`prompt_cmp_judgebase_default_20261009T131600Z`](../eval/results/prompt_cmp_judgebase_default_20261009T131600Z.md)

EXPLORATORY: n=26, below the n=50 threshold; no number here is
decision-grade.

| | v1 (run 1 / run 2) | v2 (run 1 / run 2) |
|---|---|---|
| Gate | failed, 10/14 | failed, **13/14** |
| — generated | 1/2 | **2/2** |
| — perturbed | 9/12 | 11/12 |
| nan rows | 9/78 | **0/78** |
| Unevaluated claims | — | 0 |
| Faithful-class mean (higher = fewer false flags) | 0.611 / 0.617 | **0.665 / 0.657** |
| Hallucinated-class mean (lower = correct) | 0.485 / 0.479 (11 parsed items) | 0.534 / 0.536 (14 items) |
| Distinct flagged faithful statements | 27, across 10 items | 27, across 8 items |
| Verdict flips (pooled, 6 repeats) | 2 (Q008 pair) | 2 (Q007 pair) |
| Noise floor | 0 on 19 of 23 finite, max 0.111 | 0 on 22 of 26, max 0.111, mean 0.009 |

The two hallucinated means aren't comparable: v1's leaves out the three
nan items.

#### What changed

- **Parse failures: gone.** Q001-p1 and Q010-p1 now flag their inserted
  sentence in every repeat. Q002-gen's invented title, « De l'évolution de
  la vie. », is judged unsupported in every repeat (0.800 per run). The
  judge's reason now cites the chunk headers.
- **Title false flags on faithful answers: mostly gone.** In v1, the
  opening title sentences of Q001, Q006, Q007, Q009 and Q010 were flagged,
  because the judge couldn't see any title. In v2, Q001, Q007 and Q010 are
  no longer flagged. Q001 reaches 1.000 (was 0.500), Q008 1.000 (was
  0.778) and Q009 0.167 (was 0.000). Still flagged, for claims the header
  can't settle: Q009 « À la fin du troisième chapitre de l'Évolution
  créatrice (1907)… » (a chapter, not a work), Q012 « Dans l'Évolution
  Créatrice (1907) et Les Deux Sources (1932)… », and Q006 « Dans La Pensée
  et le Mouvant (1934), Bergson reconstitue la pensée… de Berkeley » (the
  reason is about the content). Q010 drops from 0.500 to 0.333: three
  claims about the Greek-thought metaphor are now flagged (« … ne fait
  aucune référence à Bergson »).
- **The one remaining miss: Q008-p1-negation, now stable.** In v1 it was
  detected in 3 of 6 repeats; in v2 it's judged supported in **6 of 6**.
  The reason contradicts itself every time: « l'auteur y voit une certaine
  solidarité mais pas d'équivalence » (correct), then « Ainsi,
  l'affirmation que le cerveau et le mental ne sont pas solidaires est
  directement inférée du contexte ». The judge reads the right relation
  but doesn't carry the negation into its verdict. That's a judgment
  failure, not a parsing one, and the gate's only blocker now.
  `negation` has 2 items (Q004-p1 is caught).

#### Verdict

**The committed defaults still fail the gate, on one item**: 13 of 14
hallucinated items flagged in every repeat, the same in both runs. The
miss is Q008-p1-negation, a negation accepted with a self-contradicting
reason in all 6 repeats. No nan, no unevaluated claim. The faithful-class
mean is higher than v1 (**0.665 / 0.657**), and the noise floor is lower
(0 on 22 of 26 items). This is the baseline every judge variant is
compared against from now on (pass run 2 as the rerun). Nothing here
recommends a prompt change. A variant targeting negation would start from
Q008-p1.

#### Leads (not started)

- **A negation variant** (faithfulness family, `nli_verifier.md`). The
  observed failure is Q008-p1-negation: the judge states the relation the
  context asserts (« une certaine solidarité »), then accepts its negation.
  Candidate rule: a statement that denies a relation the context asserts
  gets verdict 0, even if the rest of the statement matches.
  **Tried** (`exp/prompt-judge-negation-opt`): rejected against baseline
  v3, see "Variant judge-negation-opt" below.
- **Too few negation items to judge it.** The calibration set has 2
  `negation` perturbations: Q004-p1, caught, and Q008-p1, missed. A variant
  tuned on Q008-p1 alone could fix that item without fixing negation.
  Adding `negation` perturbations first (`eval/scripts/calibration_set.py`,
  `_negate`) changes the calibration set's sha256. The baseline would then
  have to be rerun before any variant is compared to it.
  **Done** (`feat/calibration-extra-negations`): 2 extra negations,
  Q002-p2-negation and Q010-p2-negation, so 4 `negation` items and 28 in
  all; sha256 `482bed45…` → `c9460f67…`. Baseline v2 was run on the old
  set: rerun it on this one before comparing a negation variant.
- **Watch the faithful class.** Gold answers contain legitimate negations
  (e.g. Q008's « on ne peut pas en conclure que la forme du clou dessine
  celle du vêtement »). A stricter negation rule must not lower the
  faithful-class mean: check its flagged faithful statements against
  baseline v2's.

### Variant `judge-parsing-opt` (`exp/prompt-judge-parsing-opt`): rejected

Explicit JSON rules added to both faithfulness instructions
(`segment_claims.md`, `nli_verifier.md`): a comma between claims, « »
instead of inner double quotes, no escaped apostrophe. Examples and schema
unchanged. It targeted the first baseline's parse failures (Q001-p1,
Q010-p1, Q002-gen), which the code has repaired since (#57), so the only
open question was whether the rules change verdicts once parsing no longer
fails.

Same protocol as baseline v2: judge mode, `eval/calibration_set.json`, two
identical runs of `--repeat 3`, commit `a89475b`, clean tree, judge input
version 2, fingerprint `056b29f7f09c`, one checkpoint file per run.

- Run 1: [`prompt_cmp_judge_judge-parsing-opt_n26_20261010T110747Z`](../eval/results/prompt_cmp_judge_judge-parsing-opt_n26_20261010T110747Z.md)
- Run 2 (rerun, for the noise floor): [`prompt_cmp_judge_judge-parsing-opt_n26_20261010T113950Z`](../eval/results/prompt_cmp_judge_judge-parsing-opt_n26_20261010T113950Z.md)
- Report (`judge_variant_report`, vs baseline v2): [`prompt_cmp_judgevs_judge-parsing-opt_20261010T140431Z`](../eval/results/prompt_cmp_judgevs_judge-parsing-opt_20261010T140431Z.md)

EXPLORATORY: n=26, below the n=50 threshold; no number here is
decision-grade.

| | baseline v2 (run 1 / run 2) | `judge-parsing-opt` (run 1 / run 2) |
|---|---|---|
| Gate | failed, 13/14 | failed, **12/14** |
| — missed | Q008-p1-negation | Q008-p1-negation, **Q002-gen-end_to_end** |
| nan rows / unevaluated claims | 0/78 / 0 | 0/78 / 0 |
| Faithful-class mean (higher = fewer false flags) | **0.665 / 0.657** | 0.640 / 0.625 |
| Hallucinated-class mean (lower = correct) | **0.534 / 0.536** | 0.596 / 0.590 |
| Flagged faithful statements (rows) | 74 / 75 | 68 / 70 |
| Distinct flagged faithful statements | 27, across 8 items | 24, across 9 items |
| Verdict flips (pooled, 6 repeats) | **2** | 5 |
| Noise floor | 0 on 22 of 26, max 0.111, mean 0.009 | 0 on 21 of 26, max 0.111, mean 0.016 |

- **Newly missed: Q002-gen-end_to_end**, judged supported in 6 of 6
  repeats (0.800 → 1.000). The invented title « De l'évolution de la
  vie. » is accepted with a self-contradicting reason: the context names
  other titles and « ne mentionne pas un autre titre, donc l'œuvre en
  question est certainement » the invented one.
- **Per-item deltas well outside the baseline floor**, both ways:
  Q011 −0.444 (two of its three claims now flagged), Q008
  −0.111 (a legitimate negation flagged in some repeats), Q009 +0.167,
  Q012 +0.200; on the hallucinated side Q006-p1 +0.333, Q001-p1, Q010-p1
  and Q011-p1 +0.167. The rules change the judge's verdicts, not only its
  formatting.
- **Less stable**: 5 flipped statements pooled (Q007, Q008, Q011 and their
  perturbations) against 2.

**Verdict: rejected** (owner's decision). Once parsing is repaired in
code, the JSON rules bring no gain: they lose a hallucinated item at the
gate, raise the hallucinated-class mean, lower the faithful-class mean and
add flips. The expected outcome in `variant.yaml` (« no gain, at the cost
of a longer instruction ») held. Parse robustness stays in code (#57);
baseline v2 remains the reference.

### Judge baseline v3 (`exp/judge-baseline-v3`)

Baseline v2 rerun on the calibration set with 2 extra negations
(`feat/calibration-extra-negations`, #61): Q002-p2-negation and
Q010-p2-negation, so 4 `negation` items and 28 in all (sha256
`c9460f67…`). Nothing else changed: same committed default prompts
(unchanged hashes), judge input version 2, the 26 earlier items untouched.

Same protocol: judge mode, two identical runs of `--repeat 3`, commit
`45dd0b0` (main after #61), clean tree, temperature 0,
`ollama_chat/mistral`, RAGAS 0.3.9. Fingerprint `e3e7ac3357fd` (the set
changed), one checkpoint file per run.

- Run 1: [`prompt_cmp_judge_default_n28_20261011T090042Z`](../eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.md)
- Run 2 (rerun, for the noise floor): [`prompt_cmp_judge_default_n28_20261011T103203Z`](../eval/results/prompt_cmp_judge_default_n28_20261011T103203Z.md)
- Report (`judge_variant_report --baseline`): [`prompt_cmp_judgebase_default_20261011T120058Z`](../eval/results/prompt_cmp_judgebase_default_20261011T120058Z.md)

EXPLORATORY: n=28, below the n=50 threshold; no number here is
decision-grade.

| | v2 (run 1 / run 2), n=26 | v3 (run 1 / run 2), n=28 |
|---|---|---|
| Gate | failed, 13/14 | failed, 15/16 |
| — generated | 2/2 | 2/2 |
| — perturbed | 11/12 | 13/14 |
| — negation | 1/2 | 3/4 (see below: 1/4 on the negation itself) |
| nan rows / unevaluated claims | 0/78 / 0 | 0/84 / 0 |
| Faithful-class mean (higher = fewer false flags) | 0.665 / 0.657 | 0.671 / 0.666 |
| Hallucinated-class mean (lower = correct) | 0.534 / 0.536 (14 items) | 0.528 / 0.531 (16 items) |
| Flagged faithful statements (rows) | 74 / 75 | 73 / 74 |
| Distinct flagged faithful statements | 27, across 8 items | 27, across 8 items |
| Verdict flips (pooled, 6 repeats) | 2 (Q007 pair) | 3 (Q007 pair, Q009) |
| Noise floor | 0 on 22 of 26, max 0.111, mean 0.009 | 0 on 24 of 28, max 0.111, mean 0.012 |

#### The 26 earlier items: unchanged

Same inputs, same prompts: every per-item mean equals v2's or moves
within the run-to-run range both baselines show (Q007 0.822 / 0.711
against 0.756 / 0.767; Q011, Q009, Q004-p1, Q006-p1, Q009-p1 by one claim
in one repeat). The faithful-class shift (+0.006 / +0.009) is that noise,
not a change. Q008-p1-negation is still judged supported in 6 of 6
repeats, with the same self-contradicting reason.

#### The two new negations: the gate's 3/4 overstates

The gate counts an item as detected when any claim drawn from a segment
overlapping the fabricated substring gets verdict 0
(`flags_known_claim`, `eval/scripts/judge_selection.py`). Both new items
pass it, but not because the judge rejects the negation:

- **Q002-p2-negation** (« présents et futurs **ne sont pas** déterminés
  d'un seul coup »): the negated claim, « Tous les états… ne sont pas
  déterminés d'un seul coup, comme juxtaposés dans l'espace », is judged
  **supported** in 6 of 6 repeats (« ce qui implique que les états ne sont
  pas déterminés d'un seul coup »). The item passes the gate through two
  other claims from the same segment (« la bande d'un cinématographe »,
  « un déterminisme total »), which are false flags the judge also raises
  on the gold Q002. Worse, the verdict is inverted: the gold's correct
  claim (« … sont déterminés d'un seul coup ») is flagged in 6 of 6
  repeats. The perturbed item scores 0.444, above the gold's 0.273.
- **Q010-p2-negation** (« la mystique **n'est pas** un processus
  parallèle »): the negated claim is flagged, but with « ne fait aucune
  référence à Bergson », and the gold Q010's affirmative version
  (« La mystique est un processus parallèle… selon Bergson ») is flagged
  too, for the same reason. The gate credit comes from « l'oeuvre de la
  seule raison », also flagged on the gold. The judge doesn't tell the
  negation from the original.

Reading the claims, the judge rejects the negation itself on **1 of 4**
items: Q004-p1 (« ne sont pas le poète lui-même » flagged in every repeat,
while the gold's affirmative version is accepted). Q008-p1 and Q002-p2 are
accepted with a reason that justifies the negation; Q010-p2 isn't told
apart from the gold.

#### Verdict

**The committed defaults still fail the gate, on Q008-p1-negation only**
(15/16 in both runs, no nan, no unevaluated claim). On the 26 earlier
items, v3 reproduces v2. This is the baseline every judge variant is
compared against from now on (pass run 2 as the rerun); v2 can't be, since
`compare_prompt_results` needs the same calibration set. Nothing here
recommends a prompt change.

For a negation variant, the gate alone won't show progress on 3 of the 4
negation items: Q002-p2 and Q010-p2 already pass it for unrelated reasons.
Compare the verdict on the negated claim itself, per item and repeat,
against the gold's verdict on the affirmative version.

### Variant `judge-negation-opt` (`exp/prompt-judge-negation-opt`): rejected

The negation lead from baseline v2, measured against baseline v3. The
`nli_verifier` instruction gains a polarity rule: a statement that denies
what the context affirms (« ne … pas », « ne … plus », « aucun »,
« jamais »), or affirms what the context denies, gets verdict 0, even if
every other word matches the context; a negation the context itself states
is supported; the verdict must agree with the reason. Its examples gain one
off-domain example (Maria, Lyon, a car) with both cases: a negation that
contradicts the context (0), one the context states (1), and a denied
relation (0). `segment_claims` and the schema unchanged; no Bergson content
in the example (held-out check clean).

Same protocol as baseline v3: judge mode, two identical runs of
`--repeat 3`, commit `c6ba1ab`, clean tree, judge input version 2,
temperature 0, `ollama_chat/mistral`, RAGAS 0.3.9, one checkpoint file per
run.

- Run 1: [`prompt_cmp_judge_judge-negation-opt_n28_20261011T135344Z`](../eval/results/prompt_cmp_judge_judge-negation-opt_n28_20261011T135344Z.md)
- Run 2: [`prompt_cmp_judge_judge-negation-opt_n28_20261011T152607Z`](../eval/results/prompt_cmp_judge_judge-negation-opt_n28_20261011T152607Z.md)
- Report (`judge_variant_report`, vs baseline v3): [`prompt_cmp_judgevs_judge-negation-opt_20261012T071333Z`](../eval/results/prompt_cmp_judgevs_judge-negation-opt_20261012T071333Z.md)

EXPLORATORY: n=28, below the n=50 threshold; no number here is
decision-grade.

| | Baseline v3 (run 1 / run 2) | `judge-negation-opt` (run 1 / run 2) |
|---|---|---|
| Gate | failed, 15/16 | failed, 15/16 |
| — missed | Q008-p1-negation | Q008-p1-negation |
| nan rows / unevaluated claims | 0/84 / 0 | 0/84 / 0 |
| Faithful-class mean (higher = fewer false flags) | 0.671 / 0.666 | **0.175 / 0.174** |
| Hallucinated-class mean (lower = correct) | 0.528 / 0.531 | 0.234 / 0.230 |
| Flagged faithful statements (rows) | 73 / 74 | 138 / 139 |
| Distinct flagged faithful statements | 27, across 8 items | 51, across all 12 items |
| Verdict flips (pooled, 6 repeats) | 3 | 0 |
| Noise floor | 0 on 24 of 28, max 0.111 | 0 on 26 of 28, max 0.067 |

#### The negated claims: no verdict moves

Verdict per repeat (1 = supported, 6 repeats) on each negated claim and on
the gold's affirmative version:

| Item | Baseline: gold / negation | Variant: gold / negation |
|---|---|---|
| Q008 (« sont solidaires ») | 111111 / 111111 | **000000** / 111111 |
| Q004 (« le poète lui-même ») | 111111 / 000000 | **000000** / 000000 |
| Q002 (« déterminés d'un seul coup ») | 000000 / 111111 | 000000 / 111111 |
| Q010 (« processus parallèle ») | 000000 / 000000 | 000000 / 000000 |

The variant doesn't reject one more negation. It now rejects the gold's
correct claim on Q008, so the verdict is inverted there as on Q002, and on
Q004, the only item where baseline v3 told the negation from the original.
On Q008-p1 the reason still contradicts itself: « il est clair qu'il y a
une relation entre les deux… L'affirmation est donc en accord avec le
contexte ».

#### The faithful class collapses: the judge turns literal

Every gold but Q012 loses score, all outside the baseline floor (Q005
1.000 → 0.000, Q011 0.889 → 0.000, Q001 and Q003 1.000 → 0.500). The new
flags reject paraphrase and attribution: « il n'est pas explicitement
mentionné que Bergson a retranscrit cette expérience » (Q005), « le
contexte ne mentionne pas explicitement l'utilisation de l'image de la
boule de neige » (Q001). The lower hallucinated-class mean and the zero
flips come from that strictness, not from better detection: the judge
rejects consistently, it doesn't discriminate better.

#### Verdict

**Rejected.** The gate is unchanged, no negated claim's verdict moves, and
the faithful-class mean drops from 0.671 to 0.175. Our reading: the
wording « even if every other word matches the context » pushes mistral
toward word matching, not toward polarity. Baseline v3 remains the
reference.

### Frozen judge: baseline v3, with one accepted miss

The owner froze the **committed default** faithfulness prompts, as
measured by baseline v3 (run 1,
[`prompt_cmp_judge_default_n28_20261011T090042Z`](../eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.md)),
into `eval/frozen_judge.json`:

```
python -m eval.scripts.freeze_judge \
  eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json \
  --accept-miss Q008-p1-negation --justification "..."
```

The gate fails on Q008-p1-negation alone (15/16, both runs), judged
supported in 6 of 6 repeats. The only fix tried, `judge-negation-opt`,
moved no negation verdict and collapsed the faithful-class mean (0.671 →
0.175). The miss is accepted as a documented exception rather than by
loosening the gate: every other hallucinated item is still required.

**Known limitation: the frozen judge does not reliably detect a negation
that reverses a sentence's meaning.** It rejects the negated claim itself
on **1 of the 4** `negation` items, Q004-p1 only. Q008-p1 and Q002-p2 are
accepted with a reason that justifies the negation (on Q002 the gold's
correct affirmative is flagged instead), and Q010-p2 isn't told apart from
the gold. The gate's 3/4 on `negation` overstates it: Q002-p2 and Q010-p2
pass through other claims flagged in the same segment (baseline v3, "The
two new negations").

Consequence for generation mode: **a comparison of `generation.answer`
variants can't rely on the faithfulness score to catch an answer that
inverts the source's polarity**. A variant that introduces such errors may
score as well as one that doesn't. Where polarity matters, read the
answers (or the judged claims) by hand; a delta in faithfulness says
nothing about it. Lifting the limitation means a new judge variant,
compared against baseline v3, then a new freeze (which makes earlier
generation comparisons stale).

### Choosing a generation variant

Step 3 of "Judge first, then generation": `generation.answer` variants,
scored by the frozen judge. Same discipline as judge selection: a gate, two
axes side by side, no composite score, and the owner designates the winner.
Analysis: `eval/scripts/generation_selection.py` (pure functions); every
generation-mode result now carries its summary.

**What a run records.** Each row keeps the answer, the gold chunk ids
actually given and a hash of their text (`chunks_sha256`); the header keeps
a hash of the gold questions and their chunk ids (`gold_set_sha256`, also in
the checkpoint fingerprint) and the frozen judge's record (prompt hashes,
judge input version, accepted misses). A gold chunk missing from the index
is a failed row (nan), never an answer from fewer chunks. Two results whose
gold set or chunk text differ on any item are not comparable (a re-index
between two runs shows up here).

The frozen judge now records the **judge input version** it was measured
with (`JUDGE_INPUT_VERSION`, `src/generation/faithfulness.py`): generation
mode refuses a frozen judge whose version isn't the code's, and
`freeze_judge` refuses a result measured with another one. The committed
`eval/frozen_judge.json` got `judge_input_version: 2`, read from its source
result's header.

1. **Gate (deterministic, no judge)**: no answer, in any repeat, names a
   work title the corpus doesn't have or pairs a real title with a wrong
   year: the Layer 1 checks the guardrail itself blocks on
   (`src/generation/guardrail.py`). A failed generation is not a
   fabrication: it is nan, reported next to every mean.
2. **Two axes**, among candidates passing the gate: (a) the faithfulness
   mean by the frozen judge (higher = fewer unsupported claims); (b)
   stability: per-item score range and verdict flips over repeats, with the
   items whose answer is identical in every repeat beside them. Dominance is
   the judge's: preferred only if better-or-equal on both.
3. **Substance, beside the axes, never in them**: claims per answer,
   characters per answer, citations per answer, answers with at least one
   citation, citations to a chunk the answer wasn't given. An answer that
   says less has less to get wrong: when a candidate scores higher **with
   fewer claims per answer**, the report says its gain may come from saying
   less. Citations are not a gate: the local model often omits them from
   well-grounded answers (guardrail docstring), and the citation checks of
   older answers predate re-chunking.
4. **Polarity review, read by hand.** The frozen judge's known limitation
   (it doesn't reliably catch a negation that reverses a sentence) is not
   something a faithfulness delta can show. Every answer segment carrying a
   French negation marker (« ne/n' … pas, plus, jamais, rien, aucun… »,
   « non », « sans », « ni »; « ne … que » excluded) that the judge did not
   flag is listed; against a baseline, only the segments the variant newly
   writes for that item. A reading aid, over-inclusive on purpose, not a
   detector.

Unsupported claims are listed with the judge's reason (against a baseline:
the ones newly flagged), as for the faithful class in judge mode.

**Procedure**, mirroring the judge's:

```
# baseline: committed prompts, two runs for the noise floor
python -m eval.scripts.run_prompt_comparison --mode generation --repeat 3
python -m eval.scripts.run_prompt_comparison --mode generation --repeat 3 \
  --checkpoint eval/results/prompt_comparison_checkpoint_rerun.jsonl
python -m eval.scripts.generation_variant_report --baseline RUN1.json RUN2.json

# a variant (exp/prompt-<name>), once or twice
python -m eval.scripts.run_prompt_comparison --variant <name> --repeat 3
python -m eval.scripts.generation_variant_report --baseline RUN1.json RUN2.json \
  --variant VAR_RUN1.json [VAR_RUN2.json]
```

The rerun needs its own checkpoint (or `--fresh`): with the same
fingerprint, the second run would replay the first one's rows. The report
(`prompt_cmp_genbase_*` / `prompt_cmp_genvs_*`) has the gate per run,
faithfulness with nan and unevaluated claims per repeat, substance,
stability per run and pooled, the noise floor, the dominance verdict (only
when both pass the gate in every run), newly unsupported claims, the
polarity review and per-item deltas against the baseline floor.
`compare_prompt_results` gives the same gate, axes, warning and polarity
list for 2+ generation results.

The generation set is the gold dataset (n=12): every number is
exploratory, as in judge mode.

### Generation baseline (`exp/generation-baseline`)

Measurement only: the **committed default** `generation.answer`,
generation mode, judged by the frozen judge (baseline v3, accepted miss
Q008-p1-negation; the header reports "matches frozen_judge.json"). Two
identical runs of `--repeat 3`, commit `28f1e0d` (main after #65), temperature
0, `ollama_chat/mistral` for generation and judging, hosted fallback
disabled, judge input version 2, fingerprint `e67fae22348479f2`, one
checkpoint file per run.

- Run 1: [`prompt_cmp_generation_default_n12_20261012T082113Z`](../eval/results/prompt_cmp_generation_default_n12_20261012T082113Z.md)
- Run 2 (rerun, for the noise floor): [`prompt_cmp_generation_default_n12_20261012T093211Z`](../eval/results/prompt_cmp_generation_default_n12_20261012T093211Z.md)
- Report (`generation_variant_report --baseline`): [`prompt_cmp_genbase_default_20261012T103544Z`](../eval/results/prompt_cmp_genbase_default_20261012T103544Z.md)

EXPLORATORY: n=12, below the n=50 threshold; no number here is
decision-grade.

| | run 1 | run 2 |
|---|---|---|
| Gate (fabricated title, title/year mismatch) | passed, 36/36 | passed, 36/36 |
| nan / unevaluated claims / generation failures | 0 / 0 / 0 | 0 / 0 / 0 |
| Faithfulness mean (higher = fewer unsupported claims) | 0.836 | 0.821 |
| Unsupported claims (rows) | 53 | 58 |
| Claims / characters per answer | 7.22 / 885 | 7.44 / 885 |
| Citations per answer, answers with a citation | 0.56, 14/36 | 0.58, 15/36 |
| Citations to a chunk not given | 0 | 0 |
| Verdict flips | 1 | 1 |
| Items whose answer is identical in every repeat | 10/12 | 12/12 |

Pooled over 6 repeats: 10 of 12 answers are word-for-word identical
(Q005 and Q007 have two versions each), 1 verdict flip, max per-item range
0.222. Noise floor: 0 on 10 of 12 items, Q003 0.108 (one answer, judged
differently), Q005 0.074; max 0.108, mean 0.015.

Per item (run 1 / run 2): 1.000 on Q002, Q004, Q008, Q009; Q011 0.917,
Q001 0.875, Q003 0.958 / 0.850, Q012 0.800, Q010 0.778, Q006 0.750,
**Q005 0.519 / 0.444, Q007 0.436 / 0.436**.

#### The unsupported claims, read against the chunks: mostly false flags

25 distinct claims are flagged across both runs. Read against the gold
chunks:

- **21 are false flags**, all of them in the answer almost word for word
  (or a close paraphrase) in a given chunk. Q007 alone accounts for 11:
  « l'intelligence a pour essence de juger », « Le sujet, par cela seul
  qu'on le nomme, est défini comme invariable », etc., copied from
  1934_PM_c60, are rejected with reasons that describe 1934_PM_c68 or c45.
  Q005 has 6 (« un être malicieux ou méchant », « rapproché de nous, avec
  quelque chose de sociable et d'humain »: 1932_2S_c115 verbatim), with
  reasons that describe only James's account (c105–c113). Same pattern
  elsewhere: Q001 (« s'enfle continuellement de la durée qu'il ramasse »,
  judged as implying the opposite), Q012 (the c225 sentence on « une
  multiplicité indistincte »), Q006 and Q005 (« no mention of Bergson »,
  the known reason: chunks never name their author), and Q011
  (« ne considère pas les oscillations comme une fatalité historique »,
  rejected although c224 and c225 say it: a correct negation flagged, the
  mirror image of the frozen judge's blind spot).
- **3 are real errors**: Q003 (« cette illusion se produit lorsque l'on a
  une fausse reconnaissance », while the chunk says depersonalisation
  « n'est pas indissolublement liée à la fausse reconnaissance ; elle s'y
  rattache cependant »; flagged in some repeats only: this is the Q003
  noise), and Q010 ×2 (see below).
- **1 is borderline**: Q005 run 2's « la perception d'un tremblement de
  terre est décrite comme une réaction défensive de la nature », a
  compression of c103/c115.

So **Q005's and Q007's low scores are mostly the judge's, not the
generation's**: both have the longest contexts (9 and 4 chunks, Q007's
source chunk third of four), and the judge's reasons cite another chunk
than the one the claim comes from. Truncation doesn't explain it: the
contexts are far below `JUDGE_NUM_CTX` (16384). Open lead, not
investigated further.

#### What the judge misses: misattributed theses, not polarity

Polarity review (16 negated segments the judge accepted, read by hand): no
segment inverts its source. One distorts it: Q009's « des virtualités sans
nombre … qui ne conviennent pas à la matière inerte », where 1907_EC_c316
says the categories of unity and multiplicity, « faites pour la matière
inerte », don't suit those virtualities. One is incoherent: Q006's « la
philosophie de Berkeley ressemble suffisamment à celle de Berkeley ».

The generation errors that matter are **misattributed theses**: the
answer presents as Bergson's own thesis a view that the source raises only
to set aside or qualify. Each sentence can match the chunk; what is wrong
is the status the answer gives the idea (a hypothesis he discards, stated
as his conclusion). For example, the Q010 answer says the « forces
éruptives » « ont suscité le développement rationnel de la philosophie
grecque et l'ont conduite au-delà de la raison », while 1932_2S_c170 only
says « De là on pourrait conclure que… » before « Mais une autre
interprétation est possible ; et elle serait, à notre sens, plus
vraisemblable ». Two cases in this baseline:

- **Q010**: the example above. The interpretation Bergson prefers (Greek
  thought was the work of reason alone, with a mystical effort running
  beside it) is omitted. Two of its claims are flagged, but with reasons
  that don't name the misreading.
- **Q011**: « Il conclut en disant que la sagesse conseillerait une
  coopération des deux tendances »: c225 says « il semble que la sagesse
  conseillerait… Malheureusement… » and argues that full engagement in
  each direction gives the « maximum de création ». Accepted by the judge.

The judge has no way to catch these: each claim matches a sentence of the
chunk, and only its role in the argument is wrong.

#### Verdict

**The committed `generation.answer` passes the gate in every repeat of both
runs** (no fabricated title, no title/year mismatch, no failed generation),
scores 0.836 / 0.821, and is near-deterministic (10 of 12 answers identical
over 6 repeats, noise floor max 0.108). This was the baseline every
generation variant was compared against (pass run 2 as the rerun), until
`gen-citation-example-v2`'s promotion (whose two runs are now the baseline).

Reading the claims qualifies the score. About 21 of the 25 distinct
unsupported claims are judge false flags, concentrated on Q007 and Q005,
so **a faithfulness delta on those two items says more about the judge
than about the variant**. The real errors (Q003, Q010, Q011, Q009's
distortion) are mostly misattributed theses the frozen judge doesn't see. A
variant aimed at them can only be assessed by reading the answers. Nothing
here recommends a prompt change.

### Variant `gen-thesis-attribution` (`exp/prompt-gen-thesis-attribution`): rejected

The misattributed-thesis lead from the generation baseline (Q010, Q011).
`generation.answer` gains one fixed instruction, after the two existing
ones: « Marque une distinction claire entre une thèse que Bergson affirme
et une thèse qu'il ne fait que considérer (supposition, hypothèse
vraisemblable, ou thèse affirmée par un autre auteur). » Nothing else
changed.

One run of `--repeat 3` (generation mode, frozen judge, same models and
settings as the baseline), compared with both baseline runs:

- Run: [`prompt_cmp_generation_gen-thesis-attribution_n12_20261012T140612Z`](../eval/results/prompt_cmp_generation_gen-thesis-attribution_n12_20261012T140612Z.md)
- Report (`generation_variant_report --variant`): [`prompt_cmp_genvs_gen-thesis-attribution_20261012T151120Z`](../eval/results/prompt_cmp_genvs_gen-thesis-attribution_20261012T151120Z.md)

| | baseline (run 1 / run 2) | variant |
|---|---|---|
| Gate | passed 36/36, 36/36 | passed 36/36 |
| Faithfulness mean | 0.836 / 0.821 | 0.856 |
| Unsupported claims (rows) | 53 / 58 | 31 |
| Claims per answer | 7.22 / 7.44 | 6.00 |
| Citations per answer, answers with a citation | 0.56, 14/36 / 0.58, 15/36 | 1.67, 21/36 |
| Verdict flips | 1 / 1 | 0 |
| Unevaluated claims | 0 | 1 (Q005, repeat 1) |

The report warns that the higher score comes with fewer claims per answer.
11 of 12 answers changed; the per-item deltas mix real changes and judge
false flags (Q004's drop, 1.000 → 0.810, is « la vie ne se recompose pas…
se laisse regarder simplement », verbatim in 1900_R_c170).

#### The two targeted items: one fixed, one not

- **Q010: not fixed.** The answer still attributes the « forces
  extra-rationnelles » reading to Bergson and still omits the
  interpretation he finds « plus vraisemblable ». Its score rises from
  0.778 to 1.000 only because the answer is shorter: it lost the two
  flagged claims, not the error. The question itself (« Quelle métaphore
  géologique Bergson utilise-t-il… ? », gold `difficile`) frames the
  metaphor as his, and the correct answer has to map it onto the
  interpretation he prefers.
- **Q011: fixed.** « La sagesse conseillerait une coopération » is gone;
  the answer now says that « la tendance simple aurait peut-être mieux
  fait de croître sans se dédoubler, mais que cela aurait empêché le
  maximum de création », as 1932_2S_c225 does.

#### Elsewhere: as many errors introduced as removed

Removed: Q003's overstatement (now « liée à la fausse reconnaissance, mais
… pas indissolublement »), Q009's distortion of the « virtualités », Q006's
incoherent sentence.

Introduced:

- **Q002**: a question turned into an ungrammatical statement (« Il
  souligne que pourquoi l'univers déroule-t-il… »), and the core thesis
  (time an absolute, not an abstraction; the universe creating the new)
  partly lost.
- **Q009**: an asserted thesis hedged (« Bergson suggère que la conscience
  est essentiellement libre », where 1907_EC_c316 says « elle est la
  liberté même »), and a new misattributed thesis: « une continuité entre
  les espèces », an objection the chunk raises against spiritualism,
  presented as « cette thèse ».
- **Q011**: « ces lois sont immanentes à la liberté », where c225 says
  « N'abusons pas du mot "loi" dans un domaine qui est celui de la
  liberté ».
- **Q012**: the law of dichotomy assigned to the evolution of life and
  double frenzy to social life, a split c225 doesn't make.

The polarity review lists no inverted negation.

#### Verdict

**Rejected.** One of the two targeted errors is fixed, the main one (Q010)
isn't, and the side effects cancel the gains. Our reading: mistral applies
the abstract instruction as a general hedging style (« suggère », « peut
être interprétée »), not by finding the source's own markers: it hedges a
thesis Bergson asserts (Q009) and leaves alone the hypothesis he sets aside
(Q010). Rewording the instruction is unlikely to change that much: at
temperature 0 any change moves almost every answer, so with two targeted
items and one run a fix can't be told apart from that perturbation (Q011's
may be one). Naming the literal markers (« on pourrait conclure », « il
semble que », « une autre interprétation … plus vraisemblable ») is the one
rewording with a real chance, but it would be written from Q010 and tested
on Q010.

Side effect worth noting: answers cite almost three times as often
(1.67 citations per answer, against 0.56), though the format varies (a list
at the end, « (Citations : …) »), rarely inline. The committed
`generation.answer` stays in production.

### Variant `gen-citation-inline` (`exp/prompt-gen-citation-inline`): rejected

The citation lead from the generation baseline and `gen-thesis-attribution`.
In the baseline, 21–22 of 36 answers cite nothing; Q001, Q002, Q009, Q010
and Q011 never cite in any of 9 repeats; no citation is followed by more
prose (all sit at the end of the answer). The formats vary: chunk_ids
without brackets (Q008), a closing « (Citations : …) » block (Q007), a
list of brackets followed by title and pages (Q012), one bracket grouping
all 9 chunks (Q005). The variant replaces the first instruction (the
abstract « chaque affirmation doit être rattachée à un passage précis »)
with a concrete one: « Cite tes sources dans le corps du texte : chaque
phrase qui rapporte le contenu d'un extrait se termine par le chunk_id de
cet extrait entre crochets, juste avant le point (ex. : « La durée est
invention [1907_EC_c5]. »). Cite même lorsqu'il n'y a qu'un seul extrait.
Si une phrase s'appuie sur deux extraits, mets un crochet par extrait
([1907_EC_c5] [1907_EC_c6]) ; ne regroupe jamais plusieurs extraits dans
un même crochet. Le crochet ne contient que le chunk_id, sans titre ni
page, et la réponse ne se termine par aucune liste de références. »
Nothing else changed.

One run of `--repeat 3`, same models and settings as the baseline:

- Run: [`prompt_cmp_generation_gen-citation-inline_n12_20261013T073443Z`](../eval/results/prompt_cmp_generation_gen-citation-inline_n12_20261013T073443Z.md)
- Report (`generation_variant_report --variant`): [`prompt_cmp_genvs_gen-citation-inline_20261013T084827Z`](../eval/results/prompt_cmp_genvs_gen-citation-inline_20261013T084827Z.md)

| | baseline (run 1 / run 2) | variant |
|---|---|---|
| Gate | passed 36/36, 36/36 | passed 36/36 |
| Faithfulness mean | 0.836 / 0.821 | 0.789 |
| Unsupported claims (rows) | 53 / 58 | 57 |
| Claims / characters per answer | 7.22 / 7.44, 885 | 7.53, 982 |
| Citations per answer, answers with a citation | 0.56, 14/36 / 0.58, 15/36 | 0.61, 10/36 |
| Citations followed by more prose | 0 / 0 | 10 (all Q005, lines of a closing list) |
| Citations to a chunk not given | 0 | 0 |
| Verdict flips | 1 / 1 | 2 |

#### Citations: the opposite of the target

Fewer answers cite (10/36 against 14–15), and no answer puts a bracket at
the end of each sentence. Every clause is broken somewhere:

- **Closing list with title and pages**: Q005 repeat 1 lists the 10 chunks
  under « Sources : », each followed by work, section and pages.
- **Parentheses instead of brackets**: Q006 writes `(1934_PM_c96)` in all
  3 repeats, which `CITATION_PATTERN` doesn't count; the baseline cited it
  in brackets.
- **All brackets at the end**: Q008 puts `[1896_MM_c7] [1919_ES_c32]` after
  the last sentence only.
- **Citations lost** where the baseline had them: Q003, Q006, Q012.
- Q002, Q009, Q010, Q011 still never cite. Only Q001 improves (one
  citation, at the end).

The citations that remain name the right chunk.

#### Faithfulness

Lower, with longer answers (7.53 claims per answer): the drop isn't a
shorter answer's. Q001, Q002, Q006, Q012 drop outside the noise floor;
Q005 and Q010 rise. Read by hand: Q006's drop (0.750 → 0.458) is mostly
judge false flags (« no mention of Bergson »), but « Bergson reconstitue
la pensée de Berkeley » takes the ironic « salade » that 1934_PM_c96 sets
aside for his own method, a misattributed thesis. Q012 now states
« Il semble que la sagesse conseillerait une coopération des deux
tendances » as Bergson's conclusion: the baseline's Q011 error, moved to
another item. Q010's 1.000 is worthless: the « forces extra-rationnelles…
au-delà de la raison » misreading is still there. The polarity review lists
no inverted negation.

#### Verdict

**Rejected.** Mistral 7B at temperature 0 doesn't follow a detailed format
instruction, and the rewording unsettled the formats that worked (Q003,
Q006, Q012). Two leads: show the format (a short, fully cited answer as an
example), which the next variant on this branch tests; or attach each
sentence to a chunk in code, after generation, which stops relying on the
model. The committed `generation.answer` stays in production.

### Variant `gen-citation-example` (`exp/prompt-gen-citation-inline`): partial, superseded by v2

Same targeted failure as `gen-citation-inline`, run on the same branch at
the owner's request. Since mistral doesn't follow a reworded format
instruction, this variant shows the format instead: the committed citation
instruction is kept as is, and one correctly cited example answer is added
after the instructions, on another question, from real excerpts unrelated
to the gold questions (1900_R_c12, c13, c18, the comic of a man falling).
Four sentences, each ending with its bracket before the period, one with
two brackets, no closing list, and a note not to reuse its content or
chunk_ids. Nothing else changed.

- Run: [`prompt_cmp_generation_gen-citation-example_n12_20261013T085532Z`](../eval/results/prompt_cmp_generation_gen-citation-example_n12_20261013T085532Z.md)
- Report (`generation_variant_report --variant`): [`prompt_cmp_genvs_gen-citation-example_20261013T100728Z`](../eval/results/prompt_cmp_genvs_gen-citation-example_20261013T100728Z.md)

| | baseline (run 1 / run 2) | `gen-citation-inline` | variant |
|---|---|---|---|
| Gate | passed 36/36, 36/36 | passed 36/36 | passed 36/36 |
| Answers with a citation | 14/36 / 15/36 | 10/36 | **28/36** |
| Citations per answer | 0.56 / 0.58 | 0.61 | 1.83 |
| Citations to a chunk not given | 0 | 0 | 0 |
| Faithfulness mean | 0.836 / 0.821 | 0.789 | 0.707 |
| Unsupported claims (rows) | 53 / 58 | 57 | 74 |
| Claims per answer | 7.22 / 7.44 | 7.53 | 6.94 |
| Answers opening with « Selon Bergson » | 6 / 6 | 5 | **28** |

#### Citations: a real gain, not yet per sentence

Q001, Q009 and Q010, which never cited in the baseline, now do; Q003 and
Q004 cite every sentence, as the example does. The stray formats are gone
(no bare chunk_ids, no parentheses, no « Sources » list with title and
pages). The example's content isn't reused: no answer cites 1900_R_c12,
c13 or c18 (Q010's « élasticité » is in 1932_2S_c170). What remains: 42
of 178 sentences carry a citation, most answers having one bracket at the
end; Q005 (all 10 chunks), Q007 and Q011 group several chunk_ids in one
bracket, which inflates citations per answer; Q002 and Q012 never cite.

#### Faithfulness: the example's opener, copied

The example opens with « Selon Bergson, … », and 28 of 36 answers now do
(6 in the baseline). The judge often rejects a claim attributed to Bergson
because the chunks never name their author (the known false flag): rejections
whose reason is « Bergson not mentioned » rise from 15 to 27, about a dozen
of the 16–21 extra rejections. Q012 appends « selon l'œuvre de Henri
Bergson » to each sentence. Read against the chunks, the other new flags
are mostly false too (Q003's two claims and Q004's are verbatim; Q006's
« recette de cuisine » renders the chunk's « salade »); a few are small
real distortions: Q002 (« rigoureusement déterminé » is said of the
impatience in 1907_EC_c398, not of the duration), Q005 (« la conception
scientifique… dangereuse », an extrapolation), Q009 (materiality equated
with the movement of matter).

Unplanned: **Q010 is partly fixed**. The answer now gives the other
interpretation (Greek thought the work of reason alone, a mystical effort
beside it), though without saying Bergson finds it « plus vraisemblable ».
Q011 still states « la sagesse conseillerait une coopération » as his
conclusion.

#### Verdict

**Partial, not promotable as is.** Showing the format is the lever that
works (answers with a citation 14–15 → 28 of 36), but the example also
imposes an opener that trips the judge. Next: `gen-citation-example-v2`,
the same example without the attribution opener, plus sentences drawn from
several excerpts, one citing two in separate brackets (aimed at Q005, Q007,
Q011's grouped brackets).

### Variant `gen-citation-example-v2` (`exp/prompt-gen-citation-inline`): promoted

`gen-citation-example` with its two failures addressed, run on the same
branch at the owner's request. Same example, against the committed
`generation.answer`, with two changes: no attribution to Bergson anywhere
in it (it now opens « Ce n'est pas le changement brusque d'attitude qui
fait rire… »), and one more sentence, from 1900_R_c18, so that it shows
three excerpts each cited on its own and a synthesis sentence citing two
in separate brackets. Nothing else changed.

Two runs of `--repeat 3` (the second with its own checkpoint), same models
and settings as the baseline:

- Run 1: [`prompt_cmp_generation_gen-citation-example-v2_n12_20261013T101340Z`](../eval/results/prompt_cmp_generation_gen-citation-example-v2_n12_20261013T101340Z.md)
- Run 2: [`prompt_cmp_generation_gen-citation-example-v2_n12_20261013T113959Z`](../eval/results/prompt_cmp_generation_gen-citation-example-v2_n12_20261013T113959Z.md)
- Report (`generation_variant_report --variant`, both runs): [`prompt_cmp_genvs_gen-citation-example-v2_20261013T124502Z`](../eval/results/prompt_cmp_genvs_gen-citation-example-v2_20261013T124502Z.md)

| | baseline (run 1 / run 2) | `gen-citation-example` | variant (run 1 / run 2) |
|---|---|---|---|
| Gate | passed 36/36, 36/36 | passed 36/36 | passed 36/36, 36/36 |
| Answers with a citation | 14/36 / 15/36 | 28/36 | **28/36** / 28/36 |
| Sentences followed by a citation | 14/160 (run 1) | 42/178 | 28/155 |
| Brackets grouping several chunks | 0 | 8 | 7 (Q002, Q005, Q007) |
| Citations to a chunk not given, example chunk_ids reused | 0, — | 0, 0 | 0, 0 |
| Answers opening with « Selon Bergson » | 6 / 6 | 28 | **3** |
| Rejections « Bergson not mentioned » | 15 / 15 | 27 | 17 |
| Faithfulness mean | 0.836 / 0.821 | 0.707 | **0.860 / 0.862** |
| Claims per answer | 7.22 / 7.44 | 6.94 | 6.22 |
| Noise floor (max) | 0.108 | — | 0.133 (Q002) |
| Answers identical over 6 repeats, max per-item range | 10/12, 0.222 | — | 7/12, 0.333 |

No dominance: the report gives a trade-off (the variant has the higher
faithfulness mean, the baseline is more stable), and warns that the higher
score comes with fewer claims per answer.

#### Citations

The first change does what it was for: without an attribution in the
example, the « Selon Bergson » opener is gone (3 of 36) and the judge's
« Bergson not mentioned » false flags fall back to the baseline's level.
The citation gain holds: 28 of 36 answers cite, with no stray format (bare
chunk_ids, parentheses, title and pages) and no example chunk_id reused.
The second change has no effect: Q002, Q005 and Q007 still group their
chunks in one bracket, and Q012 (repeat 1) lists them on separate lines at
the end. Citations are not per sentence: nearly every answer has one
bracket, at the end (Q003 and Q004 cited per sentence in
`gen-citation-example`, no longer here). Q007, Q009, Q011 and Q012 don't
cite in at least one repeat.

#### Errors, read against the chunks

| | baseline | variant |
|---|---|---|
| Q003: depersonalisation tied to false recognition, overstated | some repeats | fixed |
| Q010: the reading Bergson sets aside, given as his thesis | present | partly fixed (the other interpretation is given, not his preference for it) |
| « La sagesse conseillerait une coopération » given as his conclusion | Q011 | moved to Q012 (repeats 2, 3) |
| Q006: the ironic « salade » given as his method | incoherent sentence | present |
| Q011: « accentuer les dangers », where 1932_2S_c225 says « supprime le danger » | — | new (repeat 1), accepted by the judge |

Roughly even. The rest of the flagged claims are mostly the known false
flags (Q001, Q002, Q005, Q010).

#### Determinism: the second run measures the judge only

Run 2's 36 answers are byte-identical to run 1's, repeat for repeat
(baseline: 34/36); on them, the judge rewords 33 reasons, segments 3 rows
differently and flips 5 verdicts out of about 220 claims. So the variant's
noise floor is the judge's alone. Both run greedy at temperature 0, but
small numerical differences on the Ollama server (plausibly prompt-prefix
cache reuse, `q8_0` KV cache, flash attention) change a token at near-ties,
which generation, one call mostly copying the excerpts, rarely meets, and
the judge, about 8 calls of free-form reasons over up to 16k tokens, often
does. The server's state matters (within a run, generation repeats differ
on 5 items, yet repeat *n* is identical across runs); why the judge's
sequential calls don't replay identically is not explained.

#### Verdict

**Tested, candidate for promotion** (the owner's call), on citation
presence: answers with a citation 14–15 → 28 of 36, stray formats gone,
faithfulness not lower beyond the noise, real errors roughly even. Not a
fix for per-sentence citation: mistral takes « one citation at the end »
from the example, not « one per sentence »; that would need attaching
sentences to chunks in code, after generation.

#### Promotion (`feat/promote-gen-citation-example-v2`)

The variant's `generation/answer.md` is now `prompts/generation/answer.md`,
version `v2` (description updated; the body is the variant's, byte for
byte, so its hash, `c2b0419a…`, is the one both variant runs recorded).
The golden snapshots gain the 4 lines of the example in each
`generation.user.txt`, nothing else. Before/after numbers are the two
tables above (baseline vs variant, two runs each).

Consequence: the generation baseline (`exp/generation-baseline`) measured
`generation.answer` v1. **The two variant runs above are the new
baseline**: they measured this exact body (same hash), and comparability
is checked per prompt on (hash, version), so a next variant differs from
them in `generation.answer` only. Pass them as `--baseline RUN1.json
RUN2.json`; their noise floor is the judge's alone (see "Determinism"
above). A fresh run of the committed v2 would show as differing from them
(version `v2` vs `v1`, same hash): only needed to re-measure the noise.

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
  freeze-judge refusals and accepted misses, the judge input version in
  the frozen record, and generation mode's frozen-judge refusal. No model
  call.
- `tests/test_generation_comparison.py` — generation selection: negation
  markers, the fabrication gate, substance (claims counted only where the
  judge answered), identical answers, the polarity review and its "newly
  asserted" filter, the fewer-claims warning, comparability on the gold set
  and chunk text, both reports, and the harness's generation-mode records
  (chunk hashes, a missing gold chunk refused, the frozen judge's record).
  No model call, no `data/processed`.

`tests/test_prompt_comparison_smoke.py` (slow) runs each mode once against
a real model with a throwaway fixture variant
(`tests/fixtures/prompt_variants/`): plumbing only.

The built-image check is a script, not part of CI (building the api image
takes minutes): `make test-container-prompts` builds the image and
compares the manifest inside the container with the host's.

## Packaging

The API image copies `prompts/` to `/app/prompts`, next to `src/`
(`Dockerfile`). The native `ml_service` runs no LLM and loads no prompt.
