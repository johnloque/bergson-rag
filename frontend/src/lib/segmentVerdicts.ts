import type { ClaimVerdictOut } from '../api/types'

// How one answer sentence is colored, from the verdicts of the claims the
// faithfulness judge drew from it (src/generation/faithfulness.py):
// - 'unsupported' if at least one claim is unsupported;
// - 'supported' if every claim is supported;
// - 'unevaluated' otherwise (no unsupported claim, but at least one whose
//   verdict couldn't be obtained — not fully checked, so not green).
// A sentence with no claim at all (a transition like "Voici ce qu'en dit
// Bergson :") has no status and stays uncolored.
export type SegmentStatus = 'supported' | 'unsupported' | 'unevaluated'

export function groupClaimsBySegment(claims: readonly ClaimVerdictOut[]): Map<number, ClaimVerdictOut[]> {
  const bySegment = new Map<number, ClaimVerdictOut[]>()
  for (const claim of claims) {
    if (claim.segment_id === null || claim.segment_id === undefined) continue
    const group = bySegment.get(claim.segment_id)
    if (group) group.push(claim)
    else bySegment.set(claim.segment_id, [claim])
  }
  return bySegment
}

export function segmentStatus(claims: readonly ClaimVerdictOut[]): SegmentStatus | null {
  if (claims.length === 0) return null
  if (claims.some((c) => c.supported === false)) return 'unsupported'
  if (claims.every((c) => c.supported === true)) return 'supported'
  return 'unevaluated'
}
