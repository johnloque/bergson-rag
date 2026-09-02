import type {
  ChunkNeighborsResponse,
  ConfidencePreviewRequest,
  ConfidencePreviewResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationSummaryOut,
  EvaluateRequest,
  EvaluateResponse,
  GenerateRequest,
  GenerateResponse,
  JudgeChunkRequest,
  JudgeChunkResponse,
  RetrieveRequest,
  RetrieveResponse,
  SetChunkIdsRequest,
  SetChunkIdsResponse,
  TurnDetailResponse,
} from './types'

// Same origin the backend's CORS middleware allows (src/api/main.py,
// FRONTEND_DEV_ORIGIN's counterpart) — overridable for a non-default API host.
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ? JSON.stringify(body.detail) : detail
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  retrieve: (body: RetrieveRequest) =>
    request<RetrieveResponse>('/retrieve', { method: 'POST', body: JSON.stringify(body) }),

  generate: (body: GenerateRequest) =>
    request<GenerateResponse>('/generate', { method: 'POST', body: JSON.stringify(body) }),

  confidencePreview: (body: ConfidencePreviewRequest) =>
    request<ConfidencePreviewResponse>('/confidence-preview', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  evaluate: (body: EvaluateRequest) =>
    request<EvaluateResponse>('/evaluate', { method: 'POST', body: JSON.stringify(body) }),

  judgeChunk: (body: JudgeChunkRequest) =>
    request<JudgeChunkResponse>('/judge-chunk', { method: 'POST', body: JSON.stringify(body) }),

  getTurn: (turnId: number) => request<TurnDetailResponse>(`/turns/${turnId}`),

  // Chunk-neighbor-persistence fix (docs/ROADMAP.md): replaces the turn's
  // current included/neighbor chunk_id set wholesale, called by
  // components/ChunkRail.tsx's debounced sync effect on every
  // include/exclude change.
  setIncludedChunks: (turnId: number, body: SetChunkIdsRequest) =>
    request<SetChunkIdsResponse>(`/turns/${turnId}/included-chunks`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  setNeighborChunks: (turnId: number, body: SetChunkIdsRequest) =>
    request<SetChunkIdsResponse>(`/turns/${turnId}/neighbor-chunks`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getChunkNeighbors: (chunkId: string) =>
    request<ChunkNeighborsResponse>(`/chunks/${chunkId}/neighbors`),

  getConversation: (conversationId: number) =>
    request<ConversationDetailResponse>(`/conversations/${conversationId}`),

  listConversations: () => request<ConversationListResponse>('/conversations'),

  renameConversation: (conversationId: number, title: string) =>
    request<ConversationSummaryOut>(`/conversations/${conversationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (conversationId: number) =>
    request<void>(`/conversations/${conversationId}`, { method: 'DELETE' }),
}
