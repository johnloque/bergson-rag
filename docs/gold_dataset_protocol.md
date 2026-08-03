# Gold dataset construction protocol

Protocol for manually building the first wave of ~50 annotated
query/document/answer triplets.

## Scope relative to query decomposition

Each item stores the raw question, as a user would type it — never a
decomposed or reformulated version. Evaluation compares this raw input
against the passages the full pipeline ultimately retrieves, regardless
of how many sub-queries it generates internally to get there. Query
decomposition itself is not scored by this dataset; it stays an internal
step of the system under test.

## Passage-first construction

Always start from a passage you are actively reading in the source XML,
never from a question you'd like to ask. Write the question backward
from the passage, re-reading it in full before drafting anything. Do not
rely on general knowledge of Bergson's doctrine — the dataset checks
grounding against specific corpus text, not against secondary
scholarship.

## Quotas (n=50)

| Category | Share | Count |
|---|---|---|
| Factual | 40% | 20 |
| Definitional | 25% | 13 |
| Comparative | 20% | 10 |
| Contested/interpretive | 15% | 7 |

Cross-cutting, within the above:
- Coverage across all 8 works (at least 4-5 items per work)
- ~6-7 items (factual/definitional) using contemporary vocabulary in the
  question while the passage uses Bergson's own period phrasing
- 3-5 items where the passage contains a quotation Bergson explicitly
  attributes to another author, flagged via `footnote_related`

## Single vs. multi ground truth

For every factual/definitional item, ask: would a different passage,
elsewhere in the corpus, answer this exact question just as correctly?

- **No** - the question is anchored by something specific to this
  passage (an example, an image, a step in the argument). Ground truth
  is one `(work, paragraph_id)` pair. Prefer this whenever possible: it's
  simpler to score and more diagnostic when retrieval fails.
- **Yes** - either narrow the question until only one passage fits, or
  accept a multi-valued ground truth: a set of `(work, paragraph_id)`
  pairs, any one of which counts as a correct retrieval. Set
  `ground_truth_type` to `multi` in that case.

This is independent from the `comparatif` category: `comparatif` is for
questions that explicitly require combining several works; `multi`
ground truth is for a question that needs only one passage but has more
than one valid candidate.

## Per-item procedure

1. Pick a passage in the paragraph-level source.
2. Record its reference as `(work, paragraph_id)`, using the word-level
   source's paragraph number - the paragraph-level source carries no
   identifier of its own, and the paragraph number is only unique within
   a single work's file, not across the corpus, so both fields are
   required together.
3. Re-read the full passage before drafting the question.
4. Write the question so the passage is necessary to answer it.
5. Apply the single-vs-multi check above; search for other equally
   valid passages if in doubt.
6. Write the expected answer (factual/definitional/comparative) as a
   tight paraphrase strictly bounded by the passage(s) - no additions.
   For contested items, write expected system behavior instead (which
   passages a good answer should draw on, what must not be asserted as
   settled).
7. Rate retrieval difficulty (easy/medium/hard) from lexical overlap
   between the question's wording and the passage's actual vocabulary.
8. Review again after drafting a few other items, to catch answers that
   leaked in general knowledge of Bergson rather than the passage itself.

## Mitigating single-annotator bias

No second annotator means no inter-annotator agreement check. Two
mitigations:
- Time-delayed self-review: re-derive each answer from the passage alone
  a few days later, without looking at your first draft.
- LLM-assisted adversarial check: have an LLM verify that each cited
  passage fully entails the expected answer, nothing added or missing -
  a faithfulness check on the gold set itself, not on generated content.

## Schema

```
id, categorie, question, ground_truth_type,
work_paragraph_pairs, reponse_attendue_resume, comportement_attendu,
vocabulaire_periode, difficulte_retrieval, footnote_related, notes
```

- `ground_truth_type`: `single` or `multi`
- `work_paragraph_pairs`: one or more `work:paragraph_id` pairs,
  semicolon-separated if more than one

## Worked example

```
id: Q-EXAMPLE
categorie: factuel
question: Selon Bergson, pourquoi le langage nous pousse-t-il a
  juxtaposer dans l'espace des phenomenes qui n'occupent pourtant aucun
  espace ?
ground_truth_type: single
work_paragraph_pairs: Essai sur les donnees immediates de la
  conscience:1
reponse_attendue_resume: Parce que le langage exige, pour que nous
  puissions nous exprimer par des mots, que nous etablissions entre nos
  idees les memes distinctions nettes et la meme discontinuite qu'entre
  les objets materiels dans l'espace - utile dans la vie pratique et
  necessaire dans la plupart des sciences, mais source possible de
  difficultes insurmontables pour certains problemes philosophiques.
comportement_attendu: (n/a - factuel)
vocabulaire_periode: bergsonien
difficulte_retrieval: facile
footnote_related: non
notes: Opening passage of the Essai - anchored by its specific framing
  of the language/space problem, unlikely to be matched by another
  passage just as well.
```

## Next wave

50 items are enough for a first working evaluation set. A second wave to
reach 150-300 total should only follow once this protocol has been
validated on the first batch, not be attempted in one pass.