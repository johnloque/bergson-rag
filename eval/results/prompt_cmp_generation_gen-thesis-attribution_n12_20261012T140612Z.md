# Prompt comparison run: generation mode, gen-thesis-attribution

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **Created**: 2026-10-12T14:06:12Z
- **Command**: `python -m eval.scripts.run_prompt_comparison --variant gen-thesis-attribution --repeat 3`
- **Source**: variant `gen-thesis-attribution` — hypothesis: Observed failure: generation baseline (eval/results/prompt_cmp_genbase_default_20261012T103544Z.md, read by hand in docs/prompts.md, "Generation baseline") presents as Bergson's thesis a view he only considers. Q010 gives the « forces éruptives » reading (1932_2S_c170: « De là on pourrait conclure que… ») as his thesis and omits the interpretation he finds « plus vraisemblable »; Q011 turns « Il semble que la sagesse conseillerait… Malheureusement… » (1932_2S_c225) into his conclusion. The committed instructions never ask to tell an asserted thesis from a considered one. Variant: one fixed instruction asking for a clear distinction between a thesis Bergson asserts and one he only considers (supposition, plausible hypothesis, or another author's thesis); nothing else changed. Question: do the Q010 and Q011 answers state Bergson's own position, without a gate failure, a faithfulness drop outside Q005/Q007 (judge false flags) or fewer claims per answer? The frozen judge can't see this error: read the answers.
- **Overridden prompts**: generation.answer
- **Models**: judge `ollama_chat/mistral`, generation `ollama_chat/mistral`; temperature {'judge': 0.0, 'generation': 0.0}
- **Retrieval**: bypassed: gold chunks (paragraph_ids resolved via src.paragraph_chunk_map, read from Qdrant)
- **Items**: 12 {'gold': 12}; repeat 3
- **Git**: `4a2f947f2d8b39d2bd5c4c2a80a3af693255ed49` (exp/prompt-gen-thesis-attribution), dirty: True
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Prompt manifest

| prompt | version | hash | custom |
|---|---|---|---|
| faithfulness.nli_verifier | v1 | `89e87a3d7dfb` | False |
| faithfulness.segment_claims | v1 | `1d73fc7146af` | False |
| generation.answer | v1 | `96a04cc58f25` | True |
| generation.system | v1 | `e6d608e1eb84` | False |
| judge_chunk.relevance | v1 | `0922b7646460` | False |
| judge_chunk.retry | v1 | `e2036cc593ab` | False |
| judge_chunk.system | v1 | `c1ad1bff969c` | False |
| library:ragas | 0.3.9 | — | — |

## Gate (no fabricated work title, no title/year mismatch, in any run)

**PASSED** over 36/36 generated answers

## Faithfulness by the frozen judge (higher = fewer unsupported claims)

Mean 0.856 over 12 items; nan per run: run 1: 0/12, run 2: 0/12, run 3: 0/12; runs with unevaluated claims (left out of their score): run 1: 1/12, run 2: 0/12, run 3: 0/12. Judge's accepted gate misses: Q008-p1-negation.

## Substance (beside the axes: an answer that says less has less to get wrong)

| run | claims/answer | chars/answer | citations/answer | answers with a citation |
|---|---|---|---|---|
| 1 | 5.833 | 898.083 | 1.667 | 7/12 |
| 2 | 6.083 | 850.917 | 1.667 | 7/12 |
| 3 | 6.083 | 850.917 | 1.667 | 7/12 |

Citations to a chunk the answer wasn't given:
- none

## Stability over repeats

Mean per-item score range 0.061 (max 0.286); verdict flips 0 of 73 statements seen in 2+ runs; 19 statements extracted in one run only; answer identical in every repeat on 9 items, varied on Q002, Q003, Q011.

## Unsupported claims (with the judge's reason)

- Q002 run 1: Pourquoi l'univers déroule-t-il ses états successifs avec une vitesse qui, au regard de la conscience, est un véritable absolu, et pourquoi avec cette vitesse déterminée plutôt qu'avec n'importe quelle autre. — Le contexte discute de la nature de la durée et de la succession dans l'univers, mais il ne fournit pas de réponse directe à la question de pourquoi l'univers déroule ses états successifs avec une vitesse déterminée plutôt qu'avec n'importe quelle autre.
- Q002 run 2: Pourquoi l'univers déroule-t-il ses états successifs avec une vitesse qui, au regard de la conscience, est un véritable absolu, et pourquoi avec cette vitesse déterminée plutôt qu'avec n'importe quelle autre. — Le contexte discute de la nature de la durée et de la succession dans l'univers, mais il ne fournit pas de réponse directe à la question de pourquoi l'univers déroule ses états successifs avec une vitesse déterminée plutôt qu'avec n'importe quelle autre.
- Q002 run 2: La vitesse de l'univers est déterminée pour Bergson. — Le contexte discute de la durée et de la succession dans l'univers, mais il ne mentionne pas explicitement la vitesse de l'univers et son détermination par Bergson.
- Q002 run 3: Pourquoi l'univers déroule-t-il ses états successifs avec une vitesse qui, au regard de la conscience, est un véritable absolu, et pourquoi avec cette vitesse déterminée plutôt qu'avec n'importe quelle autre. — Le contexte discute de la nature de la durée et de la succession dans l'univers, mais il ne fournit pas de réponse directe à la question de pourquoi l'univers déroule ses états successifs avec une vitesse déterminée plutôt qu'avec n'importe quelle autre.
- Q002 run 3: La vitesse de l'univers est déterminée pour Bergson. — Le contexte discute de la durée et de la succession dans l'univers, mais il ne mentionne pas explicitement la vitesse de l'univers et son détermination par Bergson.
- Q003 run 1: Dans cette illusion, on peut se dédoubler. — Le contexte décrit une illusion dans laquelle on peut ressentir un sentiment d'étrangeté à soi-même, mais il ne mentionne pas explicitement le dédoublement.
- Q004 run 2: Il soutient que la vie ne se recompose pas, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une partie du contexte qui soutient que la vie ne se recompose pas, mais il n'y a pas de mention explicite de la vie se laissant regarder simplement.
- Q004 run 2: La vie ne se recompose pas, selon Bergson, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une mention de Bergson, mais il n'y a pas de mention explicite de la vie se recomposant ou non. Cependant, le contexte suggère que la vie peut être observée et comprise, ce qui est en accord avec l'idée que la vie se laisse regarder simplement. Cependant, il n'y a pas de mention explicite de Bergson qui ait affirmé cette idée, donc la déclaration ne peut pas être directement inférée à partir du contexte.
- Q004 run 3: Il soutient que la vie ne se recompose pas, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une partie du contexte qui soutient que la vie ne se recompose pas, mais il n'y a pas de mention explicite de la vie se laissant regarder simplement.
- Q004 run 3: La vie ne se recompose pas, selon Bergson, mais se laisse regarder simplement. — Le contexte discute de la nature de l'imagination poétique et de la façon dont les personnages créés par les poètes peuvent donner l'impression de la vie. Il y a une mention de Bergson, mais il n'y a pas de mention explicite de la vie se recomposant ou non. Cependant, le contexte suggère que la vie peut être observée et comprise, ce qui est en contradiction avec l'idée de la vie se recomposant. Cependant, il n'y a pas de preuve directe dans le contexte pour soutenir que Bergson ait affirmé que la vie ne se recompose pas.
- Q005 run 1: Dans le cas du tremblement de terre, l'individu personnifie le phénomène en une entité permanente et individuelle, considérant que le tremblement de terre est un être individualisé qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il personnifie le tremblement de terre en une entité individuelle, mais il ne considère pas que cela soit un être individualisé qui a pour unique fonction d'être tremblement de terre. En effet, il y a une différence entre personnifier un phénomène et considérer que ce phénomène est un être individualisé.
- Q005 run 2: Dans le cas du tremblement de terre, l'individu personnifie le phénomène en une entité permanente et individuelle, considérant que le tremblement de terre est un être individualisé qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il personnifie le tremblement de terre en une entité individuelle, mais il ne considère pas que cela soit un être individualisé qui a pour unique fonction d'être tremblement de terre. En effet, il y a une différence entre personnifier un phénomène et considérer que ce phénomène est un être individualisé.
- Q005 run 3: Dans le cas du tremblement de terre, l'individu personnifie le phénomène en une entité permanente et individuelle, considérant que le tremblement de terre est un être individualisé qui a pour unique fonction d'être tremblement de terre. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il personnifie le tremblement de terre en une entité individuelle, mais il ne considère pas que cela soit un être individualisé qui a pour unique fonction d'être tremblement de terre. En effet, il y a une différence entre personnifier un phénomène et considérer que ce phénomène est un être individualisé.
- Q006 run 1: Bergson reconstruit la pensée de Berkeley à la manière d'une recette de cuisine. — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson reconstruit sa pensée à la manière d'une recette de cuisine.
- Q006 run 2: Bergson reconstruit la pensée de Berkeley à la manière d'une recette de cuisine. — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson reconstruit sa pensée à la manière d'une recette de cuisine.
- Q006 run 3: Bergson reconstruit la pensée de Berkeley à la manière d'une recette de cuisine. — Le contexte décrit la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement que Bergson reconstruit sa pensée à la manière d'une recette de cuisine.
- Q007 run 1: En les mêmes termes, le mouvement et le changement viennent se surajouter, comme des accidents, à des choses qui par elles-mêmes ne se meuvent pas, et en elles-mêmes ne changent pas. — Le texte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la nature humaine et la société. Il y a une discussion sur la logique immanente à nos langues et comment elle nous conduit à voir l'immobilité et l'immutabilité comme des essences ou substances, en supports. Cependant, il n'y a pas de directe mention de mouvement et de changement comme des accidents de choses qui ne se meuvent pas et ne changent pas par elles-mêmes.
- Q007 run 1: Cette logique du langage conduit à des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage. Il est clair que le contexte soutient que la logique du langage peut conduire à des problèmes philosophiques, mais il ne fournit pas de preuve directe que ces problèmes seraient insolubles et posés à l'envers.
- Q007 run 1: Il s'agit pour l'esprit humain d'une libération. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage et la perception. Il n'y a pas de mention de libération de l'esprit humain.
- Q007 run 2: En les mêmes termes, le mouvement et le changement viennent se surajouter, comme des accidents, à des choses qui par elles-mêmes ne se meuvent pas et en elles-mêmes ne changent pas. — Le texte discute de la manière dont la perception et la pensée humaine sont influencées par la nature et la société, et comment elles ont été mises en place pour organiser le travail des hommes dans l'espace. Il y a une discussion sur la manière dont la nature a prédestiné l'homme à la vie sociale et à la perception de l'immobilité et de l'immutabilité comme essences ou substances, mais il n'y a pas de mention directe de la manière dont les choses se meuvent ou changent en eux-mêmes.
- Q007 run 2: Cette logique du langage conduit à des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage. Il est clair que le contexte soutient que la logique du langage peut conduire à des problèmes philosophiques, mais il ne fait pas mention de problèmes insolubles ou posés à l'envers.
- Q007 run 2: Il s'agit pour l'esprit humain d'une libération. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage et la perception. Il n'y a pas de mention de libération de l'esprit humain.
- Q007 run 3: En les mêmes termes, le mouvement et le changement viennent se surajouter, comme des accidents, à des choses qui par elles-mêmes ne se meuvent pas, et en elles-mêmes ne changent pas. — Le texte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la nature humaine et la société. Il y a une discussion sur la logique immanente à nos langues et comment elle nous conduit à voir l'immobilité et l'immutabilité comme des essences ou substances. Cependant, il n'y a pas de mention directe de la relation entre les choses qui ne se meuvent pas et le mouvement et le changement.
- Q007 run 3: Cette logique du langage conduit à des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage. Il est clair que le contexte soutient que la logique du langage peut conduire à des problèmes philosophiques, mais il ne fait pas mention de problèmes insolubles ou posés à l'envers.
- Q007 run 3: Il s'agit pour l'esprit humain d'une libération. — Le contexte discute de la nature de la philosophie et de la manière dont elle est influencée par le langage et la perception. Il n'y a pas de mention de libération pour l'esprit humain.
- Q009 run 1: Il y a une continuité entre les espèces, et la vie de l'homme est considérée comme un sous-ensemble de la vie plus large. — Le contexte discute de la relation entre la vie de l'esprit et celle du corps, et de la genèse des espèces par voie de transformation graduelle. Il y a une mention de l'homme comme étant une partie de la nature, mais il n'y a pas de mention explicite d'une continuité entre les espèces ou de la vie de l'homme comme un sous-ensemble de la vie plus large.
- Q009 run 2: Il y a une continuité entre les espèces, et la vie de l'homme est considérée comme un sous-ensemble de la vie plus large. — Le contexte discute de la relation entre la vie de l'esprit et celle du corps, et de la genèse des espèces par voie de transformation graduelle. Il y a une mention de l'homme comme étant une partie de la nature, mais il n'y a pas de mention explicite d'une continuité entre les espèces ou de la vie de l'homme comme un sous-ensemble de la vie plus large.
- Q009 run 3: Il y a une continuité entre les espèces, et la vie de l'homme est considérée comme un sous-ensemble de la vie plus large. — Le contexte discute de la relation entre la vie de l'esprit et celle du corps, et de la genèse des espèces par voie de transformation graduelle. Il y a une mention de l'homme comme étant une partie de la nature, mais il n'y a pas de mention explicite d'une continuité entre les espèces ou de la vie de l'homme comme un sous-ensemble de la vie plus large.
- Q012 run 1: Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, chacune de son côté cherchant fortune dans le monde. — Le contexte décrit l'évolution générale de la vie, y compris la dichotomie des tendances, mais il ne précise pas que ces tendances se développent le plus souvent dans des espèces distinctes.
- Q012 run 2: Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, chacune de son côté cherchant fortune dans le monde. — Le contexte décrit l'évolution générale de la vie, y compris la dichotomie des tendances, mais il ne précise pas que ces tendances se développent le plus souvent dans des espèces distinctes.
- Q012 run 3: Dans l'évolution générale de la vie, les tendances ainsi créées par voie de dichotomie se développent le plus souvent dans des espèces distinctes, chacune de son côté cherchant fortune dans le monde. — Le contexte décrit l'évolution générale de la vie, y compris la dichotomie des tendances, mais il ne précise pas que ces tendances se développent le plus souvent dans des espèces distinctes.

## Polarity review (negated segments the judge accepted)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness score says nothing about polarity. Read the segments below against their chunks.

- Q001 run 1 (pas): Selon lui, chaque état d'âme, comme la perception visuelle d'un objet extérieur immobile, ne reste pas identique pendant tout le temps qu'il se produit, mais change continuellement, de manière à former une boule de neige avec lui-même.
- Q001 run 1 (pas): Cette image met en évidence la nature dynamique et évolutive de l'état d'âme, qui ne se réside pas dans un état fixe, mais dans un processus de changement.
- Q001 run 2 (pas): Selon lui, chaque état d'âme, comme la perception visuelle d'un objet extérieur immobile, ne reste pas identique pendant tout le temps qu'il se produit, mais change continuellement, de manière à former une boule de neige avec lui-même.
- Q001 run 2 (pas): Cette image met en évidence la nature dynamique et évolutive de l'état d'âme, qui ne se réside pas dans un état fixe, mais dans un processus de changement.
- Q001 run 3 (pas): Selon lui, chaque état d'âme, comme la perception visuelle d'un objet extérieur immobile, ne reste pas identique pendant tout le temps qu'il se produit, mais change continuellement, de manière à former une boule de neige avec lui-même.
- Q001 run 3 (pas): Cette image met en évidence la nature dynamique et évolutive de l'état d'âme, qui ne se réside pas dans un état fixe, mais dans un processus de changement.
- Q003 run 1 (pas): Cette dépersonnalisation est liée à la fausse reconnaissance, mais elle n'est pas indissolublement liée à elle.
- Q003 run 2 (pas): Cette dépersonnalisation est liée à la fausse reconnaissance, mais elle n'est pas indissolublement liée à elle.
- Q003 run 3 (pas): Cette dépersonnalisation est liée à la fausse reconnaissance, mais elle n'est pas indissolublement liée à elle.
- Q004 run 1 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en affirmant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 1 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q004 run 1 (pas): Il soutient que la vie ne se recompose pas, mais se laisse regarder simplement, et que l'imagination poétique permet au poète de saisir le virtuel dans le réel et de reprendre, pour en faire une œuvre complète, ce que la nature laissa en lui à l'état d'ébauche ou de simple projet. [1900_R_c170]
- Q004 run 2 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en affirmant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 2 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q004 run 3 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en affirmant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 3 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q007 run 1 (pas): Il s'agit de problèmes qui ne sont pas fondés sur la nature des choses, mais sur des habitudes contractées dans l'action.
- Q007 run 1 (non): Bergson soutient que l'esprit humain doit être libéré de cette logique du langage pour pouvoir voir dans le changement et le mouvement des réalités, et non plus des accidents.
- Q007 run 2 (pas): Il s'agit de problèmes qui ne sont pas fondés sur la nature des choses, mais sur des habitudes contractées dans l'action.
- Q007 run 2 (non): Bergson soutient que l'esprit humain doit être libéré de cette logique du langage pour pouvoir voir dans le changement et le mouvement des réalités, et non plus des accidents.
- Q007 run 3 (pas): Il s'agit de problèmes qui ne sont pas fondés sur la nature des choses, mais sur des habitudes contractées dans l'action.
- Q007 run 3 (non): Bergson soutient que l'esprit humain doit être libéré de cette logique du langage pour pouvoir voir dans le changement et le mouvement des réalités, et non plus des accidents.
- Q008 run 1 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 1 (pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que l'une est l'équivalent de l'autre ou que chaque détail de l'une correspond à un détail de l'autre.
- Q008 run 1 (ni, nullement): Il soutient que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 run 1 (pas): La thèse qu'il explique est donc que la solidarité entre la conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux, mais plutôt à l'existence d'une certaine relation entre les deux.
- Q008 run 2 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 2 (pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que l'une est l'équivalent de l'autre ou que chaque détail de l'une correspond à un détail de l'autre.
- Q008 run 2 (ni, nullement): Il soutient que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 run 2 (pas): La thèse qu'il explique est donc que la solidarité entre la conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux, mais plutôt à l'existence d'une certaine relation entre les deux.
- Q008 run 3 (pas): Bergson explique à travers l'image du manteau accroché à un clou que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique.
- Q008 run 3 (pas): Il utilise cette image pour souligner que la solidarité entre deux choses ne signifie pas que l'une est l'équivalent de l'autre ou que chaque détail de l'une correspond à un détail de l'autre.
- Q008 run 3 (ni, nullement): Il soutient que la conscience est accrochée au cerveau, mais il ne résulte nullement de là que le cerveau dessine tout le détail de la conscience, ni que la conscience soit une fonction du cerveau.
- Q008 run 3 (pas): La thèse qu'il explique est donc que la solidarité entre la conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux, mais plutôt à l'existence d'une certaine relation entre les deux.
- Q009 run 1 (sans): Enfin, Bergson suggère que la conscience est essentiellement libre, mais qu'elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 2 (sans): Enfin, Bergson suggère que la conscience est essentiellement libre, mais qu'elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 3 (sans): Enfin, Bergson suggère que la conscience est essentiellement libre, mais qu'elle ne peut traverser la matière sans s'adapter à elle.
- Q011 run 1 (pas): Cependant, il ne croit pas à la fatalité historique et affirme que les volontés suffisamment tendues peuvent briser les obstacles si elles s'y prennent à temps.
- Q011 run 1 (sans): Il conclut en disant que la tendance simple aurait peut-être mieux fait de croître sans se dédoubler, mais que cela aurait empêché le maximum de création en quantité et en qualité.
- Q011 run 2 (pas): Cependant, il ne croit pas à la fatalité historique et affirme que les volontés suffisamment tendues peuvent briser les obstacles si elles s'y prennent à temps.
- Q011 run 2 (sans): Il conclut en disant que la tendance simple aurait peut-être mieux fait de croître sans se dédoubler, mais que cela aurait empêché le maximum de création en quantité et en qualité.
- Q011 run 3 (pas): Cependant, il ne croit pas à la fatalité historique et affirme que les volontés suffisamment tendues peuvent briser les obstacles si elles s'y prennent à temps.
- Q011 run 3 (sans): Il conclut en disant que la tendance simple aurait peut-être mieux fait de croître sans se dédoubler, mais que cela aurait empêché le maximum de création en quantité et en qualité.

## Per item

| id | origin | label | category | scores per run | mean | nan runs | claims | unsupported | unevaluated |
|---|---|---|---|---|---|---|---|---|---|
| Q001 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 12 | 0 | 0 |
| Q002 | gold | faithful | définitionnel | 0.857 / 0.667 / 0.667 | 0.730 | 0/3 | 19 | 5 | 0 |
| Q003 | gold | faithful | factuel | 0.833 / 1.000 / 1.000 | 0.944 | 0/3 | 18 | 1 | 0 |
| Q004 | gold | faithful | factuel | 1.000 / 0.714 / 0.714 | 0.810 | 0/3 | 17 | 4 | 0 |
| Q005 | gold | faithful | définitionnel | 0.667 / 0.750 / 0.750 | 0.722 | 0/3 | 12 | 3 | 1 |
| Q006 | gold | faithful | factuel | 0.750 / 0.750 / 0.750 | 0.750 | 0/3 | 12 | 3 | 0 |
| Q007 | gold | faithful | définitionnel | 0.571 / 0.571 / 0.571 | 0.571 | 0/3 | 21 | 9 | 0 |
| Q008 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 12 | 0 | 0 |
| Q009 | gold | faithful | définitionnel | 0.833 / 0.833 / 0.833 | 0.833 | 0/3 | 18 | 3 | 0 |
| Q010 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 18 | 0 | 0 |
| Q011 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 24 | 0 | 0 |
| Q012 | gold | faithful | définitionnel | 0.909 / 0.909 / 0.909 | 0.909 | 0/3 | 33 | 3 | 0 |

## Failures (recorded as nan, never dropped)

None.
