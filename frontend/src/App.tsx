import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { TurnUiProvider } from './state/turnUi'
import { AppShell } from './routes/AppShell'
import { ChunkDetail } from './routes/ChunkDetail'
import { Conversation } from './routes/Conversation'
import { Documentation } from './routes/Documentation'
import { Landing } from './routes/Landing'

const queryClient = new QueryClient()

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TurnUiProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route element={<AppShell />}>
              <Route path="/new" element={<Conversation />} />
              <Route path="/c/:conversationId" element={<Conversation />} />
              <Route path="/c/:conversationId/turn/:turnId/chunk/:chunkId" element={<ChunkDetail />} />
              <Route path="/docs" element={<Documentation />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </TurnUiProvider>
    </QueryClientProvider>
  )
}
