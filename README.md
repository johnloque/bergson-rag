# bergson-rag

Chatbot RAG local sur les œuvres complètes d'Henri Bergson — retrieval
hybride (BM25 + dense + voisinage), reranking, et garde-fous
anti-hallucination avec citation systématique des sources.

Projet de portfolio data scientist / ML engineer NLP.

## Statut

🚧 En développement — Sprint 0 (cadrage). Voir [`docs/ROADMAP.md`](docs/ROADMAP.md)
pour le détail de l'architecture, de la méthodologie d'évaluation, et du
découpage en sprints.

## Stack

Python · Qdrant (dense + sparse) · BGE-M3 · FastAPI · Docker Compose ·
Kubernetes (déploiement optionnel documenté) · MCP (couche d'exposition)

## Structure du repo

Voir [`docs/ROADMAP.md`](docs/ROADMAP.md#structure-du-repo-cible).

## Licence

MIT — voir [`LICENSE`](LICENSE). Le corpus source (œuvres d'Henri Bergson,
mort en 1941) est dans le domaine public en France.

## Contribuer

Ce dépôt suit un workflow de PR même en développement solo, à but de
démonstration de pratique d'ingénierie. Voir
[`CONTRIBUTING.md`](CONTRIBUTING.md).
