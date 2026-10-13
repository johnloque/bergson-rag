# Generation variant `gen-thesis-attribution` vs baseline

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_generation_default_n12_20261012T082113Z.json`, `eval/results/prompt_cmp_generation_default_n12_20261012T093211Z.json`
- **variant**: `eval/results/prompt_cmp_generation_gen-thesis-attribution_n12_20261012T140612Z.json`
- **Differs in**: generation.answer
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Gate (no fabricated work title, no title/year mismatch, in any run)

| candidate | run | gate | answers checked | failures |
|---|---|---|---|---|
| default | 1 | PASSED | 36/36 | — |
| default | 2 | PASSED | 36/36 | — |
| gen-thesis-attribution | 1 | PASSED | 36/36 | — |

## Faithfulness by the frozen judge, and failures (per run)

| candidate | run | mean (higher = fewer unsupported claims) | nan per repeat | unevaluated per repeat | unsupported claims | generation failures |
|---|---|---|---|---|---|---|
| default | 1 | 0.836 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 53 | 0 |
| default | 2 | 0.821 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 58 | 0 |
| gen-thesis-attribution | 1 | 0.856 | r1 0/12, r2 0/12, r3 0/12 | r1 1/12, r2 0/12, r3 0/12 | 31 | 0 |

## Substance (beside the axes: an answer that says less has less to get wrong)

| candidate | run | claims/answer | chars/answer | citations/answer | answers with a citation | citations to a chunk not given |
|---|---|---|---|---|---|---|
| default | 1 | 7.222 | 885.000 | 0.556 | 14/36 | 0 |
| default | 2 | 7.444 | 885.417 | 0.583 | 15/36 | 0 |
| gen-thesis-attribution | 1 | 6.000 | 866.639 | 1.667 | 21/36 | 0 |

**Warning**: gen-thesis-attribution scores higher (0.856 vs 0.828) with fewer claims per answer (6.0 vs 7.3): the gain may come from saying less. Read the answers before crediting it.

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run | identical answers |
|---|---|---|---|---|---|---|---|
| default | run 1 | 0.035 | 0.222 | 1 | 87 | 18 | 10 |
| default | run 2 | 0.013 | 0.077 | 1 | 90 | 7 | 12 |
| default | pooled (2 runs, 6 repeats) | 0.042 | 0.222 | 1 | 94 | 17 | 10 |
| gen-thesis-attribution | run 1 | 0.061 | 0.286 | 0 | 73 | 19 | 9 |
| gen-thesis-attribution | pooled (1 runs, 3 repeats) | 0.061 | 0.286 | 0 | 73 | 19 | 9 |

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 10 items; nonzero: Q003 0.108, Q005 0.074; nan on 0 (—); max 0.108, mean 0.015 over 12 finite items
- **gen-thesis-attribution**: single run, no floor

## Selection axes (only if both pass the gate in every run)

- trade-off between default and gen-thesis-attribution: gen-thesis-attribution has the higher faithfulness mean (fewer unsupported claims), stability split (fewer flips vs. smaller range); no preference without the owner's call

## Claims newly flagged unsupported (distinct, all runs, with the judge's reason)

- Q002: Pourquoi l'univers déroule-t-il ses états successifs avec une vitesse qui, au regard de la conscience, est un véritable absolu, et pourquoi avec cette vitesse déterminée plutôt qu'avec n'importe quelle autre. — Le contexte discute de la nature de la durée et de la succession dans l'univers, mais il ne fournit pas de réponse directe à la question de pourquoi l'univers déroule ses états successifs avec une vitesse déterminée plutôt qu'avec n'importe quelle autre.
- Q002: La vitesse de l'univers est déterminée pour Bergson. — Le contexte discute de la durée et de la succession dans l'univers, mais il ne mentionne pas explicitement la vitesse de l'univers et son détermination par Bergson.
- Q003: Dans cette illusion, on peut se dédoubler. — Le contexte décrit une illusion dans laquelle on peut ressentir un sentiment d'étrangeté à soi-même, mais il ne mentionne pas explicitement le dédoublement.
- Q004: Il soutient que la vie ne se recompose pas, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une partie du contexte qui soutient que la vie ne se recompose pas, mais il n'y a pas de mention explicite de la vie se laissant regarder simplement.
- Q004: La vie ne se recompose pas, selon Bergson, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une mention de Bergson, mais il n'y a pas de mention explicite de la vie se recomposant ou non. Cependant, le contexte suggère que la vie peut être observée et comprise, ce qui est en accord avec l'idée que la vie se laisse regarder simplement. Cependant, il n'y a pas de mention explicite de Bergson qui ait affirmé cette idée, donc la déclaration ne peut pas être directement inférée à partir du contexte.
- Q005: Dans le cas du tremblement de terre, l'individu personnifie le phénomène en une entité permanente et individuelle, considérant que le tremblement de terre est un être individualisé qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il personnifie le tremblement de terre en une entité individuelle, mais il ne considère pas que cela soit un être individualisé qui a pour unique fonction d'être tremblement de terre. En effet, il y a une différence entre personnifier un phénomène et considérer que ce phénomène est un être individualisé.
- Q006: Bergson reconstruit la pensée de Berkeley à la manière d'une recette de cuisine. — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson reconstruit sa pensée à la manière d'une recette de cuisine.
- Q007: En les mêmes termes, le mouvement et le changement viennent se surajouter, comme des accidents, à des choses qui par elles-mêmes ne se meuvent pas, et en elles-mêmes ne changent pas. — Le texte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la nature humaine et la société. Il y a une discussion sur la logique immanente à nos langues et comment elle nous conduit à voir l'immobilité et l'immutabilité comme des essences ou substances, en supports. Cependant, il n'y a pas de directe mention de mouvement et de changement comme des accidents de choses qui ne se meuvent pas et ne changent pas par elles-mêmes.
- Q007: Cette logique du langage conduit à des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage. Il est clair que le contexte soutient que la logique du langage peut conduire à des problèmes philosophiques, mais il ne fournit pas de preuve directe que ces problèmes seraient insolubles et posés à l'envers.
- Q007: Il s'agit pour l'esprit humain d'une libération. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage et la perception. Il n'y a pas de mention de libération de l'esprit humain.
- Q007: En les mêmes termes, le mouvement et le changement viennent se surajouter, comme des accidents, à des choses qui par elles-mêmes ne se meuvent pas et en elles-mêmes ne changent pas. — Le texte discute de la manière dont la perception et la pensée humaine sont influencées par la nature et la société, et comment elles ont été mises en place pour organiser le travail des hommes dans l'espace. Il y a une discussion sur la manière dont la nature a prédestiné l'homme à la vie sociale et à la perception de l'immobilité et de l'immutabilité comme essences ou substances, mais il n'y a pas de mention directe de la manière dont les choses se meuvent ou changent en eux-mêmes.
- Q009: Il y a une continuité entre les espèces, et la vie de l'homme est considérée comme un sous-ensemble de la vie plus large. — Le contexte discute de la relation entre la vie de l'esprit et celle du corps, et de la genèse des espèces par voie de transformation graduelle. Il y a une mention de l'homme comme étant une partie de la nature, mais il n'y a pas de mention explicite d'une continuité entre les espèces ou de la vie de l'homme comme un sous-ensemble de la vie plus large.
- Q012: Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, chacune de son côté cherchant fortune dans le monde. — Le contexte décrit l'évolution générale de la vie, y compris la dichotomie des tendances, mais il ne précise pas que ces tendances se développent le plus souvent dans des espèces distinctes.

## Polarity review: negated segments newly asserted by the variant (read by hand)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness delta says nothing about these. Check each against its chunks.

- Q001 (pas): Selon lui, chaque état d'âme, comme la perception visuelle d'un objet extérieur immobile, ne reste pas identique pendant tout le temps qu'il se produit, mais change continuellement, de manière à former une boule de neige avec lui-même.
- Q001 (pas): Cette image met en évidence la nature dynamique et évolutive de l'état d'âme, qui ne se réside pas dans un état fixe, mais dans un processus de changement.
- Q003 (pas): Cette dépersonnalisation est liée à la fausse reconnaissance, mais elle n'est pas indissolublement liée à elle.
- Q004 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en affirmant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 (pas): Il soutient que la vie ne se recompose pas, mais se laisse regarder simplement, et que l'imagination poétique permet au poète de saisir le virtuel dans le réel et de reprendre, pour en faire une œuvre complète, ce que la nature laissa en lui à l'état d'ébauche ou de simple projet. [1900_R_c170]
- Q007 (pas): Il s'agit de problèmes qui ne sont pas fondés sur la nature des choses, mais sur des habitudes contractées dans l'action.
- Q007 (non): Bergson soutient que l'esprit humain doit être libéré de cette logique du langage pour pouvoir voir dans le changement et le mouvement des réalités, et non plus des accidents.
- Q008 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 (pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que l'une est l'équivalent de l'autre ou que chaque détail de l'une correspond à un détail de l'autre.
- Q008 (ni, nullement): Il soutient que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 (pas): La thèse qu'il explique est donc que la solidarité entre la conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux, mais plutôt à l'existence d'une certaine relation entre les deux.
- Q009 (sans): Enfin, Bergson suggère que la conscience est essentiellement libre, mais qu'elle ne peut traverser la matière sans s'adapter à elle.
- Q011 (pas): Cependant, il ne croit pas à la fatalité historique et affirme que les volontés suffisamment tendues peuvent briser les obstacles si elles s'y prennent à temps.
- Q011 (sans): Il conclut en disant que la tendance simple aurait peut-être mieux fait de croître sans se dédoubler, mais que cela aurait empêché le maximum de création en quantité et en qualité.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | gen-thesis-attribution run 1 |
|---|---|---|---|
| Q001 | 0.875 (0/3) | 0.875 (0/3) | 1.000 (0/3) |
| Q002 | 1.000 (0/3) | 1.000 (0/3) | 0.730 (0/3) |
| Q003 | 0.958 (0/3) | 0.850 (0/3) | 0.944 (0/3) |
| Q004 | 1.000 (0/3) | 1.000 (0/3) | 0.810 (0/3) |
| Q005 | 0.519 (0/3) | 0.444 (0/3) | 0.722 (0/3) |
| Q006 | 0.750 (0/3) | 0.750 (0/3) | 0.750 (0/3) |
| Q007 | 0.436 (0/3) | 0.436 (0/3) | 0.571 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q009 | 1.000 (0/3) | 1.000 (0/3) | 0.833 (0/3) |
| Q010 | 0.778 (0/3) | 0.778 (0/3) | 1.000 (0/3) |
| Q011 | 0.917 (0/3) | 0.917 (0/3) | 1.000 (0/3) |
| Q012 | 0.800 (0/3) | 0.800 (0/3) | 0.909 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|
| Q001 | 0.875 | 1.000 | 0.125 | 0.000 | outside noise |
| Q002 | 1.000 | 0.730 | -0.270 | 0.000 | outside noise |
| Q003 | 0.958 | 0.944 | -0.014 | 0.108 | within noise |
| Q004 | 1.000 | 0.810 | -0.190 | 0.000 | outside noise |
| Q005 | 0.519 | 0.722 | 0.204 | 0.074 | outside noise |
| Q006 | 0.750 | 0.750 | 0.000 | 0.000 | within noise |
| Q007 | 0.436 | 0.571 | 0.136 | 0.000 | outside noise |
| Q008 | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q009 | 1.000 | 0.833 | -0.167 | 0.000 | outside noise |
| Q010 | 0.778 | 1.000 | 0.222 | 0.000 | outside noise |
| Q011 | 0.917 | 1.000 | 0.083 | 0.000 | outside noise |
| Q012 | 0.800 | 0.909 | 0.109 | 0.000 | outside noise |
