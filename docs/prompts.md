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
- **Too few negation items to judge it.** The calibration set has 2
  `negation` perturbations: Q004-p1, caught, and Q008-p1, missed. A variant
  tuned on Q008-p1 alone could fix that item without fixing negation.
  Adding `negation` perturbations first (`eval/scripts/calibration_set.py`,
  `_negate`) changes the calibration set's sha256. The baseline would then
  have to be rerun before any variant is compared to it.
- **Watch the faithful class.** Gold answers contain legitimate negations
  (e.g. Q008's « on ne peut pas en conclure que la forme du clou dessine
  celle du vêtement »). A stricter negation rule must not lower the
  faithful-class mean: check its flagged faithful statements against
  baseline v2's.

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
