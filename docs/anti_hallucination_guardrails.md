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
    passed in, and at least one citation must be present. Extraction
    (`_extract_citations`) matches any bracketed text, not a chunk_id-shaped
    pattern — deliberate, not a missed tightening opportunity: a shape
    pattern would misfire on real data (e.g. `1932_2S_c62`, since
    `1932_2S`'s segment after the first underscore starts with a digit), and
    the check that actually matters — is this exact id one of the chunks
    given to *this* generation — is a `known_ids` set-membership test
    regardless, which a shape pattern could never substitute for. Full
    rationale in `_extract_citations`'s own docstring
    (`src/generation/guardrail.py`). Carried on
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

## Sprint 11 (`feat/backend-reference-data`): text-level title+year resolution

`fix/title-year-grounding`'s `src.works.WORKS` table resolves title/year at
the *work* level only — fine for 6 of the corpus's 8 works, but 1919_ES
("L'énergie spirituelle") and 1934_PM ("La Pensée et le Mouvant") are
anthologies of individually-dated articles/conferences/etc., each with its
own real title and first-publication year, sometimes decades apart from
the anthology's own. Before this branch, that finer identity was invisible
to both the prompt and Layer 1: a chunk from 1919_ES's real 1902 article
"L'effort intellectuel" was shown to the model only as
`1919_ES — L'énergie spirituelle (1919)`, and an answer correctly naming
that article's real title would have been flagged by
`check_title_fabrication` as fabricated (it wasn't among the known 8 work
titles), while `check_title_year_mismatch` had no way to validate its real
1902 date against anything but 1919_ES's own 1919 publication year.

**`src.works.TEXTS`** (extending `works.py`, not a second table — same
"import and extend, don't rebuild" discipline `fix/title-year-grounding`
established for `WORKS` itself) records each qualifying text's title, year,
and paragraph_id range for these two works, keyed by the individually-dated
`<div>` (`@type` one of art/conf/discours/essai/notice) it comes from.
Depends on the same load-bearing structural assumption `WORKS`'s consumers
already lean on implicitly (max div nesting depth 1, `docs/xml_audit_report.md`)
but verified specifically for these two files' actual XML, not just
inferred from the corpus-wide stat — see `scripts/extract_text_metadata.py`
and `tests/test_works.py::test_no_chunk_straddles_two_qualifying_divs`
(chunking-level) and `test_no_qualifying_div_is_nested_in_another`
(XML-level). All 17 qualifying divs across both works extracted cleanly (no
year-extraction failure to log/exclude in the real corpus — the
logged-and-excluded path is still exercised directly,
`tests/test_works.py::test_ambiguous_year_div_is_logged_and_excluded_not_defaulted`,
against a synthetic corpus).

**`resolve_paragraph_metadata(work_id, paragraph_id) -> ParagraphMetadata`**
(`{work_title, work_year, text_title, text_year}`, the last two `None`
unless `paragraph_id` falls inside a `TEXTS` entry) is the single
resolution entry point both consumers below now use instead of a
work-level-only lookup:

- **`src/generation/prompt.py`**: `_format_chunk`'s per-chunk header now
  shows the text-level title/year alongside (not instead of) the
  work-level one when applicable, e.g. a chunk from "L'effort intellectuel"
  shows both `L'énergie spirituelle (1919)` and `texte « L'effort
  intellectuel » (1902)` — the same root-cause mitigation
  `fix/title-year-grounding` applied at the work level, now precise enough
  that the model no longer needs to (mis)attribute a specific article's
  ideas to its anthology's publication year either.
- **`src/generation/guardrail.py`**: `KNOWN_WORK_TITLES`/`_KNOWN_TITLES_NORMALIZED`
  are extended with `KNOWN_TEXT_TITLES` (derived from `TEXTS`, same
  drift-avoidance reasoning as `KNOWN_WORK_TITLES`'s own derivation from
  `WORKS`), so `check_title_fabrication` no longer flags a real
  individually-dated text's title as fabricated. `_TITLE_ATTRIBUTION`
  replaces the old, work-only `_WORK_ID_BY_NORMALIZED_TITLE`: it resolves a
  matched title to *its own* correct year (the text's year for a
  text-level title, the work's year for a work-level one), so
  `check_title_year_mismatch` validates a text-level claim against the
  text's real date rather than forcing it against the enclosing
  anthology's.

Test coverage: `tests/test_works.py` (the ES_1902_EI worked example end to
end, dated-text vs. front-matter vs. non-anthology-work fallback,
the nesting/no-straddling assumption verified both at the XML level and
against the real current chunking, the logged-and-excluded year-extraction
failure path, and a regression check tying the hand-transcribed `TEXTS`
back to a fresh run of `scripts/extract_text_metadata.py`);
`tests/test_prompt.py` (chunk header shows both levels when applicable,
work-level only otherwise — hand-built chunks, no Qdrant/LLM dependency);
`tests/test_guardrail.py` (a real text-level title is not flagged as
fabricated; a text-level title paired with the anthology's year instead of
its own is flagged, with the anthology's year correctly reported as the
wrong one and the text's own year as `correct_year`).

## Sprint 11 (`feat/backend-reference-data`): paragraph_id -> chunk_id mapping

A separate, unrelated addition shipped in the same branch (different
input/output shape, different consumer, kept in its own module rather than
folded into `works.py`): `src.paragraph_chunk_map.resolve_chunk_ids`
resolves a `(work_id, paragraph_id)` pair against whatever chunking
`data/processed/chunks/` currently holds, by scanning `Chunk.paragraph_ids`
— no new XML parsing, since paragraph_ids are already stable, ingestion-
assigned identifiers and chunking is just a grouping over them. Exists to
close the gold-dataset-remapping cost `docs/gold_dataset_protocol.md`
names as a blocker for Sprint 14's chunk-size experiments: ground truth
there is keyed on paragraph_ids specifically so it survives a re-chunking
event, and this function is what turns that stable ground truth back into
whatever chunk_ids a given chunking run actually produced. A plain
importable function, not a guardrail component — has no interaction with
`generate_evaluation`/`should_auto_expand` above.

Test coverage: `tests/test_paragraph_chunk_map.py`, against real,
already-verified gold_dataset.csv mappings (Q001, Q004, Q007's four
paragraph_ids across two works) plus a round-trip check over every
paragraph/chunk pair in 1907_EC's current chunking.

## `feat/clickable-citations`: Layer 1's citation-existence result also gates a UI behavior, not just the structural flag

`check_structure`'s citation-resolution half — `StructuralCheck.citations`/
`unknown_citations`, every `[chunk_id]` bracket in the answer checked
against the `chunks` actually passed to that generation — already had one
consumer before this branch: `CitationFlag.tsx`'s warning message when a
citation doesn't resolve. This branch adds a second, independent consumer
on the frontend, reusing the exact same computed result rather than a
second existence check: a `[chunk_id]` citation in the answer's own
rendered text becomes a clickable link to Screen 4's chunk inspection view
(`feat/chunk-neighbor-expansion`) if and only if its chunk_id is **not**
in `unknown_citations` — i.e. Layer 1 already confirmed it names a chunk
present in this generation's input set. A citation Layer 1 flagged as
unknown is never linked; it keeps the existing `CitationFlag` treatment
unchanged. Full detail, including the confirmed `[chunk_id]` format (single
and multi-id-per-bracket), the markdown-composability requirement, and the
chunk_id-format-preserved-for-link-text rationale, is in
[`docs/frontend.md`](frontend.md)'s "clickable inline citations" addendum —
nothing on the backend/`check_structure` side changed for this branch, only
a new frontend reader of its existing output.

This is deliberately **not** the same question as general answer
"validity": it does not depend on `check_title_fabrication` or
`check_title_year_mismatch` (both above) — a citation can be exists-in-set
(linkable) in an answer that separately fabricates a title elsewhere, and
`should_auto_expand`'s own gate is unaffected by this addition, same as it
already was unaffected by `unknown_citations` itself (see this module's
docstring for why: citation omission/presence isn't gated, but resolution
correctness for citations that *are* present still feeds this new link
behavior regardless).

## `fix/answer-verification`: closing the resume-tracking gap `/evaluate` never got, plus a DB-level idempotency guarantee

Real-usage reports of two symptoms — verification status appearing lost
after navigating away and back, and the collapsed veil/"Lire quand même"
prompt appearing for a turn that was already verified — were investigated
together rather than assumed to be one bug or two, per standing project
discipline (`docs/ROADMAP.md`). **Finding: one shared, confirmed root
cause, but it is not the mount-logic hypothesis it might look like at
first** (a hardcoded "always render collapsed/blurred on mount" default) —
`AnswerCard.tsx`'s `expanded = revealed || evaluation?.should_auto_expand
=== true` and the hydrate effect's `evaluationStatus: g.evaluation ? 'done'
: 'idle'` (`useTurnController.ts`) already derive the right state from
whatever `GET /turns/{id}` returns, immediately, with no intermediate
defaulted-to-veiled render (confirmed by a dedicated fresh-mount regression
test, `TurnCard.integration.test.tsx`'s "mounting an already-evaluated turn
never shows the veil" — Problem 2, as reported, does not reproduce against
an already-evaluated turn). **Also confirmed: not a Sprint 12 regression.**
None of the Sprint 12 UI branches
(`feat/sidebar-restructure`/`feat/chunk-neighbor-expansion`/
`feat/answer-display-improvements`/`feat/clickable-citations`) touch
`useTurnController.ts`'s hydrate effect, `AnswerCard.tsx`'s `expanded`
derivation, or `/evaluate` (`git log --follow -p` on each file confirms
this) — and `fix/turn-lifecycle-and-manual-generation` (Sprint 10) already
shipped a dedicated regression test for exactly this "stays expanded/badged
after navigate-away-and-back" scenario, which still passes unmodified
(`docs/turn_lifecycle.md`).

**The real, still-live gap**: `/evaluate` has been a fully manual,
user-triggered action (the "Évaluer"/"Réessayer la vérification" button,
`AnswerCard.tsx`) since a Sprint 8 (`feat/frontend`) commit — not the
"frontend calls `/evaluate` automatically right after `/generate`" flow a
naive reading of the two-separate-HTTP-calls design
(`docs/backend_api.md`) might suggest, and not something this fix changes.
A generation's `evaluations` row is written only once that manual call
completes (`src/api/persistence.py`) — there is no persisted "evaluation in
progress" state, only "row absent" vs. "row present". Sprint 10 already
built exactly this kind of resume-tracking for `/generate`
(`state/pendingGenerations.ts`, an `InFlightRegistry` keyed by `turn_id`,
for the same reason: an in-app navigation unmounts `TurnCard`, but the
network request it started keeps running) — but never built the equivalent
for `/evaluate`, because at the time `/evaluate` was still believed to run
automatically right after generation, under the redirect-timing race Sprint
10 was fixing. Once a user clicks "Évaluer" and navigates away before it
resolves, the remounted card has no way to tell "still running" apart from
"never started" and falls back to `evaluationStatus: 'idle'` ("Non
vérifié") — inviting a second click that fires a genuine duplicate
`/evaluate` call for the same `generation_id`, with (until this fix) no
DB-level guard against that leaving two `evaluations` rows.

**Fix, frontend**: `state/pendingEvaluations.ts`, a second
`InFlightRegistry` instance keyed by `generation_id` (mirroring
`pendingGenerations.ts`'s shape exactly, just keyed differently — an
evaluation is per-generation, not per-turn). `runEvaluationAt`
(`useTurnController.ts`) registers its `api.evaluate` call under it; the
hydrate effect, for each persisted generation lacking an evaluation row,
checks the registry and — **only if a call is genuinely still in flight** —
resumes "Vérification en cours" and reattaches to it. It deliberately does
**not** re-issue `/evaluate` for every never-yet-verified past generation
unconditionally: `/evaluate`'s manual-trigger design is a real product
decision (Sprint 8), not an oversight, and auto-firing it on every reload
of every old, never-manually-verified turn would silently override that
decision — as well as paying for a judge call, and re-exposing this
project's own documented judge-noise variance (Sprint 10's calibration,
above), on turns nobody asked to verify.

A related latent bug surfaced while building this: `InFlightRegistry.start`
(`state/inFlightRegistry.ts`) left a failed entry parked at `status:
'error'` forever, so a *second* `start()` call under the same key — exactly
what clicking "Réessayer la vérification" does — replayed the same stale
rejection instead of actually retrying. Unexercised before now (nothing
read `pendingGenerations`'s `'error'` status), but `pendingEvaluations`'s
retry button would have inherited it immediately. Fixed at the shared
class: a failed `run()` now clears its entry, same as a succeeded one, so
the next `start()` for that key genuinely retries
(`state/inFlightRegistry.test.ts`).

**Fix, backend — the reliability half.** `/evaluate` (`src/api/main.py`)
already checked for an existing `Evaluation` row before recomputing, and
`persistence.save_evaluation` already re-checked before inserting — but
neither made that check-then-insert atomic, and FastAPI runs sync path
operations in a thread pool, so two genuinely concurrent `/evaluate` calls
for one `generation_id` really could both pass both checks before either
committed. `evaluations.generation_id` now carries a DB-level unique
constraint (`src/api/models.py`); `save_evaluation` catches the losing
request's `IntegrityError` and returns the winner's row instead of a 500.
An already-existing dev DB is retrofitted by `src/api/db.py`'s
`_sync_unique_indexes` (deduping any pre-fix duplicate rows first, keeping
the most recent per `generation_id`) — `create_all()` alone never adds a
constraint to an already-created table, the same limitation
`_sync_additive_columns` documents for columns. Full detail:
[`docs/backend_api.md`](backend_api.md).

**Follow-up (same branch): explaining, not just correctly rendering, the
verified-but-collapsed state.** The fix above made
`evaluationStatus: 'done'` + `should_auto_expand: false` render correctly
(veil + "Vérifié" badge + "Lire quand même", per this module's own
"user can always expand manually" design, above) — but a user report during
review flagged that this *correct* state still reads as contradictory:
"Vérifié" (StatusPill) means only "the check ran," not "the check passed,"
and nothing on the card said which of the three `should_auto_expand` gates
(`src/generation/guardrail.py`: retrieval confidence tier, an unsupported
Layer 2 claim, a Layer 1 structural flag) actually failed. `AnswerCard.tsx`
now shows a short explanatory line under the badge in this exact state
(`collapseReason`), naming the specific reason — structural flag and
unsupported claim are both readable directly off `EvaluateResponse`; the
retrieval-confidence-tier case has to be inferred by elimination (neither
of the other two fired), since the tier itself was deliberately dropped
from `/evaluate`'s response by the retrieval-confidence-split correction,
above, and isn't reintroduced by this fix. Structural takes priority when
both a structural and a faithfulness flag fired, matching this module's own
established severity ordering (a title/year fabrication is "a positive,
specific claim, not an omission," per the `fullyEndorsed` gating logic
already in `AnswerCard.tsx`).

Test coverage: `tests/test_persistence.py::test_save_evaluation_concurrent_duplicate_insert_returns_winner_row`
(the DB-level race, reproduced deterministically); `tests/test_api.py::test_evaluate_second_call_for_same_generation_id_reuses_existing_row`
(request-level idempotency — a real judge call, counted, invoked exactly
once across two `/evaluate` calls); `state/inFlightRegistry.test.ts` (dedup
+ the retry-after-failure fix); `TurnCard.integration.test.tsx`'s new
cases — resuming an in-flight evaluation after navigate-away-and-back, a
fresh mount of an already-`should_auto_expand: true`-evaluated turn (no
veil/spinner flash, ever), and a fresh mount of an
already-`should_auto_expand: false`-evaluated turn (immediate "Vérifié"
badge plus its collapse-reason line, never "Non vérifié" — the veil and
"Lire quand même" correctly still show in this case, per this module's own
"user can always expand manually" design, not a bug); `AnswerCard.test.tsx`'s
`collapseReason` cases (all three reasons individually, the
structural-takes-priority case, absent once expanded, absent before
evaluation actually completes). The existing live-flow fixtures
(Q001/Q004/Q008/Q009/Q002, `tests/test_guardrail.py`) are untouched — no
guardrail decision logic changed on this branch, only persistence, frontend
resume-tracking, and this explanatory copy.
