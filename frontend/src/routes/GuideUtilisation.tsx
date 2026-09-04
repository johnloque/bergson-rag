// Short walkthrough grounded in the actual current interaction flow
// (docs/frontend.md) — not an aspirational feature list. Superseded
// Documentation.tsx's longer write-up, which had drifted from the shipped
// behavior (no mention of neighbor exploration, for instance).
export function GuideUtilisation() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8 text-sm" style={{ color: 'var(--ink)' }}>
      <h1 className="text-xl font-medium">Guide d'utilisation</h1>
      <p style={{ color: 'var(--ink-2)' }}>
        Depuis une conversation, posez votre question dans le champ de saisie : le système
        recherche et reclasse les passages les plus pertinents du corpus (jusqu'à 15 passages, les
        3 mieux classés étant sélectionnés par défaut). Inspectez ces passages — lisez-les en
        entier, demandez une explication de leur pertinence, incluez ou excluez-les de la
        génération (5 au maximum), ou explorez leurs voisins immédiats dans le texte pour élargir
        votre sélection. Une fois satisfait de votre sélection, cliquez sur « Générer » pour
        obtenir une réponse synthétisée et citée. La réponse reste d'abord floutée le temps qu'une
        vérification en deux étapes s'achève — cohérence des citations, puis fidélité de chaque
        affirmation aux passages cités — et se dévoile automatiquement si elle est jugée
        suffisamment fiable, ou peut être lue immédiatement sur demande. Vous pouvez ensuite
        ajuster à nouveau votre sélection de passages et cliquer sur « Régénérer » pour obtenir une
        nouvelle réponse qui en tient compte.
      </p>
    </div>
  )
}
