---
title: "Étape 3 — Les points à instrumenter pour rendre une trace exploitable"
metadata:
  duree_cible: "1 min 45"
  images:
    - q3_points_instrumentation.png
  source: "LLM Observability with OpenTelemetry — Kartik Dudeja ; Tracing in llm-d"
---

## Question du brief

> Quels points instrumenter pour rendre une trace exploitable ?

## Message clé

Une requête doit produire une trace unique et connexe, du client jusqu'au dernier appel externe — sans propagation du `trace_id`, l'arbre se fragmente et perd sa valeur diagnostique.

## Ce qu'il faut dire

- Flux : Client → API Gateway (span racine, `trace_id`) → Orchestrateur → Retrieval / LLM / Outils → Collecte.
- Le span racine porte le `trace_id` ; le span d'orchestration porte les **versions** (modèle, prompt, config) — de quoi relier un incident à une release.
- L'article validé le montre concrètement sur un pipeline RAG : span de récupération (`retriever.engine`, latence, nb documents), span LLM (`llm.model.name`, tokens, coût), et logs JSON corrélés au `trace_id` pour pivoter entre logs et traces.
- Nommer les spans explicitement (pas `tool_call` générique), et anonymiser les prompts stockés — le rejeu de sessions réelles implique de stocker des données utilisateur.

## Transition

Une fois la trace en place, reste à savoir l'exploiter quand un test échoue.
