# Judge variant `judge-negation-opt` vs baseline

> **EXPLORATORY: n=28 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json`, `eval/results/prompt_cmp_judge_default_n28_20261011T103203Z.json`
- **variant**: `eval/results/prompt_cmp_judge_judge-negation-opt_n28_20261011T135344Z.json`, `eval/results/prompt_cmp_judge_judge-negation-opt_n28_20261011T152607Z.json`
- **Differs in**: faithfulness

## Gate (every hallucinated item flagged, in every repeat)

| candidate | run | gate | detected/items per origin | per perturbation type | missed |
|---|---|---|---|---|---|
| default | 1 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| default | 2 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| judge-negation-opt | 1 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| judge-negation-opt | 2 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |

Missed by default, detections per repeat (run 1 / run 2 …):
- Q008-p1-negation (judged supported ×6): [F,F,F] / [F,F,F]

Missed by judge-negation-opt, detections per repeat (run 1 / run 2 …):
- Q008-p1-negation (judged supported ×6): [F,F,F] / [F,F,F]

- Newly caught: —
- Newly missed: —
- Still missed: Q008-p1-negation

## Class means and nan (per run)

| candidate | run | faithful (higher = fewer false flags) | hallucinated (lower = correct) | nan rows | nan per repeat, faithful | nan per repeat, hallucinated | unevaluated per repeat, faithful | unevaluated per repeat, hallucinated | flagged faithful statements |
|---|---|---|---|---|---|---|---|---|---|
| default | 1 | 0.671 | 0.528 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 73 |
| default | 2 | 0.666 | 0.531 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 74 |
| judge-negation-opt | 1 | 0.175 | 0.234 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 138 |
| judge-negation-opt | 2 | 0.174 | 0.230 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 139 |

Distinct flagged faithful statements, default (all runs): 27 across 8 items (Q002, Q004, Q006, Q007, Q009, Q010, Q011, Q012)

Distinct flagged faithful statements, judge-negation-opt (all runs): 51 across 12 items (Q001, Q002, Q003, Q004, Q005, Q006, Q007, Q008, Q009, Q010, Q011, Q012)

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run |
|---|---|---|---|---|---|---|
| default | run 1 | 0.026 | 0.333 | 2 | 143 | 16 |
| default | run 2 | 0.034 | 0.333 | 2 | 144 | 8 |
| default | pooled (2 runs, 6 repeats) | 0.043 | 0.333 | 3 | 152 | 10 |
| judge-negation-opt | run 1 | 0.017 | 0.250 | 0 | 142 | 14 |
| judge-negation-opt | run 2 | 0.011 | 0.250 | 0 | 142 | 14 |
| judge-negation-opt | pooled (2 runs, 6 repeats) | 0.018 | 0.250 | 0 | 155 | 4 |

Flipped statements, default (pooled): 3
- Q007: Cette assimilation est utile à la vie pratique et à la plupart des sciences.
- Q009: L'humanité perpétue la même poussée vitale, agissante et créatrice en traversant la matérialité et la nécessité.
- Q007-p1-unsupported_sentence: Cette assimilation est utile à la vie pratique et à la plupart des sciences.

Flipped statements, judge-negation-opt (pooled): 0

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 24 items; nonzero: Q007 0.111, Q009 0.056, Q006-p1-unsupported_sentence 0.111, Q009-p1-unsupported_sentence 0.071; nan on 0 (—); max 0.111, mean 0.012 over 28 finite items
- **judge-negation-opt**: 0 on 26 items; nonzero: Q007 0.011, Q002-gen-end_to_end 0.067; nan on 0 (—); max 0.067, mean 0.003 over 28 finite items

## Selection axes (only if both pass the gate)

- Not applicable: at least one candidate fails the gate in some run.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | judge-negation-opt run 1 | judge-negation-opt run 2 |
|---|---|---|---|---|
| Q001 | 1.000 (0/3) | 1.000 (0/3) | 0.500 (0/3) | 0.500 (0/3) |
| Q002 | 0.273 (0/3) | 0.273 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q003 | 1.000 (0/3) | 1.000 (0/3) | 0.500 (0/3) | 0.500 (0/3) |
| Q004 | 0.500 (0/3) | 0.500 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q005 | 1.000 (0/3) | 1.000 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q006 | 0.667 (0/3) | 0.667 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q007 | 0.822 (0/3) | 0.711 (0/3) | 0.200 (0/3) | 0.189 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 0.333 (0/3) | 0.333 (0/3) |
| Q009 | 0.167 (0/3) | 0.222 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q010 | 0.333 (0/3) | 0.333 (0/3) | 0.167 (0/3) | 0.167 (0/3) |
| Q011 | 0.889 (0/3) | 0.889 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q012 | 0.400 (0/3) | 0.400 (0/3) | 0.400 (0/3) | 0.400 (0/3) |
| Q002-gen-end_to_end | 0.800 (0/3) | 0.800 (0/3) | 0.467 (0/3) | 0.400 (0/3) |
| Q004-gen-end_to_end | 0.400 (0/3) | 0.400 (0/3) | 0.200 (0/3) | 0.200 (0/3) |
| Q001-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) | 0.250 (0/3) | 0.250 (0/3) |
| Q002-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) | 0.111 (0/3) | 0.111 (0/3) |
| Q003-p1-unsupported_sentence | 0.667 (0/3) | 0.667 (0/3) | 0.333 (0/3) | 0.333 (0/3) |
| Q004-p1-negation | 0.400 (0/3) | 0.400 (0/3) | 0.200 (0/3) | 0.200 (0/3) |
| Q005-p1-proper_noun | 0.667 (0/3) | 0.667 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q006-p1-unsupported_sentence | 0.333 (0/3) | 0.444 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q007-p1-unsupported_sentence | 0.619 (0/3) | 0.619 (0/3) | 0.286 (0/3) | 0.286 (0/3) |
| Q008-p1-negation | 1.000 (0/3) | 1.000 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q009-p1-unsupported_sentence | 0.357 (0/3) | 0.286 (0/3) | 0.137 (0/3) | 0.137 (0/3) |
| Q010-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) | 0.000 (0/3) | 0.000 (0/3) |
| Q011-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) | 0.417 (0/3) | 0.417 (0/3) |
| Q012-p1-unsupported_sentence | 0.600 (0/3) | 0.600 (0/3) | 0.400 (0/3) | 0.400 (0/3) |
| Q002-p2-negation | 0.444 (0/3) | 0.444 (0/3) | 0.111 (0/3) | 0.111 (0/3) |
| Q010-p2-negation | 0.500 (0/3) | 0.500 (0/3) | 0.167 (0/3) | 0.167 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | label | origin | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|---|---|
| Q001 | faithful | gold | 1.000 | 0.500 | -0.500 | 0.000 | outside noise |
| Q002 | faithful | gold | 0.273 | 0.000 | -0.273 | 0.000 | outside noise |
| Q003 | faithful | gold | 1.000 | 0.500 | -0.500 | 0.000 | outside noise |
| Q004 | faithful | gold | 0.500 | 0.000 | -0.500 | 0.000 | outside noise |
| Q005 | faithful | gold | 1.000 | 0.000 | -1.000 | 0.000 | outside noise |
| Q006 | faithful | gold | 0.667 | 0.000 | -0.667 | 0.000 | outside noise |
| Q007 | faithful | gold | 0.822 | 0.200 | -0.622 | 0.111 | outside noise |
| Q008 | faithful | gold | 1.000 | 0.333 | -0.667 | 0.000 | outside noise |
| Q009 | faithful | gold | 0.167 | 0.000 | -0.167 | 0.056 | outside noise |
| Q010 | faithful | gold | 0.333 | 0.167 | -0.167 | 0.000 | outside noise |
| Q011 | faithful | gold | 0.889 | 0.000 | -0.889 | 0.000 | outside noise |
| Q012 | faithful | gold | 0.400 | 0.400 | 0.000 | 0.000 | within noise |
| Q002-gen-end_to_end | hallucinated | generated | 0.800 | 0.467 | -0.333 | 0.000 | outside noise |
| Q004-gen-end_to_end | hallucinated | generated | 0.400 | 0.200 | -0.200 | 0.000 | outside noise |
| Q001-p1-unsupported_sentence | hallucinated | perturbed | 0.500 | 0.250 | -0.250 | 0.000 | outside noise |
| Q002-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.111 | -0.222 | 0.000 | outside noise |
| Q003-p1-unsupported_sentence | hallucinated | perturbed | 0.667 | 0.333 | -0.333 | 0.000 | outside noise |
| Q004-p1-negation | hallucinated | perturbed | 0.400 | 0.200 | -0.200 | 0.000 | outside noise |
| Q005-p1-proper_noun | hallucinated | perturbed | 0.667 | 0.000 | -0.667 | 0.000 | outside noise |
| Q006-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.000 | -0.333 | 0.111 | outside noise |
| Q007-p1-unsupported_sentence | hallucinated | perturbed | 0.619 | 0.286 | -0.333 | 0.000 | outside noise |
| Q008-p1-negation | hallucinated | perturbed | 1.000 | 0.667 | -0.333 | 0.000 | outside noise |
| Q009-p1-unsupported_sentence | hallucinated | perturbed | 0.357 | 0.137 | -0.220 | 0.071 | outside noise |
| Q010-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.000 | -0.333 | 0.000 | outside noise |
| Q011-p1-unsupported_sentence | hallucinated | perturbed | 0.500 | 0.417 | -0.083 | 0.000 | outside noise |
| Q012-p1-unsupported_sentence | hallucinated | perturbed | 0.600 | 0.400 | -0.200 | 0.000 | outside noise |
| Q002-p2-negation | hallucinated | perturbed | 0.444 | 0.111 | -0.333 | 0.000 | outside noise |
| Q010-p2-negation | hallucinated | perturbed | 0.500 | 0.167 | -0.333 | 0.000 | outside noise |
