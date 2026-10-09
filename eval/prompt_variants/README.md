# Prompt variants

Lab notebook of prompt variants compared with
`eval/scripts/run_prompt_comparison.py`. Method, modes and selection rules:
[`docs/prompts.md`, "Comparing prompt variants"](../../docs/prompts.md#comparing-prompt-variants-featprompt-comparison).

## Registry

One row per variant, kept up to date by whoever runs it. Rejected variants
stay here and on disk: they're the record of what was tried.

| Variant | Family | Targeted failure | Status | Results | Branch |
|---|---|---|---|---|---|
| `judge-parsing-opt` | faithfulness | JSON parse failures of the first judge baseline (Q001-p1, Q010-p1, Q002-gen), since repaired in code (#57) | draft | — | `exp/prompt-judge-parsing-opt` |

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
