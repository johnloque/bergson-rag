"""Chunk retrieval filtering by work_id and by chronological bounds
(docs/ROADMAP.md, Sprint 11).

Two independent, combinable filter dimensions, both resolved via lookups
into `src.works` at query time rather than by adding a new Qdrant payload
field: this project has deliberately kept title/year as a separate lookup
(`src/works.py`), never duplicated into the vector store, to avoid a second
source of truth that would need resyncing on any correction. Same reasoning
applies here — year is never written into the Qdrant payload, for either
date mode below.

- `work_ids`: a plain allowlist, applied as a native Qdrant payload filter
  on the already-indexed `work_id` field (`src.indexing.qdrant_index.
  PAYLOAD_FIELDS`).
- `date_range`, mode `"publication"` (default): translated into the set of
  work_ids whose *work-level* publication year (`src.works.WORKS`, identical
  for all 8 works, including 1919_ES/1934_PM — their parent-work year, not
  any individual text's) falls in range, then applied the same way as
  `work_ids` — a native, pre-rerank, exact Qdrant filter. No recall loss:
  Qdrant itself decides the eligible set before dense/sparse search even
  runs.
- `date_range`, mode `"text"`: for 1919_ES and 1934_PM specifically, needs
  each candidate chunk's *individually-dated text* year
  (`src.works.resolve_paragraph_metadata`), which cannot be expressed as a
  single Qdrant payload filter without duplicating year data into the
  payload (ruled out above). Handled as a genuine post-retrieval filter —
  see `filtered_hybrid_search` below for how recall is preserved despite
  filtering after Qdrant's own top-N cutoff.

`work_ids` and `date_range` combine as an intersection: a chunk must belong
to both an allowed work_id (if given) and an allowed date range (if given).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qdrant_client import QdrantClient, models

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.retrieval.hybrid import DEFAULT_PREFETCH_LIMIT, RetrievedChunk, hybrid_search
from src.works import TEXTS, WORKS, resolve_paragraph_metadata

ANTHOLOGY_WORK_IDS: frozenset[str] = frozenset(TEXTS.keys())  # {"1919_ES", "1934_PM"}

# How much larger than the requested candidate limit to fetch, Qdrant-side,
# for an anthology work that a "text"-mode date_range can't already settle
# at the work level (see `partition_anthology_works` — the "needs_postfilter"
# case: the range excludes some but not all of that work's individually-
# dated texts). Chosen generously rather than tuned against a specific
# corpus size: even 1934_PM's 10 individually-dated texts (`src.works.TEXTS`)
# could in principle all rank inside the pipeline's native top candidates,
# and post-filtering down to whichever ones match the range must still leave
# up to the originally-requested candidate_limit standing. 5x reliably
# covers that for this corpus (1934_PM is 311 chunks total, 1919_ES 230);
# capped so a large top_k request can't make the over-fetch unbounded.
ANTHOLOGY_OVERFETCH_FACTOR = 5
ANTHOLOGY_OVERFETCH_CAP = 200


@dataclass(frozen=True)
class DateRangeFilter:
    start: int
    end: int
    mode: Literal["publication", "text"] = "publication"


def _work_year_in_range(work_id: str, date_range: DateRangeFilter) -> bool:
    metadata = WORKS.get(work_id)
    return metadata is not None and date_range.start <= metadata.year <= date_range.end


def eligible_work_ids_publication(date_range: DateRangeFilter) -> set[str]:
    """work_ids whose *work-level* publication year falls in range —
    "publication" mode's only notion of date, and also what "text" mode
    uses for the 6 non-anthology works (which have no individual-text
    dates at all)."""
    return {work_id for work_id in WORKS if _work_year_in_range(work_id, date_range)}


def _anthology_effective_years(work_id: str) -> set[int]:
    """Every distinct year a chunk of `work_id` can resolve to under "text"
    mode: each individually-dated text's own year, plus the work's
    publication year (the fallback for any paragraph not covered by a dated
    text, e.g. 1934_PM's front matter, paragraphs 1-3 — see
    `src.works.TEXTS`)."""
    years = {text.year for text in TEXTS.get(work_id, ())}
    metadata = WORKS.get(work_id)
    if metadata is not None:
        years.add(metadata.year)
    return years


@dataclass(frozen=True)
class AnthologyPartition:
    """How a "text"-mode `date_range` settles each of the two anthology
    works: `fully_included`/`fully_excluded` need no post-retrieval
    filtering at all (every chunk's effective year is already known to be
    in/out of range), so they can go through the same cheap native Qdrant
    path as any other work_id. `needs_postfilter` is the only case that
    actually needs `filtered_hybrid_search`'s over-fetch mechanism."""

    fully_included: frozenset[str]
    fully_excluded: frozenset[str]
    needs_postfilter: frozenset[str]


def partition_anthology_works(date_range: DateRangeFilter) -> AnthologyPartition:
    included: set[str] = set()
    excluded: set[str] = set()
    partial: set[str] = set()
    for work_id in ANTHOLOGY_WORK_IDS:
        years = _anthology_effective_years(work_id)
        in_range = {year for year in years if date_range.start <= year <= date_range.end}
        if in_range == years:
            included.add(work_id)
        elif not in_range:
            excluded.add(work_id)
        else:
            partial.add(work_id)
    return AnthologyPartition(frozenset(included), frozenset(excluded), frozenset(partial))


def effective_chunk_year(work_id: str, paragraph_ids: list[str]) -> int | None:
    """A chunk's "text"-mode year: its individually-dated text's year if its
    paragraph(s) fall inside one (1919_ES/1934_PM only), else the work's
    publication year. Chunking is paragraph-granular and a chunk never
    straddles two dated texts (`src/works.py`'s module docstring, verified
    by `tests/test_works.py::test_no_chunk_straddles_two_qualifying_divs`),
    so resolving off the chunk's first paragraph_id is equivalent to
    resolving every paragraph_id it carries."""
    if not paragraph_ids:
        metadata = WORKS.get(work_id)
        return metadata.year if metadata is not None else None
    resolved = resolve_paragraph_metadata(work_id, paragraph_ids[0])
    return resolved.text_year if resolved.text_year is not None else resolved.work_year


def matches_date_range(work_id: str, paragraph_ids: list[str], date_range: DateRangeFilter) -> bool:
    """Whether a chunk falls in `date_range`, honoring its `mode`: this is
    the general-purpose predicate (used directly by unit tests and
    available for any future caller), distinct from `effective_chunk_year`
    which always resolves the "text"-mode year regardless of mode.
    `filtered_hybrid_search` below never calls this in "publication" mode
    itself (that mode is handled entirely by the native Qdrant work_id
    filter, cheaper and never needing a per-chunk resolution) — it's only
    ever invoked for "text" mode's post-retrieval filtering."""
    if date_range.mode == "publication":
        metadata = WORKS.get(work_id)
        year = metadata.year if metadata is not None else None
    else:
        year = effective_chunk_year(work_id, paragraph_ids)
    return year is not None and date_range.start <= year <= date_range.end


def _work_id_filter(work_ids: set[str]) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="work_id", match=models.MatchAny(any=sorted(work_ids)))]
    )


def filtered_hybrid_search(
    client: QdrantClient,
    query: str,
    dense_embedder: DenseEmbedder,
    sparse_embedder: SparseEmbedder,
    limit: int,
    work_ids: list[str] | None = None,
    date_range: DateRangeFilter | None = None,
    prefetch_limit: int = DEFAULT_PREFETCH_LIMIT,
) -> list[RetrievedChunk]:
    """`hybrid_search`, extended with `work_ids`/`date_range` filtering
    (docs/ROADMAP.md, Sprint 11 — see this module's docstring for the
    semantics of each). Always returns at most `limit` chunks, sorted the
    same way `hybrid_search` itself sorts (fused score desc, chunk_id asc
    tie-break) — a drop-in replacement for a plain `hybrid_search` call at
    the call site (`src/api/main.py`'s `/retrieve`), still run *before*
    reranking either way.

    No filter given (`work_ids` and `date_range` both None) delegates to
    `hybrid_search` unchanged — existing/default behavior is unaffected. An
    explicit `work_ids=[]` is not the same as `work_ids=None`: an empty
    allowlist matches nothing (short-circuits to `[]` below, same as any
    other "no eligible work_id" case), where `None` means "no work_id
    restriction" — so the truthiness check must be `is not None`, not a
    plain `if work_ids`.
    """
    requested_work_ids = set(work_ids) if work_ids is not None else None

    if date_range is None:
        if requested_work_ids is None:
            return hybrid_search(
                client, query, dense_embedder, sparse_embedder, limit, prefetch_limit
            )
        if not requested_work_ids:
            return []
        return hybrid_search(
            client,
            query,
            dense_embedder,
            sparse_embedder,
            limit,
            prefetch_limit,
            query_filter=_work_id_filter(requested_work_ids),
        )

    if date_range.mode == "publication":
        eligible = eligible_work_ids_publication(date_range)
        if requested_work_ids is not None:
            eligible &= requested_work_ids
        if not eligible:
            return []
        return hybrid_search(
            client,
            query,
            dense_embedder,
            sparse_embedder,
            limit,
            prefetch_limit,
            query_filter=_work_id_filter(eligible),
        )

    # mode == "text": non-anthology works filter exactly like "publication"
    # mode (they have no individual-text dates — resolve_paragraph_metadata
    # always returns text_year=None for them, so their effective year is
    # always the work-level year anyway). The two anthology works are
    # partitioned into settled (fully in/out of range, foldable into the
    # same native filter) vs. needing the post-retrieval over-fetch path.
    partition = partition_anthology_works(date_range)
    non_anthology_eligible = {
        work_id
        for work_id in eligible_work_ids_publication(date_range)
        if work_id not in ANTHOLOGY_WORK_IDS
    }
    settled_eligible = non_anthology_eligible | set(partition.fully_included)
    partial_eligible = set(partition.needs_postfilter)
    if requested_work_ids is not None:
        settled_eligible &= requested_work_ids
        partial_eligible &= requested_work_ids

    results: list[RetrievedChunk] = []
    if settled_eligible:
        results.extend(
            hybrid_search(
                client,
                query,
                dense_embedder,
                sparse_embedder,
                limit,
                prefetch_limit,
                query_filter=_work_id_filter(settled_eligible),
            )
        )

    if partial_eligible:
        overfetch_limit = min(limit * ANTHOLOGY_OVERFETCH_FACTOR, ANTHOLOGY_OVERFETCH_CAP)
        candidates = hybrid_search(
            client,
            query,
            dense_embedder,
            sparse_embedder,
            limit=overfetch_limit,
            prefetch_limit=max(prefetch_limit, overfetch_limit),
            query_filter=_work_id_filter(partial_eligible),
        )
        results.extend(
            chunk
            for chunk in candidates
            if matches_date_range(chunk.work_id, chunk.paragraph_ids, date_range)
        )

    if not results:
        return []
    results.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
    return results[:limit]
