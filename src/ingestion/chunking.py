"""Chunk parsed works into retrieval units.

One chunk = one paragraph. Paragraph and chunk boundaries are identical;
a chunk's `paragraph_ids` always has exactly one element.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.ingestion.models import Chunk, Section, Work


def _make_chunk(work_id: str, section: Section, paragraphs: list, index: int) -> Chunk:
    return Chunk(
        chunk_id=f"{work_id}_c{index}",
        work_id=work_id,
        section_id=section.section_id,
        section_path=f"{section.region}/{section.label}",
        paragraph_ids=[p.paragraph_id for p in paragraphs],
        text="\n\n".join(p.text for p in paragraphs),
        word_count=sum(p.word_count for p in paragraphs),
        # Parsing is sequential and pages only advance, so the first and
        # last paragraph of a chunk carry its min/max page reference.
        page_start=paragraphs[0].page_start,
        page_end=paragraphs[-1].page_end,
    )


def chunk_section(work_id: str, section: Section, paragraphs: list) -> list[Chunk]:
    """Chunk one section's paragraphs. `paragraphs` must be that
    section's paragraphs, in document order. One chunk per paragraph."""
    return [
        _make_chunk(work_id, section, [paragraph], index)
        for index, paragraph in enumerate(paragraphs, start=1)
    ]


def chunk_work(work: Work) -> list[Chunk]:
    paragraphs_by_section: dict[str, list] = {}
    for paragraph in work.paragraphs:
        paragraphs_by_section.setdefault(paragraph.section_id, []).append(paragraph)

    chunks: list[Chunk] = []
    for section in work.sections:
        section_paragraphs = paragraphs_by_section.get(section.section_id, [])
        if not section_paragraphs:
            continue
        section_chunks = chunk_section(work.work_id, section, section_paragraphs)
        for i, chunk in enumerate(section_chunks, start=len(chunks) + 1):
            chunk.chunk_id = f"{work.work_id}_c{i}"
        chunks.extend(section_chunks)

    return chunks


def save_chunks(work_id: str, chunks: list[Chunk], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{work_id}.json"
    out_path.write_text(
        json.dumps([asdict(c) for c in chunks], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
