---
id: faithfulness.nli_verifier
version: v1
description: Judges whether one claim can be directly inferred from the context; English instruction, French reasons (RAGAS PydanticPrompt instruction).
variables: []
examples:
- nli_verifier.examples.yaml
library: ragas
---
Your task is to judge the faithfulness of a series of statements based on a given context. For each statement you must return verdict as 1 if the statement can be directly inferred based on the context or 0 if the statement can not be directly inferred based on the context. Check the polarity of each statement against the context: a statement that denies what the context affirms (for example with « ne … pas », « ne … plus », « aucun », « jamais »), or affirms what the context denies, gets verdict 0, even if every other word matches the context. A negation that the context itself states is supported. Your verdict must agree with your reason: if the reason says the context asserts the opposite of the statement, the verdict is 0. Copy each statement word-by-word, and always write the reason in French.
