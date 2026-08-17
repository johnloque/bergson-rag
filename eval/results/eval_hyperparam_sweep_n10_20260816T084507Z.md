# Retrieval hyperparameter sweep — exploratory

- **Generated**: 2026-08-16T08:45:07Z
- **Git commit**: `cd5f0888b2418ed03d2258b2089646c2e8608545` (branch `exp/channel-performance-comparison`)
- **Working tree had uncommitted changes at run time**: yes (uncommitted changes present)
- **Gold dataset**: `eval/gold_dataset.csv`, n=10
- **Matrix search depth**: top-50 per config (see note under part A)

This file's name and the metadata above identify this as a small-n pass —
compare the `n=` value here against any later re-run before treating results
as comparable; a re-run at n=25+ is a materially different, more trustworthy
sample, not just "more of the same data."

> **EXPLORATORY — NOT STATISTICALLY MEANINGFUL AT n=10.** docs/gold_dataset_protocol.md targets n=50; this pass is a small-sample smoke comparison only. Read the per-item rank matrix (part B) as the primary output — the aggregate table (part A) is included for convenience but recall/MRR deltas of one or two items are noise at this n.

## Determinism check

Every config below was run twice over the full gold set before any table was
computed; ranked chunk_ids and scores matched exactly across both runs (see
script stdout for the full log). The sweep tables reuse that verified first
run rather than a third, unverified pass.

## Part B — per-item rank matrix (primary output at this n)

Rank of the first gold `chunk_id` for each item, per config. `>50`
means the gold chunk did not appear in the top 50 retrieved for
that config — not necessarily "never retrievable," just outside the depth
searched here.

| id | query | dense | sparse | hybrid_k1 | hybrid_k5 | hybrid_k10 | hybrid_k20 | hybrid_k40 | hybrid_k60 |
|---|---|---|---|---|---|---|---|---|---|
| Q001 | Quel usage Bergson fait-il de l'image de la boule de neige p… | >50 | 2 | 4 | 6 | 8 | 13 | 23 | 41 |
| Q002 | Quelle thèse Bergson explique-t-il à travers l'image de la f… | 33 | 1 | 1 | 1 | 3 | 3 | 3 | 3 |
| Q003 | Comment Bergson définit-il le phénomène de dépersonnalisatio… | >50 | 1 | 2 | 3 | 6 | 10 | 19 | 25 |
| Q004 | Quel rapport Bergson établit-il entre l'imagination poétique… | >50 | 1 | 1 | 2 | 2 | 4 | 4 | 5 |
| Q005 | Pourquoi Bergson décrit-il la perception d'un tremblement de… | 2 | 1 | 2 | 2 | 2 | 2 | 2 | 2 |
| Q006 | De quel philosophe Bergson reconstitue-t-il la pensée à la m… | 2 | 43 | 3 | 4 | 5 | 5 | 5 | 5 |
| Q007 | Selon Bergson, en quoi la structure du langage est-elle sour… | 1 | 21 | 1 | 2 | 2 | 2 | 3 | 3 |
| Q008 | Quelle thèse Bergson explique-t-il à travers l'image du mant… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Q009 | Quelle thèse Bergson explique-t-il en décrivant la grande ch… | 32 | 31 | 30 | 30 | 29 | 22 | 15 | 14 |
| Q010 | Quelle métaphore géologique Bergson utilise-t-il pour compre… | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

## Part A — aggregate table (exploratory / not statistically meaningful at n=10)

recall@k and MRR per configuration, aggregated over all 10 gold items.
**Do not read small deltas between configs here as a real ranking of
methods at this sample size** — use part B to see which specific items
drive any difference. MRR is computed over the same top-50
retrieval depth as the rank matrix, so it may differ slightly from
`eval/scripts/run_eval.py`'s production config, which truncates hybrid
retrieval at top-10.

| config | recall@1 | recall@3 | recall@5 | recall@10 | mrr | n |
|---|---|---|---|---|---|---|
| dense | 0.200 | 0.500 | 0.500 | 0.500 | 0.356 | 10 |
| sparse | 0.600 | 0.700 | 0.700 | 0.700 | 0.660 | 10 |
| hybrid_k1 | 0.500 | 0.800 | 0.900 | 0.900 | 0.662 | 10 |
| hybrid_k5 | 0.300 | 0.700 | 0.800 | 0.900 | 0.528 | 10 |
| hybrid_k10 | 0.200 | 0.600 | 0.700 | 0.900 | 0.436 | 10 |
| hybrid_k20 | 0.200 | 0.500 | 0.700 | 0.800 | 0.401 | 10 |
| hybrid_k40 | 0.200 | 0.500 | 0.700 | 0.700 | 0.378 | 10 |
| hybrid_k60 | 0.200 | 0.500 | 0.700 | 0.700 | 0.370 | 10 |

## Configs

- `dense`: BGE-M3 dense-only, no fusion.
- `sparse`: BM25-on-stems sparse-only, no fusion.
- `hybrid_k{1,5,10,20,40,60}`: dense + sparse, Qdrant-native RRF fusion at
  the given `k` (`src/retrieval/hybrid.py`). Project default is k=60
  (Cormack et al. 2009 standard value, see `RRF_K` in that module) —
  the rest of this sweep is what motivates whether that default should
  ever be revisited, not a claim that it should.
