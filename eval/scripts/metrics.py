"""Retrieval-only metrics for the gold dataset: recall@k and MRR, plus
breakdowns by category / vocabulary_type / difficulty / query_style
(docs/ROADMAP.md, Sprint 3 — "First retrieval-only evaluation").

Ground truth handling: `ground_truth_type=multi` means "at least one of
this item's chunk_ids is enough" (OR semantics) — never "all required"
(AND). docs/gold_dataset_protocol.md: "a set of chunk_ids, any one of
which counts as a correct retrieval."

Breakdown groups are built unconditionally, even though the current
gold dataset has very few annotated items per group (see
eval/scripts/run_eval.py) — the code should not need rewriting once
annotation grows past the current small sample.
"""

from __future__ import annotations

from dataclasses import dataclass

RECALL_KS = (1, 3, 5, 10)
BREAKDOWN_ATTRS = ("category", "vocabulary_type", "difficulty", "query_style", "footnote_related")


@dataclass(frozen=True)
class GoldItem:
    id: str
    category: str
    query: str
    query_style: str
    ground_truth_type: str
    chunk_ids: tuple[str, ...]
    vocabulary_type: str
    difficulty: str
    footnote_related: str


@dataclass(frozen=True)
class ItemResult:
    item: GoldItem
    rank: int | None  # 1-based rank of the first matching chunk_id; None if not found


def hit_rank(retrieved_chunk_ids: list[str], gold_chunk_ids: tuple[str, ...]) -> int | None:
    """Rank of the first retrieved chunk that is any one of
    `gold_chunk_ids` (OR semantics), or None if none of them appear."""
    gold_set = set(gold_chunk_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in gold_set:
            return rank
    return None


def score_item(item: GoldItem, retrieved_chunk_ids: list[str]) -> ItemResult:
    return ItemResult(item=item, rank=hit_rank(retrieved_chunk_ids, item.chunk_ids))


def _recall_at_k(results: list[ItemResult], k: int) -> float:
    if not results:
        return 0.0
    return sum(1 for r in results if r.rank is not None and r.rank <= k) / len(results)


def _mrr(results: list[ItemResult]) -> float:
    if not results:
        return 0.0
    return sum(0.0 if r.rank is None else 1.0 / r.rank for r in results) / len(results)


def aggregate(results: list[ItemResult], ks: tuple[int, ...] = RECALL_KS) -> dict:
    metrics = {f"recall@{k}": _recall_at_k(results, k) for k in ks}
    metrics["mrr"] = _mrr(results)
    metrics["n"] = len(results)
    return metrics


def breakdown_by(
    results: list[ItemResult], attr: str, ks: tuple[int, ...] = RECALL_KS
) -> dict[str, dict]:
    groups: dict[str, list[ItemResult]] = {}
    for result in results:
        groups.setdefault(getattr(result.item, attr), []).append(result)
    return {value: aggregate(group, ks) for value, group in sorted(groups.items())}


def full_report(results: list[ItemResult], ks: tuple[int, ...] = RECALL_KS) -> dict:
    return {
        "overall": aggregate(results, ks),
        "by": {attr: breakdown_by(results, attr, ks) for attr in BREAKDOWN_ATTRS},
    }
