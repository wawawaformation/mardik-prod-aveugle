# Fiche de lecture — Pipeline d'observabilité Mardik (spans, métriques, logs)

**Schéma :** [`pipeline_observabilite_mardik.drawio`](pipeline_observabilite_mardik.drawio) / [`.png`](pipeline_observabilite_mardik.png)

## Objectif de lecture

Suivre la hiérarchie des spans d'un tour d'agent jusqu'à leur backend, et
voir quels signaux (traces / métriques / logs) sont réellement centralisés
aujourd'hui.

## Ce qu'on voit

Les 3 spans (`agent.turn` → `llm.invoke` → `tool.call`) sans attribut
personnalisé, les 2 instruments de métrique (`latency_ms`, `errors_total`),
les 2 événements de log structuré (`turn.completed`, `turn.failed`), puis
leur acheminement via le SDK OpenTelemetry vers leurs destinations
respectives.

## Points clés à retenir

- Seules les **traces** sont centralisées (Jaeger, via OTLP/gRPC).
  Métriques et logs restent en sortie standard du processus (`stdout`) —
  aucun Prometheus ni Loki câblé.
- Les spans ne portent aujourd'hui aucun attribut métier (`session_id`,
  modèle, tokens, nom d'outil) — enrichissement possible mais non fait.
- Écart assumé avec le stack complet décrit dans l'article transposé par
  Sofiane (`livrables/article_reel/`), pensé pour un pipeline RAG différent.

## Mise à jour depuis la création du schéma

- Le `service.name` des spans est maintenant correctement câblé (`mardik`,
  plus `unknown_service`) — voir CHANGELOG du 2026-09-14 12:06.
- Une seconde destination pour les traces (Langfuse) s'ajoute en option :
  voir [`traces_jaeger_langfuse_parallele.md`](../traces_jaeger_langfuse_parallele/traces_jaeger_langfuse_parallele.md).
- Les 3 spans portent maintenant des attributs métier (`session.id` partout,
  `langfuse.observation.type` = `agent`/`generation`/`tool`, modèle et
  tokens sur `llm.invoke`, `tool.name` sur `tool.call`) — le schéma/PNG
  reste figé sur l'état "sans attribut" mais `src/mardik/agent.py` fait foi.
  Jaeger affiche ces clés comme attributs plats ; Langfuse s'en sert pour
  ses vues dédiées (coût, tokens, regroupement par session/type).

## Voir aussi

- `src/mardik/telemetry.py`
- `docs/comprendre_le_code.md`
