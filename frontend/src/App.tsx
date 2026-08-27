import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { TurnUiProvider } from './state/turnUi'
import { AppShell } from './routes/AppShell'
import { ChunkDetail } from './routes/ChunkDetail'
import { Conversation } from './routes/Conversation'
import { Documentation } from './routes/Documentation'
import { Landing } from './routes/Landing'

const queryClient = new QueryClient()

export function AppRoutes() {
  // `key={location.key}` on /new's <Conversation> (docs/ROADMAP.md, Sprint
  // 10, the "nouvelle conversation" inactive-button bug): react-router does
  // not remount an element just because navigate() was called to the path
  // it's already showing — a second "Nouvelle conversation" click while
  // already on /new was otherwise a router no-op, leaving Conversation's own
  // `drafts` state (routes/Conversation.tsx) stale instead of starting a
  // genuinely fresh turn. `location.key` changes on every navigation, push
  // or not, so keying on it forces a real remount every time.
  //
  // /new/:draftId needs no such key: Conversation reads its `draftId` param
  // straight from `useParams()` on every render (not just at mount), since
  // it renders the very same <Conversation> element type as its /new
  // sibling at the same position in this tree — react-router reuses one
  // instance across them rather than remounting, so anything read only
  // once at mount time there would go stale.
  const location = useLocation()
  return (
    <Routes location={location}>
      <Route path="/" element={<Landing />} />
      <Route element={<AppShell />}>
        <Route path="/new" element={<Conversation key={location.key} />} />
        <Route path="/new/:draftId" element={<Conversation />} />
        <Route path="/c/:conversationId" element={<Conversation />} />
        <Route path="/c/:conversationId/turn/:turnId/chunk/:chunkId" element={<ChunkDetail />} />
        <Route path="/docs" element={<Documentation />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TurnUiProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </TurnUiProvider>
    </QueryClientProvider>
  )
}
