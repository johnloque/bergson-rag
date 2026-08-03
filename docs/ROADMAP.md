# Chatbot RAG — Œuvres complètes d'Henri Bergson

Portfolio data scientist / ML engineer NLP. Chatbot RAG local répondant de façon
sourcée et synthétique aux questions de chercheurs sur la pensée de Bergson,
à partir d'un corpus XML des 8 ouvrages majeurs (granularité paragraphe et
mot+lemme+POS).

## Statut

Sprint 0 — cadrage et fondations. Pas encore de code applicatif.

## Décisions d'architecture validées

- **Chunking** : hiérarchique (parent/enfant), exploitant la structure XML
  existante plutôt qu'un splitter générique.
- **Retrieval** : hybride BM25 (sur lemmes) + dense (BGE-M3) + voisinage dans
  le texte source, fusionnés par RRF.
- **Reformulation de requête** : multi-query / décomposition avant retrieval,
  pour absorber l'écart entre vocabulaire contemporain et vocabulaire
  bergsonien (*vocabulary drift*, cf. HistoRAG, Kim-Baumann & Hiltmann 2026).
- **Reranking** : cross-encoder multilingue (bge-reranker-v2-m3).
- **Garde-fous anti-hallucination** : couche de validation post-génération +
  citations obligatoires ; les synthèses générées sont traitées comme des
  propositions interprétatives à vérifier (concept de *Zwischentexte*), pas
  comme des réponses définitives.
- **Infra** : Qdrant (dense + sparse), FastAPI, Docker Compose en référence,
  manifestes Kubernetes en option documentée (pas de scaling réel nécessaire
  à ce stade).
- **MCP** : couche d'exposition en fin de projet (Sprint 7), pas au cœur du
  pipeline. Deux tools prévus : recherche hybride, lookup par référence
  exacte (navigation XPath + recherche par lemme).

## Méthodologie d'évaluation

Le système ne vise pas à trancher des débats herméneutiques mais à retrouver
et restituer fidèlement ce que dit le corpus. Le jeu de test est donc
stratifié par type de question (voir `gold_dataset_template.csv`), avec deux
régimes d'évaluation distincts :

- **Factuel / définitionnel / comparatif** (outcome-based) : ground truth =
  ensemble de passages de référence (paragraph_id). Métriques : recall@k,
  MRR, faithfulness, context precision/recall (RAGAS).
- **Contesté / interprétatif** (process-based) : pas de ground truth de
  contenu. On évalue le *comportement* du système (cite-t-il plusieurs
  passages contrastés ? signale-t-il l'absence de consensus ?), pas la
  justesse d'une interprétation.

Inspiré de HistoRAG (Kim-Baumann & Hiltmann, 2026) — architecture RAG conçue
pour l'histoire, adaptée ici à la philosophie. Différences documentées :
critères de la rubrique LLM-juge à définir spécifiquement pour Bergson (pas
de standard publié pour la philosophie à ce jour) ; pas de fenêtrage
temporel (le corpus n'est pas un corpus de presse diachronique, mais un
corpus d'un auteur unique — l'analogue pertinent serait plutôt un
fenêtrage par ouvrage/période de la pensée bergsonienne, à évaluer).

## Checklist Sprint 0

- [ ] Auditer le schéma XML (voir `docs/xml_audit_checklist.md`)
- [ ] Vérifier le statut de droits d'auteur (Bergson, mort en 1941 — domaine
      public en France depuis 2011 ; à confirmer pour d'éventuelles éditions
      critiques sous droits séparés)
- [ ] Construire le gold dataset v0 (`gold_dataset_template.csv`) — 50 à 100
      questions annotées, stratifiées, **avant** tout code de retrieval
- [ ] Setup environnement (poetry/uv), pre-commit, squelette Docker Compose
- [ ] README technique détaillant la structure du repo

## Structure du repo (cible)

```
bergson-rag/
├── data/
│   ├── raw/              # XML sources (non versionné si volumineux)
│   └── processed/        # chunks, index
├── docs/                 # audits, notes de méthodologie
├── src/
│   ├── ingestion/         # parsing XML, chunking
│   ├── indexing/          # BM25, embeddings, Qdrant
│   ├── retrieval/         # reformulation, hybride, reranking
│   ├── generation/         # prompts, validation anti-hallucination
│   └── mcp_server/         # Sprint 7
├── eval/
│   ├── gold_dataset.csv
│   └── scripts/           # RAGAS, recall@k, etc.
├── k8s/                   # manifestes optionnels (Sprint 8)
├── docker-compose.yml
└── pyproject.toml
```
