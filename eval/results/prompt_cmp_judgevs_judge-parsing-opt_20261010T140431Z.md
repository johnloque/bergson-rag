# Judge variant `judge-parsing-opt` vs baseline

> **EXPLORATORY: n=26 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_judge_default_n26_20261009T100635Z.json`, `eval/results/prompt_cmp_judge_default_n26_20261009T112759Z.json`
- **variant**: `eval/results/prompt_cmp_judge_judge-parsing-opt_n26_20261010T110747Z.json`, `eval/results/prompt_cmp_judge_judge-parsing-opt_n26_20261010T113950Z.json`
- **Differs in**: faithfulness

## Gate (every hallucinated item flagged, in every repeat)

| candidate | run | gate | detected/items per origin | per perturbation type | missed |
|---|---|---|---|---|---|
| default | 1 | FAILED | generated 2/2, perturbed 11/12 | negation 1/2, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| default | 2 | FAILED | generated 2/2, perturbed 11/12 | negation 1/2, proper_noun 1/1, unsupported_sentence 9/9 | Q008-p1-negation |
| judge-parsing-opt | 1 | FAILED | generated 1/2, perturbed 11/12 | negation 1/2, proper_noun 1/1, unsupported_sentence 9/9 | Q002-gen-end_to_end, Q008-p1-negation |
| judge-parsing-opt | 2 | FAILED | generated 1/2, perturbed 11/12 | negation 1/2, proper_noun 1/1, unsupported_sentence 9/9 | Q002-gen-end_to_end, Q008-p1-negation |

Missed by default, detections per repeat (run 1 / run 2 …):
- Q008-p1-negation (judged supported ×6): [F,F,F] / [F,F,F]

Missed by judge-parsing-opt, detections per repeat (run 1 / run 2 …):
- Q002-gen-end_to_end (judged supported ×6): [F,F,F] / [F,F,F]
- Q008-p1-negation (judged supported ×6): [F,F,F] / [F,F,F]

- Newly caught: —
- Newly missed: Q002-gen-end_to_end
- Still missed: Q008-p1-negation

## Class means and nan (per run)

| candidate | run | faithful (higher = fewer false flags) | hallucinated (lower = correct) | nan rows | nan per repeat, faithful | nan per repeat, hallucinated | unevaluated per repeat, faithful | unevaluated per repeat, hallucinated | flagged faithful statements |
|---|---|---|---|---|---|---|---|---|---|
| default | 1 | 0.665 | 0.534 | 0/78 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | 74 |
| default | 2 | 0.657 | 0.536 | 0/78 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | 75 |
| judge-parsing-opt | 1 | 0.640 | 0.596 | 0/78 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | 68 |
| judge-parsing-opt | 2 | 0.625 | 0.590 | 0/78 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | r1 0/12, r2 0/12, r3 0/12 | r1 0/14, r2 0/14, r3 0/14 | 70 |

Distinct flagged faithful statements, default (all runs): 27 across 8 items (Q002, Q004, Q006, Q007, Q009, Q010, Q011, Q012)

Distinct flagged faithful statements, judge-parsing-opt (all runs): 24 across 9 items (Q002, Q004, Q006, Q007, Q008, Q009, Q010, Q011, Q012)

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run |
|---|---|---|---|---|---|---|
| default | run 1 | 0.027 | 0.333 | 1 | 127 | 10 |
| default | run 2 | 0.033 | 0.333 | 2 | 128 | 15 |
| default | pooled (2 runs, 6 repeats) | 0.037 | 0.333 | 2 | 136 | 10 |
| judge-parsing-opt | run 1 | 0.056 | 0.333 | 5 | 121 | 1 |
| judge-parsing-opt | run 2 | 0.032 | 0.333 | 2 | 121 | 2 |
| judge-parsing-opt | pooled (2 runs, 6 repeats) | 0.062 | 0.333 | 5 | 121 | 3 |

Flipped statements, default (pooled): 2
- Q007: Cette assimilation est utile à la vie pratique et à la plupart des sciences.
- Q007-p1-unsupported_sentence: Cette assimilation est utile à la vie pratique et à la plupart des sciences.

Flipped statements, judge-parsing-opt (pooled): 5
- Q007: Cette assimilation est utile à la vie pratique et à la plupart des sciences.
- Q008: En effet, si on arrache le clou, le vêtement tombe, mais on ne peut pas en conclure que la forme du clou dessine celle du vêtement, ou que chaque détail du clou corresponde à un détail du vêtement.
- Q011: Le mouvement oscillatoire décrit par le pendule et le balancier illustre selon lui les tendances antagonistes qui se différencient, qu'il s'agisse de principes politiques ou d'inclinations individuelles.
- Q008-p1-negation: En effet, si on arrache le clou, le vêtement tombe, mais on ne peut pas en conclure que la forme du clou dessine celle du vêtement, ou que chaque détail du clou corresponde à un détail du vêtement.
- Q011-p1-unsupported_sentence: Selon l'auteur, les tendances antagonistes se différencient, qu'il s'agisse de principes politiques ou d'inclinations individuelles.

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 22 items; nonzero: Q007 0.011, Q011 0.111, Q004-p1-negation 0.033, Q009-p1-unsupported_sentence 0.071; nan on 0 (—); max 0.111, mean 0.009 over 26 finite items
- **judge-parsing-opt**: 0 on 21 items; nonzero: Q007 0.067, Q011 0.111, Q008-p1-negation 0.111, Q010-p1-unsupported_sentence 0.056, Q011-p1-unsupported_sentence 0.083; nan on 0 (—); max 0.111, mean 0.016 over 26 finite items

## Selection axes (only if both pass the gate)

- Not applicable: at least one candidate fails the gate in some run.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | judge-parsing-opt run 1 | judge-parsing-opt run 2 |
|---|---|---|---|---|
| Q001 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q002 | 0.273 (0/3) | 0.273 (0/3) | 0.250 (0/3) | 0.250 (0/3) |
| Q003 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q004 | 0.500 (0/3) | 0.500 (0/3) | 0.500 (0/3) | 0.500 (0/3) |
| Q005 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q006 | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q007 | 0.756 (0/3) | 0.767 (0/3) | 0.667 (0/3) | 0.600 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 0.889 (0/3) | 0.889 (0/3) |
| Q009 | 0.167 (0/3) | 0.167 (0/3) | 0.333 (0/3) | 0.333 (0/3) |
| Q010 | 0.333 (0/3) | 0.333 (0/3) | 0.333 (0/3) | 0.333 (0/3) |
| Q011 | 0.889 (0/3) | 0.778 (0/3) | 0.444 (0/3) | 0.333 (0/3) |
| Q012 | 0.400 (0/3) | 0.400 (0/3) | 0.600 (0/3) | 0.600 (0/3) |
| Q002-gen-end_to_end | 0.800 (0/3) | 0.800 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q004-gen-end_to_end | 0.400 (0/3) | 0.400 (0/3) | 0.400 (0/3) | 0.400 (0/3) |
| Q001-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q002-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) | 0.222 (0/3) | 0.222 (0/3) |
| Q003-p1-unsupported_sentence | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q004-p1-negation | 0.433 (0/3) | 0.400 (0/3) | 0.400 (0/3) | 0.400 (0/3) |
| Q005-p1-proper_noun | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q006-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) | 0.667 (0/3) | 0.667 (0/3) |
| Q007-p1-unsupported_sentence | 0.619 (0/3) | 0.619 (0/3) | 0.750 (0/3) | 0.750 (0/3) |
| Q008-p1-negation | 1.000 (0/3) | 1.000 (0/3) | 0.889 (0/3) | 0.778 (0/3) |
| Q009-p1-unsupported_sentence | 0.286 (0/3) | 0.357 (0/3) | 0.250 (0/3) | 0.250 (0/3) |
| Q010-p1-unsupported_sentence | 0.333 (0/3) | 0.333 (0/3) | 0.500 (0/3) | 0.444 (0/3) |
| Q011-p1-unsupported_sentence | 0.500 (0/3) | 0.500 (0/3) | 0.667 (0/3) | 0.750 (0/3) |
| Q012-p1-unsupported_sentence | 0.600 (0/3) | 0.600 (0/3) | 0.600 (0/3) | 0.600 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | label | origin | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|---|---|
| Q001 | faithful | gold | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q002 | faithful | gold | 0.273 | 0.250 | -0.023 | 0.000 | outside noise |
| Q003 | faithful | gold | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q004 | faithful | gold | 0.500 | 0.500 | 0.000 | 0.000 | within noise |
| Q005 | faithful | gold | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q006 | faithful | gold | 0.667 | 0.667 | 0.000 | 0.000 | within noise |
| Q007 | faithful | gold | 0.756 | 0.667 | -0.089 | 0.011 | outside noise |
| Q008 | faithful | gold | 1.000 | 0.889 | -0.111 | 0.000 | outside noise |
| Q009 | faithful | gold | 0.167 | 0.333 | 0.167 | 0.000 | outside noise |
| Q010 | faithful | gold | 0.333 | 0.333 | 0.000 | 0.000 | within noise |
| Q011 | faithful | gold | 0.889 | 0.444 | -0.444 | 0.111 | outside noise |
| Q012 | faithful | gold | 0.400 | 0.600 | 0.200 | 0.000 | outside noise |
| Q002-gen-end_to_end | hallucinated | generated | 0.800 | 1.000 | 0.200 | 0.000 | outside noise |
| Q004-gen-end_to_end | hallucinated | generated | 0.400 | 0.400 | 0.000 | 0.000 | within noise |
| Q001-p1-unsupported_sentence | hallucinated | perturbed | 0.500 | 0.667 | 0.167 | 0.000 | outside noise |
| Q002-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.222 | -0.111 | 0.000 | outside noise |
| Q003-p1-unsupported_sentence | hallucinated | perturbed | 0.667 | 0.667 | 0.000 | 0.000 | within noise |
| Q004-p1-negation | hallucinated | perturbed | 0.433 | 0.400 | -0.033 | 0.033 | within noise |
| Q005-p1-proper_noun | hallucinated | perturbed | 0.667 | 0.667 | 0.000 | 0.000 | within noise |
| Q006-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.667 | 0.333 | 0.000 | outside noise |
| Q007-p1-unsupported_sentence | hallucinated | perturbed | 0.619 | 0.750 | 0.131 | 0.000 | outside noise |
| Q008-p1-negation | hallucinated | perturbed | 1.000 | 0.889 | -0.111 | 0.000 | outside noise |
| Q009-p1-unsupported_sentence | hallucinated | perturbed | 0.286 | 0.250 | -0.036 | 0.071 | within noise |
| Q010-p1-unsupported_sentence | hallucinated | perturbed | 0.333 | 0.500 | 0.167 | 0.000 | outside noise |
| Q011-p1-unsupported_sentence | hallucinated | perturbed | 0.500 | 0.667 | 0.167 | 0.000 | outside noise |
| Q012-p1-unsupported_sentence | hallucinated | perturbed | 0.600 | 0.600 | 0.000 | 0.000 | within noise |
