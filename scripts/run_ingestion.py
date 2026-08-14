#!/usr/bin/env python3
"""Parse raw/src and chunk every work, writing results to data/processed/.

Usage: python3 scripts/run_ingestion.py
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.chunking import chunk_work, save_chunks
from src.ingestion.parser import parse_corpus, save_work

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main() -> None:
    works = parse_corpus(RAW_SRC_DIR)
    for work in works:
        save_work(work, PROCESSED_DIR / "works")
        chunks = chunk_work(work)
        save_chunks(work.work_id, chunks, PROCESSED_DIR / "chunks")
        print(
            f"{work.work_id}: {len(work.sections)} sections, "
            f"{len(work.paragraphs)} paragraphs, {len(chunks)} chunks"
        )


if __name__ == "__main__":
    main()
