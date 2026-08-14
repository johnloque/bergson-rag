"""Chunk parsed works into retrieval units.

Paragraph is the atomic unit: whole, consecutive paragraphs within a
single section are accumulated toward a ~500-word target. A section
boundary is always a hard chunk boundary. Word counts here are plain
`str.split()` counts — the BGE-M3 tokenizer-based budget is deferred to
Sprint 2 indexing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.ingestion.models import Chunk, Section, Work

TARGET_WORDS = 500
MAX_STANDALONE_WORDS = 750
MIN_TRAILING_WORDS = 80


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


def _merge_chunks(work_id: str, section: Section, a: Chunk, b: Chunk, index: int) -> Chunk:
    return Chunk(
        chunk_id=f"{work_id}_c{index}",
        work_id=work_id,
        section_id=section.section_id,
        section_path=a.section_path,
        paragraph_ids=a.paragraph_ids + b.paragraph_ids,
        text=f"{a.text}\n\n{b.text}",
        word_count=a.word_count + b.word_count,
        page_start=a.page_start,
        page_end=b.page_end,
    )


def chunk_section(work_id: str, section: Section, paragraphs: list) -> list[Chunk]:
    """Chunk one section's paragraphs. `paragraphs` must be that
    section's paragraphs, in document order."""
    chunks: list[Chunk] = []
    bucket: list = []
    bucket_words = 0

    def flush() -> None:
        nonlocal bucket, bucket_words
        if bucket:
            chunks.append(_make_chunk(work_id, section, bucket, len(chunks) + 1))
            bucket = []
            bucket_words = 0

    for paragraph in paragraphs:
        if paragraph.word_count > MAX_STANDALONE_WORDS:
            flush()
            chunks.append(_make_chunk(work_id, section, [paragraph], len(chunks) + 1))
            continue

        bucket.append(paragraph)
        bucket_words += paragraph.word_count
        if bucket_words >= TARGET_WORDS:
            flush()

    flush()

    if len(chunks) >= 2 and chunks[-1].word_count < MIN_TRAILING_WORDS:
        last = chunks.pop()
        previous = chunks.pop()
        chunks.append(_merge_chunks(work_id, section, previous, last, len(chunks) + 1))

    return chunks


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
