#!/usr/bin/env python3
"""Parse raw/src and chunk every work, writing results to data/processed/.

Usage: python3 scripts/run_ingestion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.chunking import chunk_work, save_chunks  # noqa: E402
from src.ingestion.parser import (  # noqa: E402
    parse_corpus,
    save_paragraph_correspondence,
    save_work,
)

RAW_SRC_DIR = REPO_ROOT / "data" / "raw" / "corpus" / "raw" / "src"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def main() -> None:
    works = parse_corpus(RAW_SRC_DIR)
    for work in works:
        save_work(work, PROCESSED_DIR / "works")
        save_paragraph_correspondence(work, PROCESSED_DIR / "paragraphs")
        chunks = chunk_work(work)
        save_chunks(work.work_id, chunks, PROCESSED_DIR / "chunks")
        print(
            f"{work.work_id}: {len(work.sections)} sections, "
            f"{len(work.paragraphs)} paragraphs, {len(chunks)} chunks"
        )


if __name__ == "__main__":
    main()
