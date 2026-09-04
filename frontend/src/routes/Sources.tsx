export function Sources() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-8 text-sm" style={{ color: 'var(--ink)' }}>
      <h1 className="text-xl font-medium">Sources</h1>
      <p style={{ color: 'var(--ink-2)' }}>
        Le corpus indexé ici est l'œuvre complète d'Henri Bergson, mort en janvier 1941 : il est
        dans le domaine public en France depuis le 1er janvier 2012, en application de la règle
        des 70 ans post-mortem (ceci n'est pas un avis juridique — une vérification indépendante
        est recommandée avant tout usage commercial). Les textes sources et leur encodage XML au
        niveau du paragraphe proviennent du projet bergson-synoptique ; les identifiants de
        paragraphe sont réattribués automatiquement à l'ingestion plutôt que réutilisés depuis
        cette source, afin que le corpus indexé ici reste sa propre référence de vérité pour
        l'identité des paragraphes. Les éditions de référence utilisées sont celles déjà encodées
        par bergson-synoptique, sans réalignement sur une autre édition.
      </p>
    </div>
  )
}
