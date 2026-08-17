"""Unit tests for eval/scripts/metrics.py — pure functions, no Qdrant or
gold dataset required."""

from __future__ import annotations

from eval.scripts.metrics import GoldItem, aggregate, breakdown_by, hit_rank, score_item

ITEM_SINGLE = GoldItem(
    id="Q1",
    category="factuel",
    query="q1",
    query_style="framed",
    ground_truth_type="single",
    chunk_ids=("a_c1",),
    expected_anwser="expected answer 1",
    vocabulary_type="bergsonien",
    difficulty="facile",
    footnote_related="non",
)

ITEM_MULTI = GoldItem(
    id="Q2",
    category="définitionnel",
    query="q2",
    query_style="keyword",
    ground_truth_type="multi",
    chunk_ids=("b_c1", "b_c2"),
    expected_anwser="expected answer 2",
    vocabulary_type="moderne",
    difficulty="moyen",
    footnote_related="oui",
)


def test_hit_rank_returns_first_matching_position():
    assert hit_rank(["x", "y", "a_c1", "z"], ("a_c1",)) == 3


def test_hit_rank_none_when_no_match():
    assert hit_rank(["x", "y"], ("a_c1",)) is None


def test_hit_rank_multi_ground_truth_is_or_not_and():
    """Only one of several chunk_ids needs to appear — never both."""
    assert hit_rank(["x", "b_c2"], ("b_c1", "b_c2")) == 2
    assert hit_rank(["b_c1", "x"], ("b_c1", "b_c2")) == 1


def test_score_item_and_aggregate_recall_and_mrr():
    result_hit = score_item(ITEM_SINGLE, ["a_c1", "other"])
    result_miss = score_item(ITEM_MULTI, ["x", "y"])
    metrics = aggregate([result_hit, result_miss])

    assert metrics["n"] == 2
    assert metrics["recall@1"] == 0.5
    assert metrics["recall@10"] == 0.5
    assert metrics["mrr"] == 0.5


def test_breakdown_by_groups_by_attribute():
    result_hit = score_item(ITEM_SINGLE, ["a_c1"])
    result_miss = score_item(ITEM_MULTI, ["x"])
    grouped = breakdown_by([result_hit, result_miss], "category")

    assert grouped["factuel"]["n"] == 1
    assert grouped["factuel"]["recall@1"] == 1.0
    assert grouped["définitionnel"]["n"] == 1
    assert grouped["définitionnel"]["recall@1"] == 0.0
