"""Deterministic segmentation of a generated answer into sentence-level
segments — the unit the UI colors and makes clickable, and the unit every
faithfulness claim is anchored to (`src/generation/faithfulness.py`).

Two levels, two mechanisms: segments are cut here, by code, with no LLM
involved; claims (atomic, pronoun-free reformulations) are still produced by
the judge LLM, which only reports *which segment* each claim comes from. A
segment yields zero, one or several claims; a claim belongs to exactly one
segment.

## Blocks first, then sentences

The answer is Markdown. It is first cut into blocks (paragraphs, list items,
blockquotes), then each block into sentences — so a segment never spans two
block-level elements, which the frontend could not highlight as one span.
Headings are skipped entirely: they assert nothing.

## Why a hand-written splitter, not pysbd or spaCy's sentencizer

Both were tried against this project's actual answer shape (French prose
with inline `[chunk_id]` citations, `CITATION_INSTRUCTION` in
`src/generation/prompt.py`) and both failed on common cases: pysbd splits
after `p.` and `ch.` (`cf. p. 42`, `ch. III`) and misses a split after `…`;
spaCy's rule-based sentencizer misses a split after `[1889_DI_c3].` and
splits a trailing `[1907_EC_c5]` citation in half. The rules below cover the
cases that actually occur, and a citation placed after the final period
(`... idée. [1907_EC_c5] Pourquoi ?`) stays attached to the sentence it
cites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.generation.prompt import CITATION_PATTERN


@dataclass(frozen=True)
class Segment:
    """One sentence of the answer. `start`/`end` are character offsets into
    the original answer string (`answer[start:end] == text`)."""

    id: int
    text: str
    start: int
    end: int


# A line that starts a new block on its own: a list item (`-`, `*`, `+`, or
# `1.` / `1)`) or a blockquote (`>`). The marker itself is excluded from the
# segment text.
_BLOCK_MARKER = re.compile(r"\s*(?:[-*+]\s+|\d+[.)]\s+|>\s?)")
_HEADING = re.compile(r"\s*#{1,6}\s")

# Sentence-final punctuation, then optional closing quotes/brackets (French
# typography allows a space before `»`), then any `[chunk_id]` citations
# placed after the period — all kept in the sentence that ends here. A split
# only happens if whitespace and a sentence-initial character follow.
_SENTENCE_END = re.compile(r"[.!?…]+(?:\s?[»”\"')])*(?:\s*\[[^\[\]]+\])*(?=\s+[«“\"(A-ZÀ-ÖØ-ÞŒ])")
_PRECEDING_WORD = re.compile(r"(\w+)$")

# Abbreviations that end in a period without ending the sentence. Single
# letters (initials, `M.`, `t.`, `s.`) are handled separately.
_ABBREVIATIONS = frozenset(
    {
        "art", "av", "cf", "ch", "chap", "cit", "coll", "dr", "éd", "ed", "env",
        "fig", "ibid", "id", "mlle", "mm", "mme", "no", "op", "pp", "sq", "sqq",
        "st", "trad", "vol",
    }
)  # fmt: skip


def segment_answer(answer: str) -> tuple[Segment, ...]:
    segments: list[Segment] = []
    for block_start, block_end in _blocks(answer):
        for start, end in _sentences(answer, block_start, block_end):
            text = answer[start:end]
            if not re.search(r"\w", CITATION_PATTERN.sub("", text)):
                continue  # citations or punctuation only — nothing to judge
            segments.append(Segment(id=len(segments), text=text, start=start, end=end))
    return tuple(segments)


def _blocks(answer: str) -> list[tuple[int, int]]:
    """(start, end) offsets of each block's content, markers excluded."""
    blocks: list[list[int]] = []
    in_block = False
    offset = 0
    for line in answer.splitlines(keepends=True):
        line_start, offset = offset, offset + len(line)
        content = line.rstrip("\r\n")
        line_end = line_start + len(content)
        if not content.strip() or _HEADING.match(content):
            in_block = False
            continue
        marker = _BLOCK_MARKER.match(content)
        if marker is not None or not in_block:
            blocks.append([line_start + (marker.end() if marker else 0), line_end])
            in_block = True
        else:
            blocks[-1][1] = line_end  # continuation line of the current block
    return [(start, end) for start, end in blocks]


def _sentences(answer: str, block_start: int, block_end: int) -> list[tuple[int, int]]:
    block = answer[block_start:block_end]
    spans: list[tuple[int, int]] = []
    sentence_start = 0
    for match in _SENTENCE_END.finditer(block):
        if _is_abbreviation(block, match):
            continue
        spans.append((sentence_start, match.end()))
        sentence_start = match.end()
    spans.append((sentence_start, len(block)))
    return [
        _strip(answer, block_start + start, block_start + end)
        for start, end in spans
        if block[start:end].strip()
    ]


def _is_abbreviation(block: str, match: re.Match[str]) -> bool:
    if not match.group().startswith(".") or match.group().startswith(".."):
        return False
    word = _PRECEDING_WORD.search(block[: match.start()])
    if word is None:
        return False
    token = word.group(1)
    return (len(token) == 1 and token.isalpha()) or token.lower() in _ABBREVIATIONS


def _strip(answer: str, start: int, end: int) -> tuple[int, int]:
    while start < end and answer[start].isspace():
        start += 1
    while end > start and answer[end - 1].isspace():
        end -= 1
    return start, end
