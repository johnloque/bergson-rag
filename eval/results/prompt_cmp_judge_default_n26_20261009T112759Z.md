# Prompt comparison run: judge mode, default

> **EXPLORATORY: n=26 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **Created**: 2026-10-09T11:27:59Z
- **Command**: `python -m eval.scripts.run_prompt_comparison --mode judge --repeat 3 --checkpoint /Users/michel/.cache/bergson-rag/judge-baseline-v2/run2/checkpoint.jsonl --output-dir /Users/michel/.cache/bergson-rag/judge-baseline-v2/run2`
- **Source**: default `default`
- **Overridden prompts**: none (defaults)
- **Models**: judge `ollama_chat/mistral`; temperature {'judge': 0.0, 'generation': None}
- **Retrieval**: none: fixed answers judged against their calibration-set chunks
- **Items**: 26 {'gold': 12, 'generated': 2, 'perturbed': 12}; repeat 3
- **Git**: `28b41a3f4988db21b8ec86c95fd69f2d513babb8` (exp/judge-baseline-v2), dirty: False
- **Frozen judge**: n/a (judge mode: this run is a candidate)
- **Held-out check** (calibration text vs. judge examples): no overlap

## Prompt manifest

| prompt | version | hash | custom |
|---|---|---|---|
| faithfulness.nli_verifier | v1 | `89e87a3d7dfb` | False |
| faithfulness.segment_claims | v1 | `1d73fc7146af` | False |
| generation.answer | v1 | `ea95d3d10495` | False |
| generation.system | v1 | `e6d608e1eb84` | False |
| judge_chunk.relevance | v1 | `0922b7646460` | False |
| judge_chunk.retry | v1 | `e2036cc593ab` | False |
| judge_chunk.system | v1 | `c1ad1bff969c` | False |
| library:ragas | 0.3.9 | — | — |

## Gate (every hallucinated item flagged in every run)

**FAILED** — missed: Q008-p1-negation (judged supported ×3)

Rests on: generated 2/2, perturbed 11/12. Per perturbation type: negation 1/2, proper_noun 1/1, unsupported_sentence 9/9. Perturbed items are crude edits: catching them shows the judge catches blatant errors, not subtle ones.

## Faithful class (higher = fewer false flags, never pooled)

Mean 0.657 over 12 items; nan per run: run 1: 0/12, run 2: 0/12, run 3: 0/12; runs with unevaluated claims (left out of their score): run 1: 0/12, run 2: 0/12, run 3: 0/12

## Hallucinated class (lower is the correct direction, never pooled)

Mean 0.536 over 14 items; nan per run: run 1: 0/14, run 2: 0/14, run 3: 0/14; runs with unevaluated claims (left out of their score): run 1: 0/14, run 2: 0/14, run 3: 0/14

## Stability over repeats

Mean per-item score range 0.033 (max 0.333); verdict flips 2 of 128 statements seen in 2+ runs; 15 statements extracted in one run only.

## Statements flagged in faithful items (investigation leads)

- Q002 run 1: Les physiciens considèrent la fonte du morceau de sucre comme un système isolé. — Le contexte ne mentionne pas explicitement que les physiciens considèrent la fonte du morceau de sucre comme un système isolé.
- Q002 run 1: Les physiciens reposent sur des abstractions relatives (verre d'eau, sucre, processus de dissolution, unités de temps...). — Le contexte discute de la nature du temps et de la perception de la durée par les êtres conscients, mais il ne fait pas explicitement mention de l'utilisation de telles abstractions par les physiciens.
- Q002 run 1: Un tel système fonctionne comme la bande d'un cinématographe. — Le contexte discute de la succession des états dans l'univers et de la durée de la vie intérieure, mais il ne fait aucune référence à un système fonctionnant comme une bande de cinématographe.
- Q002 run 1: Dans un tel système, les événements se succèdent dans un déterminisme total. — Le contexte discute de la succession des événements dans l'univers, mais il ne suggère pas que ce déroulement est totalement déterminé.
- Q002 run 1: Tous les états, passés, présents et futurs d'un tel système sont déterminés d'un seul coup. — Le contexte indique que l'auteur considère que le temps est une succession et non un éventail ou un film cinématographique, ce qui implique que les états successifs ne sont pas déterminés d'un seul coup.
- Q002 run 1: Les états d'un tel système sont juxtaposés dans l'espace. — Le contexte indique explicitement que l'univers déroule ses états successifs avec une vitesse déterminée, ce qui implique un temps qui progresse et non une juxtaposition dans l'espace.
- Q002 run 1: La fonte du morceau de sucre coïncide avec mon attente. — Le contexte indique que la fonte du sucre est un processus qui doit attendre, mais il ne fait pas mention d'une coïncidence avec l'attente.
- Q002 run 1: La fonte du morceau de sucre coïncide avec mon impatience. — Le contexte indique que la durée attendue pour la fonte du sucre est liée à l'impatience de l'individu, mais il n'y a pas de mention explicite de la coïncidence entre la fonte du sucre et l'impatience.
- Q002 run 2: Les physiciens considèrent la fonte du morceau de sucre comme un système isolé. — Le contexte ne mentionne pas explicitement que les physiciens considèrent la fonte du morceau de sucre comme un système isolé.
- Q002 run 2: Les physiciens reposent sur des abstractions relatives (verre d'eau, sucre, processus de dissolution, unités de temps...). — Le contexte discute de la nature du temps et de la perception de la durée par les êtres conscients, mais il ne fait pas explicitement mention de l'utilisation de telles abstractions par les physiciens.
- Q002 run 2: Un tel système fonctionne comme la bande d'un cinématographe. — Le contexte discute de la succession des états dans l'univers et de la durée de la vie intérieure, mais il ne fait aucune référence à un système fonctionnant comme une bande de cinématographe.
- Q002 run 2: Dans un tel système, les événements se succèdent dans un déterminisme total. — Le contexte discute de la succession des événements dans l'univers, mais il ne suggère pas que ce déroulement est totalement déterminé.
- Q002 run 2: Tous les états, passés, présents et futurs d'un tel système sont déterminés d'un seul coup. — Le contexte discute de la succession des états dans le temps et de la durée psychologique qui s'impose, ce qui implique que les états ne sont pas déterminés d'un seul coup.
- Q002 run 2: Les états d'un tel système sont juxtaposés dans l'espace. — Le contexte indique explicitement que l'univers déroule ses états successifs avec une vitesse déterminée, ce qui implique un temps qui progresse et non une juxtaposition dans l'espace.
- Q002 run 2: La fonte du morceau de sucre coïncide avec mon attente. — Le contexte indique que la fonte du sucre est un processus qui doit attendre, mais il ne fait pas mention d'une coïncidence avec l'attente.
- Q002 run 2: La fonte du morceau de sucre coïncide avec mon impatience. — Le contexte indique que la durée attendue pour la fonte du sucre est liée à l'impatience de l'individu, mais il n'y a pas de mention explicite de la coïncidence entre la fonte du sucre et l'impatience.
- Q002 run 3: Les physiciens considèrent la fonte du morceau de sucre comme un système isolé. — Le contexte ne mentionne pas explicitement que les physiciens considèrent la fonte du morceau de sucre comme un système isolé.
- Q002 run 3: Les physiciens reposent sur des abstractions relatives (verre d'eau, sucre, processus de dissolution, unités de temps...). — Le contexte discute de la nature du temps et de la perception de la durée par les êtres conscients, mais il ne fait pas explicitement mention de l'utilisation de telles abstractions par les physiciens.
- Q002 run 3: Un tel système fonctionne comme la bande d'un cinématographe. — Le contexte discute de la succession des états dans l'univers et de la durée de la vie intérieure, mais il ne fait aucune référence à un système fonctionnant comme une bande de cinématographe.
- Q002 run 3: Dans un tel système, les événements se succèdent dans un déterminisme total. — Le contexte discute de la succession des événements dans l'univers, mais il ne suggère pas que ce déroulement est totalement déterminé.
- Q002 run 3: Tous les états, passés, présents et futurs d'un tel système sont déterminés d'un seul coup. — Le contexte indique que l'auteur considère que le temps est une succession et non un éventail ou un film cinématographique, ce qui implique que les états successifs ne sont pas déterminés d'un seul coup.
- Q002 run 3: Les états d'un tel système sont juxtaposés dans l'espace. — Le contexte indique explicitement que l'univers déroule ses états successifs avec une vitesse déterminée, ce qui implique un temps qui progresse et non une juxtaposition dans l'espace.
- Q002 run 3: La fonte du morceau de sucre coïncide avec mon attente. — Le contexte indique que la fonte du sucre est un processus qui doit attendre, mais il ne fait pas mention d'une coïncidence avec l'attente.
- Q002 run 3: La fonte du morceau de sucre coïncide avec mon impatience. — Le contexte indique que la durée attendue pour la fonte du sucre est liée à l'impatience de l'individu, mais il n'y a pas de mention explicite de la coïncidence entre la fonte du sucre et l'impatience.
- Q004 run 1: Les personnages imaginés approfondissent toutes les directions possibles que le poète aurait pu suivre dans sa vie. — Le contexte indique que l'imagination poétique permet au poète de s'approfondir dans une direction intérieure, mais il n'y a aucune mention de ce que les personnages imaginés approfondissent des directions possibles de la vie du poète.
- Q004 run 1: Quoiqu'il n'en ait effectivement suivi qu'une seule. — Le contexte discute de la capacité de l'imagination poétique à prendre des aspects différents de la vie et à les combiner pour créer des personnages complexes, sans mentionner explicitement que le poète ait suivi qu'une seule de ces directions possibles.
- Q004 run 2: Les personnages imaginés approfondissent toutes les directions possibles que le poète aurait pu suivre dans sa vie. — Le contexte indique que l'imagination poétique permet au poète de s'approfondir dans une direction intérieure, mais il n'y a aucune mention de ce que les personnages imaginés approfondissent des directions possibles de la vie du poète.
- Q004 run 2: Quoiqu'il n'en ait effectivement suivi qu'une seule. — Le contexte discute de la capacité de l'imagination poétique à prendre des aspects différents de la vie et à les combiner pour créer des personnages complexes, sans mentionner explicitement que le poète ait suivi qu'une seule de ces directions possibles.
- Q004 run 3: Les personnages imaginés approfondissent toutes les directions possibles que le poète aurait pu suivre dans sa vie. — Le contexte indique que l'imagination poétique permet au poète de s'approfondir dans une direction intérieure, mais il n'y a aucune mention de ce que les personnages imaginés approfondissent des directions possibles de la vie du poète.
- Q004 run 3: Quoiqu'il n'en ait effectivement suivi qu'une seule. — Le contexte discute de la capacité de l'imagination poétique à prendre des aspects différents de la vie et à les combiner pour créer des personnages complexes, sans mentionner explicitement que le poète ait suivi qu'une seule de ces directions possibles.
- Q006 run 1: Dans La Pensée et le Mouvant (1934), Bergson reconstitue la pensée du philosophe Berkeley (à l'exception de sa théorie de la vision). — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson a reconstitué sa pensée dans La Pensée et le Mouvant, à l'exception de sa théorie de la vision. Il est donc impossible de déduire directement cette affirmation du contexte.
- Q006 run 2: Dans La Pensée et le Mouvant (1934), Bergson reconstitue la pensée du philosophe Berkeley (à l'exception de sa théorie de la vision). — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson a reconstitué sa pensée dans La Pensée et le Mouvant, à l'exception de sa théorie de la vision. Il est donc impossible de déduire directement cette affirmation du contexte.
- Q006 run 3: Dans La Pensée et le Mouvant (1934), Bergson reconstitue la pensée du philosophe Berkeley (à l'exception de sa théorie de la vision). — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson a reconstitué sa pensée dans La Pensée et le Mouvant, à l'exception de sa théorie de la vision. Il est donc impossible de déduire directement cette affirmation du contexte.
- Q007 run 1: Cette assimilation est utile à la vie pratique et à la plupart des sciences. — Le contexte discute sur la manière dont la philosophie peut être influencée par les habitudes de langage et les concepts élaborés par l'organisme social, et comment ces concepts peuvent ne pas correspondre aux articulations du réel. Il y a une discussion sur la manière dont la philosophie peut être limitée par le langage et comment elle peut être contrainte à recevoir une solution toute faite. Cependant, il n'y a pas de mention explicite de l'utilité de cette assimilation à la vie pratique et aux sciences.
- Q007 run 2: Cette donnée fondamentale nous pousse à penser dans l'espace. — Le contexte discute de la manière dont la pensée est structurée par le langage et la nature, et il ne fait aucune mention de la notion de pensée dans l'espace.
- Q007 run 3: Cette donnée fondamentale nous pousse à penser dans l'espace. — Le contexte discute de la manière dont la pensée est structurée par le langage et la nature, et il ne fait aucune mention de la notion de pensée dans l'espace.
- Q007 run 3: Cette assimilation est utile à la vie pratique et à la plupart des sciences. — Le contexte discute sur la manière dont la philosophie peut être influencée par les habitudes de langage et les concepts élaborés par l'organisme social, et comment ces concepts peuvent ne pas correspondre aux articulations du réel. Il y a une discussion sur la manière dont la philosophie peut être limitée par le langage et comment elle peut être contrainte à recevoir une solution toute faite. Cependant, il n'y a pas de mention explicite de l'utilité de cette assimilation à la vie pratique et aux sciences.
- Q009 run 1: À la fin du troisième chapitre de l'Évolution créatrice (1907), Bergson décrit l'humanité comme une grande armée qui galope. — Le contexte décrit la philosophie de Bergson et sa relation avec la vie spirituelle, la vie de l'esprit à celle du corps, la conscience, l'intelligence, la matière, la liberté, etc., mais il ne décrit pas explicitement que Bergson décrit l'humanité comme une grande armée qui galope à la fin du troisième chapitre de l'Évolution créatrice.
- Q009 run 1: Bergson illustre ainsi sa thèse de la solidarité de l'univers entier. — Le contexte décrit la philosophie de Bergson et sa thèse sur la vie, la conscience et l'intelligence, mais il ne mentionne pas explicitement que Bergson illustre sa thèse de la solidarité de l'univers entier.
- Q009 run 1: Dans ce mouvement, la conscience n'apparaît plus isolée du reste de l'humanité. — Le contexte décrit la conscience comme étant distincte de l'organisme qu'elle anime, mais il ne la présente pas comme isolée du reste de l'humanité. Au contraire, il décrit l'humanité comme une armée immense qui galope à côté de chacun de nous, en avant et en arrière de nous.
- Q009 run 1: L'humanité s'appuie sur l'animal. — Le contexte décrit l'humanité comme une immense armée qui galope à côté de chacun de nous, en avant et en arrière de nous, mais il ne mentionne pas explicitement que l'humanité s'appuie sur l'animal.
- Q009 run 1: L'humanité perpétue la même poussée vitale, agissante et créatrice en traversant la matérialité et la nécessité. — Le contexte décrit la relation entre la vie de l'esprit et celle du corps, la conscience et l'intelligence, la liberté humaine et la matière, et la survie des âmes. Il y a une description de la vie de l'humanité comme un flot qui monte, qui est conscience, et qui est distinct de la matière. Cependant, il n'y a pas de mention explicite de la poussée vitale, agissante et créatrice de l'humanité en traversant la matérialité et la nécessité.
- Q009 run 2: À la fin du troisième chapitre de l'Évolution créatrice (1907), Bergson décrit l'humanité comme une grande armée qui galope. — Le contexte décrit la philosophie de Bergson et sa relation avec la vie spirituelle, la vie de l'esprit à celle du corps, la conscience, l'intelligence, la matière, la liberté, etc., mais il ne décrit pas explicitement que Bergson décrit l'humanité comme une grande armée qui galope à la fin du troisième chapitre de l'Évolution créatrice.
- Q009 run 2: Bergson illustre ainsi sa thèse de la solidarité de l'univers entier. — Le contexte décrit la philosophie de Bergson et sa thèse sur la vie, la conscience et l'intelligence, mais il ne mentionne pas explicitement que Bergson illustre sa thèse de la solidarité de l'univers entier.
- Q009 run 2: Dans ce mouvement, la conscience n'apparaît plus isolée du reste de l'humanité. — Le contexte décrit la conscience comme étant distincte de l'organisme qu'elle anime, mais il ne la présente pas comme isolée du reste de l'humanité. Au contraire, il décrit l'humanité comme une armée immense qui galope à côté de chacun de nous, en avant et en arrière de nous.
- Q009 run 2: L'humanité s'appuie sur l'animal. — Le contexte décrit l'humanité comme une immense armée qui galope à côté de chacun de nous, en avant et en arrière de nous, mais il ne mentionne pas explicitement que l'humanité s'appuie sur l'animal.
- Q009 run 2: L'humanité perpétue la même poussée vitale, agissante et créatrice en traversant la matérialité et la nécessité. — Le contexte décrit la relation entre la vie de l'esprit et celle du corps, la conscience et l'intelligence, la liberté humaine et la matière, et la survie des âmes. Il y a une description de la vie de l'humanité comme un flot qui monte, qui est conscience, et qui est distinct de la matière. Cependant, il n'y a pas de mention explicite de la poussée vitale, agissante et créatrice de l'humanité en traversant la matérialité et la nécessité.
- Q009 run 3: À la fin du troisième chapitre de l'Évolution créatrice (1907), Bergson décrit l'humanité comme une grande armée qui galope. — Le contexte décrit la philosophie de Bergson et sa relation avec la vie spirituelle, la vie de l'esprit à celle du corps, la conscience, l'intelligence, la matière, la liberté, etc., mais il ne décrit pas explicitement que Bergson décrit l'humanité comme une grande armée qui galope à la fin du troisième chapitre de l'Évolution créatrice.
- Q009 run 3: Bergson illustre ainsi sa thèse de la solidarité de l'univers entier. — Le contexte décrit la philosophie de Bergson et sa thèse sur la vie, la conscience et l'intelligence, mais il ne mentionne pas explicitement que Bergson illustre sa thèse de la solidarité de l'univers entier.
- Q009 run 3: Dans ce mouvement, la conscience n'apparaît plus isolée du reste de l'humanité. — Le contexte décrit la conscience comme étant distincte de l'organisme qu'elle anime, mais il ne la présente pas comme isolée du reste de l'humanité. Au contraire, il décrit l'humanité comme une armée immense qui galope à côté de chacun de nous, en avant et en arrière de nous.
- Q009 run 3: L'humanité s'appuie sur l'animal. — Le contexte décrit l'humanité comme une immense armée qui galope à côté de chacun de nous, en avant et en arrière de nous, mais il ne mentionne pas explicitement que l'humanité s'appuie sur l'animal.
- Q009 run 3: L'humanité perpétue la même poussée vitale, agissante et créatrice en traversant la matérialité et la nécessité. — Le contexte décrit la relation entre la vie de l'esprit et celle du corps, la conscience et l'intelligence, la liberté humaine et la matière, et la survie des âmes. Il y a une description de la vie de l'humanité comme un flot qui monte, qui est conscience, et qui est distinct de la matière. Cependant, il n'y a pas de mention explicite de la poussée vitale, agissante et créatrice de l'humanité en traversant la matérialité et la nécessité.
- Q010 run 1: Bergson récuse la transformation graduelle interne (de dialectique en mystique) dans le développement de la pensée grecque. — Le contexte décrit la transformation graduelle interne de la dialectique en mystique dans le développement de la pensée grecque, ce qui implique que Bergson ne récuse pas cette transformation.
- Q010 run 1: Selon Bergson, le développement de la pensée grecque est l'oeuvre de la seule raison. — Le contexte décrit la pensée grecque comme ayant été l'œuvre d'une force extra-rationnelle et de la raison, mais il ne mentionne pas explicitement que Bergson considère le développement de la pensée grecque comme étant l'œuvre de la seule raison.
- Q010 run 1: La mystique est un processus parallèle au développement de la pensée grecque, selon Bergson. — Le contexte discute de l'évolution de la pensée grecque et de la possibilité d'une influence extra-rationnelle, mais il ne mentionne pas explicitement Bergson ou la théorie de Bergson.
- Q010 run 1: Ces poussées éruptives conditionnent invisiblement l'activité sédimentaire, selon la métaphore géologique utilisée par Bergson. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne fait aucune référence à une métaphore géologique utilisée par Bergson.
- Q010 run 2: Bergson récuse la transformation graduelle interne (de dialectique en mystique) dans le développement de la pensée grecque. — Le contexte décrit la transformation graduelle interne de la dialectique en mystique dans le développement de la pensée grecque, ce qui implique que Bergson ne récuse pas cette transformation.
- Q010 run 2: Selon Bergson, le développement de la pensée grecque est l'oeuvre de la seule raison. — Le contexte décrit la pensée grecque comme ayant été l'œuvre d'une force extra-rationnelle et de la raison, mais il ne mentionne pas explicitement que Bergson considère le développement de la pensée grecque comme étant l'œuvre de la seule raison.
- Q010 run 2: La mystique est un processus parallèle au développement de la pensée grecque, selon Bergson. — Le contexte discute de l'évolution de la pensée grecque et de la possibilité d'une influence extra-rationnelle, mais il ne fait aucune mention de Bergson ou de sa théorie.
- Q010 run 2: De même que les poussées éruptives conditionnent invisiblement l'activité sédimentaire (seul phénomène observable), selon Bergson. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne fait aucune référence à Bergson ou à son point de vue sur les poussées éruptives et l'activité sédimentaire.
- Q010 run 3: Bergson récuse la transformation graduelle interne (de dialectique en mystique) dans le développement de la pensée grecque. — Le contexte décrit la transformation graduelle interne de la dialectique en mystique dans le développement de la pensée grecque, ce qui implique que Bergson ne récuse pas cette transformation.
- Q010 run 3: Selon Bergson, le développement de la pensée grecque est l'oeuvre de la seule raison. — Le contexte décrit la pensée grecque comme ayant été l'œuvre d'une force extra-rationnelle et de la raison, mais il ne mentionne pas explicitement que Bergson considère le développement de la pensée grecque comme étant l'œuvre de la seule raison.
- Q010 run 3: La mystique est un processus parallèle au développement de la pensée grecque, selon Bergson. — Le contexte discute de l'évolution de la pensée grecque et de la possibilité d'une influence extra-rationnelle, mais il ne fait aucune mention de Bergson ou de sa théorie.
- Q010 run 3: De même que les poussées éruptives conditionnent invisiblement l'activité sédimentaire (seul phénomène observable), selon Bergson. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne fait aucune référence à Bergson ou à son point de vue sur les poussées éruptives et l'activité sédimentaire.
- Q011 run 2: Selon lui, ces tendances antagonistes se différencient, qu'il s'agisse de principes politiques ou d'inclinations individuelles. — Le contexte discute de tendances antagonistes dans l'évolution psychologique et sociale, mais il ne précise pas qu'elles se différencient entre principes politiques ou inclinations individuelles.
- Q011 run 3: Selon lui, ces tendances antagonistes se différencient, qu'il s'agisse de principes politiques ou d'inclinations individuelles. — Le contexte discute de tendances antagonistes dans l'évolution psychologique et sociale de l'homme, mais il ne précise pas si ces tendances se différencient entre principes politiques ou inclinations individuelles.
- Q012 run 1: Dans l'Évolution Créatrice (1907) et Les Deux Sources (1932), Bergson décrit la croissance de la vie en utilisant la métaphore de la gerbe. — Le contexte décrit en détail les idées de Bergson sur l'évolution de la vie, mais il ne mentionne pas explicitement qu'il utilise la métaphore de la gerbe pour décrire la croissance de la vie.
- Q012 run 1: Sur le plan psychologique, ce processus se traduit nécessairement par un sacrifice. — Le contexte ne discute pas explicitement de sacrifices liés au processus psychologique décrit. Il s'agit plutôt d'une évolution de tendances divergentes et complémentaires, mais il n'est pas directement informatif sur des sacrifices.
- Q012 run 1: L'individu choisit une route et abandonne toutes celles qu'il aurait pu suivre. — Le contexte indique que l'individu choisit entre différentes tendances, mais il ne mentionne pas qu'il abandonne toutes les autres possibilités.
- Q012 run 2: Dans l'Évolution Créatrice (1907) et Les Deux Sources (1932), Bergson décrit la croissance de la vie en utilisant la métaphore de la gerbe. — Le contexte décrit en détail les idées de Bergson sur l'évolution de la vie, mais il ne mentionne pas explicitement qu'il utilise la métaphore de la gerbe pour décrire la croissance de la vie.
- Q012 run 2: Sur le plan psychologique, ce processus se traduit nécessairement par un sacrifice. — Le contexte ne discute pas explicitement de sacrifices liés au processus psychologique décrit. Il s'agit plutôt d'une évolution de tendances divergentes et complémentaires, mais il n'est pas directement informatif sur des sacrifices.
- Q012 run 2: L'individu choisit une route et abandonne toutes celles qu'il aurait pu suivre. — Le contexte indique que l'individu choisit entre différentes tendances, mais il ne mentionne pas qu'il abandonne toutes les autres possibilités.
- Q012 run 3: Dans l'Évolution Créatrice (1907) et Les Deux Sources (1932), Bergson décrit la croissance de la vie en utilisant la métaphore de la gerbe. — Le contexte décrit en détail les idées de Bergson sur l'évolution de la vie, mais il ne mentionne pas explicitement qu'il utilise la métaphore de la gerbe pour décrire la croissance de la vie.
- Q012 run 3: Sur le plan psychologique, ce processus se traduit nécessairement par un sacrifice. — Le contexte ne discute pas explicitement de sacrifices liés au processus psychologique décrit. Il s'agit plutôt d'une évolution de tendances divergentes et complémentaires, mais il n'est pas directement informatif sur des sacrifices.
- Q012 run 3: L'individu choisit une route et abandonne toutes celles qu'il aurait pu suivre. — Le contexte indique que l'individu choisit entre différentes tendances, mais il ne fait pas mention d'une seule route étant choisie et toutes les autres étant abandonnées.

## Per item

| id | origin | label | category | scores per run | mean | nan runs | claims | unsupported | unevaluated |
|---|---|---|---|---|---|---|---|---|---|
| Q001 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 6 | 0 | 0 |
| Q002 | gold | faithful | définitionnel | 0.273 / 0.273 / 0.273 | 0.273 | 0/3 | 33 | 24 | 0 |
| Q003 | gold | faithful | factuel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 6 | 0 | 0 |
| Q004 | gold | faithful | factuel | 0.500 / 0.500 / 0.500 | 0.500 | 0/3 | 12 | 6 | 0 |
| Q005 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 9 | 0 | 0 |
| Q006 | gold | faithful | factuel | 0.667 / 0.667 / 0.667 | 0.667 | 0/3 | 9 | 3 | 0 |
| Q007 | gold | faithful | définitionnel | 0.800 / 0.833 / 0.667 | 0.767 | 0/3 | 17 | 4 | 0 |
| Q008 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 9 | 0 | 0 |
| Q009 | gold | faithful | définitionnel | 0.167 / 0.167 / 0.167 | 0.167 | 0/3 | 18 | 15 | 0 |
| Q010 | gold | faithful | définitionnel | 0.333 / 0.333 / 0.333 | 0.333 | 0/3 | 18 | 12 | 0 |
| Q011 | gold | faithful | définitionnel | 1.000 / 0.667 / 0.667 | 0.778 | 0/3 | 9 | 2 | 0 |
| Q012 | gold | faithful | définitionnel | 0.400 / 0.400 / 0.400 | 0.400 | 0/3 | 15 | 9 | 0 |
| Q002-gen-end_to_end | generated | hallucinated | définitionnel | 0.800 / 0.800 / 0.800 | 0.800 | 0/3 | 15 | 3 | 0 |
| Q004-gen-end_to_end | generated | hallucinated | factuel | 0.400 / 0.400 / 0.400 | 0.400 | 0/3 | 30 | 18 | 0 |
| Q001-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.500 / 0.500 / 0.500 | 0.500 | 0/3 | 12 | 6 | 0 |
| Q002-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.333 / 0.333 / 0.333 | 0.333 | 0/3 | 27 | 18 | 0 |
| Q003-p1-unsupported_sentence | perturbed | hallucinated | factuel | 0.667 / 0.667 / 0.667 | 0.667 | 0/3 | 9 | 3 | 0 |
| Q004-p1-negation | perturbed | hallucinated | factuel | 0.400 / 0.400 / 0.400 | 0.400 | 0/3 | 15 | 9 | 0 |
| Q005-p1-proper_noun | perturbed | hallucinated | définitionnel | 0.667 / 0.667 / 0.667 | 0.667 | 0/3 | 9 | 3 | 0 |
| Q006-p1-unsupported_sentence | perturbed | hallucinated | factuel | 0.333 / 0.333 / 0.333 | 0.333 | 0/3 | 9 | 6 | 0 |
| Q007-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.714 / 0.571 / 0.571 | 0.619 | 0/3 | 21 | 8 | 0 |
| Q008-p1-negation | perturbed | hallucinated | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 9 | 0 | 0 |
| Q009-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.500 / 0.286 / 0.286 | 0.357 | 0/3 | 22 | 14 | 0 |
| Q010-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.333 / 0.333 / 0.333 | 0.333 | 0/3 | 18 | 12 | 0 |
| Q011-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.500 / 0.500 / 0.500 | 0.500 | 0/3 | 12 | 6 | 0 |
| Q012-p1-unsupported_sentence | perturbed | hallucinated | définitionnel | 0.600 / 0.600 / 0.600 | 0.600 | 0/3 | 15 | 6 | 0 |

## Failures (recorded as nan, never dropped)

None.
