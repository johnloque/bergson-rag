import { api } from '../api/client'

// Shared by Landing.tsx's returning-session skip and Presentation.tsx's
// "Entrer dans l'application" button — both are "enter the app proper"
// exits from the pre-app screens and must resolve identically (Sprint 8's
// returning-user rule: last conversation if one exists, else a fresh one).
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
