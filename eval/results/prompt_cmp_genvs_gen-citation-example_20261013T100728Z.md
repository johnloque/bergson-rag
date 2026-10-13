# Generation variant `gen-citation-example` vs baseline

> **EXPLORATORY: n=12 items, below the n=50 volume threshold (docs/gold_dataset_protocol.md). No number here is decision-grade, and this tooling never picks a winner: the owner does.**

- **baseline**: `eval/results/prompt_cmp_generation_default_n12_20261012T082113Z.json`, `eval/results/prompt_cmp_generation_default_n12_20261012T093211Z.json`
- **variant**: `eval/results/prompt_cmp_generation_gen-citation-example_n12_20261013T085532Z.json`
- **Differs in**: generation.answer
- **Frozen judge**: matches frozen_judge.json (frozen 2026-10-12T07:29:55Z from eval/results/prompt_cmp_judge_default_n28_20261011T090042Z.json); accepted gate misses: Q008-p1-negation

## Gate (no fabricated work title, no title/year mismatch, in any run)

| candidate | run | gate | answers checked | failures |
|---|---|---|---|---|
| default | 1 | PASSED | 36/36 | — |
| default | 2 | PASSED | 36/36 | — |
| gen-citation-example | 1 | PASSED | 36/36 | — |

## Faithfulness by the frozen judge, and failures (per run)

| candidate | run | mean (higher = fewer unsupported claims) | nan per repeat | unevaluated per repeat | unsupported claims | generation failures |
|---|---|---|---|---|---|---|
| default | 1 | 0.836 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 53 | 0 |
| default | 2 | 0.821 | r1 0/12, r2 0/12, r3 0/12 | r1 0/12, r2 0/12, r3 0/12 | 58 | 0 |
| gen-citation-example | 1 | 0.707 | r1 0/12, r2 0/12, r3 0/12 | r1 1/12, r2 0/12, r3 1/12 | 74 | 0 |

## Substance (beside the axes: an answer that says less has less to get wrong)

| candidate | run | claims/answer | chars/answer | citations/answer | answers with a citation | citations to a chunk not given |
|---|---|---|---|---|---|---|
| default | 1 | 7.222 | 885.000 | 0.556 | 14/36 | 0 |
| default | 2 | 7.444 | 885.417 | 0.583 | 15/36 | 0 |
| gen-citation-example | 1 | 6.944 | 1002.722 | 1.833 | 28/36 | 0 |

## Stability

| candidate | scope | mean range | max range | flips | matched | single-run | identical answers |
|---|---|---|---|---|---|---|---|
| default | run 1 | 0.035 | 0.222 | 1 | 87 | 18 | 10 |
| default | run 2 | 0.013 | 0.077 | 1 | 90 | 7 | 12 |
| default | pooled (2 runs, 6 repeats) | 0.042 | 0.222 | 1 | 94 | 17 | 10 |
| gen-citation-example | run 1 | 0.093 | 0.524 | 2 | 78 | 37 | 6 |
| gen-citation-example | pooled (1 runs, 3 repeats) | 0.093 | 0.524 | 2 | 78 | 37 | 6 |

## Noise floor (per-item |run 1 - run 2|)

- **default**: 0 on 10 items; nonzero: Q003 0.108, Q005 0.074; nan on 0 (—); max 0.108, mean 0.015 over 12 finite items
- **gen-citation-example**: single run, no floor

## Selection axes (only if both pass the gate in every run)

- default preferred over gen-citation-example (better-or-equal on both axes)

## Claims newly flagged unsupported (distinct, all runs, with the judge's reason)

- Q002: Cette durée psychologique est rigoureusement déterminée. — Le contexte discute de la durée psychologique et son caractère absolu pour la conscience, mais il ne fait pas mention d'une détermination rigoureuse.
- Q002: Cette durée psychologique est liée à la latitude de création. — Le contexte discute de la durée psychologique et de la succession des états dans l'univers, mais il ne fait pas explicitement de lien entre cette durée psychologique et la latitude de création.
- Q002: Lorsque l'on prépare un verre d'eau sucrée, il est nécessaire d'attendre que le sucre fonde. — Le contexte discute de la nature du temps et de la succession des événements, mais il ne fait pas explicitement mention de la préparation d'un verre d'eau sucrée.
- Q003: Cette dépersonnalisation est liée à la fausse reconnaissance. — Le contexte décrit la dépersonnalisation comme étant une illusion qui peut être liée à la fausse reconnaissance, mais il ne fait pas explicitement la liaison entre les deux.
- Q003: Cette dépersonnalisation n'est pas indissolublement liée à la fausse reconnaissance. — Le contexte indique que la dépersonnalisation est liée à la fausse reconnaissance, car il est expliqué que la dépersonnalisation s'y rattache.
- Q004: Au contraire, la vie ne se recompose pas, elle se laisse regarder simplement. — Le contexte discute de l'imagination poétique et la façon dont elle permet de voir plus profondément la réalité. Il y a une contradiction entre l'affirmation et le contexte qui soutient que la vie ne se recompose pas, mais plutôt qu'elle se laisse observer.
- Q005: Cette perception permet de dissiper la frayeur, ou plutôt d'empêcher sa naissance. — Le contexte décrit la perception du tremblement de terre comme ayant un air bonhomme et permettant de le traiter avec familiarité, ce qui permet de dissiper la peur. Il n'y a donc pas de mention de la perception permettant d'empêcher la naissance de la peur.
- Q005: La conception scientifique du tremblement de terre, qui précise la représentation intellectuelle, est considérée comme dangereuse car elle ne nous apporte pas de moyen d'y échapper. — Le contexte décrit l'expérience de William James lors du tremblement de terre de 1906 en Californie et sa perception de l'événement comme un être individuel et vivant. Il y a une réaction défensive de la nature contre le danger, et l'intelligence suscite des images et des idées qui rassurent. La conception scientifique du tremblement de terre est considérée comme artificielle et contraire à cette perception spontanée. Il n'est donc pas directement informatif que la conception scientifique du tremblement de terre est dangereuse car elle ne nous apporte pas de moyen d'y échapper.
- Q005: La réaction défensive de la nature se produit donc contre l'émotion de la crainte qui est inhibiteur, lorsque le péril est extrême. — Le contexte décrit la réaction défensive de la nature en réponse à une agression de la nature, notamment un tremblement de terre. Cette réaction est décrite comme une réaction contre la crainte, mais il n'est pas explicitement indiqué que la crainte soit inhibiteur lorsque le péril est extrême.
- Q006: Selon Bergson, il reconstruit la pensée d'un certain philosophe en la comparant à une recette de cuisine. — Le contexte ne mentionne pas explicitement la comparaison de la pensée à une recette de cuisine, mais il y a une allusion à la métaphore de la salade, ce qui peut suggérer une comparaison entre la pensée et la cuisine. Cependant, il n'y a pas de preuve directe dans le contexte pour confirmer cette affirmation.
- Q006: Bergson compare la reconstitution de la pensée de Berkeley à une recette de cuisine. — Le contexte décrit la reconstitution de la pensée de Berkeley en termes de tranches de philosophie ancienne et moderne, mêlées avec certains aphorismes cueillis chez les néo-platoniciens, mais il n'y a aucune mention de cuisine ou de comparaison avec une recette.
- Q006: Bergson ajoute ensuite ces éléments dans un mélange. — Le contexte discute de la philosophie de Berkeley et son influence sur d'autres philosophes, mais il ne mentionne pas explicitement Bergson ou son travail. Il n'y a donc pas de preuve directe que Bergson a ajouté ces éléments dans un mélange.
- Q006: Bergson ajoute une certaine impatience agressive à l'égard du dogmatisme mathématique. — Le contexte discute de la philosophie de Berkeley, mais il y a mention de la philosophie de Bergson en tant qu'une des sources des éléments nécessaires à la reconstitution extérieure de la philosophie de Berkeley. Il n'y a pas de mention directe d'une impatience agressive de Bergson à l'égard du dogmatisme mathématique.
- Q006: Le désir, naturel chez un évêque philosophe, de réconcilier la raison avec la foi est ajouté par Bergson. — Le contexte ne mentionne pas explicitement Bergson, mais il est possible de déduire que l'auteur de la pièce discute de philosophes anciens et modernes, y compris un évêque philosophe, sans que Bergson soit explicitement mentionné. Cependant, il n'y a pas de preuve directe dans le contexte pour soutenir que Bergson a été ajouté à la philosophie discutée.
- Q006: Selon les extraits fournis, Bergson compare la reconstitution de la pensée de Berkeley à une recette de cuisine. — Le contexte décrit la reconstitution de la pensée de Berkeley en termes de tranches de philosophie ancienne et moderne, d'aphorismes cueillis chez les néo-platoniciens, et de mélange de vinaigre et d'huile, ce qui ne laisse pas entendre que Bergson compare la reconstitution de la pensée de Berkeley à une recette de cuisine.
- Q006: Bergson ajoute le désir, naturel chez un évêque philosophe, de réconcilier la raison avec la foi. — Le contexte discute de la philosophie de Berkeley, mais il ne fait aucune mention de Bergson. Cependant, il est possible de déduire que Bergson a pu être mentionné dans les aphorismes cueillis chez les néo-platoniciens, mais il n'y a pas de preuve directe dans le contexte.
- Q007: La philosophie est donc condamnée par avance à recevoir une solution toute faite ou à simplement choisir entre les solutions coéternelles à cette position du problème. — Le contexte discute sur la nature de la philosophie et comment elle est influencée par le langage et les concepts. Il ne fait pas directement allusion à la possibilité de recevoir une solution toute faite ou de choisir entre des solutions coéternelles à une position du problème.
- Q007: Selon Bergson, il est nécessaire de déraciner l'inclination profonde de l'esprit humain à voir dans le changement et le mouvement des accidents, à ériger l'immutabilité et l'immobilité en essences ou substances, en supports, pour pouvoir renverser le sens de son opération habituelle, et partir du changement et du mouvement, envisagés comme la réalité même, et ne plus voir dans les arrêts ou les états que des instantanés pris sur du mouvant. — Le contexte discute de la philosophie et de la manière dont elle est influencée par la nature de notre langage et de notre perception. Bergson est mentionné comme un philosophe qui a commencé à penser que la perception et la pensée humaine sont influencées par une inclination à voir l'immutabilité et l'immobilité comme des essences ou des substances, mais il n'est pas explicitement affirmé que Bergson ait dit que cela est nécessaire pour renverser le sens de l'opération habituelle de l'esprit humain.
- Q008: Il souligne que, comme un manteau est solidaire du clou auquel il est accroché, il ne peut être conclu que chaque détail du cerveau correspond à un détail de la conscience. — Le contexte discute de la relation entre le cerveau et la conscience, et il est clair que l'auteur ne soutient pas que chaque détail du cerveau correspond à un détail de la conscience, mais plutôt qu'il y a une certaine relation entre les deux.
- Q009: Selon Bergson, la grande chevauchée du vivant décrit la solidarité de la vie dans la nature. — Le contexte décrit la relation entre la vie de l'esprit et celle du corps, la vie entière, la matière et la conscience, et la liberté de la conscience. Il y a une mention de la solidarité de la vie consciente et de l'activité cérébrale, mais il n'y a pas de mention explicite de la grande chevauchée du vivant décrivant la solidarité de la vie dans la nature.
- Q009: La matérialité elle-même est le mouvement de la matière. — Le contexte décrit la matérialité comme un flot qui monte, et que contrarie le mouvement descendant de la matière. Cependant, il ne fait pas explicitement de la matérialité elle-même égale au mouvement de la matière.
- Q009: Tous les vivants, depuis les plus simples jusqu'à l'homme, rendent sensible une impulsion unique à leurs yeux. — Le contexte décrit la relation entre la vie de l'esprit et celle du corps, et la solidarité de la vie consciente et de l'activité cérébrale. Il évoque la genèse des espèces par voie de transformation graduelle, ce qui implique une diversité de formes de vie. Cependant, il ne s'agit pas d'une affirmation directe sur l'impulsion unique des vivants, donc le verdict est 0.
- Q009: Cette thèse suggère que la vie est une entité indivisible qui se déplace dans le temps et l'espace. — Le contexte décrit la vie comme un flot qui monte et se subdivise en individus, ce qui suggère une division de la vie en entités distinctes et non une entité indivisible.
- Q009: Selon Bergson, tout le vivant se tient en solidarité et se déplace dans un mouvement inverse du mouvement de la matière, qui est la matérialité elle-même. — Le contexte décrit la philosophie de Bergson, qui traite de la vie spirituelle et de sa relation à la vie du corps. Il explique que la conscience est distincte de l'organisme qu'elle anime, mais il ne mentionne pas explicitement que tout le vivant se tient en solidarité et se déplace dans un mouvement inverse du mouvement de la matière, qui est la matérialité elle-même.
- Q010: Bergson propose également une autre interprétation possible. — Le contexte discute de l'évolution de la pensée humaine, mais il ne mentionne pas explicitement Bergson. Cependant, il est possible que Bergson ait proposé une autre interprétation, car il est connu pour avoir écrit sur la philosophie grecque, mais cela n'est pas directement déduit du contexte.
- Q011: C'est lorsqu'une tendance, avantageuse en elle-même, est incapable de se modérer autrement que par l'action d'une tendance antagoniste, laquelle se trouve ainsi être également avantageuse. — Le contexte discute de la loi de dichotomie qui provoque la réalisation de tendances divergentes à partir d'une tendance simple. Il est également mentionné que ces tendances peuvent être avantageuses, mais il n'est pas explicitement indiqué que l'une doit être avantageuse et l'autre antagoniste pour qu'elles puissent s'équilibrer.
- Q011: Selon Bergson, les oscillations historiques peuvent être perçues comme des alternances de flux et de reflux, mais il ne considère pas que cela résulte d'une fatalité historique. — Le contexte discute de la nature des oscillations historiques et de la possibilité de leur régularité, mais il ne mentionne pas explicitement la position de Bergson sur la question de la fatalité historique.
- Q011: Il y a un risque de catastrophe si l'on pousse trop loin une tendance avantageuse en l'absence d'une tendance antagoniste qui la contrarierait. — Le contexte discute de la loi de dichotomie qui provoque la réalisation de tendances divergentes à partir d'une tendance simple, et de la loi de double frénésie qui exige que chacune de ces tendances soit suivie jusqu'au bout. Il y a donc mention d'une tendance avantageuse et d'une tendance antagoniste, mais il n'y a pas de mention d'un risque de catastrophe si l'une de ces tendances est poussée trop loin en l'absence de l'autre.
- Q012: La personnalité d'enfant d'un individu, quoique indivisible, réunissait en elle des personnes diverses qui pouvaient rester fondues ensemble parce qu'elles étaient à l'état naissant, selon l'œuvre de Henri Bergson. — L'œuvre de Henri Bergson n'est pas mentionnée dans le contexte, donc il n'est pas possible de dire si la personnalité d'enfant d'un individu est décrite comme réunissant en elle des personnes diverses qui peuvent rester fondues ensemble parce qu'elles sont à l'état naissant, selon l'œuvre de Henri Bergson.
- Q012: La route que nous parcourrons dans le temps est jonchée des débris de tout ce que nous commencions d'être, de tout ce que nous aurions pu devenir, selon l'œuvre de Henri Bergson. — Le contexte discute de l'évolution de la vie et de la tendance vitale à se développer en forme de gerbe, créant des directions divergentes entre lesquelles se partagera l'élan. Il n'y a pas de mention d'Henri Bergson ou de son œuvre, donc on ne peut pas déduire que la route que nous parcourrons dans le temps est jonchée des débris de tout ce que nous commencions d'être, de tout ce que nous aurions pu devenir, selon l'œuvre de Henri Bergson.
- Q012: La nature, qui dispose d'un nombre incalculable de vies, n'est pas astreinte à de pareils sacrifices, selon l'œuvre de Henri Bergson. — Le contexte ne mentionne pas explicitement l'œuvre de Henri Bergson, donc on ne peut pas déduire que la déclaration est vraie dans le contexte.
- Q012: Elle conserve les diverses tendances qui ont bifurqué en grandissant et crée des séries divergentes d'espèces qui évolueront séparément, selon l'œuvre de Henri Bergson. — Le contexte discute de l'évolution de la vie et de la dissociation des tendances en cours de route, mais il ne fait aucune référence à Henri Bergson ou à son œuvre.
- Q012: Dans ce contexte, les tendances qui se sont constituées par dissociation se développent le plus souvent dans des espèces distinctes ; elles vont, chacune de son côté, chercher fortune dans le monde ; la matérialité qu'elles se sont donnée les empêche de venir se ressouder pour ramener en plus fort, en plus complexe, en plus évolué, la tendance originelle, selon l'œuvre de Henri Bergson. — Le contexte traite de l'évolution générale de la vie, y compris la psychologique et sociale, et ne fait pas explicitement référence à l'œuvre de Henri Bergson.
- Q012: La personnalité d'enfant, quoique indivisible, réunissait en elle des personnes diverses qui pouvaient rester fondues ensemble parce qu'elles étaient à l'état naissant, selon l'œuvre de Henri Bergson. — L'œuvre de Henri Bergson n'est pas mentionnée dans le contexte, donc on ne peut pas déduire que la personnalité d'enfant est décrite comme tel dans son œuvre.

## Polarity review: negated segments newly asserted by the variant (read by hand)

The frozen judge does not reliably detect a negation that reverses a sentence's meaning (docs/prompts.md, "Frozen judge: baseline v3"): a faithfulness delta says nothing about these. Check each against its chunks.

- Q001 (pas): Selon Bergson, l'image de la boule de neige illustre la perception du changement en soulignant la constante transformation de chaque état d'âme, même lorsque l'on ne le perçoit pas.
- Q001 (sans): Bien que les états d'âme soient souvent perçus comme stables, Bergson souligne que chaque état est en fait un changement en cours, et que la vérité est que l'on change sans cesse. [1907_EC_c13]
- Q002 (pas): En effet, lorsque l'on prépare un verre d'eau sucrée, il est nécessaire d'attendre que le sucre fonde, ce qui indique que la durée psychologique de l'attente est un absolu pour la conscience, alors que pour la science physique, le temps n'est pas un absolu mais un nombre.
- Q004 (pas): Selon Bergson, l'imagination poétique ne compose pas ses héros avec des morceaux empruntés à droite et à gauche autour d'elle, comme pour coudre un habit d'Arlequin [1900_R_c170].
- Q004 (plus): L'imagination poétique ne peut être qu'une vision plus complète de la réalité.
- Q004 (plus): L'imagination poétique ne peut être qu'une vision plus complète de la réalité [1900_R_c170].
- Q007 (rien): Selon Bergson, la structure du langage est source de problèmes en philosophie car elle est intellectuelle et calquée sur les mots, qui ont été élaborés par l'organisme social en vue d'un objet qui n'a rien de métaphysique.
- Q007 (pas): La philosophie accepte souvent une division du réel qui a toutes chances de ne pas correspondre aux articulations naturelles des choses, car elle subit le problème tel qu'il est posé par le langage.
- Q007 (pas): En effet, les concepts sont inclus dans les mots et ont été élaborés pour un travail pour lequel la plupart ne sont pas faits.
- Q008 (pas): Selon Bergson, la thèse qu'il explique à travers l'image du manteau accroché à un clou est que la solidarité entre l'état de conscience et le cerveau ne permet pas de conclure au "parallélisme" des deux séries psychologique et physiologique.
- Q008 (pas): Il insiste sur le fait que l'observation, l'expérience, et par conséquent la science ne permettent d'affirmer que l'existence d'une certaine relation entre le cerveau et la conscience, mais pas que le cerveau dessine tout le détail de la conscience ou que la conscience soit une fonction du cerveau. [1896_MM_c7] [1919_ES_c32]
- Q011 (pas): Selon Bergson, les oscillations historiques peuvent être perçues comme des alternances de flux et de reflux, mais il ne considère pas que cela résulte d'une fatalité historique.
- Q011 (rien): Cette loi n'a rien de mystérieux, elle exprime simplement le fait que une tendance est la poussée d'une multiplicité indistincte, qui n'est d'ailleurs indistincte, et n'est multiplicité, que si on la considère rétrospectivement, quand des vues diverses prises après coup sur son indivision passée la composent avec des éléments qui ont été en réalité créés par son développement.
- Q011 (pas): Ils ne manifestent pas une nécessité qui dominerait les causes particulières d'alternance et qui s'imposerait d'une manière générale aux événements humains.

## Per-item means (mean of repeats; nan runs/runs)

| id | default run 1 | default run 2 | gen-citation-example run 1 |
|---|---|---|---|
| Q001 | 0.875 (0/3) | 0.875 (0/3) | 1.000 (0/3) |
| Q002 | 1.000 (0/3) | 1.000 (0/3) | 0.667 (0/3) |
| Q003 | 0.958 (0/3) | 0.850 (0/3) | 0.738 (0/3) |
| Q004 | 1.000 (0/3) | 1.000 (0/3) | 0.750 (0/3) |
| Q005 | 0.519 (0/3) | 0.444 (0/3) | 0.433 (0/3) |
| Q006 | 0.750 (0/3) | 0.750 (0/3) | 0.540 (0/3) |
| Q007 | 0.436 (0/3) | 0.436 (0/3) | 0.667 (0/3) |
| Q008 | 1.000 (0/3) | 1.000 (0/3) | 0.750 (0/3) |
| Q009 | 1.000 (0/3) | 1.000 (0/3) | 0.619 (0/3) |
| Q010 | 0.778 (0/3) | 0.778 (0/3) | 0.875 (0/3) |
| Q011 | 0.917 (0/3) | 0.917 (0/3) | 0.806 (0/3) |
| Q012 | 0.800 (0/3) | 0.800 (0/3) | 0.643 (0/3) |

## Deltas (run 1 of each, marked against the baseline floor)

| id | baseline | variant | delta | floor | noise |
|---|---|---|---|---|---|
| Q001 | 0.875 | 1.000 | 0.125 | 0.000 | outside noise |
| Q002 | 1.000 | 0.667 | -0.333 | 0.000 | outside noise |
| Q003 | 0.958 | 0.738 | -0.220 | 0.108 | outside noise |
| Q004 | 1.000 | 0.750 | -0.250 | 0.000 | outside noise |
| Q005 | 0.519 | 0.433 | -0.085 | 0.074 | outside noise |
| Q006 | 0.750 | 0.540 | -0.210 | 0.000 | outside noise |
| Q007 | 0.436 | 0.667 | 0.231 | 0.000 | outside noise |
| Q008 | 1.000 | 0.750 | -0.250 | 0.000 | outside noise |
| Q009 | 1.000 | 0.619 | -0.381 | 0.000 | outside noise |
| Q010 | 0.778 | 0.875 | 0.097 | 0.000 | outside noise |
| Q011 | 0.917 | 0.806 | -0.111 | 0.000 | outside noise |
| Q012 | 0.800 | 0.643 | -0.157 | 0.000 | outside noise |
