"""The evidence-conditioned generation prompt (docs/ROADMAP.md, Sprint 5).

One template (`prompts/generation/answer.md`, refactor/prompts-to-files),
dynamically conditioned on `EvidenceSignals` — not branch-specific separate
templates. The rendered prompt always includes the
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
which the citation format (the citation instruction in
`prompts/generation/answer.md`) and Layer 1
(`src/generation/guardrail.py`) both still key on. This is the primary
mitigation for that failure mode — `check_title_year_mismatch`
(`src/generation/guardrail.py`) remains the safety net for whatever still
gets through, same defense-in-depth split as every other guardrail in this
project.

## Text-level grounding (Sprint 11, `feat/backend-reference-data`)

For a chunk whose paragraphs fall inside one of 1919_ES's or 1934_PM's
individually-dated texts (`src.works.TEXTS`), the chunk's evidence header also
shows that text's own real title and year, alongside (not instead of) the
work-level title/year above — e.g. a chunk from 1919_ES's "L'effort
intellectuel" article shows both `L'énergie spirituelle (1919)` (the
anthology) and `L'effort intellectuel (1902)` (the actual text), since the
anthology's own 1919 publication date is not the year the model should
attribute a specific article's ideas to. Resolved via
`src.works.resolve_paragraph_metadata(chunk.work_id, chunk.paragraph_ids[0])`
— the first paragraph_id is representative of the whole chunk because
chunking never crosses a section/div boundary
(`tests/test_works.py::test_no_chunk_straddles_two_qualifying_divs`), so
every paragraph in a chunk always resolves to the same text-level metadata.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from src.generation.chunk_judgment import ChunkJudgment
from src.generation.signals import EvidenceSignals, GenerationChunk
from src.prompts.loader import Prompt, load_prompt, prompts_used
from src.works import resolve_paragraph_metadata, work_label

# Prompt wording lives in prompts/generation/ (docs/prompts.md), branching
# included: answer.md is one Jinja2 template, so one hash identifies the
# whole evidence-conditioned prompt. This module only shapes its input data.
SYSTEM_PROMPT = load_prompt("generation.system")
ANSWER_PROMPT = load_prompt("generation.answer")

# The `[chunk_id]` bracket format the citation instruction
# (prompts/generation/answer.md) asks the model to produce — defined once
# here, since this module is what feeds the model that instruction.
# `src/generation/guardrail.py`'s `check_structure` (Layer 1, no LLM call)
# imports this rather than hardcoding a second copy of the same pattern: the
# two modules must agree on exactly one citation format, and a shared symbol
# is what keeps them agreeing on it.
CITATION_PATTERN = re.compile(r"\[([^\[\]]+)\]")


def generation_prompts_used(answer_prompt: Prompt = ANSWER_PROMPT) -> dict[str, dict[str, Any]]:
    """`prompts_used` record for one `generate_from_chunks` call."""
    return prompts_used(SYSTEM_PROMPT, answer_prompt)


def _chunk_data(chunk: GenerationChunk, judgment: ChunkJudgment | None) -> dict[str, Any]:
    """Template input for one evidence block. `text_title`/`text_year` are set
    when `chunk` falls inside an individually-dated text (Sprint 11,
    `feat/backend-reference-data`) — see this module's docstring
    ("Text-level grounding") for why `chunk.paragraph_ids[0]` is
    representative of the whole chunk."""
    metadata = resolve_paragraph_metadata(chunk.work_id, chunk.paragraph_ids[0])
    return {
        "chunk_id": chunk.chunk_id,
        "work_id": chunk.work_id,
        # Shown alongside work_id, never instead of it: the citation format
        # and Layer 1 (src/generation/guardrail.py) both key on work_id.
        "work_label": work_label(chunk.work_id),
        "text_title": metadata.text_title,
        "text_year": metadata.text_year,
        "section_path": chunk.section_path,
        "page_start": chunk.page_start["display"],
        "page_end": chunk.page_end["display"],
        "text": chunk.text,
        "judgment": judgment,
    }


def build_prompt(
    query: str,
    chunks: Sequence[GenerationChunk],
    signals: EvidenceSignals,
    chunk_judgments: Mapping[str, ChunkJudgment] | None = None,
    *,
    answer_prompt: Prompt = ANSWER_PROMPT,
) -> str:
    """`answer_prompt`: the committed `generation.answer` unless given; only
    the prompt-comparison eval tooling passes another (docs/prompts.md)."""
    chunk_judgments = chunk_judgments or {}
    return answer_prompt.render(
        query=query,
        chunks=[_chunk_data(chunk, chunk_judgments.get(chunk.chunk_id)) for chunk in chunks],
        works=[{"id": work, "label": work_label(work)} for work in signals.works],
        is_multi_work=signals.is_multi_work,
        is_convergent=signals.is_convergent,
        is_confident=signals.is_confident,
    )
