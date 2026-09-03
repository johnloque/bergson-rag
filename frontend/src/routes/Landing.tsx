import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AbstractGraphic } from '../components/AbstractGraphic'
import { Wordmark } from '../components/Wordmark'
import { lastConversationPath } from '../lib/entry'
import { hasSeenLanding, markLandingSeen } from '../lib/session'

export function Landing() {
  const navigate = useNavigate()
  const [show, setShow] = useState(false)
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
      {/* Goes to the Presentation screen, not straight into the app — that
          entry point (`lastConversationPath`) lives on Presentation's own
          "Entrer dans l'application" button (docs/frontend.md). */}
      <button
        type="button"
        onClick={() => navigate('/presentation')}
        className="rounded-lg px-6 py-2 text-sm font-medium text-white"
        style={{ background: 'var(--red)' }}
      >
        Commencer
      </button>
    </div>
  )
}
