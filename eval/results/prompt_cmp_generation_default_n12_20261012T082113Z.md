# Prompt comparison run: generation mode, default

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **Created**: 2026-10-12T08:21:13Z
- **Command**: `python -m eval.scripts.run_prompt_comparison --mode generation --repeat 3`
- **Source**: default `default`
- **Overridden prompts**: none (defaults)
- **Models**: judge `ollama_chat/mistral`, generation `ollama_chat/mistral`; temperature {'judge': 0.0, 'generation': 0.0}
- **Retrieval**: bypassed: gold chunks (paragraph_ids resolved via src.paragraph_chunk_map, read from Qdrant)
- **Items**: 12 {'gold': 12}; repeat 3
- **Git**: `28f1e0db29ecf84138f86f53956c45ed235c84c0` (exp/generation-baseline), dirty: False
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

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

## Gate (no fabricated work title, no title/year mismatch, in any run)

**PASSED** over 36/36 generated answers

## Faithfulness by the frozen judge (higher = fewer unsupported claims)

Mean 0.836 over 12 items; nan per run: run 1: 0/12, run 2: 0/12, run 3: 0/12; runs with unevaluated claims (left out of their score): run 1: 0/12, run 2: 0/12, run 3: 0/12. Judge's accepted gate misses: Q008-p1-negation.

## Substance (beside the axes: an answer that says less has less to get wrong)

| run | claims/answer | chars/answer | citations/answer | answers with a citation |
|---|---|---|---|---|
| 1 | 7.167 | 884.167 | 0.500 | 4/12 |
| 2 | 7.250 | 885.417 | 0.583 | 5/12 |
| 3 | 7.250 | 885.417 | 0.583 | 5/12 |

Citations to a chunk the answer wasn't given:
- none

## Stability over repeats

Mean per-item score range 0.035 (max 0.222); verdict flips 1 of 87 statements seen in 2+ runs; 18 statements extracted in one run only; answer identical in every repeat on 10 items, varied on Q005, Q007.

## Unsupported claims (with the judge's reason)

- Q001 run 1: La durée est accumulée dans chaque état d'âme. — Le contexte indique que l'état d'âme est en constante évolution et que sa durée coule continuellement. Il est donc possible de déduire que la durée n'est pas accumulée dans chaque état d'âme.
- Q001 run 2: La durée est accumulée dans chaque état d'âme. — Le contexte indique que l'état d'âme est en constante évolution et que sa durée coule continuellement. Il est donc possible de déduire que la durée n'est pas accumulée dans chaque état d'âme.
- Q001 run 3: La durée est accumulée dans chaque état d'âme. — Le contexte indique que l'état d'âme change continuellement et que sa durée coule, ce qui implique que la durée n'est pas accumulée dans chaque état d'âme.
- Q003 run 1: Cette illusion se produit lorsque l'on a une fausse reconnaissance. — Le contexte décrit l'illusion sans mentionner explicitement une fausse reconnaissance, mais il décrit des symptômes qui peuvent être associés à une fausse reconnaissance. Cependant, il n'y a pas de preuve directe que l'illusion décrite est liée à une fausse reconnaissance.
- Q005 run 1: Selon Bergson, la perception d'un tremblement de terre est décrite pour expliquer la manière dont l'intelligence humaine réagit à des événements graves et inattendus, tels que des catastrophes naturelles. — Le contexte décrit la perception de William James d'un tremblement de terre et comment il l'a interprété comme une entité individuelle, mais il n'y a pas de mention de Bergson expliquant la perception de tremblement de terre pour expliquer la réaction de l'intelligence humaine à des événements graves.
- Q005 run 1: Bergson souligne que, lorsqu'un tel événement survient, l'intelligence humaine peut ressentir une crainte face à l'imprévisible et à la puissance de la nature. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie, où il ressentit une allégresse et une admiration face à l'événement, plutôt que crainte. Il personnifia le tremblement de terre en une entité permanente et individuelle, mais il ne décrit pas une crainte face à l'imprévisible et à la puissance de la nature.
- Q005 run 2: Selon Bergson, la perception d'un tremblement de terre est décrite comme une réaction défensive de la nature. — Le contexte décrit la perception de William James d'un tremblement de terre et sa réaction personnelle à cet événement, mais il n'y a pas de mention de Bergson ou de ses idées.
- Q005 run 2: Il considérait que l'intention et l'animation du tremblement de terre semblaient appartenir à un agent vivant. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il y décrit comment il a personnifié le tremblement de terre en une entité individuelle, mais il ne décrit pas explicitement qu'il considère que l'intention et l'animation du tremblement de terre semblaient appartenir à un agent vivant.
- Q005 run 2: En résumé, Bergson décrit la perception d'un tremblement de terre comme une réaction défensive de la nature contre la crainte. — Le contexte décrit la perception de William James d'un tremblement de terre et sa personnification de l'événement en une entité individuelle. Il n'y a pas de mention de Bergson décrivant la perception d'un tremblement de terre comme une réaction défensive de la nature contre la crainte.
- Q005 run 2: Le tremblement de terre est traité comme un être malicieux ou méchant. — Le contexte décrit comment les personnes ont interprété le tremblement de terre comme un événement, mais il n'y a pas de mention explicite de traitement du tremblement de terre comme un être malicieux ou méchant.
- Q005 run 2: Mais il est rapproché de nous avec quelque chose de sociable et d'humain. — Le contexte décrit la réaction de l'homme face à des événements naturels tels que tremblements de terre, inondations, ouragans, etc. Il décrit comment l'homme personnifie ces événements en des entités qui ne sont pas des personnalités complètes mais ont des intentions. Le contexte ne mentionne pas explicitement que ces entités sont sociable ou humaines.
- Q005 run 3: Selon Bergson, la perception d'un tremblement de terre est décrite comme une réaction défensive de la nature. — Le contexte décrit la perception de William James d'un tremblement de terre et sa réaction personnelle à cet événement, mais il n'y a pas de mention de Bergson ou de ses idées.
- Q005 run 3: Il considérait que l'intention et l'animation du tremblement de terre semblaient appartenir à un agent vivant. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie. Il y décrit comment il a personnifié le tremblement de terre en une entité individuelle, mais il ne décrit pas explicitement qu'il considérait que l'intention et l'animation du tremblement de terre semblaient appartenir à un agent vivant.
- Q005 run 3: En résumé, Bergson décrit la perception d'un tremblement de terre comme une réaction défensive de la nature contre la crainte. — Le contexte décrit la perception de William James d'un tremblement de terre et sa personnification de l'événement en une entité individuelle. Il n'y a pas de mention de Bergson décrivant la perception d'un tremblement de terre comme une réaction défensive de la nature contre la crainte.
- Q005 run 3: Le tremblement de terre est traité comme un être malicieux ou méchant. — Le contexte décrit comment les personnes ont interprété le tremblement de terre comme un événement, mais il n'y a pas de mention explicite de traitement du tremblement de terre comme un être malicieux ou méchant.
- Q005 run 3: Mais il est rapproché de nous avec quelque chose de sociable et d'humain. — Le contexte décrit la réaction de l'homme face à des événements naturels tels que tremblements de terre, inondations, ouragans, etc. Il décrit comment l'homme personnifie ces événements en des entités qui ne sont pas des personnalités complètes mais ont des intentions. Le contexte ne mentionne pas explicitement que ces entités sont sociable ou humaines.
- Q006 run 1: Bergson reconstitue la pensée d'un philosophe, en particulier de George Berkeley. — Le contexte discute la philosophie de Berkeley et mentionne des philosophes anciens et modernes qui ont des éléments similaires à sa philosophie, mais il ne mentionne pas explicitement Bergson et sa reconstitution de la pensée de Berkeley.
- Q006 run 2: Bergson reconstitue la pensée d'un philosophe, en particulier de George Berkeley. — Le contexte discute la philosophie de Berkeley et mentionne des philosophes anciens et modernes qui ont des éléments similaires à sa philosophie, mais il ne mentionne pas explicitement Bergson et sa reconstitution de la pensée de Berkeley.
- Q006 run 3: Bergson reconstitue la pensée d'un philosophe, en particulier de George Berkeley. — Le contexte discute la philosophie de Berkeley et mentionne des philosophes anciens et modernes qui ont des éléments similaires à sa philosophie, mais il ne mentionne pas explicitement Bergson et sa reconstitution de la pensée de Berkeley.
- Q007 run 1: En les mêmes termes, le mouvement et le changement sont considérés comme des accidents. — Le contexte discute de la manière dont la perception, la pensée, le langage et l'action humaine sont organisés pour voir dans l'immobilité et l'immutabilité les essences ou substances, en supports, et en considérant le changement et le mouvement comme des accidents. Il n'y a donc pas de mention directe de l'affirmation.
- Q007 run 1: Cette logique implique que l'intelligence a pour essence de juger. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. Cette logique ne fait pas explicitement mention de l'essence de l'intelligence étant de juger.
- Q007 run 1: Le sujet, par cela seul qu'on le nomme, est défini comme invariable. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne fait pas directement référence à la définition d'un sujet comme invariable.
- Q007 run 1: La variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. — Le contexte discute sur la nature de la perception et de la pensée, et l'auteur critique la logique immanente à nos langues qui considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. L'auteur propose que la perception, la pensée, le langage, toutes les activités individuelles ou sociales de l'esprit conspirent à nous mettre en présence d'objets que nous pouvons tenir pour invariables et immobiles pendant que nous les considérons. Ainsi, il ne peut pas être directement déduit que la variation résidera dans la diversité des états qu'on affirmera de lui tour à tour.
- Q007 run 1: Bergson soutient que pour résoudre ces problèmes, il faut renverser le sens de l'opération habituelle de la pensée. — Le texte discute à propos de la philosophie et de la manière dont elle est organisée pour la vie sociale, mais il ne mentionne pas explicitement Bergson ou sa position sur la nécessité de renverser le sens de l'opération habituelle de la pensée.
- Q007 run 1: Il faut partir du changement et du mouvement, envisagés comme la réalité même. — Le contexte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la nature et le langage. Il ne fait pas directement mention de la nécessité de partir du changement et du mouvement comme la réalité même.
- Q007 run 1: Ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant. — Le contexte discute de la nature de la perception et de la pensée, et l'auteur suggère que l'homme a tendance à voir les objets comme invariables pendant qu'il les considère, ce qui est en contradiction avec l'idée de ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant.
- Q007 run 2: En les mêmes termes, le mouvement et le changement sont considérés comme des accidents. — Le contexte discute de la manière dont la perception, la pensée, le langage et l'action humaine sont organisés pour voir dans l'immobilité et l'immutabilité les essences ou substances, en supports, et en considérant le changement et le mouvement comme des accidents. Il n'y a donc pas de mention directe de l'affirmation.
- Q007 run 2: Cette logique implique que l'intelligence a pour essence de juger. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. Cette logique ne fait pas explicitement mention de l'essence de l'intelligence étant de juger.
- Q007 run 2: Le sujet, par cela seul qu'on le nomme, est défini comme invariable. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne fait pas directement référence à la définition d'un sujet comme invariable.
- Q007 run 2: La variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. — Le contexte discute sur la nature de la perception et de la pensée, et l'auteur critique la logique immanente à nos langues qui considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. Il y a donc un lien entre la variation et les états, mais il n'est pas explicitement affirmé que la variation réside dans la diversité des états qu'on affirmera de lui tour à tour.
- Q007 run 2: La solution consiste à renverser le sens de l'opération habituelle de la pensée. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne propose pas explicitement une solution consistant à renverser le sens de l'opération habituelle de la pensée.
- Q007 run 2: À partir du changement et du mouvement, envisagés comme la réalité même. — Le contexte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la nature et le langage. Il ne fait pas directement référence à la réalité comme étant le changement et le mouvement.
- Q007 run 2: À ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant. — Le contexte discute sur la nature de la perception et de la pensée, et l'auteur y fait référence à la manière dont l'esprit humain voit les choses comme invariables pendant qu'on les considère, ce qui est en contradiction avec l'idée de voir les arrêts ou les états comme des instantanés pris sur du mouvant.
- Q007 run 3: En les mêmes termes, le mouvement et le changement sont considérés comme des accidents. — Le contexte discute de la manière dont la perception, la pensée, le langage et l'action humaine sont organisés pour voir dans l'immobilité et l'immutabilité les essences ou substances, en supports, et en considérant le changement et le mouvement comme des accidents. Il n'y a donc pas de mention directe de l'affirmation que le mouvement et le changement sont considérés comme des accidents.
- Q007 run 3: Cette logique implique que l'intelligence a pour essence de juger. — Le contexte discute de la logique immanente à nos langues, qui est celle d'Aristote, et qui est basée sur l'attribution d'un prédicat à un sujet. Cette logique ne fait pas explicitement mention de l'essence de l'intelligence étant de juger.
- Q007 run 3: Le sujet, par cela seul qu'on le nomme, est défini comme invariable. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne fait pas directement référence à la définition d'un sujet comme invariable.
- Q007 run 3: La variation résidera dans la diversité des états qu'on affirmera de lui tour à tour. — Le contexte discute sur la nature de la perception et de la pensée, et l'auteur critique la logique immanente à nos langues qui considère l'immobilité et l'immutabilité comme de droit, et le mouvement et le changement comme des accidents. L'auteur propose que la perception, la pensée, le langage, toutes les activités individuelles ou sociales de l'esprit conspirent à nous mettre en présence d'objets que nous pouvons tenir pour invariables et immobiles pendant que nous les considérons. Ainsi, il ne peut pas être directement déduit que la variation résidera dans la diversité des états qu'on affirmera de lui tour à tour.
- Q007 run 3: En procédant ainsi par apposition d'un prédicat à un sujet, du stable au stable, nous suivons la pente de notre intelligence. — Le contexte discute sur la nature de la perception, la pensée et le langage, et comment ils sont influencés par la nature. Il explique comment la perception, la pensée et le langage sont conçus pour organiser le travail des hommes dans l'espace, et comment ils sont d'essence intellectuelle. Le contexte ne discute pas explicitement de la manière dont l'intelligence suit une pente en apposant un prédicat à un sujet.
- Q007 run 3: La solution consiste à renverser le sens de l'opération habituelle de la pensée. — Le contexte discute de la nature de la perception, de la pensée et du langage, et de leur influence sur la philosophie. Il ne propose pas explicitement une solution consistant à renverser le sens de l'opération habituelle de la pensée.
- Q007 run 3: À partir du changement et du mouvement, envisagés comme la réalité même. — Le contexte discute de la nature de la perception et de la pensée, et de la façon dont elles sont influencées par la langue et les habitudes. Il ne fait pas directement référence à la réalité comme étant le changement et le mouvement.
- Q007 run 3: À ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant. — Le contexte discute sur la nature de la perception et de la pensée, et l'auteur y fait référence à la manière dont l'esprit humain voit les choses comme invariables pendant qu'on les considère, ce qui est en contradiction avec l'idée de voir les arrêts ou les états comme des instantanés pris sur du mouvant.
- Q010 run 1: Les forces éruptives, selon Bergson, ont suscité le développement rationnel de la philosophie grecque. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne mentionne pas explicitement les forces éruptives de Bergson comme étant à l'origine du développement rationnel de la philosophie grecque.
- Q010 run 1: Elles ont conduit la philosophie grecque au-delà de la raison. — Le contexte décrit l'évolution de la pensée humaine, qui fut purement rationnelle et aboutit à un épanouissement de la dialectique en mystique. Cependant, il est possible que l'on puisse interpréter le développement de la pensée grecque comme étant l'œuvre de la seule raison, mais avec des efforts pour aller chercher une vision, un contact, la révélation d'une réalité transcendante. Cependant, le contexte ne suggère pas explicitement que la philosophie grecque a été conduite au-delà de la raison, mais plutôt que la dialectique a évolué en mystique.
- Q010 run 2: Les forces éruptives, selon Bergson, ont suscité le développement rationnel de la philosophie grecque. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne mentionne pas explicitement les forces éruptives de Bergson comme étant à l'origine du développement rationnel de la philosophie grecque.
- Q010 run 2: Elles ont conduit la philosophie grecque au-delà de la raison. — Le contexte décrit l'évolution de la pensée humaine, qui fut purement rationnelle et aboutit à un épanouissement de la dialectique en mystique. Cependant, il est possible que l'on puisse interpréter le développement de la pensée grecque comme étant l'œuvre de la seule raison, mais avec des efforts pour aller chercher une vision, un contact, la révélation d'une réalité transcendante. Cependant, le contexte ne suggère pas explicitement que la philosophie grecque a été conduite au-delà de la raison, mais plutôt que la dialectique a évolué en mystique.
- Q010 run 3: Les forces éruptives, selon Bergson, ont suscité le développement rationnel de la philosophie grecque. — Le contexte discute de l'évolution de la pensée humaine et de la philosophie grecque, mais il ne mentionne pas explicitement les forces éruptives de Bergson comme étant à l'origine du développement rationnel de la philosophie grecque.
- Q010 run 3: Elles ont conduit la philosophie grecque au-delà de la raison. — Le contexte décrit l'évolution de la pensée humaine, qui fut purement rationnelle et aboutit à un épanouissement de la dialectique en mystique. Cependant, il est possible que l'on puisse interpréter le développement de la pensée grecque comme étant l'œuvre de la seule raison, mais avec des efforts pour aller chercher une vision, un contact, la révélation d'une réalité transcendante. Cependant, le contexte ne suggère pas explicitement que la philosophie grecque a été conduite au-delà de la raison, mais plutôt que la dialectique a évolué en mystique.
- Q011 run 1: Henri Bergson ne considère pas les oscillations comme une fatalité historique. — Le contexte ne mentionne pas explicitement les opinions de Henri Bergson sur les oscillations comme une fatalité historique. Il est seulement écrit qu'il y a des oscillations dans l'histoire, mais pas qu'il les considère comme une fatalité.
- Q011 run 2: Henri Bergson ne considère pas les oscillations comme une fatalité historique. — Le contexte ne mentionne pas explicitement les opinions de Henri Bergson sur les oscillations comme une fatalité historique. Il est seulement écrit qu'il y a des oscillations dans l'histoire, mais pas qu'il les considère comme une fatalité.
- Q011 run 3: Henri Bergson ne considère pas les oscillations comme une fatalité historique. — Le contexte ne mentionne pas explicitement les opinions de Henri Bergson sur les oscillations comme une fatalité historique. Il est seulement écrit qu'il y a des oscillations dans l'histoire, mais pas de commentaires sur leur nature ou leur origine.
- Q012 run 1: Cette loi est expliquée comme résultant du fait que la tendance vitale est la poussée d'une multiplicité indistincte. — Le contexte explique la loi de dichotomie comme résultant de la dissociation des tendances, mais il ne mentionne pas explicitement que la tendance vitale est la poussée d'une multiplicité indistincte.
- Q012 run 2: Cette loi est expliquée comme résultant du fait que la tendance vitale est la poussée d'une multiplicité indistincte. — Le contexte explique la loi de dichotomie comme résultant de la dissociation de tendances, mais il ne mentionne pas explicitement que la tendance vitale est la poussée d'une multiplicité indistincte.
- Q012 run 3: Cette loi est expliquée comme résultant du fait que la tendance vitale est la poussée d'une multiplicité indistincte. — Le contexte explique la loi de dichotomie comme résultant de la dissociation des tendances, mais il ne mentionne pas explicitement que la tendance vitale est la poussée d'une multiplicité indistincte.

## Polarity review (negated segments the judge accepted)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness score says nothing about polarity. Read the segments below against their chunks.

- Q001 run 1 (pas): Cette image met en évidence la nature dynamique et incessante du changement, qui ne se limite pas à des changements brusques ou évidents, mais se produit également de manière continue et subtile.
- Q001 run 2 (pas): Cette image met en évidence la nature dynamique et incessante du changement, qui ne se limite pas à des changements brusques ou évidents, mais se produit également de manière continue et subtile.
- Q001 run 3 (pas): Cette image met en évidence la nature dynamique et incessante du changement, qui ne se limite pas à des changements brusques ou évidents, mais se produit également de manière continue et subtile.
- Q002 run 1 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas seulement une abstraction, une relation ou un nombre pour la science physique, mais qu'il est un absolu pour la conscience humaine.
- Q002 run 1 (sans): Il suggère que cette durée psychologique est liée à la durée réelle de l'univers, qui est créée sans cesse et ne peut être donnée d'un seul coup, comme sur une bande du cinématographe.
- Q002 run 1 (sans): Il affirme que l'univers lui-même, plutôt que d'être un système entièrement calculable, est entrelacé d'êtres organisés et prend sans cesse des formes nouvelles et originales, comme nos états de conscience.
- Q002 run 2 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas seulement une abstraction, une relation ou un nombre pour la science physique, mais qu'il est un absolu pour la conscience humaine.
- Q002 run 2 (sans): Il suggère que cette durée psychologique est liée à la durée réelle de l'univers, qui est créée sans cesse et ne peut être donnée d'un seul coup, comme sur une bande du cinématographe.
- Q002 run 2 (sans): Il affirme que l'univers lui-même, plutôt que d'être un système entièrement calculable, est entrelacé d'êtres organisés et prend sans cesse des formes nouvelles et originales, comme nos états de conscience.
- Q002 run 3 (pas): Dans les extraits fournis, Henri Bergson explique à travers l'image de la fonte d'un morceau de sucre dans un verre d'eau que le temps n'est pas seulement une abstraction, une relation ou un nombre pour la science physique, mais qu'il est un absolu pour la conscience humaine.
- Q002 run 3 (sans): Il suggère que cette durée psychologique est liée à la durée réelle de l'univers, qui est créée sans cesse et ne peut être donnée d'un seul coup, comme sur une bande du cinématographe.
- Q002 run 3 (sans): Il affirme que l'univers lui-même, plutôt que d'être un système entièrement calculable, est entrelacé d'êtres organisés et prend sans cesse des formes nouvelles et originales, comme nos états de conscience.
- Q004 run 1 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 1 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q004 run 2 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 2 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q004 run 3 (plus): Bergson établit un rapport entre l'imagination poétique et la réalité en considérant que l'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 run 3 (pas, plus): Selon lui, les personnages que crée le poète ne sont pas des compositions faites à partir de morceaux empruntés autour de lui, mais plutôt une vision plus profonde de la réalité.
- Q005 run 1 (pas): Cela permet de créer des entités qui n'ont pas besoin d'être des personnalités complètes, mais qui ont des intentions ou qui coïncident avec elles.
- Q005 run 1 (sans): Cette entité participe de la personnalité sans être une personne complète, et elle permet de dissiper la crainte ou de l'empêcher de naître.
- Q006 run 1 (pas): Il souligne que la philosophie de Berkeley ressemble suffisamment à celle de Berkeley, de loin, mais ne l'identifie pas complètement. [1934_PM_c96]
- Q006 run 2 (pas): Il souligne que la philosophie de Berkeley ressemble suffisamment à celle de Berkeley, de loin, mais ne l'identifie pas complètement. [1934_PM_c96]
- Q006 run 3 (pas): Il souligne que la philosophie de Berkeley ressemble suffisamment à celle de Berkeley, de loin, mais ne l'identifie pas complètement. [1934_PM_c96]
- Q007 run 1 (pas): Cependant, cette logique implique des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers, car ils ne correspondent pas à la réalité.
- Q007 run 2 (pas): Cependant, cette logique implique des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers, car ils ne correspondent pas à la réalité.
- Q007 run 3 (pas): Cependant, cette logique implique des problèmes philosophiques qui sont et qui resteront insolubles, étant posés à l'envers, car ils ne correspondent pas à la réalité.
- Q008 run 1 (pas): Dans les extraits fournis, Henri Bergson explique que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique (1896_MM_c7).
- Q008 run 1 (ni, pas): Il utilise l'image du manteau accroché à un clou pour illustrer cette idée, en soulignant que la solidarité entre les deux ne signifie pas que chaque détail du cerveau correspond à un détail de la conscience, ni que la conscience soit une fonction du cerveau (1919_ES_c32).
- Q008 run 1 (pas): Bergson soutient que l'observation et l'expérience ne permettent d'affirmer que l'existence d'une certaine relation entre le cerveau et la conscience, mais pas que le cerveau dessine tout le détail de la conscience ou que la conscience soit l'équivalent du cerveau.
- Q008 run 2 (pas): Dans les extraits fournis, Henri Bergson explique que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique (1896_MM_c7).
- Q008 run 2 (ni, pas): Il utilise l'image du manteau accroché à un clou pour illustrer cette idée, en soulignant que la solidarité entre les deux ne signifie pas que chaque détail du cerveau correspond à un détail de la conscience, ni que la conscience soit une fonction du cerveau (1919_ES_c32).
- Q008 run 2 (pas): Bergson soutient que l'observation et l'expérience ne permettent d'affirmer que l'existence d'une certaine relation entre le cerveau et la conscience, mais pas que le cerveau dessine tout le détail de la conscience ou que la conscience soit l'équivalent du cerveau.
- Q008 run 3 (pas): Dans les extraits fournis, Henri Bergson explique que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure à un parallélisme entre les deux séries psychologique et physiologique (1896_MM_c7).
- Q008 run 3 (ni, pas): Il utilise l'image du manteau accroché à un clou pour illustrer cette idée, en soulignant que la solidarité entre les deux ne signifie pas que chaque détail du cerveau correspond à un détail de la conscience, ni que la conscience soit une fonction du cerveau (1919_ES_c32).
- Q008 run 3 (pas): Bergson soutient que l'observation et l'expérience ne permettent d'affirmer que l'existence d'une certaine relation entre le cerveau et la conscience, mais pas que le cerveau dessine tout le détail de la conscience ou que la conscience soit l'équivalent du cerveau.
- Q009 run 1 (pas, sans): Selon lui, cette chevauchée est la conscience, qui enveloppe des virtualités sans nombre qui se compénètrent, et qui ne conviennent pas à la matière inerte.
- Q009 run 1 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 1 (sans): La conscience est essentiellement libre, mais elle ne peut traverser la matière sans s'adapter à elle, ce qui est ce qu'on appelle l'intellectualité.
- Q009 run 2 (pas, sans): Selon lui, cette chevauchée est la conscience, qui enveloppe des virtualités sans nombre qui se compénètrent, et qui ne conviennent pas à la matière inerte.
- Q009 run 2 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 2 (sans): La conscience est essentiellement libre, mais elle ne peut traverser la matière sans s'adapter à elle, ce qui est ce qu'on appelle l'intellectualité.
- Q009 run 3 (pas, sans): Selon lui, cette chevauchée est la conscience, qui enveloppe des virtualités sans nombre qui se compénètrent, et qui ne conviennent pas à la matière inerte.
- Q009 run 3 (sans): La conscience est distincte de l'organisme qu'elle anime, mais elle ne peut traverser la matière sans s'adapter à elle.
- Q009 run 3 (sans): La conscience est essentiellement libre, mais elle ne peut traverser la matière sans s'adapter à elle, ce qui est ce qu'on appelle l'intellectualité.

## Per item

| id | origin | label | category | scores per run | mean | nan runs | claims | unsupported | unevaluated |
|---|---|---|---|---|---|---|---|---|---|
| Q001 | gold | faithful | définitionnel | 0.875 / 0.875 / 0.875 | 0.875 | 0/3 | 24 | 3 | 0 |
| Q002 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 12 | 0 | 0 |
| Q003 | gold | faithful | factuel | 0.875 / 1.000 / 1.000 | 0.958 | 0/3 | 18 | 1 | 0 |
| Q004 | gold | faithful | factuel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 18 | 0 | 0 |
| Q005 | gold | faithful | définitionnel | 0.667 / 0.444 / 0.444 | 0.519 | 0/3 | 24 | 12 | 0 |
| Q006 | gold | faithful | factuel | 0.750 / 0.750 / 0.750 | 0.750 | 0/3 | 12 | 3 | 0 |
| Q007 | gold | faithful | définitionnel | 0.462 / 0.462 / 0.385 | 0.436 | 0/3 | 39 | 22 | 0 |
| Q008 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 12 | 0 | 0 |
| Q009 | gold | faithful | définitionnel | 1.000 / 1.000 / 1.000 | 1.000 | 0/3 | 23 | 0 | 0 |
| Q010 | gold | faithful | définitionnel | 0.778 / 0.778 / 0.778 | 0.778 | 0/3 | 27 | 6 | 0 |
| Q011 | gold | faithful | définitionnel | 0.917 / 0.917 / 0.917 | 0.917 | 0/3 | 36 | 3 | 0 |
| Q012 | gold | faithful | définitionnel | 0.800 / 0.800 / 0.800 | 0.800 | 0/3 | 15 | 3 | 0 |

## Failures (recorded as nan, never dropped)

None.
