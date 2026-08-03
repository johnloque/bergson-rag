# Conventions de développement

Projet solo, mais workflow de PR maintenu volontairement pour la rigueur et
la démonstration de pratique d'ingénierie (portfolio).

## Organisation Sprint → Issue → Branche → PR

- Un **sprint** = un GitHub Milestone (`Sprint 0`, `Sprint 1`, ...),
  correspondant au découpage documenté dans `docs/ROADMAP.md`.
- Chaque objectif d'un sprint = une **Issue**, rattachée au Milestone.
  Un sprint contient plusieurs issues (plusieurs features/objectifs).
- Chaque issue se développe sur sa propre **branche**, jamais directement
  sur `main`.
- Chaque branche se ferme par une **Pull Request** vers `main`, même en
  solo.

Le sprint est donc une métadonnée de gestion de projet (Milestone), pas
une information encodée dans le nom de branche — les branches restent
nommées d'après la feature qu'elles portent, pas d'après le sprint, pour
rester lisibles même si le découpage en sprints est réajusté en cours de
route.

## Nommage des branches

Convention : `<type>/<description-courte-en-kebab-case>`

Types utilisés :
- `feat/` — nouvelle fonctionnalité (ex. `feat/hierarchical-chunking`)
- `fix/` — correction de bug
- `exp/` — expérimentation ML à comparer (ex. `exp/bge-m3-vs-e5-embeddings`)
  — spécifique aux projets ML : une branche par variante testée, avec ses
  métriques dans la PR, avant de décider ce qui devient la baseline
- `docs/` — documentation uniquement
- `chore/` — tooling, CI, dépendances
- `refactor/` — sans changement de comportement

## Commits

Convention [Conventional Commits](https://www.conventionalcommits.org/) :
`type(scope): description au présent`

```
feat(chunking): ajoute le decoupage hierarchique parent-enfant
fix(retrieval): corrige la fusion RRF quand un des deux index est vide
docs(readme): met a jour le statut du sprint 1
```

Permet un changelog automatisable et un historique lisible — un vrai plus
pour un recruteur qui parcourt l'historique git.

## Pull Requests

- Une PR = une issue = un sujet, volontairement petite et focalisée.
- Titre de PR au format Conventional Commits.
- Description : quoi/pourquoi, issue liée (`Closes #12`), et — spécificité
  ML — **métriques avant/après** dès que la PR touche au retrieval, au
  chunking ou à la génération (recall@k, faithfulness RAGAS, etc.). Une PR
  qui change le comportement du pipeline sans chiffre à l'appui n'est pas
  mergeable.
- Auto-review avant merge (checklist ci-dessous) ; possibilité d'utiliser
  Claude Code pour une revue de diff automatisée, à mentionner comme
  pratique dans le README du portfolio.
- **Squash merge** vers `main` : un commit propre par feature dans
  l'historique de `main`, quel que soit le nombre de commits intermédiaires
  sur la branche.
- `main` protégée : pas de push direct, PR obligatoire (à activer dans les
  paramètres GitHub du repo).

## Checklist avant merge

- [ ] Tests passent (dès que la CI est en place, Sprint 1+)
- [ ] Si retrieval/génération impacté : métriques d'évaluation jointes à la PR
- [ ] Pas de secrets/clés API commités
- [ ] `docs/ROADMAP.md` mis à jour si la portée du sprint a changé

## Tags de release

Un tag léger à la clôture de chaque sprint (`sprint-0-done`, puis semver
`v0.1.0` à partir d'un premier pipeline end-to-end fonctionnel) — permet de
retrouver facilement l'état du projet à chaque étape pour une démo en
entretien.
