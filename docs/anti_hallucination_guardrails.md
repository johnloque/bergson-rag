# Anti-hallucination guardrails (Sprint 6)

Post-generation validation, citation formatting.

**Scope decision, superseding the roadmap's original one-line scope.** Two
designs were considered and dropped before landing on the one actually
built:

- **A hard refusal** (an explicit "no reliable answer" response) — dropped.
  `generate_from_chunks` always generates and always returns an answer,
  regardless of retrieval confidence or the faithfulness score computed on
  it afterward. Generated syntheses are already treated as interpretive
  proposals to verify, not definitive answers (see the roadmap's "Validated
  architecture decisions"); a refusal doesn't fit that framing and removes
  a citable, checkable answer the user could otherwise inspect.
- **A separate pre-generation blocking gate** (deciding not to generate at
  all below some confidence threshold) — dropped for the same reason, plus
  a second one: retrieval confidence and generation faithfulness are
  measured independently and don't move together (confirmed by this
  sprint's own test fixtures — Q001/Q004 have a fine, correctly-retrieved
  gold chunk but a hallucinated answer; Q009 has a genuinely poor retrieval
  but the model still declines to fabricate). Gating on retrieval alone
  would have blocked good-faithfulness answers and let some hallucinations
  through untouched.

**What was built instead: presentation-only gating, unified into one
mechanism.** The first generated answer — initial or a manual regeneration —
is always rendered collapsed by default, unconditionally. It auto-expands
only once a post-generation evaluation comes back positive on both an
independent structural/faithfulness check and a retrieval-confidence read.
The user can always expand it manually regardless. This sprint builds the
decision logic and the data it depends on; the actual collapsed-by-default
rendering and persistence of the evaluation result are **deferred to Sprint
7** (see risk note below).

## Implemented

All in `src/generation/`:

- `generate_from_chunks` (`generate.py`) gains an optional `chunk_judgments`
  parameter — unaffected existing behavior when `None` (Test A from Sprint 5
  still calls it that way). When populated, each judged chunk's label and
  justification are rendered inline with that chunk's evidence text in the
  prompt (`prompt.py`), as an additional signal — not a filter; the caller
  is expected to have already excluded chunks before calling.
- `generate_evaluation(query, chunks, answer) -> EvaluationResult`
  (`guardrail.py`), run after any `generate_from_chunks` call, identically
  for an initial generation and a manual regeneration:
  - **Layer 1**, `check_structure` — deterministic, no LLM call: every
    `[chunk_id]` citation in the answer must resolve to a chunk actually
    passed in, and at least one citation must be present. Carried on
    `EvaluationResult` for the caller/UI, but **not** wired into
    `should_auto_expand`'s own gate (see next point) — the local generation
    model was found, empirically, to often omit citations even from
    well-grounded answers, which would make the gate practically
    unreachable if citation presence were required.
  - **Layer 2**, `check_faithfulness` (`faithfulness.py`, unchanged
    call site, extended return type) — the one LLM call this function
    makes. `check_faithfulness` now also returns RAGAS's per-claim verdicts
    (`FaithfulnessResult.claims`), not just the aggregate score, obtained by
    calling the metric's own two internal steps directly instead of
    `single_turn_score()` — the same two LLM calls, not a second pass —
    so a guardrail can name *which* claim is unsupported.
  - **Retrieval confidence tier**, `signals.retrieval_confidence_tier` —
    imported directly from `src/generation/signals.py`, not reimplemented
    here: the exact same signal Sprint 5's `EvidenceSignals.is_confident`
    already computes, mapped to four tiers (très faible / faible / moyenne
    / élevée) instead of Sprint 5's binary confident/not-confident split.
    One shared definition for both sprints, not two independently-tuned
    ones — see the correction note below for why this needed revisiting
    after this sprint's first pass.
- `should_auto_expand(evaluation) -> bool` (`guardrail.py`): true only if
  retrieval confidence is at least "moyenne" (`signals.CONFIDENT_TIERS`) and
  Layer 2 flagged no unsupported claim.

## Correction made within this sprint, before merge

The retrieval confidence signal was originally a reused-as-is copy of
Sprint 5's coefficient of variation (CV) of cross-encoder rerank scores,
mapped to four tiers with an *inverted* polarity from Sprint 5's own
`CONFIDENCE_CV_THRESHOLD` (lower CV read as higher confidence here, the
opposite of Sprint 5's higher-CV-is-confident reading). That inversion was
a real inconsistency, not just a documentation nuance — the same named
statistic meant opposite things depending on which module read it.

Root cause: CV is scale-free and a function of the whole candidate set's
composition, not of how good the single best piece of evidence actually is.
Sprint 5 only ever needed a *relative* discrimination question ("does the
reranker prefer one candidate over the others, among already-plausible
chunks") where higher spread legitimately reads as more confident. Sprint 6
needs an *absolute* question ("is there real evidence here at all"), and in
that regime CV misleads: a genuine retrieval miss (near-zero scores across
the board) inflates CV, because tiny absolute differences between near-zero
numbers balloon their *relative* spread, while a real relevant cluster of
scores sits close together in absolute terms and reads as *low* CV — the
opposite of what "low CV = uncertain" would suggest.

Fixed by replacing CV with the single highest cross-encoder score among the
chunks (not their spread) as the shared primitive behind both
`EvidenceSignals.is_confident` (Sprint 5) and `retrieval_confidence_tier`
(Sprint 6, the one public function both now go through) — one definition
(`src/generation/signals.py`), no polarity flip needed anywhere, and
well-defined for a single chunk (no `None`-defaulting edge case CV needed).
This also let `CAUTION_INSTRUCTION` (`prompt.py`) drop its "flat or
non-discriminating" framing, which was already a slightly imprecise trigger
for what Sprint 5 actually wanted (flat-but-uniformly-high scores don't
warrant caution; a low best score does, regardless of spread). Calibrated
against real `bge-reranker-v2-m3` scores on gold_dataset.csv items, not fit
as a formal sweep (see `src/generation/signals.py` for the specific cut
points and numbers) — same "documented placeholder, revisit with a larger
gold dataset" discipline as this project's other thresholds.

## Other decisions

- **No second LLM call for the guardrail decision.** A small judge
  calibration (n=4: Q001/Q004 confirmed hallucinations, Q006/Q008 confirmed
  faithful) found the hosted Mistral judge rates the confirmed
  hallucinations as faithful (0.857–0.929) — a second opinion from it could
  overturn a correct local-judge signal in exactly the wrong direction, so
  `generate_evaluation` only ever calls the local 7B judge, once per
  generated answer. This was a small manual check, not a formal before/after
  metrics run against the full gold dataset — reported honestly as such,
  not withheld; a proper before/after comparison needs the larger dataset
  this project is still short of (see gold-dataset-volume notes elsewhere
  in this doc).
- **No auto-correction loop** (generate → critique → revise) — rejected in
  favor of user-initiated regeneration via `chunk_judgments` instead.

## `chunk_judgments` — committed interface contract

`judge_chunks` itself is out of scope for this branch (its own, later
branch) — this sprint only builds the consumer side. The shape it must
conform to is fixed now, in `src/generation/chunk_judgment.py`:

```python
ChunkJudgment = {"label": "pertinent" | "partiellement pertinent" |
                 "non pertinent", "justification": str}
# generate_from_chunks(..., chunk_judgments: dict[str, ChunkJudgment] | None)
```

Tested against a hand-constructed fixture (`tests/test_guardrail.py`), not
a real `judge_chunks` call, since one doesn't exist yet — this is the target
that branch's output must match, not a placeholder expected to drift.

## Deferred to Sprint 7, with a concrete risk

UI rendering (the actual collapsed/auto-expanded badge) and backend
persistence of the evaluation result are both out of scope here — this
sprint only builds the decision logic (`generate_evaluation`,
`should_auto_expand`) and its inputs. Risk this defers: `generate_evaluation`
runs after generation completes, not before it's shown, and nothing
persists its result yet — a user who navigates away or closes the session
before `generate_evaluation` finishes, or before a session is persisted,
never sees the answer's final expanded/collapsed badge state. Sprint 7
needs to close this gap, not just add the rendering.

## Follow-up correction (Sprint 8): retrieval confidence moved from post-evaluation display to a pre-generation preview

Originally, the retrieval confidence tier was computed inside
`generate_evaluation` (this sprint) and surfaced as a field on
`/evaluate`'s response (Sprint 7a-b), rendered as a gauge inside the
expanded, post-evaluation answer card (Sprint 8). On reflection this showed
the signal at the wrong moment and in the wrong place: retrieval confidence
is a property of the *evidence*, knowable before generation ever runs, not
a property of the *answer* — showing it only after `/evaluate` completed
meant the user had already committed to generating (and had to wait through
the full generate → evaluate round trip) before seeing a signal that could
have informed whether to curate the chunk rail first. It also duplicated
`should_auto_expand`'s own internal use of the same tier without adding
information, since a low tier already suppresses auto-expand.

Fixed by extracting the tier computation into
`src.generation.signals.retrieval_confidence_tier` (already a standalone
function; `generate_evaluation` now takes the tier as a parameter instead
of computing it) and giving it two call sites, not the previous single
implicit one: a new `POST /confidence-preview` endpoint, called live by the
frontend at the chunk-rail level on every include/exclude toggle (debounced
~300ms), and `POST /generate`, which computes the same tier server-side
over the chunks it was actually given and persists it on the `generations`
row — never a client-submitted value, the same trust boundary Sprint 7b
already applied to `/evaluate`'s `(query, chunks, answer)`. `/evaluate`
reads that persisted value back purely to gate `should_auto_expand`
internally; its response no longer carries a `retrieval_confidence_tier`
field, since re-showing it there would just duplicate what
`/confidence-preview` already showed before generation.
`should_auto_expand`'s decision logic itself is unchanged (tier at
"moyenne" or above AND no unsupported claims) — only where its confidence
input comes from changed.

On the frontend, the confidence gauge (`ConfidenceGauge.tsx`, unchanged
visually — same 4-segment bar, `--blue` for the confident tiers,
`--gray-dark` for the two weak tiers) moved from the expanded answer card
to directly above the chunk rail (`ChunkRail.tsx`); the answer card now
renders only the citation integrity flag and faithfulness highlighting.

## Test coverage

`tests/test_guardrail.py` — Q001/Q004 hand-crafted confirmed-hallucination
fixtures (Layer 2 flags the specific fabricated claim, `should_auto_expand`
false despite fine retrieval confidence), Q008 (answer generated and
returned unmodified regardless of evaluation outcome), Q009 (real
hybrid_search+rerank pipeline, a genuine persistent miss — très faible
tier, `should_auto_expand` false), Q002 (strong case, auto-expands), a
hand-crafted Layer 1 unknown-citation case, the `chunk_judgments`
prompt-content check, and a manual-regeneration case reusing the Q001
fixture logic against a `chunk_judgments`-populated `generate_from_chunks`
call. Sprint 10 (below) adds real-fabrication title-detection cases to
this file.

## Sprint 10 (`fix/faithfulness-citation-detection`): judge-noise calibration update + Layer 1 title-fabrication extension

Real-usage reports after v0 shipped ("correct passages flagged as
unsupported") could have two distinct causes: (1) the Q008-type judge
noise already known from this sprint's own n=4 calibration (above), now
possibly at a higher real-usage rate than that tiny sample suggested; or
(2) a genuine scope gap in Layer 1's `check_structure`, which only ever
verified *structured* `[chunk_id]` citations, never prose. Standing
project discipline (docs/ROADMAP.md) required investigating both before
writing any fix — both turned out to be real.

### (1) Judge noise, re-calibrated at n=20

The original n=4 calibration (above) sampled two confirmed hallucinations
and two confirmed-faithful items. This sprint re-examined all 20 real,
non-hand-picked `generate_from_chunks` answers already on record from this
project's own `eval/scripts/run_ragas_eval.py` full run
(`eval/results/eval_ragas_n10_20260816T203232Z.md` +
`eval/results/ragas_checkpoint.jsonl`, commit `7c9d99f`, `ollama_chat/mistral`
generation and judge, `temperature=0`) — 10 `generation_only` items (gold
chunk_ids, retrieval bypassed) and 10 `end_to_end` items (real
hybrid_search + rerank + generate) — reused rather than regenerated, since
they are already real pipeline output at a fixed, reproducible commit, not
hand-picked fixtures. Each item's RAGAS faithfulness score was checked
by hand against the actual cited chunk text (`data/processed/chunks/*.json`
for `generation_only`, where the exact evidence set is known; corpus
knowledge and the gold `expected_anwser` for `end_to_end`, where the exact
retrieved set isn't persisted) to judge whether the flagged content was
genuinely unsupported or a judge false positive.

**Result: judge noise is real and substantially more common than the n=4
check suggested.** In `generation_only` mode alone, 5 of 10 items
(Q003 0.500, Q004 0.750, Q005 0.286, Q006 0.500, Q010 0.000) scored below
1.0 despite the answer being, on manual reading, a substantively accurate
paraphrase or near-verbatim quotation of the cited chunk — Q010 in
particular ("Bergson utilise la métaphore de la sédimentation
géologique... conditionnés par des forces éruptives invisibles...") is
close to a verbatim rendering of its chunk's own sentence, yet was scored
faithfulness=**0.0**, the most severe possible false-positive outcome.
That is a 50% item-level over-flagging rate in the mode that isolates
generation/judge quality from retrieval noise — an order of magnitude
above what n=4 implied. `end_to_end` mode adds at least one more clear
case (Q008, scored 0.0 against content that closely tracks the same real
"manteau accroché à un clou" passage `generation_only`'s Q008 scored
1.0 on) plus three `nan` (judge parse failure, no signal at all — a
related, already-documented reliability gap, not a false positive but not
a working guardrail signal either).

This is not a new bug — it is the same accepted Q008-type noise floor
this sprint already documented, now quantified at a scale that makes it
clear it is not a rare edge case in real usage. Per `docs/ROADMAP.md`'s
gold-dataset-volume discipline (the same threshold applied to stems vs.
lemmas, cross-encoder vs. multi-vector reranking, and query
reformulation), actually reducing this noise floor — a judge-model swap,
a different prompting strategy, or an ensemble — is a calibration effort
that needs a larger, purpose-built gold set of flagged/unflagged examples
to evaluate against, not something to attempt inside this fix branch.
**Deferred as an open `exp/` candidate**, not closed: the next step is
accumulating enough real flagged/unflagged examples (this n=20 pass is a
start) to run that comparison meaningfully.

### (2) Layer 1 scope gap — confirmed, and fixed

Reading `check_structure`'s actual implementation (`src/generation/guardrail.py`,
pre-Sprint-10) confirmed the gap plainly: it extracts `[chunk_id]` brackets
(`CITATION_PATTERN`) and checks each against the `chunks` passed in — it
has no path at all for a claim like `l'œuvre de 1900 intitulée "Le comique
de caractère"` embedded in ordinary prose. The original Q004 calibration
case (this sprint, above) was exactly this shape. Two real, non-hand-picked
`end_to_end` answers from the same n=20 pass above confirm this is a live
failure mode, not a hypothetical one:

- Q004 `end_to_end` fabricated **"Le comique de caractère"** as the title
  of the real 1900 work (actually "Le rire" / "Essai sur la signification
  du comique"), and separately misattributed the real title "L'évolution
  créatrice" to 1934 instead of 1907, in the same answer. RAGAS *did*
  score this 0.0 — Layer 2 caught it — but the answer contains zero
  `[chunk_id]` citations, so Layer 1's citation-resolution check had
  nothing to flag.
- Q002 `end_to_end` fabricated **"De l'évolution de la vie. Mécanisme et
  finalité"** as the title of 1907_EC (the real title is "L'Évolution
  créatrice"). RAGAS scored this answer faithfulness=**1.0** — Layer 2
  missed it outright. This is the concrete proof that the Layer 1 gap has
  independent cost, not just redundant coverage of what Layer 2 already
  catches.

**Fix**: `check_structure` now also runs `check_title_fabrication`
(`src/generation/guardrail.py`) — deterministic, no LLM call, no
dependency on `chunks`. It extracts any quoted title introduced by the cue
word "intitulé(e)" (the exact pattern both real fabrications above used)
and flags it unless it matches, after accent/case/whitespace
normalization, one of the corpus's 8 known work titles or alternate
titles (`KNOWN_WORK_TITLES`, hardcoded — the corpus is a fixed, closed set
per `docs/ROADMAP.md`'s scope decision, and this must work before any
ingestion has produced `data/processed/works/*.json`, a gitignored build
artifact). The cue-word anchor is a deliberate precision choice: at the
time this check was built, the model was never shown real work titles in
the prompt (only `work_id`, e.g. `1907_EC` — `src/generation/prompt.py`),
so any title it named came from its own background knowledge, but a
quoted span *without* that cue is often a genuine verbatim quotation from
a chunk, which must not be flagged. (`fix/title-year-grounding`, below,
later added the real title/year to the prompt too — see that section for
why the cue anchor is kept as-is rather than revisited.) `StructuralCheck`
gained a `fabricated_titles` field, and unlike
the citation-resolution half of Layer 1 (kept out of `should_auto_expand`'s
gate because the local model often omits `[chunk_id]` brackets even from
well-grounded answers), `fabricated_titles` *is* wired into the gate: a
title fabrication is a positive, specific claim, not an omission, so the
same false-positive risk doesn't apply.

**Scope boundary, stated plainly**: this only verifies that a *named
title exists* in the corpus, not that its surrounding attribution (year,
work_id) is also correct. A second real case, Q007 `end_to_end` (same n=20
pass), attributed the real title "Matière et mémoire" to chunk work_id
`1888_EDIC` (which is actually "Essai sur les données immédiates de la
conscience") — RAGAS scored this 1.0, and this check does not flag it
either, since "Matière et mémoire" is a real title. Verifying
year/work-id attribution accuracy is a fuzzier problem than closed-set
title lookup and is left out of this deterministic check; Layer 2 remains
the (unreliable, per above) backstop for that failure mode. This check
needs to answer only the case it targets correctly — catching one
fabricated title already blocks auto-expand for the whole answer, so it
does not need to catch every error in a given answer to be useful.

Wired through the API (`StructuralCheckOut.fabricated_titles`,
`src/api/schemas.py`/`src/api/main.py`) and the frontend
(`CitationFlag.tsx`, `StructuralCheckOut` in `frontend/src/api/types.ts`)
— the same collapsed/flag-only presentation `unknown_citations` already
used, extended rather than duplicated. `StructuralCheckOut.fabricated_titles`
defaults to `[]` in the Pydantic schema specifically so evaluations
persisted before this field existed (`evaluations.structural_flags`,
`src/api/models.py`) still deserialize via `_evaluation_row_to_response`.

Test coverage (`tests/test_guardrail.py`): `check_title_fabrication`
exercised directly against both real fabrications above (no LLM call);
a genuine-titles case (canonical, alternate, and an accent/case-insensitive
spelling variant) confirming no new false-positive source was introduced;
the Q004 case shown caught by Layer 1 alone, with `should_auto_expand`
constructed against a stubbed fully-faithful `FaithfulnessResult` to
isolate Layer 1's own contribution to the gate; the Q002 case reproducing
the real historical judge output (faithfulness=1.0, no flagged claims) to
show `should_auto_expand` now blocks a case that used to slip through
before this branch; and an explicit regression assertion on the existing
Q008 test that `structural.fabricated_titles == ()` for that confirmed-faithful,
title-free answer — this branch changes nothing about Q008's behavior.

## `fix/title-year-grounding`: title+year prompt grounding + Layer 1 pairing check

Two independent, complementary changes closing the scope gap Sprint 10
named explicitly above ("this only verifies that the *title itself* exists
... not that the surrounding attribution (year, work_id) is also
correct") — not a rewrite of Sprint 10's `check_title_fabrication`, and
neither change is meant to substitute for the other, same defense-in-depth
principle as everywhere else in this guardrail system (Layer 1 + Layer 2 +
confidence tier, none trusted alone).

**Shared prerequisite: `src/works.py`.** A new module holding
`WORKS: dict[str, WorkMetadata]` — title, alternate titles, and publication
year for the corpus's fixed, closed set of 8 works, hardcoded (same
reasoning as Sprint 10's `KNOWN_WORK_TITLES`: must work before any
ingestion has run). `docs/ROADMAP.md`'s Sprint 11 entry anticipated a
static work_id -> year table for date-range retrieval filtering; that table
didn't exist yet on this branch, so this module *is* it (extended with
title, which Sprint 11 didn't need but this branch does) — **Sprint 11
should import and extend `src.works.WORKS`, not build a second table.**
`KNOWN_WORK_TITLES` (`src/generation/guardrail.py`) is now derived from
`WORKS` instead of an independently hardcoded copy, so the fabrication
check and the new pairing check below can't drift apart on what a "real"
title is.

**1. Root-cause mitigation: title+year now shown in the generation prompt
(`src/generation/prompt.py`).** Before this branch, the model was shown
only `work_id` per chunk (e.g. `1907_EC`) and had to recall the actual
title/year from its own background knowledge to name them in prose — the
real source of both fabrication shapes found in calibration: an invented
title entirely (Q002/Q004's "Le comique de caractère" /
"De l'évolution de la vie...") and a real title attached to the wrong year
(Q004's "1934" for the real 1907 work "L'évolution créatrice"). Every
chunk header and multi-work group label now shows `src.works.work_label`
(`"{title} ({year})"`) alongside `work_id`, e.g.
`1907_EC — L'Évolution créatrice (1907)` — additive, not a replacement:
`work_id` is still shown, since the citation format and Layer 1 both key
on it. This is the primary mitigation; it reduces how often the model
needs to fabricate a title or year at all, but does not guarantee it never
will (see the Q004 empirical check below).

**2. Strengthened detection: `check_title_year_mismatch`
(`src/generation/guardrail.py`).** For each "intitulé(e)"-cued title an
answer names (the same cue-anchored extraction Sprint 10 built, kept as-is
on this branch — see below), if the title matches a real known work but a
year mentioned within a fixed character window of the cue
(`_YEAR_CONTEXT_WINDOW = 60`, a documented placeholder sized from this
project's two real fabrication cases, not a formal sweep) doesn't match
that work's real year, the pairing is flagged
(`StructuralCheck.title_year_mismatches`). Wired into `check_structure`
(Layer 1) and `should_auto_expand`'s gate directly, same as
`fabricated_titles`: a title+year pairing is a positive, specific
attribution claim, not an omission, so the citation-omission false-positive
concern that keeps `unknown_citations` out of the gate doesn't apply here
either. Direct regression test for the scope gap named above: Q004's real
"1934 intitulée 'L'évolution créatrice'" fabrication, previously invisible
to both Layer 1 checks, is now flagged (`tests/test_guardrail.py`).

**On the "intitulé(e)" cue-word limitation**: still present, and
`check_title_year_mismatch` reuses it as-is rather than a broader
title-detection rewrite. This branch treats the cue-word fragility concern
as *lower priority*, not resolved: mitigation (1) above is expected to
reduce how often the model introduces a title via an unanticipated phrasing
in the first place (it no longer needs to reach for background knowledge
to name one), which weakens the original motivation for a rewrite, but this
branch has no new evidence — positive or negative — that the concern is
actually gone. Revisit only if real usage after this branch ships shows it
still is.

**Empirical check, not assumed**: `tests/test_guardrail.py`'s
`test_q004_title_year_grounding_empirical_regeneration` regenerates Q004
with the new prompt grounding in place and reports (via
`check_structure`'s output, printed for inspection) whether the original
fabrication still occurs, rather than asserting the prompt fix eliminates
it — LLMs can still err with the correct title/year directly in front of
them, just less often. This is a single-item empirical spot-check, not a
before/after calibration run against the full gold dataset; a proper
before/after comparison needs the larger gold dataset this project is
still short of, same standing limitation as Sprint 6/10's judge
calibration above.

Test coverage (`tests/test_guardrail.py`): `check_title_year_mismatch`
exercised directly against a hand-constructed real-title-wrong-year case
(Q004's actual misattribution), a correct-pairing case (no false positive),
and a fabricated-title case (confirms this check defers to
`check_title_fabrication` rather than trying to also validate a year
against a title it can't resolve to a known work); the real historical
Q004 `end_to_end` answer shown to trigger both checks at once (a
fabricated title *and* a real-title/wrong-year pairing in the same
answer); the empirical Q004 regeneration check above; and an explicit
regression assertion on the existing Q008 test that
`structural.title_year_mismatches == ()` — this branch changes nothing
about Q008's behavior. Prompt-side coverage (`tests/test_generation.py`):
both the multi-work (Q007) and mono-work (Q001) prompt-branch tests assert
the real title and year for every represented work appear in the
constructed prompt, alongside (not instead of) `work_id`.

**API/frontend wiring — also done on this branch, plus a related fix found
while doing it.** `title_year_mismatches` is wired through the API
(`StructuralCheckOut.title_year_mismatches`, `TitleYearMismatchOut`,
`src/api/schemas.py`/`src/api/main.py`) and frontend
(`frontend/src/api/types.ts`, `CitationFlag.tsx`), same collapsed/flag-only
presentation `fabricated_titles`/`unknown_citations` already used, extended
rather than duplicated — a first draft of this branch deferred this pass,
but reviewing the actual `AnswerCard.tsx` behavior surfaced a real,
user-visible consequence worth fixing in the same branch rather than
deferring further (below).

**Fixed alongside it: the "fully endorsed" badge's Layer-1 blind spot.**
`AnswerCard.tsx`'s "Réponse intégralement confirmée par les passages
cités." statement (`fullyEndorsed`) was computed from Layer 2's claims
only, independent of Layer 1 entirely. Concretely: `should_auto_expand`
already collapses the answer when `fabricated_titles` or
`title_year_mismatches` fires, but a user can still force it open via "Lire
quand même" — and once open, if Layer 2 didn't independently flag the same
claim (the real Q002 case above: RAGAS scored that fabrication
faithfulness=1.0), the card would show the green "fully confirmed" badge
with no visible warning at all, directly contradicting the reason it was
collapsed in the first place. Fixed by gating `fullyEndorsed` on Layer 1's
own two gating flags too (`hasStructuralFlags` in `AnswerCard.tsx`) — the
same two flags already in `should_auto_expand`'s gate, not a new
independent threshold. `unknown_citations` deliberately stays out of this
new check, same reasoning as its exclusion from `should_auto_expand`
itself (`src/generation/guardrail.py`'s module docstring): it's excluded
for a different, already-documented reason (citation omission noise), not
an oversight being repeated here.

Test coverage: `frontend/src/components/CitationFlag.test.tsx` (renders the
year-mismatch message; still renders nothing when all three structural
signals are clean) and `AnswerCard.test.tsx` (two new cases: full
endorsement suppressed when `fabricated_titles` is non-empty despite every
claim being supported, and the same for `title_year_mismatches` — direct
regression coverage for the blind spot above).
