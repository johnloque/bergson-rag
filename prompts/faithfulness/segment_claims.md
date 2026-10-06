---
id: faithfulness.segment_claims
version: v1
description: Decomposes each numbered answer segment into standalone claims, grouped by segment (RAGAS PydanticPrompt instruction).
variables: []
examples:
- segment_claims.examples.yaml
library: ragas
---
À partir d'une question et d'une réponse découpée en segments numérotés, parcours les segments dans l'ordre. Décompose chaque segment en une ou plusieurs affirmations pleinement compréhensibles seules. Aucune affirmation ne doit contenir de pronom : sers-toi des autres segments pour savoir à quoi renvoie un pronom. Une affirmation ne reprend que le contenu de son propre segment, jamais celui d'un autre. Chaque segment apparaît exactement une fois dans la sortie, sous son propre segment_id ; un segment qui n'affirme rien reçoit une liste d'affirmations vide. Rédige toutes les affirmations en français. Réponds au format JSON.
