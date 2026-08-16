#!/usr/bin/env python3
"""Ad-hoc CLI to run the full retrieval + reranking + generation pipeline
against a live Qdrant index end-to-end, from a single query string.

Hybrid (dense BGE-M3 + sparse BM25, RRF-fused) retrieval
(src/retrieval/hybrid.py) -> cross-encoder reranking
(src/retrieval/reranking.py) -> evidence-conditioned LLM synthesis
(src/generation/generate.py), then prints the retrieved evidence and the
generated answer. For manual testing/inspection only — not used by the
indexing, ingestion, retrieval, or generation pipelines themselves.

Usage:
    scripts/query_pipeline.py "la duree et la memoire"
    scripts/query_pipeline.py "duree memoire" -k 5 --model anthropic/claude-haiku-4-5

Requires Qdrant running with the collection already built
(scripts/build_index.py), and a reachable LLM (Ollama running locally with
the default model pulled, or MISTRAL_API_KEY / BERGSON_LLM_FALLBACK_MODEL
set — see docs/generation_strategy.md).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qdrant_client import QdrantClient  # noqa: E402

from src.generation.generate import (  # noqa: E402
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    generate_from_chunks,
)
from src.generation.signals import GenerationChunk  # noqa: E402
from src.indexing.embeddings import DenseEmbedder, SparseEmbedder  # noqa: E402
from src.indexing.qdrant_index import COLLECTION_NAME  # noqa: E402
from src.retrieval.hybrid import DEFAULT_PREFETCH_LIMIT, hybrid_search  # noqa: E402
from src.retrieval.reranking import (  # noqa: E402
    DEFAULT_RERANK_CANDIDATES,
    CrossEncoderReranker,
    RerankedChunk,
    rerank,
)

QDRANT_URL = "http://localhost:6333"
SNIPPET_LENGTH = 300
DEFAULT_LIMIT = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full retrieval + reranking + generation pipeline on a single query."
    )
    parser.add_argument("query", help="Query text.")
    parser.add_argument(
        "-k",
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            f"Number of reranked chunks to pass to the LLM as evidence (default: {DEFAULT_LIMIT})."
        ),
    )
    parser.add_argument(
        "--prefetch-limit",
        type=int,
        default=DEFAULT_PREFETCH_LIMIT,
        help=(
            "Per-pipeline (dense/sparse) candidate pool size before RRF fusion "
            f"(default: {DEFAULT_PREFETCH_LIMIT})."
        ),
    )
    parser.add_argument(
        "--rerank-candidates",
        type=int,
        default=DEFAULT_RERANK_CANDIDATES,
        help=f"Candidate pool size passed to the reranker (default: {DEFAULT_RERANK_CANDIDATES}).",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip reranking and generate directly from the hybrid retrieval output.",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"LiteLLM model string (default: {DEFAULT_MODEL})."
    )
    parser.add_argument(
        "--fallback-model",
        default=None,
        help=(
            "LiteLLM model string used if --model fails "
            f"(default: $BERGSON_LLM_FALLBACK_MODEL or {DEFAULT_FALLBACK_MODEL})."
        ),
    )
    parser.add_argument(
        "--collection",
        default=COLLECTION_NAME,
        help=f"Collection name (default: {COLLECTION_NAME}).",
    )
    parser.add_argument(
        "--qdrant-url", default=QDRANT_URL, help=f"Qdrant URL (default: {QDRANT_URL})."
    )
    parser.add_argument(
        "--full", action="store_true", help="Print each chunk's full text instead of a snippet."
    )
    parser.add_argument(
        "--show-prompt", action="store_true", help="Also print the full prompt sent to the LLM."
    )
    return parser.parse_args()


def format_page_range(page_start: dict, page_end: dict) -> str:
    start, end = page_start["display"], page_end["display"]
    return start if start == end else f"{start}-{end}"


def snippet(text: str, length: int = SNIPPET_LENGTH) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if len(collapsed) <= length else collapsed[:length].rstrip() + "..."


def print_evidence(chunks: list[GenerationChunk], full: bool) -> None:
    print(f"=== Evidence ({len(chunks)} chunk(s)) ===\n")
    for rank_no, chunk in enumerate(chunks, start=1):
        pages = format_page_range(chunk.page_start, chunk.page_end)
        header = f"{chunk.work_id}  {chunk.section_path}  p. {pages}"
        if isinstance(chunk, RerankedChunk):
            score = f"rerank_score={chunk.rerank_score:.4f}  rrf_score={chunk.rrf_score:.4f}"
        else:
            score = f"score={chunk.score:.4f}"
        print(f"[{rank_no}] {score}  {header}")
        print(f"    chunk_id={chunk.chunk_id}")
        print(f"    {chunk.text if full else snippet(chunk.text)}")
        print()


def main() -> None:
    args = parse_args()
    client = QdrantClient(url=args.qdrant_url)

    retrieve_limit = args.limit if args.no_rerank else max(args.limit, args.rerank_candidates)
    retrieved = hybrid_search(
        client,
        args.query,
        dense_embedder=DenseEmbedder(),
        sparse_embedder=SparseEmbedder(),
        limit=retrieve_limit,
        prefetch_limit=args.prefetch_limit,
        collection_name=args.collection,
    )

    chunks: list[GenerationChunk]
    if args.no_rerank:
        chunks = list(retrieved[: args.limit])
    else:
        chunks = rerank(args.query, retrieved, CrossEncoderReranker())[: args.limit]

    if not chunks:
        print("No results.")
        return

    print_evidence(chunks, args.full)

    result = generate_from_chunks(
        args.query,
        chunks,
        client,
        model=args.model,
        fallback_model=args.fallback_model,
    )

    if args.show_prompt:
        print("=== Prompt ===\n")
        print(result.prompt)
        print()

    signals = result.signals
    print("=== Signals ===\n")
    print(
        f"works={list(signals.works)}  "
        f"convergence={signals.convergence}  is_convergent={signals.is_convergent}  "
        f"rerank_cv={signals.rerank_cv}  is_confident={signals.is_confident}"
    )
    print()

    print(f"=== Answer (model={result.model}) ===\n")
    print(result.answer)


if __name__ == "__main__":
    main()
