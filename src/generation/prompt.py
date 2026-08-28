"""The evidence-conditioned generation prompt (docs/ROADMAP.md, Sprint 5).

One template, dynamically conditioned on `EvidenceSignals` — not
branch-specific separate templates. `build_prompt` always includes the
mandatory citation and interpretive-framing instructions, then appends
exactly one work-structure instruction and one convergence instruction
(chosen by the corresponding signal), and optionally an epistemic-caution
instruction when reranking confidence is low. This is the generation
pipeline's own conditioning reaction to weak evidence, not the
anti-hallucination guardrail — no refusal / "no reliable answer" handling
here, that's Sprint 6 (docs/ROADMAP.md).

`chunk_judgments` (Sprint 6, docs/ROADMAP.md — the `ChunkJudgment` contract
in `src/generation/chunk_judgment.py`) is optional, separate conditioning: when a
chunk in the input selection has a prior relevance judgment (from a future
`judge_chunks` call, on a manual regeneration), its label and justification
are rendered inline with that chunk's evidence text, plus one instruction
telling the model this prior assessment exists. It is not a filter — chunks
already excluded by the caller never appear here at all.

## Title/year grounding (`fix/title-year-grounding`)

Every chunk header and multi-work group now shows the source work's real
title and publication year (`src.works.work_label`) alongside `work_id`,
e.g. `1907_EC — L'Évolution créatrice (1907)` instead of just `1907_EC`.
Before this branch the model was shown only `work_id` and had to recall the
actual title/year from its own background knowledge to name them in
prose — the root cause `docs/anti_hallucination_guardrails.md` identifies
for both fabrication shapes found in calibration (an invented title, and a
real title attached to the wrong year, e.g. Q004's "1934" for the real 1907
work "L'évolution créatrice"). Giving the model the correct values directly
removes the need to recall them at all; it does not replace `work_id`,
which the citation format (`CITATION_INSTRUCTION` below) and Layer 1
(`src/generation/guardrail.py`) both still key on. This is the primary
mitigation for that failure mode — `check_title_year_mismatch`
(`src/generation/guardrail.py`) remains the safety net for whatever still
gets through, same defense-in-depth split as every other guardrail in this
project.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.signals import EvidenceSignals, GenerationChunk
from src.works import work_label

SYSTEM_PROMPT = (
    "Tu es un assistant qui répond à des questions sur la philosophie de Henri Bergson "
    "en te fondant strictement sur les extraits sources fournis. N'utilise aucune "
    "connaissance de Bergson extérieure à ces extraits."
)

CITATION_INSTRUCTION = (
    "Cite systématiquement tes affirmations en indiquant le chunk_id du passage source "
    "entre crochets (ex. [1907_EC_c5]) : chaque affirmation doit être rattachée à un "
    "passage précis."
)

# The `[chunk_id]` bracket format CITATION_INSTRUCTION above asks the model
# to produce — defined once here, since this module is what teaches the
# model the format. `src/generation/guardrail.py`'s `check_structure`
# (Layer 1, no LLM call) imports this rather than hardcoding a second copy
# of the same pattern: the two modules must agree on exactly one citation
# format, and a shared symbol is what keeps them agreeing on it.
CITATION_PATTERN = re.compile(r"\[([^\[\]]+)\]")

INTERPRETIVE_FRAMING_INSTRUCTION = (
    "Présente ta réponse comme une synthèse interprétative à vérifier auprès des "
    "passages cités, pas comme une conclusion définitive et arrêtée."
)

MONO_WORK_INSTRUCTION = (
    "Tous les extraits proviennent d'une seule œuvre : présente la réponse de façon "
    "continue, sans avoir besoin de distinguer les sources par œuvre."
)

CONVERGENT_INSTRUCTION = (
    "Les passages convergent : tu peux les synthétiser directement en une réponse unifiée."
)

DIVERGENT_INSTRUCTION = (
    "Les passages ne convergent pas clairement : présente-les séparément plutôt que "
    "de les fondre dans un récit unique, et ne présente jamais la réponse comme un "
    "consensus si les passages ne s'accordent pas clairement entre eux."
)

CAUTION_INSTRUCTION = (
    "Le meilleur score de pertinence attribué par le reranker à cette sélection de "
    "passages reste modéré : formule la réponse avec une prudence épistémique "
    "appropriée."
)

CHUNK_JUDGMENT_INSTRUCTION = (
    "Certains extraits sont accompagnés d'un jugement de pertinence préalable "
    "(étiquette et justification) : prends-le en compte comme signal supplémentaire "
    "sur la pertinence du passage, sans t'y limiter."
)


def _work_ref(work_id: str) -> str:
    """`"{work_id} — {title} ({year})"` — `work_id` is kept alongside the
    title/year (not replaced by it): the citation format and Layer 1
    (`src/generation/guardrail.py`) both still key on `work_id`."""
    return f"{work_id} — {work_label(work_id)}"


def _multi_work_instruction(works: tuple[str, ...]) -> str:
    work_refs = ", ".join(_work_ref(work) for work in works)
    return (
        f"Les extraits proviennent de {len(works)} œuvres distinctes ({work_refs}) : "
        "regroupe le contexte par œuvre et attribue explicitement chaque affirmation à "
        "l'œuvre dont elle provient."
    )


def _page_range(page_start: dict, page_end: dict) -> str:
    start, end = page_start["display"], page_end["display"]
    return start if start == end else f"{start}-{end}"


def _format_chunk(chunk: GenerationChunk, judgment: ChunkJudgment | None) -> str:
    pages = _page_range(chunk.page_start, chunk.page_end)
    header = f"[{chunk.chunk_id}] ({_work_ref(chunk.work_id)}, {chunk.section_path}, p. {pages})"
    block = f"{header}\n{chunk.text}"
    if judgment is not None:
        block += f"\n(Jugement de pertinence : {judgment['label']} — {judgment['justification']})"
    return block


def _format_evidence(
    chunks: Sequence[GenerationChunk],
    works: tuple[str, ...],
    chunk_judgments: Mapping[str, ChunkJudgment],
) -> str:
    def format_one(chunk: GenerationChunk) -> str:
        return _format_chunk(chunk, chunk_judgments.get(chunk.chunk_id))

    if len(works) <= 1:
        return "\n\n".join(format_one(chunk) for chunk in chunks)
    blocks = []
    for work in works:
        work_chunks = [chunk for chunk in chunks if chunk.work_id == work]
        body = "\n\n".join(format_one(chunk) for chunk in work_chunks)
        blocks.append(f"=== {_work_ref(work)} ===\n{body}")
    return "\n\n".join(blocks)


def build_prompt(
    query: str,
    chunks: Sequence[GenerationChunk],
    signals: EvidenceSignals,
    chunk_judgments: Mapping[str, ChunkJudgment] | None = None,
) -> str:
    chunk_judgments = chunk_judgments or {}
    instructions = [CITATION_INSTRUCTION, INTERPRETIVE_FRAMING_INSTRUCTION]
    instructions.append(
        _multi_work_instruction(signals.works) if signals.is_multi_work else MONO_WORK_INSTRUCTION
    )
    instructions.append(CONVERGENT_INSTRUCTION if signals.is_convergent else DIVERGENT_INSTRUCTION)
    if not signals.is_confident:
        instructions.append(CAUTION_INSTRUCTION)
    if any(chunk.chunk_id in chunk_judgments for chunk in chunks):
        instructions.append(CHUNK_JUDGMENT_INSTRUCTION)

    instructions_block = "\n".join(f"- {instruction}" for instruction in instructions)
    evidence_block = _format_evidence(chunks, signals.works, chunk_judgments)

    return (
        f"CONSIGNES :\n{instructions_block}\n\n"
        f"EXTRAITS SOURCES :\n{evidence_block}\n\n"
        f"QUESTION :\n{query}"
    )
