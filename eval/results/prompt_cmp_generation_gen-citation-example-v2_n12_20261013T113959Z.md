# Prompt comparison run: generation mode, gen-citation-example-v2

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **Created**: 2026-10-13T11:39:59Z
- **Command**: `python -m eval.scripts.run_prompt_comparison --variant gen-citation-example-v2 --repeat 3 --checkpoint eval/results/prompt_comparison_checkpoint_rerun.jsonl --output-dir /private/tmp/claude-501/-Users-michel-Dev-bergson-rag/d4d83649-9c82-4947-9a4d-e1e8c138924c/scratchpad/run4`
- **Source**: variant `gen-citation-example-v2` — hypothesis: Observed failure: gen-citation-example (eval/results/prompt_cmp_genvs_gen-citation-example_20261013T100728Z.md, read by hand in docs/prompts.md, "Variant gen-citation-example") raised answers with a citation from 14-15 to 28 of 36, but 28 answers copied the example's « Selon Bergson » opener (6 in the baseline), and the frozen judge's « Bergson not mentioned » false flags rose from 15 to 27 (faithfulness 0.707); Q005, Q007 and Q011 still grouped several chunk_ids in one bracket, and most answers cited once, at the end. Variant: the same example, against the committed generation.answer, with two changes: no attribution to Bergson anywhere in it, and one more sentence (from 1900_R_c18) so that it shows three excerpts each cited on its own and a synthesis sentence citing two in separate brackets. Nothing else changed. Question: do answers keep citing as often, stop opening with « Selon Bergson », cite per sentence and one chunk per bracket, with the faithfulness back near the baseline (outside Q005/Q007), no example chunk_id reused and no gate failure? Citations are stripped before judging: count them and read them. Run on exp/prompt-gen-citation-inline at the owner's request.
- **Overridden prompts**: generation.answer
- **Models**: judge `ollama_chat/mistral`, generation `ollama_chat/mistral`; temperature {'judge': 0.0, 'generation': 0.0}
- **Retrieval**: bypassed: gold chunks (paragraph_ids resolved via src.paragraph_chunk_map, read from Qdrant)
- **Items**: 12 {'gold': 12}; repeat 3
- **Git**: `5dfe46e4d51122435adb868ed3aeeee9383f5708` (exp/prompt-gen-citation-inline), dirty: False
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Prompt manifest

| prompt | version | hash | custom |
|---|---|---|---|
| faithfulness.nli_verifier | v1 | `89e87a3d7dfb` | False |
| faithfulness.segment_claims | v1 | `1d73fc7146af` | False |
| generation.answer | v1 | `c2b0419aef0b` | True |
| generation.system | v1 | `e6d608e1eb84` | False |
| judge_chunk.relevance | v1 | `0922b7646460` | False |
| judge_chunk.retry | v1 | `e2036cc593ab` | False |
| judge_chunk.system | v1 | `c1ad1bff969c` | False |
| library:ragas | 0.3.9 | — | — |

## Gate (no fabricated work title, no title/year mismatch, in any run)

**PASSED** over 36/36 generated answers

## Faithfulness by the frozen judge (higher = fewer unsupported claims)

Mean 0.862 over 12 items; nan per run: run 1: 0/12, run 2: 0/12, run 3: 0/12; runs with unevaluated claims (left out of their score): run 1: 0/12, run 2: 1/12, run 3: 1/12. Judge's accepted gate misses: Q008-p1-negation.

## Substance (beside the axes: an answer that says less has less to get wrong)

| run | claims/answer | chars/answer | citations/answer | answers with a citation |
|---|---|---|---|---|
| 1 | 5.667 | 888.583 | 2.083 | 10/12 |
| 2 | 6.500 | 950.583 | 1.917 | 9/12 |
| 3 | 6.500 | 950.583 | 1.917 | 9/12 |

Citations to a chunk the answer wasn't given:
- none

## Stability over repeats

Mean per-item score range 0.063 (max 0.333); verdict flips 2 of 78 statements seen in 2+ runs; 20 statements extracted in one run only; answer identical in every repeat on 7 items, varied on Q001, Q007, Q010, Q011, Q012.

## Unsupported claims (with the judge's reason)

- Q001 run 1: La boule de neige est utilisée pour montrer que, comme une boule de neige grandit continuellement en accumulant de la neige, chaque état d'âme grandit en accumulant de la durée. — Le contexte ne mentionne pas explicitement l'utilisation d'une boule de neige pour illustrer la croissance de chaque état d'âme en accumulant de la durée.
- Q001 run 2: La boule de neige est utilisée pour montrer que, comme une boule de neige grandit continuellement en accumulant de la neige, de même, chaque état d'âme grandit en accumulant de la durée. — Le contexte ne mentionne pas explicitement la boule de neige. La boule de neige est utilisée comme un exemple pour illustrer le changement continu de l'état d'âme, mais pas pour montrer que chaque état d'âme grandit en accumulant de la durée.
- Q001 run 3: La boule de neige est utilisée pour montrer que, comme une boule de neige grandit continuellement en accumulant de la neige, de même, chaque état d'âme grandit en accumulant de la durée. — Le contexte ne mentionne pas explicitement la boule de neige. La boule de neige est utilisée comme un exemple pour illustrer le changement continu de l'état d'âme, mais pas pour montrer que chaque état d'âme grandit en accumulant de la durée.
- Q005 run 1: Bergson décrit la perception d'un tremblement de terre pour expliquer comment l'intelligence humaine réagit à des événements graves et soudains, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson.
- Q005 run 2: Bergson décrit la perception d'un tremblement de terre pour expliquer comment l'intelligence humaine réagit à des événements graves et soudains, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson.
- Q005 run 3: Bergson décrit la perception d'un tremblement de terre pour expliquer comment l'intelligence humaine réagit à des événements graves et soudains, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il y réagit, mais il n'y a pas de mention de Bergson.
- Q006 run 1: Bergson reconstitue la pensée d'un certain philosophe en la comparant à une recette de cuisine. — Le contexte ne fait aucune référence à Bergson ou à une comparaison de la pensée à une recette de cuisine.
- Q006 run 1: Bergson donne un aspect original à l'ensemble de la doctrine. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson. Il n'y a donc pas de lien direct entre le contexte et l'affirmation.
- Q006 run 1: C'est une méthode de synthèse qui permet à Bergson de présenter une philosophie comme une entité cohérente. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson ou de sa méthode de synthèse.
- Q006 run 2: Bergson reconstitue la pensée d'un certain philosophe en la comparant à une recette de cuisine. — Le contexte ne mentionne pas explicitement la comparaison de la pensée d'un certain philosophe à une recette de cuisine par Bergson.
- Q006 run 2: Bergson donne un aspect original à l'ensemble de la doctrine. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson. Il n'y a donc pas de lien direct entre le contexte et l'affirmation.
- Q006 run 2: C'est une méthode de synthèse qui permet à Bergson de présenter une philosophie comme une entité cohérente. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson ou de sa méthode de synthèse.
- Q006 run 3: Bergson reconstitue la pensée d'un certain philosophe en la comparant à une recette de cuisine. — Le contexte ne mentionne pas explicitement la comparaison de la pensée d'un certain philosophe à une recette de cuisine par Bergson.
- Q006 run 3: Bergson donne un aspect original à l'ensemble de la doctrine. — Le contexte traite de la philosophie de Berkeley et ne fait aucune mention de Bergson. Il n'y a donc pas de lien direct entre le contexte et l'affirmation.
- Q006 run 3: C'est une méthode de synthèse qui permet à Bergson de présenter une philosophie comme une entité cohérente. — Le contexte ne fait aucune mention de Bergson ou de sa méthode de synthèse. Le contexte traite de la philosophie de Berkeley et ne fournit aucune preuve de la présence de Bergson ou de sa méthode.
- Q007 run 2: Cette logique considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. — Le texte discute de la logique immanente à nos langues, qui considère l'intelligence comme ayant pour essence de juger par l'attribution d'un prédicat à un sujet. Cette logique est formulée par Aristote et considère que le sujet, par cela seul qu'on le nomme, est défini comme invariable ; la variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, la logique considérée dans le texte ne considère pas l'immobilité et l'immutabilité comme de droit, mais plutôt comme des caractéristiques des sujets, qui peuvent changer de caractéristiques.
- Q007 run 2: L'immobilité et l'immutabilité sont considérés comme des substances invariables dans cette logique. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. La substance est censée invariable, et la variation réside dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, l'immobilité et l'immutabilité sont considérés comme des caractéristiques des substances, et non pas comme des substances invariables.
- Q007 run 3: Cette logique considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. — Le texte discute de la logique immanente à nos langues, qui considère l'intelligence comme ayant pour essence de juger par l'attribution d'un prédicat à un sujet. Cette logique est formulée par Aristote et considère que le sujet, par cela seul qu'on le nomme, est défini comme invariable ; la variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, la logique considérée dans le texte ne considère pas l'immobilité et l'immutabilité comme de droit, mais plutôt comme des caractéristiques des sujets, qui peuvent changer de caractéristiques.
- Q007 run 3: L'immobilité et l'immutabilité sont considérés comme des substances invariables dans cette logique. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. La substance est censée invariable, et la variation réside dans la diversité des états qu'on affirmera de lui tour à tour. Ainsi, l'immobilité et l'immutabilité sont considérés comme des caractéristiques des substances, et non pas comme des substances invariables.
- Q009 run 1: Selon Bergson, cette grande chevauchée est conscience. — Le contexte décrit une grande armée qui galope, ce qui peut être interprété comme une métaphore pour la conscience, mais il n'y a pas de mention explicite de Bergson affirmant que cette grande chevauchée est conscience.
- Q009 run 1: La conscience, d'après Bergson, est essentiellement libre. — Le contexte décrit la philosophie de Bergson, qui traite de la vie spirituelle et de sa relation à la vie du corps. Il y a plusieurs références à la conscience, mais il n'y a pas de mention explicite de sa liberté essentielle.
- Q009 run 2: Selon Bergson, cette grande chevauchée est conscience. — Le contexte décrit une grande armée qui galope, ce qui peut être interprété comme une métaphore pour la conscience, mais il n'y a pas de mention explicite de Bergson affirmant que cette grande chevauchée est conscience.
- Q009 run 3: Selon Bergson, cette grande chevauchée est conscience. — Le contexte décrit une grande armée qui galope, ce qui peut être interprété comme une métaphore pour la conscience, mais il n'y a pas de mention explicite de Bergson affirmant que cette grande chevauchée est conscience.
- Q009 run 3: La conscience, d'après Bergson, est essentiellement libre. — Le contexte décrit la philosophie de Bergson, qui traite de la vie spirituelle et de sa relation à la vie du corps. Il y a plusieurs références à la conscience, mais il n'y a pas de mention explicite de sa liberté essentielle.
- Q010 run 1: Selon lui, selon cette interprétation, le développement de la pensée grecque serait l'œuvre de la seule raison. — Le contexte discute de la pénétration de l'orphisme et l'épanouissement de la dialectique en mystique, mais il ne mentionne pas explicitement que l'auteur croit que le développement de la pensée grecque serait l'œuvre de la seule raison.
- Q010 run 2: Dans ce cas, l'effort n'aurait jamais atteint le but. — Le contexte décrit une évolution de la pensée humaine qui a abouti à un développement rationnel et mystique. Il ne suggère pas que l'effort aurait jamais atteint le but.
- Q010 run 3: Dans ce cas, l'effort n'aurait jamais atteint le but. — Le contexte décrit une évolution de la pensée humaine qui a abouti à un développement rationnel et mystique. Il ne suggère pas que l'effort aurait jamais atteint le but.
- Q011 run 1: Cependant, il ne considère pas ces oscillations comme une fatalité historique, mais plutôt comme le résultat de certains dispositifs sociaux ou individuels. — Le contexte discute de la nature des oscillations historiques et de la possibilité de briser les obstacles par des volontés suffisamment tendues, sans mentionner explicitement que ces oscillations sont le résultat de dispositifs sociaux ou individuels.
- Q011 run 2: Bergson souligne que les actions prolongées dans un sens amènent une réaction dans le sens opposé, créant ainsi un mouvement en spirale plutôt qu'un oscillation pendulaire classique. — Le contexte discute de l'oscillation et de la spirale dans l'histoire, mais il ne mentionne pas explicitement que Bergson souligne un mouvement en spirale plutôt qu'un oscillation pendulaire classique.
- Q011 run 2: Les oscillations historiques ne sont pas dues à une nécessité historique mais plutôt à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel. — Le contexte discute des alternances de flux et de reflux observés en histoire, et attribue ces oscillations à des causes psychologiques et sociales, ce qui implique que les oscillations historiques ne sont pas uniquement dues à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel.
- Q011 run 3: Les oscillations historiques décrites par Bergson sont caractérisées par des allers-retours. — Le contexte décrit les oscillations historiques comme des mouvements en spirale, qui s'observent en histoire, plutôt que des allers-retours. Il est donc possible de déduire que les oscillations décrites par Bergson ne sont pas caractérisées par des allers-retours.
- Q011 run 3: Les oscillations historiques ne sont pas dues à une nécessité historique mais plutôt à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel. — Le contexte discute des alternances de flux et de reflux observés en histoire, et attribue ces oscillations à des causes psychologiques et sociales, ce qui implique que les oscillations historiques ne sont pas uniquement dues à des dispositifs simples mis en place par l'homme social ou des dispositions de l'homme individuel.

## Polarity review (negated segments the judge accepted)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness score says nothing about polarity. Read the segments below against their chunks.

- Q001 run 1 (pas): Bergson utilise l'image de la boule de neige pour illustrer la perception du changement en soulignant que, contrairement à ce que l'on pourrait croire, chaque état d'âme ne reste pas identique pendant toute sa durée.
- Q001 run 2 (pas): Bergson utilise l'image de la boule de neige pour illustrer la perception du changement en soulignant que, contrairement à ce que l'on pourrait croire, chaque état d'âme ne reste pas identique pendant toute sa durée.
- Q001 run 3 (pas): Bergson utilise l'image de la boule de neige pour illustrer la perception du changement en soulignant que, contrairement à ce que l'on pourrait croire, chaque état d'âme ne reste pas identique pendant toute sa durée.
- Q002 run 1 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas une abstraction, une relation, un nombre pour la conscience humaine, mais un absolu qui coïncide avec un certain degré d'impatience qui est, lui, rigoureusement déterminé.
- Q002 run 1 (sans): Il conclut en affirmant que si nous pouvions embrasser l'univers dans son ensemble, inorganique mais entretissu d'êtres organisés, nous le verrions prendre sans cesse des formes aussi neuves, aussi originales, aussi imprévisibles que nos états de conscience. [1907_EC_c25, 1907_EC_c398, 1934_PM_c16]
- Q002 run 2 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas une abstraction, une relation, un nombre pour la conscience humaine, mais un absolu qui coïncide avec un certain degré d'impatience qui est, lui, rigoureusement déterminé.
- Q002 run 2 (sans): Il conclut en affirmant que si nous pouvions embrasser l'univers dans son ensemble, inorganique mais entretissu d'êtres organisés, nous le verrions prendre sans cesse des formes aussi neuves, aussi originales, aussi imprévisibles que nos états de conscience. [1907_EC_c25, 1907_EC_c398, 1934_PM_c16]
- Q002 run 3 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas une abstraction, une relation, un nombre pour la conscience humaine, mais un absolu qui coïncide avec un certain degré d'impatience qui est, lui, rigoureusement déterminé.
- Q002 run 3 (sans): Il conclut en affirmant que si nous pouvions embrasser l'univers dans son ensemble, inorganique mais entretissu d'êtres organisés, nous le verrions prendre sans cesse des formes aussi neuves, aussi originales, aussi imprévisibles que nos états de conscience. [1907_EC_c25, 1907_EC_c398, 1934_PM_c16]
- Q004 run 1 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 2 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 3 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q005 run 1 (pas): Des entités surgissent, qui n'ont pas besoin d'être des personnalités complètes : il leur suffit d'avoir des intentions, ou même de coïncider avec elles.
- Q005 run 2 (pas): Des entités surgissent, qui n'ont pas besoin d'être des personnalités complètes : il leur suffit d'avoir des intentions, ou même de coïncider avec elles.
- Q005 run 3 (pas): Des entités surgissent, qui n'ont pas besoin d'être des personnalités complètes : il leur suffit d'avoir des intentions, ou même de coïncider avec elles.
- Q007 run 1 (rien): Selon Bergson, la structure du langage est source de problèmes en philosophie car elle est calquée sur les mots, qui ont été élaborés par l'organisme social en vue d'un objet qui n'a rien de métaphysique.
- Q007 run 1 (pas): La philosophie accepterait ainsi une division du réel qui a toutes chances de ne pas correspondre aux articulations naturelles des choses.
- Q007 run 1 (pas): En d'autres termes, le langage exige que nous établissions entre nos idées les mêmes distinctions nettes et précises, la même discontinuité qu'entre les objets matériels, ce qui peut conduire à des problèmes insolubles lorsque l'on s'obstine à juxtaposer dans l'espace les phénomènes qui n'occupent pas d'espace, ou à mettre parfois un terme à des difficultés insurmontables que certains problèmes philosophiques soulèvent. [1888_EDIC_c1, 1934_PM_c60]
- Q007 run 2 (pas): Celles-ci sont de fabrication humaine et ne viennent pas du fond des choses, mais d'un transport automatique, à la spéculation, des habitudes contractées dans l'action.
- Q007 run 3 (pas): Celles-ci sont de fabrication humaine et ne viennent pas du fond des choses, mais d'un transport automatique, à la spéculation, des habitudes contractées dans l'action.
- Q008 run 1 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 1 (ni, pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que chacun des détails de l'une correspond à chacun des détails de l'autre, ni que les deux soient la même chose.
- Q008 run 1 (ni, nullement): Il souligne que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 run 2 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 2 (ni, pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que chacun des détails de l'une correspond à chacun des détails de l'autre, ni que les deux soient la même chose.
- Q008 run 2 (ni, nullement): Il souligne que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 run 3 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 3 (ni, pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que chacun des détails de l'une correspond à chacun des détails de l'autre, ni que les deux soient la même chose.
- Q008 run 3 (ni, nullement): Il souligne que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q009 run 1 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 2 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 2 (sans): La conscience est essentiellement libre, mais elle ne peut agir sans s'adapter à la matière.
- Q009 run 3 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q012 run 1 (plus): Cette loi est appliquée à l'évolution générale de la vie, où les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, et à l'évolution de la vie psychologique et sociale, où les tendances se développent dans le même individu ou dans la même société, et ne peuvent d'ordinaire se développer que successivement.
- Q012 run 2 (plus): Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, tandis que dans l'évolution de la vie psychologique et sociale, les tendances se développent dans le même individu ou dans la même société, et ne peuvent d'ordinaire se développer que successivement.
- Q012 run 3 (plus): Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, tandis que dans l'évolution de la vie psychologique et sociale, les tendances se développent dans le même individu ou dans la même société, et ne peuvent d'ordinaire se développer que successivement.

## Per item

| id | origin | label | category | scores per run | mean | nan runs | claims | unsupported | unevaluated |
|---|---|---|---|---|---|---|---|---|---|
| Q001 | gold | faithful | définitionnel | 0.800 / 0.857 / 0.857 | 0.838 | 0/3 | 19 | 3 | 0 |
| Q002 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 15 | 0 | 0 |
| Q003 | gold | faithful | factuel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 15 | 0 | 0 |
| Q004 | gold | faithful | factuel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 18 | 0 | 0 |
| Q005 | gold | faithful | définitionnel | 0.833 / 0.833 / 0.833 | 0.833 | 0/3 | 18 | 3 | 0 |
| Q006 | gold | faithful | factuel | 0.500 / 0.500 / 0.500 | 0.500 | 0/3 | 18 | 9 | 0 |
| Q007 | gold | faithful | définitionnel | 1.000 / 0.667 / 0.667 | 0.778 | 0/3 | 16 | 4 | 0 |
| Q008 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 12 | 0 | 0 |
| Q009 | gold | faithful | définitionnel | 0.714 / 0.857 / 0.714 | 0.762 | 0/3 | 21 | 5 | 0 |
| Q010 | gold | faithful | définitionnel | 0.875 / 0.909 / 0.909 | 0.898 | 0/3 | 30 | 3 | 0 |
| Q011 | gold | faithful | définitionnel | 0.857 / 0.667 / 0.667 | 0.730 | 0/3 | 19 | 5 | 0 |
| Q012 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 23 | 0 | 2 |

## Failures (recorded as nan, never dropped)

None.
