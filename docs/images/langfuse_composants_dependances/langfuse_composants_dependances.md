# Fiche de lecture — Langfuse self-hébergé : composants et dépendances

**Schéma :** [`langfuse_composants_dependances.drawio`](langfuse_composants_dependances.drawio) / [`.png`](langfuse_composants_dependances.png)

## Objectif de lecture

Comprendre pourquoi chaque conteneur du stack Langfuse existe, et qui parle
à qui — pas juste « il faut 6 conteneurs ».

## Ce qu'on voit

Deux processus applicatifs (`langfuse-web`, `langfuse-worker`) et quatre
dépendances d'infrastructure (`postgres`, `clickhouse`, `redis`, `minio`),
avec le flux réel : Mardik envoie en OTLP/HTTP à `langfuse-web`, qui empile
dans `redis` (file d'attente) plutôt que de traiter en direct ;
`langfuse-worker` dépile et écrit dans `clickhouse` (données analytiques)
et `minio` (événements bruts).

## Points clés à retenir

- **Pourquoi Redis ?** Découpler la réponse rapide à l'ingestion (web) du
  traitement réel (worker) — sans lui, une requête d'ingestion bloquerait
  sur l'écriture analytique.
- **MinIO n'est pas optionnel.** Ce n'est pas réservé aux médias/gros
  fichiers : `langfuse-web` et `langfuse-worker` ont un `depends_on` strict
  dessus, et l'« event upload » vers S3 fait partie du chemin d'ingestion
  normal (contrairement à l'export batch, lui explicitement désactivable).
- **« S3 » ≠ Amazon.** C'est un protocole HTTP standard (lire/écrire un
  objet dans un bucket) que MinIO réimplémente entièrement en local, dans
  le conteneur Docker — aucun compte AWS, aucun accès internet requis pour
  cette partie.
- `postgres` porte les métadonnées (projets, utilisateurs, clés API),
  `clickhouse` porte les données analytiques (traces/observations) —
  séparation classique OLTP / OLAP.
- **Images épinglées en v3, pas v4.** Vérifié en démarrant réellement les
  deux versions : les images `:4` tournent par défaut en mode
  `events_only`, qui désactive `GET /api/public/traces` (404) au profit
  d'une nouvelle API v2 plus complexe — inutile pour une exploration
  simple. `:3` fonctionne immédiatement avec l'API classique.

## Voir aussi

- `docs/superpowers/specs/2026-09-14-langfuse-self-hosted-design.md`
- `docs/superpowers/plans/2026-09-14-langfuse-self-hosted.md` (note de
  version détaillée)
- [`traces_jaeger_langfuse_parallele.md`](../traces_jaeger_langfuse_parallele/traces_jaeger_langfuse_parallele.md)
- `docker-compose.yml`, `CHANGELOG.md`
