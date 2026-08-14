"""Data model for parsed Bergson works: paragraphs, sections, and chunks.

Paragraph IDs do not exist in the source XML — they are assigned
sequentially per work at parse time (see parser.py), making the corpus
its own single source of truth for paragraph identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Region = Literal["front", "body", "back"]


@dataclass(frozen=True)
class PageRef:
    """A page reference resolved during parsing.

    ``number`` is None when the source ``<pb>`` has no ``@n`` — a
    genuinely unnumbered page in the original edition, not an encoding
    gap. In that case ``display`` holds a relational string (e.g.
    "entre les p. 86 et 87") derived from the nearest numbered pages,
    never a fabricated number.
    """

    number: int | None
    display: str


@dataclass
class Paragraph:
    """The atomic unit of the corpus: one ``<p>`` (or verse block)."""

    paragraph_id: str
    work_id: str
    section_id: str
    index: int  # 1-based sequential position within the work
    text: str
    word_count: int
    page_start: PageRef
    page_end: PageRef


@dataclass
class Section:
    """One structural division (``<div>``, or an implicit head-delimited
    block in un-``<div>``-wrapped front/back matter — see parser.py)."""

    section_id: str
    work_id: str
    region: Region
    div_type: str | None
    label: str
    index: int  # 1-based position of this section within the work
    paragraph_ids: list[str] = field(default_factory=list)
    page_start: PageRef | None = None
    page_end: PageRef | None = None


@dataclass
class Work:
    work_id: str
    title: str
    alt_titles: list[str]
    first_pub_date: str
    source_edition_date: str
    source_desc: str
    sections: list[Section] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class Chunk:
    """A retrieval unit: whole, consecutive paragraphs from one section.

    Parent section context (label, path) is looked up by ``section_id``
    at retrieval time, not duplicated into ``text``.
    """

    chunk_id: str
    work_id: str
    section_id: str
    section_path: str
    paragraph_ids: list[str]
    text: str
    word_count: int
    page_start: PageRef
    page_end: PageRef
