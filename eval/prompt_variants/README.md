# Prompt variants

Lab notebook of prompt variants compared with
`eval/scripts/run_prompt_comparison.py`. Method, modes and selection rules:
[`docs/prompts.md`, "Comparing prompt variants"](../../docs/prompts.md#comparing-prompt-variants-featprompt-comparison).

## Registry

One row per variant, kept up to date by whoever runs it. Rejected variants
stay here and on disk: they're the record of what was tried.

| Variant | Family | Targeted failure | Status | Results | Branch |
|---|---|---|---|---|---|
| `judge-parsing-opt` | faithfulness | JSON parse failures of the first judge baseline (Q001-p1, Q010-p1, Q002-gen), since repaired in code (#57) | rejected | [vs baseline v2](../results/prompt_cmp_judgevs_judge-parsing-opt_20261010T140431Z.md): gate 12/14 (newly misses Q002-gen), faithful mean 0.640 / 0.625 | `exp/prompt-judge-parsing-opt` |
| `judge-negation-opt` | faithfulness | Q008-p1-negation accepted 6/6 in baseline v3 (negated claim itself rejected on 1 of 4 negation items) | rejected | [vs baseline v3](../results/prompt_cmp_judgevs_judge-negation-opt_20261012T071333Z.md): gate 15/16 (Q008-p1 still missed), faithful mean 0.175 / 0.174 | `exp/prompt-judge-negation-opt` |
| `gen-thesis-attribution` | generation | Misattributed theses in the generation baseline: Q010 (« forces éruptives » reading Bergson sets aside, given as his thesis), Q011 | rejected | [vs generation baseline](../results/prompt_cmp_genvs_gen-thesis-attribution_20261012T151120Z.md): gate 36/36, faithfulness 0.856 with fewer claims per answer (6.0 vs 7.3); Q011 fixed, Q010 not, as many errors introduced as removed | `exp/prompt-gen-thesis-attribution` |
| `gen-citation-inline` | generation | Citations in the generation baseline: 21–22/36 answers cite nothing, Q001/Q002/Q009/Q010/Q011 never cite, none per sentence, unstable formats (bare ids, closing lists, title and pages, one bracket for 9 chunks) | rejected | [vs generation baseline](../results/prompt_cmp_genvs_gen-citation-inline_20261013T084827Z.md): gate 36/36, faithfulness 0.789 with more claims per answer (7.5 vs 7.3); answers with a citation down to 10/36, none per sentence | `exp/prompt-gen-citation-inline` |
| `gen-citation-example` | generation | Same as `gen-citation-inline`; shows the format with one cited example answer instead of rewording | tested (partial, superseded by v2) | [vs generation baseline](../results/prompt_cmp_genvs_gen-citation-example_20261013T100728Z.md): gate 36/36, answers with a citation 28/36 (baseline 14–15), faithfulness 0.707, mostly « Bergson not mentioned » false flags from the example's copied « Selon Bergson » opener | `exp/prompt-gen-citation-inline` |
| `gen-citation-example-v2` | generation | `gen-citation-example`'s copied « Selon Bergson » opener (judge false flags 15 → 27) and grouped brackets (Q005, Q007, Q011) | promoted (`feat/promote-gen-citation-example-v2`) | [vs generation baseline, two runs](../results/prompt_cmp_genvs_gen-citation-example-v2_20261013T124502Z.md): gate 36/36 ×2, answers with a citation 28/36, opener gone, faithfulness 0.860 / 0.862 with fewer claims per answer (6.2 vs 7.3); grouped brackets remain, one citation at the end | `exp/prompt-gen-citation-inline` |

Generation variants (`generation/answer.md`) are judged by the frozen
judge against a generation baseline (two runs of the committed
`generation.answer`; since v2, the two `gen-citation-example-v2` runs):
`eval/scripts/generation_variant_report.py`, rules in
[`docs/prompts.md`, "Choosing a generation variant"](../../docs/prompts.md#choosing-a-generation-variant).
Their faithfulness score can't show a polarity inversion: read the report's
polarity review list.

## Layout

```
eval/prompt_variants/<name>/
├── variant.yaml
└── faithfulness/                 # or generation/, never both
    ├── nli_verifier.md           # only the files that differ from prompts/
    └── nli_verifier.examples.yaml
```

A variant is a partial overlay of `prompts/`: same layout, only the files
that differ. A `.md` file may keep its front-matter header (same `id`, same
`variables`) or hold the bare body. Comparable files:
`generation/answer.md`, and the faithfulness family
(`faithfulness/segment_claims.md`, `faithfulness/nli_verifier.md` and their
`.examples.yaml` files). Refused: anything under `judge_chunk/` (no ground
truth), `generation/system.md`, `*.schema.yaml` (descriptions compiled into
Python classes), and generation and faithfulness files together.

`variant.yaml`:

```yaml
name: <directory name>
hypothesis: The observed failure this variant targets (item ids, result file).
based_on:            # default hash of every prompt in the family, at creation
  faithfulness.segment_claims: <hash>
  faithfulness.nli_verifier: <hash>
status: draft        # draft | tested | rejected | promoted
results: []          # result files (eval/results/prompt_cmp_*.json)
```

Current hashes: `uv run python -c "from src.prompts.loader import get_prompt_manifest as m; print(m())"`.
If a default changes after the variant is written, runs warn and the
header says STALE (not blocked).

## Rules

- **A variant starts from an observed failure**: a result file, an item, a
  statement, written in `hypothesis`. No speculative rewording.
- **One variable at a time**: one family per variant, enforced.
- **One `exp/` branch per variant** (`exp/prompt-<name>`), holding the
  variant directory and its result files. This directory on `main` only
  gets what those branches merge.
- **Rejected variants are kept**, status `rejected`, with their results:
  a lab notebook, not a graveyard to clean up.
- **Promotion** = copying the variant's files into `prompts/` in their own
  branch, with the version label bumped, golden snapshots regenerated, and
  before/after numbers in the PR (`docs/prompts.md`, "Rules for changing a
  prompt"). Then status `promoted`. A promoted faithfulness variant changes
  the judge: freeze it again, and earlier generation comparisons are
  invalidated.
