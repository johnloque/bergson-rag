// A sidebar destination like GuideUtilisation and Sources, nested under
// AppShell — reached from Landing's "Commencer" and from clicking the
// wordmark/icon at any later point (components/Sidebar.tsx). No longer a
// standalone pre-app screen: since it renders inside AppShell, the sidebar
// itself (conversation list, "Nouvelle conversation") is the way into the
// app, so there's no separate "enter" step here (docs/frontend.md).
export function Presentation() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8 text-sm" style={{ color: 'var(--ink)' }}>
      <h1 className="text-xl font-medium">Présentation</h1>
      {/* README's "What it does" paragraph, near-verbatim in French. */}
      <p style={{ color: 'var(--ink-2)' }}>
        L'utilisateur pose une question en français, éventuellement restreinte par œuvre et/ou
        date de publication. Le système récupère et reclasse les passages pertinents, permet de
        les inspecter et de les sélectionner — en expliquant la pertinence de n'importe quel
        passage à la demande — puis ne génère une réponse synthétisée et citée qu'à la demande de
        l'utilisateur : l'examen des sources et la génération sont deux étapes distinctes, non un
        seul passage automatique.
      </p>
    </div>
  )
}
