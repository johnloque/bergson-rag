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
call.
