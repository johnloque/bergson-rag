---
id: judge_chunk.relevance
version: v1
description: User prompt judging one excerpt's relevance to the question (label + justification, as JSON).
variables:
- query
- chunk
---
Évalue si l'extrait ci-dessous permet de répondre à la question posée. Attribue une étiquette parmi exactement ces trois valeurs : "pertinent", "partiellement pertinent", "non pertinent". Rédige une justification de 2 à 4 phrases qui s'appuie sur le contenu concret de l'extrait (une idée, une image ou un terme qui s'y trouve réellement) — jamais une formule générique qui vaudrait pour n'importe quel extrait. Réponds uniquement avec un objet JSON de la forme {"label": "...", "justification": "..."}, sans texte avant ni après.

QUESTION :
{{ query }}

EXTRAIT [{{ chunk.chunk_id }}] ({{ chunk.work_id }}) :
{{ chunk.text }}
