---
title: "Q2 — Les métriques qui révèlent la santé d'une application IA"
metadata:
  duree_cible: "2 min"
  images:
    - q2_metriques_sante.png
---

## Question du brief

> Quelles métriques révèlent la santé d'une application ?

## Message clé

Un appel au modèle qui répond HTTP 200 prouve que l'inférence a abouti — pas que la génération est bonne. Les 4 signaux d'or classiques ne couvrent qu'un quart du problème.

## Ce qu'il faut dire

- Rappeler les 4 signaux d'or (latence, trafic, erreurs, saturation) : nécessaires, mais insuffisants pour un système probabiliste.
- 4 familles de métriques à suivre, de gauche à droite sur le schéma :
  - **Opérationnel** : le service tient-il — latence par étape en P95, erreurs segmentées par cause.
  - **Économique** : combien ça coûte — tokens et coût par session, utile aussi pour détecter une dérive (boucle d'agent).
  - **Comportement d'agent** : nombre d'étapes, retries, boucles — famille souvent absente des tableaux de bord, la plus révélatrice d'une panne récurrente.
  - **Qualité** : la réponse est-elle juste — ancrage au contexte, signaux précoces sans modèle d'évaluation (feedback négatif, régénération, refus).
- Conclure sur la priorisation : pour Mardik en 3 jours, on instrumente d'abord la latence par étape, les erreurs par cause, et les boucles d'agent — ce sont elles qui pointent le plus directement une panne récurrente.

## Transition vers Q3

Ces métriques ne servent à rien sans savoir où les accrocher dans le code.
