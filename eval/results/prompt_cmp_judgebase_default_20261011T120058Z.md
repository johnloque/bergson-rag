# Judge baseline

> **EXPLORATORY: n=28 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json`, `eval/results/prompt_cmp_judge_default_n28_20261011T103203Z.json`

## Gate (every hallucinated item flagged, in every repeat)

| candidate | run | gate | detected/items per origin | per perturbation type | missed |
|---|---|---|---|---|---|
| default | 1 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| default | 2 | FAILED | generated 2/2, perturbed 13/14 | negation 3/4, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |

Missed by default, detections per repeat (run 1 / run 2 …):
- Q008-p1-negation (judged supported ×6): [F,F,F] / [F,F,F]

## Class means and nan (per run)

| candidate | run | faithful (higher = fewer false flags) | hallucinated (lower = correct) | nan rows | nan per repeat, faithful | nan per repeat, hallucinated | unevaluated per repeat, faithful | unevaluated per repeat, hallucinated | flagged faithful statements |
|---|---|---|---|---|---|---|---|---|---|
| default | 1 | 0.671 | 0.528 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 73 |
| default | 2 | 0.666 | 0.531 | 0/84 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | r1 0/12, r2 0/12, r3 0/12 | r1 0/16, r2 0/16, r3 0/16 | 74 |

Distinct flagged faithful statements, default (all runs): 27 across 8 items (Q002, Q004, Q006, Q007, Q009, Q010, Q011, Q012)

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run |
|---|---|---|---|---|---|---|
| default | run 1 | 0.026 | 0.333 | 2 | 143 | 16 |
| default | run 2 | 0.034 | 0.333 | 2 | 144 | 8 |
| default | pooled (2 runs, 6 repeats) | 0.043 | 0.333 | 3 | 152 | 10 |

Flipped statements, default (pooled): 3
- Q007: Cette assimilation est utile à la vie pratique et à la plupart des sciences.
- Q009: L'humanité perpétue la même poussée vitale, agissante et créatrice en traversant la matérialité et la nécessité.
- Q007-p1-unsupported_sentence: Cette assimilation est utile à la vie pratique et à la plupart des sciences.

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 24 items; nonzero: Q007 0.111, Q009 0.056, Q006-p1-unsupported_sentence 0.111, Q009-p1-unsupported_sentence 0.071; nan on 0 (—); max 0.111, mean 0.012 over 28 finite items

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 |
|---|---|---|
| Q001 | 1.000 (0/3) | 1.000 (0/3) |
| Q002 | 0.273 (0/3) | 0.273 (0/3) |
| Q003 | 1.000 (0/3) | 1.000 (0/3) |
| Q004 | 0.500 (0/3) | 0.500 (0/3) |
| Q005 | 1.000 (0/3) | 1.000 (0/3) |
| Q006 | 0.667 (0/3) | 0.667 (0/3) |
| Q007 | 0.822 (0/3) | 0.711 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) |
| Q009 | 0.167 (0/3) | 0.222 (0/3) |
| Q010 | 0.333 (0/3) | 0.333 (0/3) |
| Q011 | 0.889 (0/3) | 0.889 (0/3) |
| Q012 | 0.400 (0/3) | 0.400 (0/3) |
| Q002-gen-end_to_end | 0.800 (0/3) | 0.800 (0/3) |
| Q004-gen-end_to_end | 0.400 (0/3) | 0.400 (0/3) |
| Q001-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) |
| Q002-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) |
| Q003-p1-unsupported_sentence | 0.667 (0/3) | 0.667 (0/3) |
| Q004-p1-negation | 0.400 (0/3) | 0.400 (0/3) |
| Q005-p1-proper_noun | 0.667 (0/3) | 0.667 (0/3) |
| Q006-p1-unsupported_sentence | 0.333 (0/3) | 0.444 (0/3) |
| Q007-p1-unsupported_sentence | 0.619 (0/3) | 0.619 (0/3) |
| Q008-p1-negation | 1.000 (0/3) | 1.000 (0/3) |
| Q009-p1-unsupported_sentence | 0.357 (0/3) | 0.286 (0/3) |
| Q010-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) |
| Q011-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) |
| Q012-p1-unsupported_sentence | 0.600 (0/3) | 0.600 (0/3) |
| Q002-p2-negation | 0.444 (0/3) | 0.444 (0/3) |
| Q010-p2-negation | 0.500 (0/3) | 0.500 (0/3) |
