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
"""

from __future__ import annotations

from collections.abc import Sequence

from src.generation.signals import EvidenceSignals, GenerationChunk

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

INTERPRETIVE_FRAMING_INSTRUCTION = (
    "Présente ta réponse comme une synthèse interprétative à vérifier auprès des "
    "passages cités, pas comme une conclusion définitive et arrêtée."
)

MONO_WORK_INSTRUCTION = (
    "Tous les extraits proviennent d'une seule œuvre : présente la réponse de façon "
    "continue, sans avoir besoin de distinguer les sources par œuvre."
)

CONVERGENT_INSTRUCTION = (
    "Les passages convergent : tu peux les synthétiser directement en une réponse " "unifiée."
)

DIVERGENT_INSTRUCTION = (
    "Les passages ne convergent pas clairement : présente-les séparément plutôt que "
    "de les fondre dans un récit unique, et ne présente jamais la réponse comme un "
    "consensus si les passages ne s'accordent pas clairement entre eux."
)

CAUTION_INSTRUCTION = (
    "Le score de pertinence du reranker est plat ou peu discriminant sur cette "
    "sélection de passages : formule la réponse avec une prudence épistémique "
    "appropriée."
)


def _multi_work_instruction(works: tuple[str, ...]) -> str:
    return (
        f"Les extraits proviennent de {len(works)} œuvres distinctes ({', '.join(works)}) : "
        "regroupe le contexte par œuvre et attribue explicitement chaque affirmation à "
        "l'œuvre dont elle provient."
    )


def _page_range(page_start: dict, page_end: dict) -> str:
    start, end = page_start["display"], page_end["display"]
    return start if start == end else f"{start}-{end}"


def _format_chunk(chunk: GenerationChunk) -> str:
    pages = _page_range(chunk.page_start, chunk.page_end)
    return f"[{chunk.chunk_id}] ({chunk.work_id}, {chunk.section_path}, p. {pages})\n{chunk.text}"


def _format_evidence(chunks: Sequence[GenerationChunk], works: tuple[str, ...]) -> str:
    if len(works) <= 1:
        return "\n\n".join(_format_chunk(chunk) for chunk in chunks)
    blocks = []
    for work in works:
        work_chunks = [chunk for chunk in chunks if chunk.work_id == work]
        body = "\n\n".join(_format_chunk(chunk) for chunk in work_chunks)
        blocks.append(f"=== {work} ===\n{body}")
    return "\n\n".join(blocks)


def build_prompt(query: str, chunks: Sequence[GenerationChunk], signals: EvidenceSignals) -> str:
    instructions = [CITATION_INSTRUCTION, INTERPRETIVE_FRAMING_INSTRUCTION]
    instructions.append(
        _multi_work_instruction(signals.works) if signals.is_multi_work else MONO_WORK_INSTRUCTION
    )
    instructions.append(CONVERGENT_INSTRUCTION if signals.is_convergent else DIVERGENT_INSTRUCTION)
    if not signals.is_confident:
        instructions.append(CAUTION_INSTRUCTION)

    instructions_block = "\n".join(f"- {instruction}" for instruction in instructions)
    evidence_block = _format_evidence(chunks, signals.works)

    return (
        f"CONSIGNES :\n{instructions_block}\n\n"
        f"EXTRAITS SOURCES :\n{evidence_block}\n\n"
        f"QUESTION :\n{query}"
    )
