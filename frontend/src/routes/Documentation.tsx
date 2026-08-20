import { IconExternalLink } from '@tabler/icons-react'

const REPO_URL = 'https://github.com/johnloque/bergson-rag'

export function Documentation() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5 p-8 text-sm" style={{ color: 'var(--ink)' }}>
      <h1 className="text-xl font-medium">Guide d'utilisation</h1>

      <p style={{ color: 'var(--ink-2)' }}>
        Bergson-RAG explore l'œuvre complète d'Henri Bergson à partir d'une question posée en
        langage naturel. L'outil recherche les passages les plus pertinents dans le corpus, en
        propose une synthèse rédigée, puis vérifie automatiquement cette synthèse avant de vous la
        présenter en clair.
      </p>

      <section className="flex flex-col gap-1.5">
        <h2 className="font-medium">Poser une question</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Depuis une conversation, écrivez votre question dans le champ en bas de l'écran. L'outil
          recherche les passages pertinents, rédige une réponse synthétique citant ses sources,
          puis lance une vérification de fidélité en arrière-plan.
        </p>
      </section>

      <section className="flex flex-col gap-1.5">
        <h2 className="font-medium">Lire une réponse</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Chaque réponse apparaît d'abord floutée, le temps que la vérification se termine. Vous
          pouvez cliquer sur « Lire quand même » à tout moment pour la découvrir immédiatement — la
          vérification continue en arrière-plan et met à jour l'affichage (jauge de confiance,
          passages surlignés) dès qu'elle aboutit. Une réponse jugée suffisamment fiable se
          dévoile automatiquement.
        </p>
      </section>

      <section className="flex flex-col gap-1.5">
        <h2 className="font-medium">Inspecter les sources</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Les passages utilisés pour construire la réponse apparaissent sous forme de vignettes.
          Cliquez sur « Inspecter » pour lire un passage en entier, demander une explication de sa
          pertinence, ou l'inclure/exclure d'une prochaine régénération de la réponse.
        </p>
      </section>

      <section className="flex flex-col gap-1.5">
        <h2 className="font-medium">Régénérer une réponse</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Après avoir ajusté les passages inclus ou exclus, le bouton « Régénérer » relance la
          synthèse en tenant compte de votre sélection et de vos éventuelles évaluations de
          pertinence.
        </p>
      </section>

      <a
        href={REPO_URL}
        target="_blank"
        rel="noreferrer"
        className="mt-2 flex w-fit items-center gap-1.5 text-sm font-medium"
        style={{ color: 'var(--red)' }}
      >
        Dépôt GitHub du projet
        <IconExternalLink size={14} />
      </a>
    </div>
  )
}
