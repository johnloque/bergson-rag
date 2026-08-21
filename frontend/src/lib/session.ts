// sessionStorage (not localStorage): the landing page must reappear if the
// tab/session restarts, but stay skipped across in-session navigation
// (docs/ROADMAP.md, Sprint 8, Screen 1).
const LANDING_SEEN_KEY = 'bergson_seen_landing'

export function hasSeenLanding(): boolean {
  return sessionStorage.getItem(LANDING_SEEN_KEY) === '1'
}

export function markLandingSeen(): void {
  sessionStorage.setItem(LANDING_SEEN_KEY, '1')
}
