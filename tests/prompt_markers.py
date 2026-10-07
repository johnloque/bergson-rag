"""Distinctive phrases of each conditional instruction in
prompts/generation/answer.md, for tests asserting which branch a rendered
prompt took. The instruction texts used to be importable Python constants;
since refactor/prompts-to-files they live only in the template, and
tests/test_prompt_snapshots.py checks their exact wording.
"""

CITATION_INSTRUCTION = "Cite systématiquement tes affirmations en indiquant le chunk_id"
INTERPRETIVE_FRAMING_INSTRUCTION = "Présente ta réponse comme une synthèse interprétative"
MONO_WORK_INSTRUCTION = "Tous les extraits proviennent d'une seule œuvre"
CONVERGENT_INSTRUCTION = "Les passages convergent :"
DIVERGENT_INSTRUCTION = "Les passages ne convergent pas clairement"
CAUTION_INSTRUCTION = "formule la réponse avec une prudence épistémique"
CHUNK_JUDGMENT_INSTRUCTION = "Certains extraits sont accompagnés d'un jugement de pertinence"
