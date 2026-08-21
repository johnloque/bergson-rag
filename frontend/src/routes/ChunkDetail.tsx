import { useMutation, useQuery } from '@tanstack/react-query'
import { IconArrowLeft } from '@tabler/icons-react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { RelevancePill } from '../components/RelevancePill'
import { getCachedChunk } from '../state/chunkCache'
import { useTurnUi } from '../state/turnUi'

function chunkNumber(chunkId: string): string {
  const match = chunkId.match(/_c(\d+)$/)
  return match ? match[1] : chunkId
}

export function ChunkDetail() {
  const params = useParams()
  const navigate = useNavigate()
  const conversationId = Number(params.conversationId)
  const turnId = Number(params.turnId)
  const chunkId = params.chunkId as string
  const turnUi = useTurnUi()

  const chunk = getCachedChunk(chunkId)
  const included = turnUi.getIncluded(turnId, chunkId)
  const judgment = turnUi.getJudgment(turnId, chunkId)

  const { data: turnDetail } = useQuery({
    queryKey: ['turn', turnId],
    queryFn: () => api.getTurn(turnId),
  })

  const judgeMutation = useMutation({
    mutationFn: () => {
      if (!chunk || !turnDetail) throw new Error('chunk or turn not loaded')
      return api.judgeChunk({ query: turnDetail.query, chunk: toInput(chunk), turn_id: turnId })
    },
    onSuccess: (result) => turnUi.setJudgment(turnId, chunkId, result),
  })

  function toInput(c: NonNullable<typeof chunk>) {
    return {
      chunk_id: c.chunk_id,
      text: c.text,
      work_id: c.work_id,
      section_path: c.section_path,
      paragraph_ids: c.paragraph_ids,
      page_start: c.page_start,
      page_end: c.page_end,
      score: c.score,
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => navigate(`/c/${conversationId}`)}
          className="flex items-center gap-1.5 text-sm"
          style={{ color: 'var(--ink-2)' }}
        >
          <IconArrowLeft size={16} />
          Retour
        </button>
        <span className="text-sm" style={{ color: 'var(--ink-3)' }}>
          {chunk?.work_id || 'Ouvrage'} · chunk {chunkNumber(chunkId)}
        </span>
      </div>

      <div className="grid grid-cols-[1fr_260px] gap-6">
        <div>
          <div className="rounded-xl p-4" style={{ background: 'var(--paper-2)', border: '0.5px solid var(--hairline)' }}>
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed" style={{ color: 'var(--ink)' }}>
              {chunk?.text || 'Texte indisponible pour ce passage (session précédente).'}
            </p>
          </div>
          {chunk && (
            <p className="mt-2 font-mono text-xs" style={{ color: 'var(--ink-3)' }}>
              score {chunk.score.toFixed(2)}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => judgeMutation.mutate()}
              disabled={judgeMutation.isPending || !chunk}
              className="flex-1 rounded-lg py-1.5 text-sm font-medium text-white disabled:opacity-50"
              style={{ background: 'var(--red)' }}
            >
              {judgeMutation.isPending ? 'Analyse…' : 'Expliquer'}
            </button>
            <button
              type="button"
              onClick={() => turnUi.toggleChunk(turnId, chunkId)}
              className="flex-1 rounded-lg border py-1.5 text-sm font-medium"
              style={{ borderColor: 'var(--hairline)', color: 'var(--ink)' }}
            >
              {included ? 'Exclure' : 'Inclure'}
            </button>
          </div>

          {judgment && (
            <div className="flex flex-col gap-2">
              <RelevancePill label={judgment.label} />
              <p className="text-[13px]" style={{ color: 'var(--ink-2)' }}>
                {judgment.justification}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
