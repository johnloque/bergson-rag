---
id: faithfulness.nli_verifier
version: smoke
description: Throwaway fixture (plumbing only).
variables: []
examples:
- nli_verifier.examples.yaml
library: ragas
---
Your task is to judge the faithfulness of a series of statements based on a given context. For each statement you must return verdict as 1 if the statement can be directly inferred based on the context or 0 if the statement can not be directly inferred based on the context. Copy each statement word-by-word, and always write the reason in French. Be brief.
