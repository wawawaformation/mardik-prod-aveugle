---
title: "Étape 2 — Les métriques qui révèlent la santé d'une application IA"
metadata:
  duree_cible: "1 min 45"
  images:
    - q2_metriques_sante.png
  source: "LLM Observability with OpenTelemetry: A Practical Guide — Kartik Dudeja"
---

## Question du brief

> Quelles métriques révèlent la santé d'une application ?

## Message clé

Un appel au modèle qui répond HTTP 200 prouve que l'inférence a abouti — pas que la génération est bonne. Les 4 signaux d'or classiques (latence, trafic, erreurs, saturation) sont nécessaires mais insuffisants.

## Ce qu'il faut dire

- 4 familles à suivre : **opérationnel** (latence par étape en P95, erreurs par cause), **économique** (tokens et coût par session), **comportement d'agent** (nombre d'étapes, retries, boucles — souvent absent des dashboards), **qualité** (ancrage au contexte, feedback négatif).
- L'article OpenTelemetry validé illustre concrètement ces métriques sur un pipeline RAG réel : compteur de volume de requêtes, histogrammes de latence, usage tokens, coût estimé — collectés via un OTel Collector exporté vers Prometheus.
- Priorité pour 3 jours : latence par étape, erreurs par cause, boucles d'agent — ce sont elles qui pointent le plus directement une panne récurrente.

## Transition

Ces métriques ne servent à rien sans savoir où les accrocher dans le code.
