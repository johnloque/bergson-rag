"""Unit tests for src/generation/prompt.py's Sprint 11 text-level grounding
(`feat/backend-reference-data`) — hand-built `RetrievedChunk`s, no Qdrant/LLM
dependency, unlike tests/test_generation.py's prompt tests which need real
retrieved chunks.
"""

from __future__ import annotations

from src.generation.prompt import build_prompt
from src.generation.signals import EvidenceSignals
from src.retrieval.hybrid import RetrievedChunk

PAGE = {"number": 1, "display": "1"}


def _header(chunk: RetrievedChunk) -> str:
    """The rendered evidence header line for `chunk`, alone in a prompt."""
    signals = EvidenceSignals(
        works=(chunk.work_id,), convergence=None, is_convergent=True, is_confident=True
    )
    prompt = build_prompt("question", [chunk], signals)
    return next(line for line in prompt.splitlines() if line.startswith(f"[{chunk.chunk_id}]"))


def _chunk(work_id: str, chunk_id: str, paragraph_ids: list[str]) -> RetrievedChunk:
    return RetrievedChunk(
        score=1.0,
        work_id=work_id,
        chunk_id=chunk_id,
        section_id="s1",
        section_path="body/Test",
        paragraph_ids=paragraph_ids,
        page_start=PAGE,
        page_end=PAGE,
        text="texte de test",
    )


def test_chunk_inside_dated_text_shows_both_work_and_text_title_year():
    chunk = _chunk("1919_ES", "1919_ES_c1", ["1919_ES_p153", "1919_ES_p154"])
    header = _header(chunk)
    assert "L'énergie spirituelle (1919)" in header
    assert "L'effort intellectuel" in header
    assert "(1902)" in header
    assert "1919_ES" in header


def test_chunk_outside_any_dated_text_shows_work_level_only():
    # 1934_PM front matter (p1-p3), before the first dated text at p4.
    chunk = _chunk("1934_PM", "1934_PM_c1", ["1934_PM_p1"])
    header = _header(chunk)
    assert "La Pensée et le Mouvant (1934)" in header
    assert "texte «" not in header


def test_chunk_from_non_anthology_work_shows_work_level_only():
    chunk = _chunk("1907_EC", "1907_EC_c5", ["1907_EC_p13"])
    header = _header(chunk)
    assert "L'Évolution créatrice (1907)" in header
    assert "texte «" not in header
