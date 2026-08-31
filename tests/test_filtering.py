"""Unit + integration tests for src/retrieval/filtering.py (docs/ROADMAP.md,
Sprint 11 — chunk retrieval filtering by work and by chronological bounds).

Two tiers, same discipline as tests/test_retrieval.py and tests/test_works.py:

- Pure logic (`eligible_work_ids_publication`, `partition_anthology_works`,
  `effective_chunk_year`, `matches_date_range`, and `filtered_hybrid_search`'s
  empty-filter short-circuit paths) needs neither Qdrant nor the embedding
  models — these run unconditionally.
- `filtered_hybrid_search` end-to-end needs the live `bergson_chunks`
  collection (real corpus, real embedders) — skipped if unreachable, same
  `_qdrant_skip` pattern as tests/test_retrieval.py and tests/test_api.py.

The "L'effort intellectuel" (1902, `1919_ES_p153`-`1919_ES_p203`) fixture
query below is a real chunk's own text (`data/processed/chunks/1919_ES.json`,
chunk `1919_ES_c153`) used as the query — confirmed live to rank that exact
chunk (and only 1919_ES chunks from a spread of its individually-dated
texts) at the top of an unfiltered hybrid_search, which is what makes it
useful for distinguishing "text" mode from "publication" mode: both modes
have real, differently-dated 1919_ES chunks to include or exclude.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from src.indexing.embeddings import DenseEmbedder, SparseEmbedder
from src.indexing.qdrant_index import COLLECTION_NAME
from src.retrieval.filtering import (
    ANTHOLOGY_WORK_IDS,
    AnthologyPartition,
    DateRangeFilter,
    effective_chunk_year,
    eligible_work_ids_publication,
    filtered_hybrid_search,
    matches_date_range,
    partition_anthology_works,
)
from src.retrieval.hybrid import hybrid_search

QDRANT_URL = "http://localhost:6333"


def _collection_populated() -> bool:
    try:
        client = QdrantClient(url=QDRANT_URL)
        if not client.collection_exists(COLLECTION_NAME):
            return False
        return client.count(collection_name=COLLECTION_NAME).count > 0
    except Exception:
        return False


_qdrant_skip = pytest.mark.skipif(
    not _collection_populated(),
    reason="Qdrant not reachable or `bergson_chunks` empty — run `docker compose up qdrant` "
    "and scripts/build_index.py first",
)


@pytest.fixture(scope="module")
def client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


@pytest.fixture(scope="module")
def dense_embedder() -> DenseEmbedder:
    return DenseEmbedder()


@pytest.fixture(scope="module")
def sparse_embedder() -> SparseEmbedder:
    return SparseEmbedder()


# --- pure logic: eligible_work_ids_publication -------------------------------


def test_eligible_work_ids_publication_uses_work_level_year():
    # 1900_R (1900), 1907_EC (1907), 1919_ES (1919) — all three fall in
    # range at the *work* level, including 1919_ES's own anthology year,
    # not any individual text's (its dated texts range 1901-1913, entirely
    # outside this window, but that's irrelevant to "publication" mode).
    eligible = eligible_work_ids_publication(DateRangeFilter(1900, 1920))
    assert eligible == {"1900_R", "1907_EC", "1919_ES"}


def test_eligible_work_ids_publication_excludes_out_of_range_works():
    eligible = eligible_work_ids_publication(DateRangeFilter(1850, 1890))
    assert eligible == {"1888_EDIC"}


# --- pure logic: partition_anthology_works -----------------------------------


def test_partition_fully_excludes_work_with_no_year_in_range():
    # 1934_PM's years (its individually-dated texts plus its own 1934
    # publication year) never include 1919.
    partition = partition_anthology_works(DateRangeFilter(1919, 1919))
    assert "1934_PM" in partition.fully_excluded
    assert "1934_PM" not in partition.fully_included
    assert "1934_PM" not in partition.needs_postfilter


def test_partition_needs_postfilter_when_range_only_covers_work_year():
    # 1919_ES's own publication year (1919) is in range, but none of its
    # individually-dated texts' years (1901-1913) are — some chunks
    # (front-matter-equivalent / directly on the work year) would pass,
    # others (every dated text) would not: a genuine partial case.
    partition = partition_anthology_works(DateRangeFilter(1919, 1919))
    assert "1919_ES" in partition.needs_postfilter


def test_partition_fully_includes_work_when_range_covers_every_text_year():
    # 1919_ES's dated texts span 1901-1913; its own publication year is
    # 1919. A range covering all of it settles the whole work with no
    # post-filtering needed.
    partition = partition_anthology_works(DateRangeFilter(1901, 1919))
    assert "1919_ES" in partition.fully_included


def test_partition_covers_both_anthology_works():
    partition = partition_anthology_works(DateRangeFilter(0, 3000))
    assert isinstance(partition, AnthologyPartition)
    assert partition.fully_included == ANTHOLOGY_WORK_IDS


# --- pure logic: effective_chunk_year / matches_date_range -------------------


def test_effective_chunk_year_uses_text_year_for_dated_text():
    # The example named in this branch's task description: ES_1902_EI ->
    # "L'effort intellectuel", 1902 (src/works.py's TEXTS, also exercised by
    # tests/test_works.py::test_known_example_es_1902_ei).
    assert effective_chunk_year("1919_ES", ["1919_ES_p153"]) == 1902


def test_effective_chunk_year_falls_back_to_work_year_for_front_matter():
    # 1934_PM's dated texts (src.works.TEXTS) start at paragraph 4 — p1-p3
    # are front matter covered by no individually-dated text, so this must
    # fall back to the work's own 1934 publication year rather than being
    # silently excluded or left unresolved.
    assert effective_chunk_year("1934_PM", ["1934_PM_p1"]) == 1934
    assert effective_chunk_year("1934_PM", ["1934_PM_p2"]) == 1934
    assert effective_chunk_year("1934_PM", ["1934_PM_p3"]) == 1934


def test_effective_chunk_year_is_work_year_for_non_anthology_work():
    # No TEXTS entry at all for 1907_EC — resolve_paragraph_metadata always
    # returns text_year=None for it, so this must equal the work-level year.
    assert effective_chunk_year("1907_EC", ["1907_EC_p1"]) == 1907


def test_matches_date_range_distinguishes_text_year_from_work_year():
    chunk = ("1919_ES", ["1919_ES_p153"])  # "L'effort intellectuel", 1902
    assert matches_date_range(*chunk, DateRangeFilter(1902, 1902, "text")) is True
    assert matches_date_range(*chunk, DateRangeFilter(1919, 1919, "text")) is False
    # "publication" mode only ever looks at the work-level year (1919).
    assert matches_date_range(*chunk, DateRangeFilter(1919, 1919, "publication")) is True
    assert matches_date_range(*chunk, DateRangeFilter(1902, 1902, "publication")) is False


# --- pure logic: filtered_hybrid_search's empty-filter short circuit ---------
# These never reach Qdrant (client/embedders are intentionally None below),
# so they run unconditionally — the point is exactly that no query is made.


def test_filtered_hybrid_search_empty_work_ids_short_circuits():
    assert filtered_hybrid_search(None, "q", None, None, limit=10, work_ids=[]) == []


def test_filtered_hybrid_search_no_eligible_publication_year_short_circuits():
    # No work was published in this range at all.
    result = filtered_hybrid_search(
        None, "q", None, None, limit=10, date_range=DateRangeFilter(1, 100, "publication")
    )
    assert result == []


def test_filtered_hybrid_search_contradictory_filters_short_circuit():
    # work_ids names a real work, but date_range excludes it entirely —
    # the intersection is empty, same as any other "no eligible work_id"
    # case: no query is made, no error is raised.
    result = filtered_hybrid_search(
        None,
        "q",
        None,
        None,
        limit=10,
        work_ids=["1907_EC"],
        date_range=DateRangeFilter(1919, 1919, "publication"),
    )
    assert result == []


# --- integration: "publication" mode (default) — unchanged behavior ---------

Q002_QUERY = (
    "Quelle thèse Bergson explique-t-il à travers l'image de la fonte d'un morceau de "
    "sucre dans un verre d'eau ?"
)
# Confirmed live against the current (paragraph-per-chunk) index — see
# eval/gold_dataset.csv's Q002 row (paragraph_ids 1907_EC_p25, 1907_EC_p398,
# 1934_PM_p16), which these chunk_ids are the direct paragraph-chunked
# equivalent of.
Q002_GOLD_CHUNK_IDS = frozenset({"1907_EC_c25", "1907_EC_c398", "1934_PM_c16"})


@_qdrant_skip
def test_no_filter_matches_unfiltered_hybrid_search(client, dense_embedder, sparse_embedder):
    """`work_ids` and `date_range` both absent must be exactly equivalent to
    a plain `hybrid_search` call — the "existing/default behavior is
    unaffected" guarantee (docs/ROADMAP.md)."""
    plain = hybrid_search(client, Q002_QUERY, dense_embedder, sparse_embedder, limit=10)
    filtered = filtered_hybrid_search(client, Q002_QUERY, dense_embedder, sparse_embedder, limit=10)
    assert [c.chunk_id for c in filtered] == [c.chunk_id for c in plain]
    assert [c.score for c in filtered] == [c.score for c in plain]


@_qdrant_skip
def test_single_work_id_filter_restricts_to_that_work(client, dense_embedder, sparse_embedder):
    result = filtered_hybrid_search(
        client, Q002_QUERY, dense_embedder, sparse_embedder, limit=10, work_ids=["1907_EC"]
    )
    assert result
    assert {c.work_id for c in result} == {"1907_EC"}
    assert {c.chunk_id for c in result} & Q002_GOLD_CHUNK_IDS


@_qdrant_skip
def test_publication_date_range_excludes_later_works(client, dense_embedder, sparse_embedder):
    """A range covering 1907_EC (1907) but not 1934_PM (1934) must exclude
    every 1934_PM chunk, even though 1934_PM has a real gold chunk for this
    query (1934_PM_c16, Q002_GOLD_CHUNK_IDS above)."""
    result = filtered_hybrid_search(
        client,
        Q002_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        date_range=DateRangeFilter(1900, 1910, "publication"),
    )
    assert result
    assert "1934_PM" not in {c.work_id for c in result}
    assert {c.chunk_id for c in result} & Q002_GOLD_CHUNK_IDS


# --- integration: "text" mode, 1919_ES's "L'effort intellectuel" (1902) ----

# The opening sentence of 1919_ES_c153 itself (data/processed/chunks/
# 1919_ES.json) — using a chunk's own text as the query reliably surfaces
# that exact chunk plus a spread of other 1919_ES chunks from several of
# its individually-dated texts (confirmed live), which is what lets this
# query distinguish "text" mode from "publication" mode below.
EFFORT_INTELLECTUEL_QUERY = (
    "Le problème que nous abordons ici est distinct du problème de l'attention, "
    "tel que le pose la psychologie contemporaine."
)
EFFORT_INTELLECTUEL_CHUNK_ID = "1919_ES_c153"  # "L'effort intellectuel", 1902


@_qdrant_skip
def test_text_mode_range_covering_only_the_text_year_includes_it(
    client, dense_embedder, sparse_embedder
):
    result = filtered_hybrid_search(
        client,
        EFFORT_INTELLECTUEL_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1919_ES"],
        date_range=DateRangeFilter(1902, 1902, "text"),
    )
    assert EFFORT_INTELLECTUEL_CHUNK_ID in {c.chunk_id for c in result}


@_qdrant_skip
def test_text_mode_range_covering_only_work_year_excludes_the_earlier_text(
    client, dense_embedder, sparse_embedder
):
    """The test that actually distinguishes "text" from "publication" mode
    (docs/ROADMAP.md): a range covering 1919_ES's own publication year
    (1919) but not "L'effort intellectuel"'s actual year (1902) must
    exclude that text's chunks under "text" mode, and correctly include
    them under "publication" mode — same query, same range, only `mode`
    differs."""
    text_mode = filtered_hybrid_search(
        client,
        EFFORT_INTELLECTUEL_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1919_ES"],
        date_range=DateRangeFilter(1919, 1919, "text"),
    )
    publication_mode = filtered_hybrid_search(
        client,
        EFFORT_INTELLECTUEL_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1919_ES"],
        date_range=DateRangeFilter(1919, 1919, "publication"),
    )
    assert EFFORT_INTELLECTUEL_CHUNK_ID not in {c.chunk_id for c in text_mode}
    assert EFFORT_INTELLECTUEL_CHUNK_ID in {c.chunk_id for c in publication_mode}


@_qdrant_skip
def test_text_mode_excludes_a_different_dated_text_in_the_same_work(
    client, dense_embedder, sparse_embedder
):
    """A range covering only 1902 ("L'effort intellectuel") must exclude
    chunks from other individually-dated texts within the SAME work
    (1919_ES) that an unfiltered/publication-mode call would surface —
    confirmed live: this query's publication-mode results include chunks
    from "Le souvenir du présent..." (1908, paragraphs 101-152) and
    "'Fantômes de vivants'..." (1913, paragraphs 48-68)."""
    result = filtered_hybrid_search(
        client,
        EFFORT_INTELLECTUEL_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1919_ES"],
        date_range=DateRangeFilter(1902, 1902, "text"),
    )
    assert result
    for chunk in result:
        paragraph_index = int(chunk.paragraph_ids[0].split("_p")[-1])
        assert 153 <= paragraph_index <= 203, (
            f"{chunk.chunk_id} ({chunk.paragraph_ids}) falls outside 'L'effort "
            "intellectuel''s paragraph range (153-203) but was not excluded by "
            "date_range=[1902,1902] mode='text'"
        )


@_qdrant_skip
def test_text_mode_preserves_requested_top_n_via_overfetch(client, dense_embedder, sparse_embedder):
    """Regression test for the recall-loss risk named in docs/ROADMAP.md:
    filtering "text" mode candidates after Qdrant's own top-N cutoff could
    silently shrink the result set below the requested top_k. Confirmed
    live that this query's top ~50+ fused candidates over 1919_ES contain
    well more than 10 chunks from "L'effort intellectuel" (paragraphs
    153-203) alone, so a full top_k=10 must come back — not fewer — thanks
    to the over-fetch/truncate mechanism (ANTHOLOGY_OVERFETCH_FACTOR)."""
    result = filtered_hybrid_search(
        client,
        EFFORT_INTELLECTUEL_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1919_ES"],
        date_range=DateRangeFilter(1902, 1902, "text"),
    )
    assert len(result) == 10


# --- integration: "text" mode, non-anthology work — regression check --------


@_qdrant_skip
def test_text_mode_matches_publication_mode_for_non_anthology_work(
    client, dense_embedder, sparse_embedder
):
    """1907_EC has no individually-dated text at all (no `src.works.TEXTS`
    entry) — "text" mode must behave identically to "publication" mode for
    it, not just approximately: no accidental behavior change for the 6
    works that don't have text-level dates."""
    wide_range = DateRangeFilter(1850, 1950)
    publication_mode = filtered_hybrid_search(
        client,
        Q002_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1907_EC"],
        date_range=DateRangeFilter(1850, 1950, "publication"),
    )
    text_mode = filtered_hybrid_search(
        client,
        Q002_QUERY,
        dense_embedder,
        sparse_embedder,
        limit=10,
        work_ids=["1907_EC"],
        date_range=DateRangeFilter(wide_range.start, wide_range.end, "text"),
    )
    assert [c.chunk_id for c in text_mode] == [c.chunk_id for c in publication_mode]
    assert [c.score for c in text_mode] == [c.score for c in publication_mode]
