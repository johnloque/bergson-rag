import { api } from '../api/client'

// Used by Landing.tsx's returning-session skip to enter the app directly
// (Sprint 8's returning-user rule: last conversation if one exists, else a
// fresh one).
export async function lastConversationPath(): Promise<string> {
  try {
    const { conversations } = await api.listConversations()
    if (conversations.length > 0) {
      return `/c/${conversations[0].conversation_id}`
    }
  } catch {
    // API unreachable — fall through to a fresh conversation.
  }
  return '/new'
}
