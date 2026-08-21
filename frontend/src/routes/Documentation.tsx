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
        <h2 className="font-medium">Comment la réponse est vérifiée</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Chaque réponse générée est ensuite évaluée par deux contrôles indépendants, jamais par
          l'outil qui a rédigé la réponse elle-même :
        </p>
        <p style={{ color: 'var(--ink-2)' }}>
          Un contrôle structurel vérifie que chaque citation présente
          dans le texte correspond bien à un passage réellement fourni au modèle. Un contrôle de
          fidélité décompose la réponse en affirmations
          élémentaires et vérifie individuellement si chacune est étayée par les passages cités.
        </p>
        <p style={{ color: 'var(--ink-2)' }}>
          Quand une affirmation n'est pas retrouvée telle quelle dans les passages cités, le
          passage correspondant est surligné dans la réponse. À l'inverse, quand toutes les
          affirmations de la réponse sont étayées par les passages cités, l'outil l'indique
          explicitement plutôt que de rester silencieux sur ce point : « Réponse intégralement
          confirmée par les passages cités. »
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

      <section className="flex flex-col gap-1.5">
        <h2 className="font-medium">Poursuivre la conversation</h2>
        <p style={{ color: 'var(--ink-2)' }}>
          Pour éviter de multiplier les conversations, vous pouvez poser plusieurs questions d'affilée (par exemple pour regrouper celles qui portent sur des thèmes communs). Cela n'a en revanche aucun impact sur les mécanismes de récupération des passages pertinents et de génération / évaluation.
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
