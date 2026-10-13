# Generation variant `gen-citation-inline` vs baseline

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_generation_default_n12_20261012T082113Z.json`, `eval/results/prompt_cmp_generation_default_n12_20261012T093211Z.json`
- **variant**: `eval/results/prompt_cmp_generation_gen-citation-inline_n12_20261013T073443Z.json`
- **Differs in**: generation.answer
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Gate (no fabricated work title, no title/year mismatch, in any run)

| candidate | run | gate | answers checked | failures |
|---|---|---|---|---|
| default | 1 | PASSED | 36/36 | — |
| default | 2 | PASSED | 36/36 | — |
| gen-citation-inline | 1 | PASSED | 36/36 | — |

## Faithfulness by the frozen judge, and failures (per run)

| candidate | run | mean (higher = fewer unsupported claims) | nan per repeat | unevaluated per repeat | unsupported claims | generation failures |
|---|---|---|---|---|---|---|
| default | 1 | 0.836 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 53 | 0 |
| default | 2 | 0.821 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 58 | 0 |
| gen-citation-inline | 1 | 0.789 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 57 | 0 |

## Substance (beside the axes: an answer that says less has less to get wrong)

| candidate | run | claims/answer | chars/answer | citations/answer | answers with a citation | citations to a chunk not given |
|---|---|---|---|---|---|---|
| default | 1 | 7.222 | 885.000 | 0.556 | 14/36 | 0 |
| default | 2 | 7.444 | 885.417 | 0.583 | 15/36 | 0 |
| gen-citation-inline | 1 | 7.528 | 981.806 | 0.611 | 10/36 | 0 |

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run | identical answers |
|---|---|---|---|---|---|---|---|
| default | run 1 | 0.035 | 0.222 | 1 | 87 | 18 | 10 |
| default | run 2 | 0.013 | 0.077 | 1 | 90 | 7 | 12 |
| default | pooled (2 runs, 6 repeats) | 0.042 | 0.222 | 1 | 94 | 17 | 10 |
| gen-citation-inline | run 1 | 0.049 | 0.190 | 2 | 91 | 26 | 7 |
| gen-citation-inline | pooled (1 runs, 3 repeats) | 0.049 | 0.190 | 2 | 91 | 26 | 7 |

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 10 items; nonzero: Q003 0.108, Q005 0.074; nan on 0 (—); max 0.108, mean 0.015 over 12 finite items
- **gen-citation-inline**: single run, no floor

## Selection axes (only if both pass the gate in every run)

- default preferred over gen-citation-inline (better-or-equal on both axes)

## Claims newly flagged unsupported (distinct, all runs, with the judge's reason)

- Q001: La boule de neige représente la manière dont l'état d'âme humain se transforme et se développe en temps réel, en accumulant de la durée. — Le contexte discute de la nature du changement constant de l'état d'âme humaine, mais il ne fait pas explicitement mention de la boule de neige comme une représentation de cela.
- Q002: Pour la science physique, le temps est une abstraction, un nombre. — Le contexte discute de la nature du temps pour les êtres conscients et les systèmes matériels, et il est clair que le temps est perçu comme un absolu pour la conscience, ce qui implique qu'il n'est pas seulement une abstraction ou un nombre pour eux. Il n'y a pas de mention explicite de la science physique considérant le temps comme une abstraction ou un nombre.
- Q002: Il affirme que l'univers matériel, dans son ensemble, ne forme pas un système entièrement calculable. — Le texte discute de la nature du temps et de la succession des événements dans l'univers, mais il ne fait pas de déclaration explicite sur l'univers matériel étant entièrement calculable ou non.
- Q004: Bergson reprend pour en faire une œuvre complète ce que la nature laissa en lui à l'état d'ébauche ou de simple projet. — Le contexte discute de l'imagination poétique et de la création des personnages par les poètes, mais il ne fait aucune mention de Bergson. Il ne peut donc pas être directement déduit que Bergson reprend ce que la nature laissa en lui à l'état d'ébauche ou de simple projet.
- Q005: Bergson décrit la perception d'un tremblement de terre pour expliquer comment l'intelligence humaine réagit à des événements graves et inattendus, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson.
- Q005: L'intelligence humaine, lorsqu'elle est confrontée à une agression de la nature, personnifie le phénomène en une entité permanente et individuelle, qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il personnifie le tremblement de terre en une entité individuelle, mais il ne s'agit pas d'une entité permanente et qui a pour unique fonction d'être tremblement de terre.
- Q005: Selon Bergson, la perception d'un tremblement de terre est décrite pour montrer comment l'intelligence humaine réagit face à des événements graves et inattendus, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson ou de sa théorie.
- Q005: L'intelligence humaine peut personnifier le tremblement de terre en une entité permanente et individuelle, qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il décrit comment il a personnifié le tremblement de terre en une entité individuelle, mais il ne décrit pas qu'elle a pour unique fonction d'être tremblement de terre. Il décrit également comment il a perçu le tremblement de terre comme un agent vivant, mais il ne décrit pas qu'il s'agit d'une entité permanente et individuelle qui a pour unique fonction d'être tremblement de terre.
- Q006: Bergson compare la pensée de Berkeley à une recette de cuisine. — Le contexte ne mentionne pas de comparaison entre la pensée de Berkeley et une recette de cuisine.
- Q006: Bergson décrit ce processus en mettant en évidence les quatre thèses fondamentales de Berkeley. — Le contexte traite de la philosophie de Berkeley et de ses quatre thèses fondamentales, mais il ne mentionne pas Bergson. Il est donc impossible de déduire que Bergson décrit ce processus en mettant en évidence les quatre thèses fondamentales de Berkeley.
- Q006: Bergson mélange ces thèses avec des idées issues de la philosophie néo-platonicienne. — Le contexte discute de la philosophie de Berkeley et les quatre thèses fondamentales de son idéalisme, nominalisme, spiritualisme et théisme. Il n'y a pas de mention de Bergson ou de sa philosophie néo-platonicienne, donc on ne peut pas déduire qu'il mélange ces thèses avec des idées issues de la philosophie néo-platonicienne.
- Q006: Bergson montre une certaine impatience agressive à l'égard du dogmatisme mathématique. — Le contexte discute de la philosophie de Berkeley, mais il y a mention d'une impatience agressive à l'égard du dogmatisme mathématique, ce qui peut être interprété comme une caractéristique de Berkeley, mais pas nécessairement de Bergson.
- Q006: Bergson compare le processus de reconstitution de la pensée de Berkeley à une recette de cuisine. — Le contexte décrit la reconstitution de la philosophie de Berkeley, mais il n'y a aucune mention d'une comparaison avec une recette de cuisine.
- Q006: Les idées issues de la philosophie néo-platonicienne sont mêlées à celles de Bergson. — Le contexte traite de la philosophie de Berkeley et de ses influences, mais il n'y a aucune mention de Bergson ou de sa philosophie néo-platonicienne.
- Q007: Selon Bergson, la vision du monde impliquée dans notre langage est immanente à nos langues et est formulée par Aristote. — Le contexte discute sur la philosophie et la nature de la perception, la pensée et le langage, mais il ne mentionne pas explicitement que Bergson ait affirmé que la vision du monde impliquée dans notre langage est immanente à nos langages et est formulée par Aristote.
- Q007: Dans cette vision du monde, le sujet est défini comme invariable. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne fait pas directement référence à la définition du sujet comme invariable.
- Q007: Nous obéissons à la nature en procédant ainsi. — Le contexte discute de la nature de la pensée et du langage, et comment ils sont influencés par la nature, mais il ne discute pas explicitement de l'obéissance à la nature en procédant ainsi.
- Q007: Cette vision du monde conduit à des problèmes philosophiques insolubles car ils sont posés à l'envers. — Le contexte discute de la nature de la perception, du langage et de la pensée, et comment elles peuvent conduire à des problèmes philosophiques. Il est expliqué que ces problèmes peuvent être insolubles car ils sont posés à l'envers, mais il n'est pas directement inversé que cette vision du monde conduit à des problèmes philosophiques insolubles.
- Q007: Bergson pense que l'esprit humain doit être libéré de cette vision du monde pour pouvoir comprendre la réalité du changement et du mouvement. — Le contexte discute de la philosophie et de la manière dont elle est influencée par la nature de notre langage et de notre perception. Il ne fait pas directement mention de Bergson ou de ses idées spécifiques.
- Q007: La vision du monde impliquée par la structure du langage est immanente à nos langues et est formulée par Aristote. — Le contexte discute de la philosophie et de la manière dont elle est influencée par la structure du langage et l'intelligence, mais il ne mentionne pas explicitement Aristote en tant que formulant la vision du monde impliquée par la structure du langage.
- Q007: Il est nécessaire pour l'esprit humain de renverser le sens de son opération habituelle, de partir du changement et du mouvement, envisagés comme la réalité même, et de ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant. — Le contexte discute de la nature de la perception, du langage et de la pensée humaine, et l'auteur y explique comment ces derniers sont organisés pour la vie sociale et pour le travail en commun. Il y est question de la perception de l'immobilité et de l'immutabilité comme essences ou substances, mais il n'y a pas de mention de la nécessité pour l'esprit humain de renverser le sens de son opération habituelle.
- Q009: La conscience ne peut traverser la matière sans s'adapter à elle, ce qui est ce qu'on appelle l'intellectualité. — Le contexte discute de la relation entre la vie de l'esprit et celle du corps, et il est clair que la conscience est décrite comme étant distincte de l'organisme qu'elle anime, mais il n'y a pas de mention explicite de l'adaptation de la conscience à la matière étant appelée l'intellectualité.
- Q012: Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes. — Le contexte discute de l'évolution générale de la vie, mais il ne fait pas explicitement mention de l'évolution de ces tendances se développant le plus souvent dans des espèces distinctes.
- Q012: Dans l'évolution de la vie psychologique et sociale, il arrive que l'expression soit rigoureusement juste. — Le contexte discute de la loi de dichotomie et de la loi de double frénésie dans l'évolution générale de la vie, mais il ne fait pas explicitement mention de l'évolution de la vie psychologique et sociale.
- Q012: Il semble que la sagesse conseillerait alors une coopération des deux tendances. — Le contexte discute de la dichotomie des tendances et leur évolution divergente, mais il ne mentionne pas explicitement la coopération des deux tendances.

## Polarity review: negated segments newly asserted by the variant (read by hand)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness delta says nothing about these. Check each against its chunks.

- Q002 (non): Il suggère que la durée de l'univers, qui est déterminée par la succession des états successifs, est liée à la latitude de création et à la vie, et non pas à la matière seule.
- Q004 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la vie.
- Q005 (pas): Il souligne que la croyance signifie essentiellement confiance, et que l'origine première n'est pas la crainte, mais une assurance contre la crainte.
- Q007 (pas): Bergson souligne que ces problèmes ne viennent pas du fond des choses, mais d'un transport automatique, à la spéculation, des habitudes contractées dans l'action.
- Q008 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 (pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que l'une est l'équivalent de l'autre ou que chaque détail de l'une correspond à un détail de l'autre.
- Q008 (ni, nullement): Il soutient que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q009 (sans): Selon lui, cette chevauchée est la conscience, qui enveloppe des virtualités sans nombre et qui ne peut être divisée en individualités distinctes que par la matière.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | gen-citation-inline run 1 |
|---|---|---|---|
| Q001 | 0.875 (0/3) | 0.875 (0/3) | 0.667 (0/3) |
| Q002 | 1.000 (0/3) | 1.000 (0/3) | 0.667 (0/3) |
| Q003 | 0.958 (0/3) | 0.850 (0/3) | 1.000 (0/3) |
| Q004 | 1.000 (0/3) | 1.000 (0/3) | 0.944 (0/3) |
| Q005 | 0.519 (0/3) | 0.444 (0/3) | 0.746 (0/3) |
| Q006 | 0.750 (0/3) | 0.750 (0/3) | 0.458 (0/3) |
| Q007 | 0.436 (0/3) | 0.436 (0/3) | 0.481 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 1.000 (0/3) |
| Q009 | 1.000 (0/3) | 1.000 (0/3) | 0.889 (0/3) |
| Q010 | 0.778 (0/3) | 0.778 (0/3) | 1.000 (0/3) |
| Q011 | 0.917 (0/3) | 0.917 (0/3) | 0.917 (0/3) |
| Q012 | 0.800 (0/3) | 0.800 (0/3) | 0.700 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|
| Q001 | 0.875 | 0.667 | -0.208 | 0.000 | outside noise |
| Q002 | 1.000 | 0.667 | -0.333 | 0.000 | outside noise |
| Q003 | 0.958 | 1.000 | 0.042 | 0.108 | within noise |
| Q004 | 1.000 | 0.944 | -0.056 | 0.000 | outside noise |
| Q005 | 0.519 | 0.746 | 0.228 | 0.074 | outside noise |
| Q006 | 0.750 | 0.458 | -0.292 | 0.000 | outside noise |
| Q007 | 0.436 | 0.481 | 0.046 | 0.000 | outside noise |
| Q008 | 1.000 | 1.000 | 0.000 | 0.000 | within noise |
| Q009 | 1.000 | 0.889 | -0.111 | 0.000 | outside noise |
| Q010 | 0.778 | 1.000 | 0.222 | 0.000 | outside noise |
| Q011 | 0.917 | 0.917 | 0.000 | 0.000 | within noise |
| Q012 | 0.800 | 0.700 | -0.100 | 0.000 | outside noise |
