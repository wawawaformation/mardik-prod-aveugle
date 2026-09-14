---
title: "Synthèse — Schéma d'observabilité de l'application Mardik"
metadata:
  duree_cible: "1 min 30"
  images:
    - schema_observabilite_mardik.png
---

## Livrable du brief

> Livrable de conception : note de diagnostic + schéma d'observabilité (points de trace + métriques).

## Message clé

Ce schéma est la synthèse des quatre réponses précédentes : il assemble sur un seul flux ce que Q3 dit d'instrumenter, ce que Q2 dit de mesurer, et la boucle que Q4 dit de fermer.

## Ce qu'il faut dire

- Reprendre le flux une dernière fois, vite : Client → API Gateway → Orchestrateur → Retriever / LLM / Outils → Collecte.
- Trois propriétés à pointer du doigt, dans l'ordre :
  1. Un **`trace_id` unique**, propagé de bout en bout — l'arbre de spans reste connexe.
  2. Les **versions** (modèle, prompt, config) attachées au span d'orchestration — tout incident se relie à une release.
  3. La **boucle fermée par le bas** : les tests d'intégration journalisent le `trace_id`, donc un échec de test pointe directement vers sa trace.
- Conclure sur le statut du document : ceci est une cible de conception, pas encore vérifiée sur le dépôt réel — la phase suivante est le développement (tests, instrumentation, correction de deux incidents récurrents).

## Clôture

C'est cette boucle complète — instrumenter, mesurer, tester, diagnostiquer — qui rend Mardik diagnosticable. Merci.
