---
title: "Q1 — Test d'intégration vs unitaire, et observer une application IA"
metadata:
  duree_cible: "2 min"
  images:
    - q1a_perimetre_tests_agent.png
    - q1b_observer_application_ia.png
---

## Question du brief

> Qu'est-ce qu'un test d'intégration pour un agent (vs unitaire), et que veut dire observer une application IA ?

## Message clé

Un test unitaire ne voit qu'une brique ; un test d'intégration rejoue une session réelle. Observer, c'est reconstituer *comment* une réponse a été produite, pas seulement *si* le serveur a répondu.

## Ce qu'il faut dire

- **`q1a`** : test unitaire = provider mocké sur une brique isolée. Test d'intégration = toute la chaîne, mais le LLM est non déterministe. Solution : **enregistrer une session réelle une fois, la rejouer** ensuite de façon déterministe — on gagne la détection de régression sur le code, pas sur le modèle.
- **`q1b`** : à gauche, la boîte noire — HTTP 200 ne garantit pas une réponse juste, l'application « ment sur sa santé ». À droite, la même requête en arbre de spans : ici, le second appel échoue à cause d'un contexte tronqué en amont, invisible depuis la seule réponse finale.

## Transition vers Q2

Observer suppose de savoir quoi mesurer.
