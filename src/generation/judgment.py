"""`ChunkJudgment` — the interface contract between `judge_chunks` (its own,
later branch, docs/ROADMAP.md — "on-demand relevance judgment ... per chunk")
and `generate_from_chunks`' consumer side, built this sprint
(docs/ROADMAP.md, Sprint 6).

`judge_chunks` itself does not exist yet. This shape is committed now, ahead
of that branch, so `generate_from_chunks` has something concrete to accept
and so the future `judge_chunks` implementation has a fixed target to
conform to rather than a shape that drifts between the two branches.

A `ChunkJudgment` is keyed by `chunk_id` in the `dict` passed to
`generate_from_chunks(..., chunk_judgments=...)`. It carries a prior human-
or LLM-triggered relevance assessment of one chunk still present in the
caller's chunk selection — not a filtering mechanism itself (the caller may
already have dropped chunks before calling `generate_from_chunks`;
`chunk_judgments` only annotates the chunks still included, so the
generation prompt can factor in that prior assessment as an extra signal
alongside the chunk's own text).
"""

from __future__ import annotations

from typing import Literal, TypedDict

ChunkJudgmentLabel = Literal["pertinent", "partiellement pertinent", "non pertinent"]


class ChunkJudgment(TypedDict):
    label: ChunkJudgmentLabel
    justification: str
