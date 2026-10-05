"""Unit tests for src/generation/segmentation.py — deterministic, no model
or Qdrant needed. The French cases below are the ones pysbd and spaCy's
sentencizer were found to get wrong (see the module docstring)."""

from __future__ import annotations

from src.generation.segmentation import segment_answer


def _texts(answer: str) -> list[str]:
    return [segment.text for segment in segment_answer(answer)]


def test_offsets_point_back_into_the_answer():
    answer = "  Bergson distingue la durée du temps. Il la décrit [1889_DI_c3].\n\nAutre bloc."
    segments = segment_answer(answer)
    assert [s.id for s in segments] == [0, 1, 2]
    for segment in segments:
        assert answer[segment.start : segment.end] == segment.text


def test_abbreviations_and_initials_do_not_end_a_sentence():
    answer = (
        "Il la décrit, cf. p. 42 de l'Essai, comme une multiplicité. "
        "Selon M. Bergson et H. Höffding, voir ch. III."
    )
    assert _texts(answer) == [
        "Il la décrit, cf. p. 42 de l'Essai, comme une multiplicité.",
        "Selon M. Bergson et H. Höffding, voir ch. III.",
    ]


def test_ellipsis_ends_a_sentence():
    assert _texts("Une multiplicité qualitative… Selon lui, rien d'autre.") == [
        "Une multiplicité qualitative…",
        "Selon lui, rien d'autre.",
    ]


def test_citation_stays_with_the_sentence_it_follows():
    answer = "La durée [1889_DI_c3]. Elle prolonge cette idée. [1907_EC_c5] Pourquoi ?"
    assert _texts(answer) == [
        "La durée [1889_DI_c3].",
        "Elle prolonge cette idée. [1907_EC_c5]",
        "Pourquoi ?",
    ]


def test_quoted_question_followed_by_lowercase_is_one_sentence():
    assert _texts("« Pourquoi ? » demande-t-il. Parce que la vie est création.") == [
        "« Pourquoi ? » demande-t-il.",
        "Parce que la vie est création.",
    ]


def test_decimal_numbers_do_not_split():
    assert _texts("Une valeur de 3.5 fois. Puis rien.") == ["Une valeur de 3.5 fois.", "Puis rien."]


def test_markdown_blocks_bound_segments_and_headings_are_skipped():
    answer = (
        "## Titre\n\n"
        "- Premier point. Deuxième phrase\n  qui continue.\n"
        "2. Autre point [1900_R_c24]\n"
        "> Citation\n\n"
        "Paragraphe sans point final\nsur deux lignes"
    )
    assert _texts(answer) == [
        "Premier point.",
        "Deuxième phrase\n  qui continue.",
        "Autre point [1900_R_c24]",
        "Citation",
        "Paragraphe sans point final\nsur deux lignes",
    ]


def test_citation_only_and_empty_answers_yield_no_segment():
    assert segment_answer("") == ()
    assert segment_answer("   \n\n") == ()
    assert _texts("[1907_EC_c5]\n\nVrai contenu.") == ["Vrai contenu."]
