import { InFlightRegistry } from './inFlightRegistry'
import type { EvaluateResponse } from '../api/types'

// Keyed by generation_id (docs/backend_api.md: one evaluation per
// generation). Mirrors state/pendingGenerations.ts, but for /evaluate
// instead of /generate — necessary because /evaluate has been a manual,
// user-triggered action ("Évaluer"/"Réessayer la vérification" in
// AnswerCard.tsx) since well before the Sprint 10 turn-lifecycle fix, yet
// only /generate ever got this resume-tracking treatment (Sprint 10's own
// "Fixed verification status bug" commit). Clicking "Évaluer" starts a real
// network call that keeps running even if the user navigates away before it
// resolves — the evaluations row is only written once the request
// completes (src/api/persistence.py), so a card remounted afterwards
// (state/useTurnController.ts's hydrate effect) has no persisted trace of
// it and would otherwise fall back to 'idle', showing "Non vérifié" and an
// "Évaluer" button again — inviting a second click that fires a genuine
// duplicate /evaluate call (fix/answer-verification).
export const pendingEvaluations = new InFlightRegistry<EvaluateResponse>()
