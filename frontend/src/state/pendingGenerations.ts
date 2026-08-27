import { InFlightRegistry } from './inFlightRegistry'

export interface PendingGenerationResult {
  generationId: number
  answer: string
  model: string
}

// Keyed by turn_id (always known once /retrieve has resolved, so unlike
// state/pendingConversations.ts this needs no client-generated id or
// dedicated route). Lets a turn's card, remounted after the user navigated
// away mid-"Générer" and back, resume showing the in-progress spinner and
// reattach to the same /generate call instead of leaving no sign it's still
// running — see useTurnController.ts's `generate` and its hydrate effect.
export const pendingGenerations = new InFlightRegistry<PendingGenerationResult>()
