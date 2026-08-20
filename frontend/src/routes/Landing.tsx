import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { AbstractGraphic } from '../components/AbstractGraphic'
import { Wordmark } from '../components/Wordmark'
import { hasSeenLanding, markLandingSeen } from '../lib/session'

async function lastConversationPath(): Promise<string> {
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

export function Landing() {
  const navigate = useNavigate()
  const [show, setShow] = useState(false)
  const [starting, setStarting] = useState(false)
  // Guards against React StrictMode's dev-only double effect invocation:
  // without it, the second invocation would see the flag the first one just
  // set and redirect away from a landing page the user never got to see.
  const decided = useRef(false)

  useEffect(() => {
    if (decided.current) return
    decided.current = true
    if (hasSeenLanding()) {
      void lastConversationPath().then((path) => navigate(path, { replace: true }))
      return
    }
    markLandingSeen()
    setShow(true)
  }, [navigate])

  async function handleStart() {
    setStarting(true)
    const path = await lastConversationPath()
    navigate(path)
  }

  if (!show) return null

  return (
    <div
      className="flex h-screen w-screen flex-col items-center justify-center gap-6"
      style={{ background: 'var(--paper)' }}
    >
      <AbstractGraphic />
      <Wordmark size={34} />
      <p className="max-w-xs text-center text-sm" style={{ color: 'var(--ink-2)' }}>
        Explorez la pensée de Bergson, une source à la fois
      </p>
      <button
        type="button"
        onClick={handleStart}
        disabled={starting}
        className="rounded-lg px-6 py-2 text-sm font-medium text-white disabled:opacity-60"
        style={{ background: 'var(--red)' }}
      >
        Commencer
      </button>
    </div>
  )
}
