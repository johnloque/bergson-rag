#!/usr/bin/env python3
"""End-to-end smoke test against a running stack (docs/ROADMAP.md, Sprint 9).

Exercises /retrieve -> /generate for gold-dataset query Q002
(eval/gold_dataset.csv) through the api container's published port,
confirming the whole chain -- corpus fetch, indexing, all four services,
pulled model -- actually works together, not just that each piece works
in isolation.

Usage: uv run python scripts/smoke_test.py
Requires: `make quickstart` (or an equivalent already-running stack)
complete -- the api reachable at BERGSON_API_BASE (default
http://localhost:8000) with an indexed corpus and a pulled model.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("BERGSON_API_BASE", "http://localhost:8000")

# Same query/gold chunk_ids as tests/test_api.py's Q002 fixture
# (eval/gold_dataset.csv, ground_truth_type "multi" -- any one of the
# three chunk_ids suffices as evidence).
Q002_QUERY = (
    "Quelle thèse Bergson explique-t-il à travers l'image de la fonte d'un "
    "morceau de sucre dans un verre d'eau ?"
)
Q002_GOLD_CHUNK_IDS = {"1907_EC_c9", "1907_EC_c163", "1934_PM_c6"}


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # CPU-only reranking/generation (docs/ROADMAP.md's CPU-only Ollama
        # note applies equally to the in-process cross-encoder reranker)
        # can genuinely take several minutes on modest hardware, especially
        # on a cold first call before models are resident in memory.
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"FAIL: {path} returned HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"FAIL: could not reach {API_BASE}{path} ({exc.reason}) -- is the stack up?")


def main() -> None:
    print(f"Retrieving against {API_BASE} for Q002...")
    retrieve_response = _post("/retrieve", {"query": Q002_QUERY, "top_k": 5})
    turn_id = retrieve_response["turn_id"]
    chunks = retrieve_response["chunks"]
    if not chunks:
        sys.exit("FAIL: /retrieve returned no chunks for Q002 -- is the corpus indexed?")

    retrieved_ids = {c["chunk_id"] for c in chunks}
    matched_gold = retrieved_ids & Q002_GOLD_CHUNK_IDS
    if not matched_gold:
        sys.exit(
            f"FAIL: none of the gold chunk_ids {sorted(Q002_GOLD_CHUNK_IDS)} were retrieved "
            f"(got {sorted(retrieved_ids)}) -- indexing likely incomplete or against the wrong "
            "corpus"
        )
    print(f"  retrieved gold chunk(s): {sorted(matched_gold)}")

    print("Generating an answer from the retrieved chunks...")
    generate_body = {
        "turn_id": turn_id,
        "chunks": [
            {
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "work_id": c["work_id"],
                "section_path": c["section_path"],
                "paragraph_ids": c["paragraph_ids"],
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "score": c["score"],
            }
            for c in chunks
        ],
    }
    generate_response = _post("/generate", generate_body)
    answer = generate_response.get("answer", "")
    if not answer.strip():
        sys.exit("FAIL: /generate returned an empty answer -- is Ollama up with the model pulled?")

    print(f"  model used: {generate_response.get('model_used')}")
    print(f"  answer ({len(answer)} chars): {answer[:200]}{'...' if len(answer) > 200 else ''}")
    print("\nOK: /retrieve -> /generate smoke test passed for Q002.")


if __name__ == "__main__":
    main()
