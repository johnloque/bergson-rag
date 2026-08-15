"""Text normalization for indexing — two independent outputs computed
once per chunk by `normalize_text()`.

- Lemma+POS (spaCy, model version pinned in pyproject.toml): the
  canonical dictionary form. Not used for BM25 this sprint — stored for
  other consumers (MCP exact-lemma lookup, the companion lexicon-graph
  project). Linguistically motivated, not a retrieval optimization
  (docs/ROADMAP.md).
- Stem (French Snowball/Savoy, via `snowballstemmer`): rule-based
  suffix stripping, more robust to 1889-1932 French than a lemmatizer
  trained on contemporary text. This is what feeds the BM25 sparse
  index this sprint.

`Normalization.bm25_text` is the single seam between normalization
output and the sparse embedder (see src/indexing/embeddings.py): it
joins stems today. Swapping the BM25 index to lemmas later (the
stems-vs-lemmas comparison planned for a later sprint, docs/ROADMAP.md)
means changing this one property to join `lemmas` instead — the
embedding and Qdrant-indexing code do not change.

Both outputs are computed once per chunk (here) and persisted
(src/indexing/indexer.py), rather than recomputed wherever they're
needed — stemming, in particular, must run exactly once per chunk since
its result is both stored to disk (for inspection) and fed to the
sparse embedder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import snowballstemmer
import spacy

SPACY_MODEL = "fr_core_news_lg"

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_stemmer = snowballstemmer.stemmer("french")
_nlp: spacy.language.Language | None = None


def _get_nlp() -> spacy.language.Language:
    global _nlp
    if _nlp is None:
        _nlp = spacy.load(SPACY_MODEL, disable=["parser", "ner"])
    return _nlp


@dataclass(frozen=True)
class LemmaToken:
    text: str
    lemma: str
    pos: str


@dataclass(frozen=True)
class StemToken:
    text: str
    stem: str


@dataclass(frozen=True)
class Normalization:
    lemmas: list[LemmaToken]
    stems: list[StemToken]

    @property
    def bm25_text(self) -> str:
        """Text handed to the BM25 sparse embedder. Stems this sprint —
        see module docstring for the planned stems-vs-lemmas swap."""
        return " ".join(t.stem for t in self.stems)


def lemmatize(text: str) -> list[LemmaToken]:
    """spaCy lemma+POS for each non-space, non-punct token."""
    doc = _get_nlp()(text)
    return [
        LemmaToken(text=t.text, lemma=t.lemma_, pos=t.pos_)
        for t in doc
        if not t.is_space and not t.is_punct
    ]


def stem(text: str) -> list[StemToken]:
    """French Snowball stem for each of `text`'s word tokens."""
    words = _TOKEN_RE.findall(text.lower())
    stems = _stemmer.stemWords(words)
    return [StemToken(text=w, stem=s) for w, s in zip(words, stems, strict=True)]


def normalize_text(text: str) -> Normalization:
    return Normalization(lemmas=lemmatize(text), stems=stem(text))
