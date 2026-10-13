# Generation variant `gen-citation-example-v2` vs baseline

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_generation_default_n12_20261012T082113Z.json`, `eval/results/prompt_cmp_generation_default_n12_20261012T093211Z.json`
- **variant**: `eval/results/prompt_cmp_generation_gen-citation-example-v2_n12_20261013T101340Z.json`, `eval/results/prompt_cmp_generation_gen-citation-example-v2_n12_20261013T113959Z.json`
- **Differs in**: generation.answer
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Gate (no fabricated work title, no title/year mismatch, in any run)

| candidate | run | gate | answers checked | failures |
|---|---|---|---|---|
| default | 1 | PASSED | 36/36 | — |
| default | 2 | PASSED | 36/36 | — |
| gen-citation-example-v2 | 1 | PASSED | 36/36 | — |
| gen-citation-example-v2 | 2 | PASSED | 36/36 | — |

## Faithfulness by the frozen judge, and failures (per run)

| candidate | run | mean (higher = fewer unsupported claims) | nan per repeat | unevaluated per repeat | unsupported claims | generation failures |
|---|---|---|---|---|---|---|
| default | 1 | 0.836 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 53 | 0 |
| default | 2 | 0.821 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 58 | 0 |
| gen-citation-example-v2 | 1 | 0.860 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 1/12, r3 1/12 | 32 | 0 |
| gen-citation-example-v2 | 2 | 0.862 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 1/12, r3 1/12 | 32 | 0 |

## Substance (beside the axes: an answer that says less has less to get wrong)

| candidate | run | claims/answer | chars/answer | citations/answer | answers with a citation | citations to a chunk not given |
|---|---|---|---|---|---|---|
| default | 1 | 7.222 | 885.000 | 0.556 | 14/36 | 0 |
| default | 2 | 7.444 | 885.417 | 0.583 | 15/36 | 0 |
| gen-citation-example-v2 | 1 | 6.222 | 929.917 | 1.972 | 28/36 | 0 |
| gen-citation-example-v2 | 2 | 6.222 | 929.917 | 1.972 | 28/36 | 0 |

**Warning**: gen-citation-example-v2 scores higher (0.861 vs 0.828) with fewer claims per answer (6.2 vs 7.3): the gain may come from saying less. Read the answers before crediting it.

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run | identical answers |
|---|---|---|---|---|---|---|---|
| default | run 1 | 0.035 | 0.222 | 1 | 87 | 18 | 10 |
| default | run 2 | 0.013 | 0.077 | 1 | 90 | 7 | 12 |
| default | pooled (2 runs, 6 repeats) | 0.042 | 0.222 | 1 | 94 | 17 | 10 |
| gen-citation-example-v2 | run 1 | 0.081 | 0.333 | 2 | 77 | 29 | 7 |
| gen-citation-example-v2 | run 2 | 0.063 | 0.333 | 2 | 78 | 20 | 7 |
| gen-citation-example-v2 | pooled (2 runs, 6 repeats) | 0.081 | 0.333 | 3 | 96 | 12 | 7 |

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 10 items; nonzero: Q003 0.108, Q005 0.074; nan on 0 (—); max 0.108, mean 0.015 over 12 finite items
- **gen-citation-example-v2**: 0 on 9 items; nonzero: Q002 0.133, Q009 0.054, Q011 0.056; nan on 0 (—); max 0.133, mean 0.020 over 12 finite items

## Selection axes (only if both pass the gate in every run)

- trade-off between default and gen-citation-example-v2: gen-citation-example-v2 has the higher faithfulness mean (fewer unsupported claims), default more stable; no preference without the owner's call

## Claims newly flagged unsupported (distinct, all runs, with the judge's reason)

- Q001: La boule de neige est utilisée pour montrer que, comme une boule de neige grandit continuellement en accumulant de la neige, chaque état d'âme grandit en accumulant de la durée. — Le contexte ne mentionne pas explicitement l'utilisation d'une boule de neige pour illustrer la croissance de chaque état d'âme en accumulant de la durée.
- Q001: La boule de neige est utilisée pour montrer que, comme une boule de neige grandit continuellement en accumulant de la neige, de même, chaque état d'âme grandit en accumulant de la durée. — Le contexte ne mentionne pas explicitement la boule de neige. La boule de neige est utilisée comme un exemple pour illustrer le changement continu de l'état d'âme, mais pas pour montrer que chaque état d'âme grandit en accumulant de la durée.
- Q002: Si nous pouvions embrasser l'univers dans son ensemble, inorganique mais entretissu d'êtres organisés, nous le verrions prendre sans cesse des formes aussi neuves, aussi originales, aussi imprévisibles que nos états de conscience. — Le contexte discute de la succession et de la durée du temps, mais il ne fait pas explicitement mention de l'univers étant entretissu d'êtres organisés et de ses formes étant imprévisibles comme nos états de conscience.
- Q005: Bergson décrit la perception d'un tremblement de terre pour expliquer comment l'intelligence humaine réagit à des événements graves et soudains, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson.
- Q006: Bergson reconstitue la pensée d'un certain philosophe en la comparant à une recette de cuisine. — Le contexte ne mentionne pas explicitement la comparaison de la pensée d'un certain philosophe à une recette de cuisine par Bergson.
- Q006: Bergson donne un aspect original à l'ensemble de la doctrine. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson. Il n'y a donc pas de lien direct entre le contexte et l'affirmation.
- Q006: C'est une méthode de synthèse qui permet à Bergson de présenter une philosophie comme une entité cohérente. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson ou de sa méthode de synthèse.
- Q007: Cette logique considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. — Le texte discute de la logique immanente à nos langues, qui considère l'intelligence comme ayant pour essence de juger par l'attribution d'un prédicat à un sujet. Cette logique est formulée par Aristote et considère que le sujet, par cela seul qu'on le nomme, est défini comme invariable ; la variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, la logique considérée dans le texte ne considère pas l'immobilité et l'immutabilité comme de droit, mais plutôt comme des caractéristiques des sujets, qui peuvent changer de caractéristiques.
- Q007: L'immobilité et l'immutabilité sont considérés comme des substances invariables dans cette logique. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. La substance est censée invariable, et la variation réside dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, l'immobilité et l'immutabilité sont considérés comme des caractéristiques des substances, et non pas comme des substances invariables.
- Q009: Selon Bergson, cette grande chevauchée est conscience. — Le contexte décrit une grande armée qui galope, ce qui peut être interprété comme une métaphore pour la conscience, mais il n'y a pas de mention explicite de Bergson affirmant que cette grande chevauchée est conscience.
- Q009: La conscience, d'après Bergson, est essentiellement libre. — Le contexte décrit la philosophie de Bergson, qui traite de la vie spirituelle et de sa relation à la vie du corps. Il y a plusieurs références à la conscience, mais il n'y a pas de mention explicite de sa liberté essentielle.
- Q010: Bergson propose également une autre interprétation possible. — Le contexte discute de l'évolution de la pensée humaine, mais il ne mentionne pas explicitement Bergson. Cependant, il est possible que Bergson ait proposé une autre interprétation, car il est connu pour avoir écrit sur la philosophie grecque, mais cela n'est pas directement déduit du contexte.
- Q010: Dans ce cas, l'effort n'aurait jamais atteint le but. — Le contexte décrit une évolution de la pensée humaine qui a abouti à un développement rationnel et mystique. Il ne suggère pas que l'effort aurait jamais atteint le but.
- Q011: Cependant, il ne considère pas ces oscillations comme une fatalité historique, mais plutôt comme le résultat de certains dispositifs sociaux ou individuels. — Le contexte discute de la nature des oscillations historiques et de la possibilité de briser les obstacles par des volontés suffisamment tendues, sans mentionner explicitement que ces oscillations sont le résultat de dispositifs sociaux ou individuels.
- Q011: Les oscillations historiques décrites par Bergson sont caractérisées par des allers-retours. — Le contexte décrit les oscillations historiques comme des mouvements en spirale, qui s'observent en histoire, plutôt que des allers-retours. Il est donc possible de déduire que les oscillations décrites par Bergson ne sont pas caractérisées par des allers-retours.
- Q011: Les oscillations historiques ne sont pas dues à une nécessité historique mais plutôt à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel. — Le contexte discute des alternances de flux et de reflux observés en histoire, et attribue ces oscillations à des causes psychologiques et sociales, ce qui implique que les oscillations historiques ne sont pas uniquement dues à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel.
- Q010: Selon lui, selon cette interprétation, le développement de la pensée grecque serait l'œuvre de la seule raison. — Le contexte discute de la pénétration de l'orphisme et l'épanouissement de la dialectique en mystique, mais il ne mentionne pas explicitement que l'auteur croit que le développement de la pensée grecque serait l'œuvre de la seule raison.
- Q011: Bergson souligne que les actions prolongées dans un sens amènent une réaction dans le sens opposé, créant ainsi un mouvement en spirale plutôt qu'un oscillation pendulaire classique. — Le contexte discute de l'oscillation et de la spirale dans l'histoire, mais il ne mentionne pas explicitement que Bergson souligne un mouvement en spirale plutôt qu'un oscillation pendulaire classique.

## Polarity review: negated segments newly asserted by the variant (read by hand)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness delta says nothing about these. Check each against its chunks.

- Q001 (pas): Bergson utilise l'image de la boule de neige pour illustrer la perception du changement en soulignant que, contrairement à ce que l'on pourrait croire, chaque état d'âme ne reste pas identique pendant toute sa durée.
- Q002 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas une abstraction, une relation, un nombre pour la conscience humaine, mais un absolu qui coïncide avec un certain degré d'impatience qui est, lui, rigoureusement déterminé.
- Q002 (sans): Il conclut en affirmant que si nous pouvions embrasser l'univers dans son ensemble, inorganique mais entretissu d'êtres organisés, nous le verrions prendre sans cesse des formes aussi neuves, aussi originales, aussi imprévisibles que nos états de conscience. [1907_EC_c25, 1907_EC_c398, 1934_PM_c16]
- Q005 (pas): Des entités surgissent, qui n'ont pas besoin d'être des personnalités complètes : il leur suffit d'avoir des intentions, ou même de coïncider avec elles.
- Q007 (rien): Selon Bergson, la structure du langage est source de problèmes en philosophie car elle est calquée sur les mots, qui ont été élaborés par l'organisme social en vue d'un objet qui n'a rien de métaphysique.
- Q007 (pas): La philosophie accepterait ainsi une division du réel qui a toutes chances de ne pas correspondre aux articulations naturelles des choses.
- Q007 (pas): En d'autres termes, le langage exige que nous établissions entre nos idées les mêmes distinctions nettes et précises, la même discontinuité qu'entre les objets matériels, ce qui peut conduire à des problèmes insolubles lorsque l'on s'obstine à juxtaposer dans l'espace les phénomènes qui n'occupent pas d'espace, ou à mettre parfois un terme à des difficultés insurmontables que certains problèmes philosophiques soulèvent. [1888_EDIC_c1, 1934_PM_c60]
- Q007 (pas): Celles-ci sont de fabrication humaine et ne viennent pas du fond des choses, mais d'un transport automatique, à la spéculation, des habitudes contractées dans l'action.
- Q008 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 (ni, pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que chacun des détails de l'une correspond à chacun des détails de l'autre, ni que les deux soient la même chose.
- Q008 (ni, nullement): Il souligne que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q009 (sans): La conscience est essentiellement libre, mais elle ne peut agir sans s'adapter à la matière.
- Q012 (plus): Cette loi est appliquée à l'évolution générale de la vie, où les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, et à l'évolution de la vie psychologique et sociale, où les tendances se développent dans le même individu ou dans la même société, et ne peuvent d'ordinaire se développer que successivement.
- Q012 (plus): Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, tandis que dans l'évolution de la vie psychologique et sociale, les tendances se développent dans le même individu ou dans la même société, et ne peuvent d'ordinaire se développer que successivement.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | gen-citation-example-v2 run 1 | gen-citation-example-v2 run 2 |
|---|---|---|---|---|
| Q001 | 0.875 (0/3) | 0.875 (0/3) | 0.838 (0/3) | 0.838 (0/3) |
| Q002 | 1.000 (0/3) | 1.000 (0/3) | 0.867 (0/3) | 1.000 (0/3) |
| Q003 | 0.958 (0/3) | 0.850 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q004 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q005 | 0.519 (0/3) | 0.444 (0/3) | 0.833 (0/3) | 0.833 (0/3) |
| Q006 | 0.750 (0/3) | 0.750 (0/3) | 0.500 (0/3) | 0.500 (0/3) |
| Q007 | 0.436 (0/3) | 0.436 (0/3) | 0.778 (0/3) | 0.778 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q009 | 1.000 (0/3) | 1.000 (0/3) | 0.815 (0/3) | 0.762 (0/3) |
| Q010 | 0.778 (0/3) | 0.778 (0/3) | 0.898 (0/3) | 0.898 (0/3) |
| Q011 | 0.917 (0/3) | 0.917 (0/3) | 0.786 (0/3) | 0.730 (0/3) |
| Q012 | 0.800 (0/3) | 0.800 (0/3) | 1.000 (0/3) | 1.000 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|
| Q001 | 0.875 | 0.838 | -0.037 | 0.000 | outside noise |
| Q002 | 1.000 | 0.867 | -0.133 | 0.000 | outside noise |
| Q003 | 0.958 | 1.000 | 0.042 | 0.108 | within noise |
| Q004 | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q005 | 0.519 | 0.833 | 0.315 | 0.074 | outside noise |
| Q006 | 0.750 | 0.500 | -0.250 | 0.000 | outside noise |
| Q007 | 0.436 | 0.778 | 0.342 | 0.000 | outside noise |
| Q008 | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q009 | 1.000 | 0.815 | -0.185 | 0.000 | outside noise |
| Q010 | 0.778 | 0.898 | 0.120 | 0.000 | outside noise |
| Q011 | 0.917 | 0.786 | -0.131 | 0.000 | outside noise |
| Q012 | 0.800 | 1.000 | 0.200 | 0.000 | outside noise |
